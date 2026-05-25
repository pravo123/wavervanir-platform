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

## Future slices (planned)

* Wire `DataProviderStatus` to the live `GET /v1/data/providers` endpoint
  (with a single env var: `VITE_WAVERVANIR_API_URL`). Falls back to the
  fixture if the env var is blank.
* Wire `MarketSnapshotGrid` to the demo provider on the hosted API so the
  numbers move deterministically per symbol but still without any paid
  data dependency.
* Add a small "upload sanitized broker JSON" widget that POSTs to
  `/v1/data/broker-snapshot/risk-summary`. Strictly opt-in.
