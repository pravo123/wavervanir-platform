# Architecture — wavervanir-platform

## Five-layer context

| Layer | Status in this repo |
| --- | --- |
| L0 — Open methodology (`cbsrm`, `derivatives-risk-framework`) | External, public, NOT in this repo. |
| L1 — Hosted research API | **`api/`** (this repo). FastAPI, SQLite (MVP), Stripe test-mode. |
| L2 — Risk Intelligence Workbench | **`landing/`** (this repo, MVP marketing only). Full workbench is later. |
| L3 — Execution Risk Suite | Private. NOT in this repo. |
| L4 — Regulator / central-bank pilot | Bespoke. NOT in this repo. |

## API shape (MVP slice)

```
GET  /health                       — public, no auth, returns {status, version}
POST /v1/cbsrm/macro-composite     — bearer auth, rate-limited, audited
                                     Body: {"window_id": "2008Q4" | "2020Q1" | "2023Q1"}
GET  /v1/cbsrm/macro-composite/windows  — bearer auth, lists supported window IDs
POST /v1/waitlist                  — public, captcha-less rate-limited per-IP
POST /stripe/webhook               — Stripe-signed, provisions/revokes keys
```

`SRISK`, `ΔCoVaR`, `MES` endpoints are explicitly **out of scope** for this first slice
(operator constraint 2026-05-25). They are added in a follow-up after macro-composite + waitlist
are green and deployed.

## Storage (MVP)

SQLite file at `api/wavervanir_api.sqlite` (dev) / Postgres URL via `DB_URL` (prod).

Tables:

```
api_keys      (id, key_hash, tier, status, stripe_customer_id, created_at, revoked_at)
audit_log     (id, key_id, route, request_sha256, response_sha256, status_code, latency_ms, ts)
waitlist      (id, email, tier_interest, source, created_at)
rate_buckets  (key_id, window_start, count)  — in-memory in MVP, optional persistence
```

No raw request bodies or response payloads are persisted. Only SHA-256 hashes.

## Public / private boundary

Enforced by `tests/test_no_private_imports.py`. AST scan over the entire `api/src/` tree.
Any import whose dotted name matches the forbidden regex causes the test to fail and CI to fail.

Forbidden patterns:

- `volanx`, `VOLANX`
- `VOLANX.brokers`, `VOLANX.execution`, `VOLANX.routing`, `VOLANX.options_intel`
- `BrokerRouter`, `OrderSpec`, `place_order`
- `risk_army`, `gauntlet`, `truth_ledger`, `bayesian_gate`

Permitted:

- `cbsrm.*`
- `fastapi`, `pydantic`, `httpx`, `sqlmodel`, `stripe`, standard library

## CI

`.github/workflows/ci.yml` runs:

1. `pip install -e api/[dev]`
2. `pytest api/tests/`
3. (Optional) `pip-audit -r api/requirements.txt` and `bandit -r api/src/` if installed.

No deploy automation in MVP — deployment is an explicit operator action.
