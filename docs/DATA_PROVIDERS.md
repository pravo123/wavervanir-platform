# Data Providers

`wavervanir-api` exposes a small data-ingestion surface for research and risk
work. It is provider-agnostic and **public/private-boundary safe** by
construction.

## Four provider kinds

| Name              | Kind   | Source                                      | Network in tests | Public? |
|-------------------|--------|---------------------------------------------|------------------|---------|
| `demo`            | fetch  | deterministic hash of symbol                | none             | yes     |
| `fmp`             | fetch  | Financial Modeling Prep (`FMP_API_KEY`)     | none (stubbed)   | yes     |
| `bullflow`        | fetch  | Bullflow API or a local JSON/CSV file       | none (stubbed)   | yes     |
| `broker_snapshot` | upload | sanitized JSON/CSV the operator uploads     | none             | yes     |

Tastytrade / Tastyworks / IBKR / Alpaca / Tradier broker SDKs are
**forbidden** in this repo. Their data may reach the platform only through
the `broker_snapshot` upload path after upstream sanitization. The AST guard
test `api/tests/test_no_private_imports.py` enforces this on every CI run.

## Endpoints

| Method | Path                                              | Purpose                              |
|-------:|---------------------------------------------------|--------------------------------------|
| GET    | `/v1/data/providers`                              | list providers + enabled/disabled    |
| GET    | `/v1/data/snapshot/{symbol}?provider=…&kind=…`    | fetch a single market or flow row    |
| POST   | `/v1/data/broker-snapshot/validate`               | validate + sanitize an upload        |
| POST   | `/v1/data/broker-snapshot/risk-summary`           | validate + return aggregate exposure |

All four endpoints require a bearer API key.

## Choosing a provider

```
fetch a price?     → demo (free) | fmp (real, env-gated)
fetch options flow? → bullflow (env or file)
aggregate a portfolio? → broker_snapshot (upload sanitized JSON/CSV)
```

## Boundary rules (reminders)

1. **No broker SDK imports.** Period.
2. **No raw broker payloads.** Sanitize upstream in your private workflow.
3. **No account numbers / tokens.** The validator rejects payloads that
   trip the forbidden-field regex set in
   `wavervanir_api/providers/broker_snapshot.py`.
4. **No live network calls in tests.** Every provider exposes an injectable
   client; CI must stay offline.

## Related docs

* `docs/FMP_SETUP.md`
* `docs/BULLFLOW_SETUP.md`
* `docs/TASTYWORKS_SNAPSHOT_SCHEMA.md`
* `docs/PRIVACY_BOUNDARY.md`
