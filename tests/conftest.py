import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from nour_transfers.app import create_app

BRANCHES = ("branch-a", "branch-b")
ITEMS = {
    "MED-A": {"name": "Medicine A", "chronic": True, "reserve": 5},
    "MED-B": {"name": "Medicine B", "chronic": False, "reserve": 2},
}
STOCK = {
    "branch-a": {"MED-A": 10, "MED-B": 20},
    "branch-b": {"MED-A": 3, "MED-B": 15},
}
SALES = {
    "branch-a": {"MED-A": 2.0, "MED-B": 1.0},
    "branch-b": {"MED-A": 1.0, "MED-B": 0.0},
}
NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def app():
    return create_app(STOCK, ITEMS, SALES, NOW)


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


def make_app(stock=None, items=None, sales=None, now=None):
    if stock is None:
        stock = {b: dict(v) for b, v in STOCK.items()}
    if items is None:
        items = {k: dict(v) for k, v in ITEMS.items()}
    if sales is None:
        sales = {b: dict(v) for b, v in SALES.items()}
    if now is None:
        now = NOW
    return create_app(stock, items, sales, now)
