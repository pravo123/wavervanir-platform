# Demo Risk Intelligence Dashboard

The landing page at `risk.wavervanir.com` (or local Vite preview) carries a
**frontend-only** Demo Risk Intelligence Dashboard. It is meant for review,
pilot demos, and partner walkthroughs — not for live data delivery.

## What it shows

| Section | Source | Live? |
|---|---|---|
| Data providers panel | `landing/src/data/demoRisk.ts` | no |
| Market snapshot grid (SPY, QQQ, IWM, GLD, TLT, BTCUSD) | fixture | no |
| Flow / risk intelligence panel (SPY, NVDA, IWM) | fixture | no |
| Portfolio risk summary preview | fixture (mirrors `api/tests/fixtures/sample_broker_snapshot.json`) | no |
| Generate demo risk report (Markdown preview) | composed in-browser | no |

## What it does NOT do

* Does not call `/v1/data/*` endpoints.
* Does not call any broker SDK.
* Does not reveal any account number.
* Does not send any data off the page (the "Generate demo risk report"
  button composes a Markdown body in-browser).
* Does not claim live trading, broker execution, or guaranteed returns.

## Why frontend-only for this slice

Three reasons:

1. **Demo portability.** The dashboard renders identically on `localhost`,
   on Cloudflare Pages preview, and on any future static-hosted preview.
   No backend dependency = no preview-environment debugging.
2. **Boundary safety.** Until the API is hosted with real `FMP_API_KEY` /
   `BULLFLOW_*` secrets, calling `/v1/data/*` from the public site would
   either fail loud (no key) or expose a public key by accident. Fixtures
   eliminate both risks.
3. **Schema discipline.** `landing/src/data/demoRisk.ts` mirrors the live
   API response shapes (`MarketSnapshot`, `FlowSnapshot`,
   `PortfolioRiskSummary`). When we flip to real data in a later slice
   (planned: prompt 06/20 or 07/20), only the data source changes — the
   components stay untouched.

## File map

```
landing/src/
  data/demoRisk.ts                            ← all fixture data + types
  components/
    DataProviderStatus.tsx                    ← provider availability panel
    MarketSnapshotGrid.tsx                    ← 6-symbol market grid
    RiskIntelligencePreview.tsx               ← flow signals
    PortfolioRiskPreview.tsx                  ← sanitized portfolio summary
    DemoReportPreview.tsx                     ← "Generate demo risk report" CTA
  App.tsx                                     ← wires the section above /pricing
  styles.css                                  ← dashboard styles, dark theme

landing/tests/
  demo-risk-dashboard.test.tsx                ← all dashboard contract tests
```

## Disclaimer copy

The visible disclaimer at the top of the section, sourced from
`DEMO_DATA_DISCLAIMER` in `landing/src/data/demoRisk.ts`:

> This demo uses fixture/sample data. Live FMP, Bullflow, and broker-snapshot
> integrations are provider-ready but not active on this public demo.

If you change this string, update the corresponding test in
`tests/demo-risk-dashboard.test.tsx`.

## Live provider-status mode (shipped)

`DataProviderStatus` now reads the live `/v1/data/providers` endpoint when an
API origin is configured. The contract is **fail-open**:

1. **`VITE_WAVERVANIR_API_URL` blank or unset** — the tiles render
   `DEMO_PROVIDERS` immediately, no fetch call is made, no UI noise.
2. **`VITE_WAVERVANIR_API_URL` set and reachable** — the tiles render
   `DEMO_PROVIDERS` on first paint, then swap to the live list once the
   fetch resolves. No spinner is shown (avoids layout shift).
3. **`VITE_WAVERVANIR_API_URL` set but fetch fails** (network error, 4xx/5xx,
   malformed payload) — the tiles stay on `DEMO_PROVIDERS` and a small italic
   "Fixture fallback active." note appears below the grid.

```dotenv
# landing/.env (gitignored)
VITE_WAVERVANIR_API_URL=http://127.0.0.1:8000
```

### What is and is not sent

* `GET ${VITE_WAVERVANIR_API_URL}/v1/data/providers` only.
* `Accept: application/json` and `credentials: omit`.
* **No `Authorization` header.** This endpoint is a discovery surface; if
  your deployed API gates it behind a key, the tiles will fail-over to
  fixtures until a future slice adds a public proxy or a token flow.

### Boundary reminders

* `VITE_*` values bake into the browser bundle and are PUBLIC. Never put
  Stripe / FMP / Bullflow / Tastytrade keys in any `VITE_*` var.
* The fixture fallback is intentional — the landing page must remain useful
  even when the API is down, missing, or rate-limited.

## Future slices (planned)

* Wire `MarketSnapshotGrid` to the demo provider on the hosted API so the
  numbers move deterministically per symbol but still without any paid
  data dependency.
* Add a small "upload sanitized broker JSON" widget that POSTs to
  `/v1/data/broker-snapshot/risk-summary`. Strictly opt-in.
