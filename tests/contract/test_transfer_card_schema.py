import json
import os

import jsonschema
import pytest

from tests.conftest import make_app


def schema():
    path = os.path.join("contracts", "transfer_card.schema.json")
    with open(path) as f:
        return json.load(f)


def extract_cards(resp_json):
    if isinstance(resp_json, list):
        return resp_json
    if isinstance(resp_json, dict):
        for key in ("transfers", "items", "data", "cards"):
            if key in resp_json and isinstance(resp_json[key], list):
                return resp_json[key]
        # maybe single card
        return [resp_json]
    return []


def test_request_response_validates_schema(client):
    r = client.post("/v1/transfers", json={
        "fromBranch": "branch-a",
        "toBranch": "branch-b",
        "itemCode": "MED-A",
        "quantity": 2,
    })
    assert r.status_code == 201
    jsonschema.validate(r.json(), schema())


def test_inbox_cards_validate_schema(client):
    client.post("/v1/transfers", json={
        "fromBranch": "branch-a",
        "toBranch": "branch-b",
        "itemCode": "MED-A",
        "quantity": 2,
    })
    r = client.get("/v1/branches/branch-b/transfers")
    assert r.status_code == 200
    cards = extract_cards(r.json())
    assert len(cards) >= 1
    for card in cards:
        jsonschema.validate(card, schema())


def test_requested_at_has_z(client):
    r = client.post("/v1/transfers", json={
        "fromBranch": "branch-a",
        "toBranch": "branch-b",
        "itemCode": "MED-A",
        "quantity": 1,
    })
    assert r.status_code == 201
    assert r.json()["requestedAt"].endswith("Z")
