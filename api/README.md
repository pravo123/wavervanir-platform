# wavervanir-api

FastAPI service exposing the public **CBSRM** library as a hosted, authenticated, audit-chained API.

## Endpoints (MVP slice)

```
GET  /health
GET  /v1/cbsrm/macro-composite/windows
POST /v1/cbsrm/macro-composite          {"window_id": "2008Q4"|"2020Q1"|"2023Q1"}
POST /v1/waitlist                       {"email": "...", "tier_interest": "researcher|pro|institutional"}
POST /stripe/webhook                    (Stripe-signed)
```

`/v1/cbsrm/srisk`, `/v1/cbsrm/delta-covar`, `/v1/cbsrm/mes` are explicitly out of MVP scope.

## Local dev

```bash
cd api
python -m venv .venv && source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
cp .env.example .env
pytest -q
uvicorn wavervanir_api.app:create_app --factory --reload
```

## Configuration

All config via environment variables (see `.env.example`). No live keys ever committed.

| Var | Default | Purpose |
| --- | --- | --- |
| `WAVERVANIR_ENV` | `dev` | `dev` / `prod` |
| `WAVERVANIR_DB_URL` | `sqlite:///./wavervanir_api.sqlite` | DB connection string |
| `WAVERVANIR_API_KEY_PEPPER` | (required in prod) | server-side pepper for hashing API keys |
| `STRIPE_WEBHOOK_SECRET` | (required for webhook tests) | `whsec_...` test-mode secret |
| `STRIPE_API_KEY` | unused in MVP | `sk_test_...` |
| `WAVERVANIR_RATE_LIMIT_FREE` | `100` | calls/day for free tier |
| `WAVERVANIR_RATE_LIMIT_PAID` | `5000` | calls/day for paid tier |

## Boundary

This service imports **only** `cbsrm` from the public stack. The AST guard test
(`tests/test_no_private_imports.py`) fails CI if anything else creeps in.
