import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from .rules import days_of_cover, priority, can_transfer

PRIORITY_ORDER = {"urgent": 0, "high": 1, "normal": 2}

ALLOWED_ORIGINS = ["https://branch.nour.example", "http://localhost:5173"]


def _as_utc(dt):
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    if callable(dt):
        return _as_utc(dt())
    # string
    s = str(dt)
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        d = datetime.fromisoformat(s)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def _format_iso(dt):
    d = _as_utc(dt)
    return d.isoformat(timespec="seconds").replace("+00:00", "Z")


def _normalize_items(items):
    out = {}
    if isinstance(items, dict):
        for code, info in items.items():
            info = dict(info) if isinstance(info, dict) else {"value": info}
            info.setdefault("code", code)
            info.setdefault("item_code", code)
            info.setdefault("chronic", bool(info.get("is_chronic", info.get("chronic", False))))
            if "reserve" not in info:
                info["reserve"] = info.get("min_reserve", info.get("reserve_qty", 0))
            out[code] = info
    elif isinstance(items, (list, tuple)):
        for info in items:
            info = dict(info) if isinstance(info, dict) else {"value": info}
            code = info.get("item_code") or info.get("itemCode") or info.get("code") or info.get("id")
            info.setdefault("code", code)
            info.setdefault("chronic", bool(info.get("is_chronic", info.get("chronic", False))))
            if "reserve" not in info:
                info["reserve"] = info.get("min_reserve", info.get("reserve_qty", 0))
            out[code] = info
    return out


def _normalize_nested(data):
    out = {}
    if isinstance(data, dict):
        for branch, inner in data.items():
            if isinstance(inner, dict):
                out[branch] = dict(inner)
            else:
                out[branch] = inner
    return out


class ProblemError(Exception):
    def __init__(self, status, title, detail=None, problem_type=None, headers=None):
        self.status = status
        self.title = title
        self.detail = detail
        self.problem_type = problem_type
        self.headers = headers


def problem_response(status, title, detail=None, problem_type=None, headers=None, errors=None):
    body = {"type": problem_type or "about:blank", "title": title, "status": status}
    if detail is not None:
        body["detail"] = detail
    if errors is not None:
        body["errors"] = errors
    return JSONResponse(status_code=status, content=body, media_type="application/problem+json", headers=headers)


class TransferRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fromBranch: str
    toBranch: str
    itemCode: str
    quantity: int = Field(ge=1)


