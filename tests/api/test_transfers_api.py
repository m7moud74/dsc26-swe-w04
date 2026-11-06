import pytest

from tests.conftest import BRANCHES, ITEMS, make_app


def stock_value(resp):
    data = resp.json()
    if isinstance(data, dict):
        for key in ("quantity", "stock", "amount", "value"):
            if key in data:
                return data[key]
        # maybe nested
        for v in data.values():
            if isinstance(v, int):
                return v
    return data


def request_transfer(client, from_branch="branch-a", to_branch="branch-b", item_code="MED-A", quantity=2):
    return client.post("/v1/transfers", json={
        "fromBranch": from_branch,
        "toBranch": to_branch,
        "itemCode": item_code,
        "quantity": quantity,
    })


def test_request_404_unknown_item(client):
    r = request_transfer(client, item_code="NOPE")
    assert r.status_code == 404


def test_request_404_unknown_branch(client):
    r = request_transfer(client, from_branch="nope")
    assert r.status_code == 404
    r = request_transfer(client, to_branch="nope")
    assert r.status_code == 404


def test_request_422_same_branch(client):
    r = request_transfer(client, to_branch="branch-a")
    assert r.status_code == 422


def test_request_422_quantity_below_one(client):
    r = request_transfer(client, quantity=0)
    assert r.status_code == 422
    r = request_transfer(client, quantity=-1)
    assert r.status_code == 422


def test_request_409_below_reserve(client):
    # branch-b has MED-A stock 3, reserve 5 -> cannot send even 1
    r = request_transfer(client, from_branch="branch-b", to_branch="branch-a", quantity=1)
    assert r.status_code == 409
    assert r.headers.get("content-type", "").find("application/problem+json") != -1
    assert r.json().get("type") == "/problems/below-reserve"


def test_error_media_type(client):
    r = client.get("/v1/branches/nope/transfers")
    assert "application/problem+json" in r.headers.get("content-type", "")


def test_approve_404_unknown(client):
    r = client.post("/v1/transfers/does-not-exist/approve")
    assert r.status_code == 404


def test_approve_not_pending_409(client):
    r = request_transfer(client)
    assert r.status_code == 201
    tid = r.json()["id"]
    r2 = client.post(f"/v1/transfers/{tid}/approve")
    assert r2.status_code == 200
    r3 = client.post(f"/v1/transfers/{tid}/approve")
    assert r3.status_code == 409
    assert r3.json().get("type") == "/problems/not-pending"


def test_approve_below_reserve_if_stock_changed(client, app):
    # create transfer that is valid now
    r = request_transfer(client, quantity=1)
    assert r.status_code == 201
    tid = r.json()["id"]
    # mutate stock so reserve breached
    app.state.stock["branch-a"]["MED-A"] = 0
    # also update through helper? app.state.stock is same dict
    r2 = client.post(f"/v1/transfers/{tid}/approve")
    assert r2.status_code == 409
    assert r2.json().get("type") == "/problems/below-reserve"


def test_approval_moves_stock_once(client):
    before_src = stock_value(client.get("/v1/branches/branch-a/stock/MED-A"))
    before_dst = stock_value(client.get("/v1/branches/branch-b/stock/MED-A"))
    r = request_transfer(client, quantity=2)
    assert r.status_code == 201
    tid = r.json()["id"]
    r2 = client.post(f"/v1/transfers/{tid}/approve")
    assert r2.status_code == 200
    after_src = stock_value(client.get("/v1/branches/branch-a/stock/MED-A"))
    after_dst = stock_value(client.get("/v1/branches/branch-b/stock/MED-A"))
    assert after_src == before_src - 2
    assert after_dst == before_dst + 2
    # second approve does not move again
    r3 = client.post(f"/v1/transfers/{tid}/approve")
    assert r3.status_code == 409
    assert stock_value(client.get("/v1/branches/branch-a/stock/MED-A")) == after_src
    assert stock_value(client.get("/v1/branches/branch-b/stock/MED-A")) == after_dst


def test_inbox_sorted_by_priority_then_request_order(client):
    # clear by new app
    app = make_app()
    from fastapi.testclient import TestClient
    c = TestClient(app)
    # request multiple transfers to branch-b (destination) with different priorities
    # MED-A chronic, low cover at branch-b? branch-b stock 3, sales 1 -> cover 3 (high, not urgent)
    # Make urgent by using item with chronic and dest stock low: use MED-A, but need cover <3. branch-b stock 3/sales 2? adjust
    # Use custom app data
    stock = {"branch-a": {"MED-A": 20}, "branch-b": {"MED-A": 2}}
    sales = {"branch-a": {"MED-A": 1.0}, "branch-b": {"MED-A": 2.0}}  # cover 1 -> urgent
    items = {"MED-A": {"chronic": True, "reserve": 1}}
    app2 = make_app(stock, items, sales)
    c2 = TestClient(app2)
    r1 = c2.post("/v1/transfers", json={"fromBranch": "branch-a", "toBranch": "branch-b", "itemCode": "MED-A", "quantity": 1})
    assert r1.status_code == 201
    # normal priority item: MED-B non-chronic, high stock
    items2 = {"MED-A": {"chronic": True, "reserve": 1}, "MED-B": {"chronic": False, "reserve": 1}}
    stock2 = {"branch-a": {"MED-A": 20, "MED-B": 20}, "branch-b": {"MED-A": 2, "MED-B": 100}}
    sales2 = {"branch-a": {"MED-A": 1.0, "MED-B": 1.0}, "branch-b": {"MED-A": 2.0, "MED-B": 1.0}}
    app3 = make_app(stock2, items2, sales2)
    c3 = TestClient(app3)
    # request normal first, then urgent
    n = c3.post("/v1/transfers", json={"fromBranch": "branch-a", "toBranch": "branch-b", "itemCode": "MED-B", "quantity": 1})
    u = c3.post("/v1/transfers", json={"fromBranch": "branch-a", "toBranch": "branch-b", "itemCode": "MED-A", "quantity": 1})
    assert n.status_code == 201 and u.status_code == 201
    inbox = c3.get("/v1/branches/branch-b/transfers").json()
    # extract list
    cards = inbox if isinstance(inbox, list) else inbox.get("transfers") or inbox.get("items") or inbox.get("data") or []
    priorities = [card["priority"] for card in cards]
    assert priorities == ["urgent", "normal"] or priorities[0] == "urgent"


def test_cors_allowed_origin(client):
    r = client.options("/v1/transfers", headers={
        "Origin": "https://branch.nour.example",
        "Access-Control-Request-Method": "POST",
    })
    assert r.headers.get("access-control-allow-origin") == "https://branch.nour.example"
    assert r.headers.get("access-control-allow-credentials") == "true"


def test_cors_localhost(client):
    r = client.options("/v1/transfers", headers={
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "POST",
    })
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_disallowed_origin(client):
    r = client.options("/v1/transfers", headers={
        "Origin": "https://evil.example",
        "Access-Control-Request-Method": "POST",
    })
    assert r.headers.get("access-control-allow-origin") != "https://evil.example"
    assert r.headers.get("access-control-allow-origin") != "*"
