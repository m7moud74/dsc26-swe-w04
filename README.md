# dsc26-swe-w04 — Nour transfers test suite

Test suite for the Nour pharmacy stock-transfer backend. It targets the public
interface described in `SPEC.md`: the three helpers in `nour_transfers.rules`
and the FastAPI app produced by `nour_transfers.app.create_app`.

## Layout

```
tests/
  conftest.py
  unit/        # rules.py unit tests
  api/         # HTTP tests through TestClient
  contract/    # responses validated against contracts/transfer_card.schema.json
```

## Setup

```bash
git init -b main
uv venv --python 3.12
source .venv/bin/activate          # Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
pytest -q
```

## Running

```bash
python -m pytest -q -p no:cacheprovider -p no:warnings tests/
```