def create_app(stock, items, sales, now):
    stock = _normalize_nested(stock)
    items = _normalize_items(items)
    sales = _normalize_nested(sales)
    branches = list(stock.keys())

    transfers = {}  # id -> dict
    transfer_order = []

    app = FastAPI(title="Nour Transfers", version="1.0.0")
    app.state.stock = stock
    app.state.items = items
    app.state.sales = sales
    app.state.now = now
    app.state.branches = branches

    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(ProblemError)
    async def handle_problem(request: Request, exc: ProblemError):
        return problem_response(exc.status, exc.title, exc.detail, exc.problem_type, exc.headers)

    @app.exception_handler(RequestValidationError)
    async def handle_validation(request: Request, exc: RequestValidationError):
        errors = []
        seen = set()
        for err in exc.errors():
            loc = list(err.get("loc", []))
            key = tuple(loc)
            if key in seen:
                continue
            seen.add(key)
            errors.append({"loc": loc, "msg": err.get("msg")})
        return problem_response(422, "Validation Error", errors=errors)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http(request: Request, exc: StarletteHTTPException):
        titles = {400: "Bad Request", 401: "Unauthorized", 403: "Forbidden", 404: "Not Found",
                  405: "Method Not Allowed", 409: "Conflict", 422: "Unprocessable Entity"}
        title = titles.get(exc.status_code, "HTTP Error")
        detail = exc.detail if isinstance(exc.detail, str) else None
        headers = getattr(exc, "headers", None)
        return problem_response(exc.status_code, title, detail, headers=headers)

    def get_branch_stock(branch, item_code):
        return stock.get(branch, {}).get(item_code, 0)

    def get_sales(branch, item_code):
        return sales.get(branch, {}).get(item_code, 0)

    def make_card(t):
        return {
            "id": t["id"],
            "fromBranch": t["fromBranch"],
            "toBranch": t["toBranch"],
            "itemCode": t["itemCode"],
            "quantity": t["quantity"],
            "priority": t["priority"],
            "status": t["status"],
            "requestedAt": t["requestedAt"],
        }

    @app.post("/v1/transfers", status_code=201)
    async def create_transfer(body: TransferRequest):
        from_branch = body.fromBranch
        to_branch = body.toBranch
        item_code = body.itemCode
        quantity = body.quantity

        if from_branch not in branches or to_branch not in branches:
            raise ProblemError(404, "Not Found", "Unknown branch.")
        if item_code not in items:
            raise ProblemError(404, "Not Found", "Unknown item.")
        if from_branch == to_branch:
            raise ProblemError(422, "Unprocessable Entity", "Same branch.")

        item = items[item_code]
        reserve = item.get("reserve", 0)
        from_stock = get_branch_stock(from_branch, item_code)

        if not can_transfer(from_stock, quantity, reserve):
            raise ProblemError(409, "Below Reserve", "Transfer would breach reserve.", problem_type="/problems/below-reserve")

        # destination cover for priority
        dest_stock = get_branch_stock(to_branch, item_code)
        dest_sales = get_sales(to_branch, item_code)
        try:
            cover = days_of_cover(dest_stock, dest_sales)
        except Exception:
            cover = None
        is_chronic = bool(item.get("chronic", False))
        prio = priority(is_chronic, cover)

        tid = f"trf_{uuid.uuid4().hex[:8]}"
        card = {
            "id": tid,
            "fromBranch": from_branch,
            "toBranch": to_branch,
            "itemCode": item_code,
            "quantity": quantity,
            "priority": prio,
            "status": "pending",
            "requestedAt": _format_iso(now),
        }
        transfers[tid] = card
        transfer_order.append(tid)
        return JSONResponse(status_code=201, content=make_card(card))

    @app.post("/v1/transfers/{transfer_id}/approve")
    async def approve_transfer(transfer_id: str):
        t = transfers.get(transfer_id)
        if t is None:
            raise ProblemError(404, "Not Found", "Unknown transfer.")
        if t["status"] != "pending":
            raise ProblemError(409, "Not Pending", "Transfer is not pending.", problem_type="/problems/not-pending")

        item_code = t["itemCode"]
        quantity = t["quantity"]
        from_branch = t["fromBranch"]
        to_branch = t["toBranch"]
        item = items.get(item_code, {})
        reserve = item.get("reserve", 0)
        from_stock = get_branch_stock(from_branch, item_code)

        if not can_transfer(from_stock, quantity, reserve):
            raise ProblemError(409, "Below Reserve", "Stock changed; transfer would breach reserve.", problem_type="/problems/below-reserve")

        # move stock
        stock[from_branch][item_code] = stock[from_branch].get(item_code, 0) - quantity
        stock[to_branch][item_code] = stock[to_branch].get(item_code, 0) + quantity
        t["status"] = "approved"
        return JSONResponse(status_code=200, content=make_card(t))

    @app.get("/v1/branches/{branch}/transfers")
    async def inbox(branch: str):
        if branch not in branches:
            raise ProblemError(404, "Not Found", "Unknown branch.")
        result = [transfers[tid] for tid in transfer_order if transfers[tid]["toBranch"] == branch]
        result.sort(key=lambda t: (PRIORITY_ORDER.get(t["priority"], 9), transfer_order.index(t["id"])))
        return [make_card(t) for t in result]

    @app.get("/v1/branches/{branch}/stock/{item_code}")
    async def stock_endpoint(branch: str, item_code: str):
        if branch not in branches:
            raise ProblemError(404, "Not Found", "Unknown branch.")
        if item_code not in items:
            raise ProblemError(404, "Not Found", "Unknown item.")
        q = get_branch_stock(branch, item_code)
        return {"quantity": q, "stock": q}

    return app


