# WaverVanir Platform - Ankit Handoff

This is the async handoff for the WaverVanir Risk Intelligence Platform.

The goal is simple: Ankit should be able to open the package, understand the
product surface, run the demo locally, and merge it into the existing
WaverVanir website without needing live data, paid hosting, Stripe setup, or
private VolanX access.

## Current State

The public platform is now more than a static pricing page. It includes:

- A Vite + React landing app in `landing/`.
- A visible demo Risk Intelligence dashboard using fixture data.
- Provider-ready data abstractions for `demo`, `fmp`, `bullflow`, and
  upload-only `broker_snapshot`.
- A FastAPI backend in `api/` with auth, plan-aware rate limits, audit logging,
  Stripe test-mode billing scaffolding, onboarding, CBSRM routes, and
  data-provider routes.
- Contributor onboarding docs and GitHub PR/issue templates.
- Public/private guardrails that forbid importing private VolanX or broker SDK
  modules into this public repo.

No commercial data is required for the handoff.

## What Ankit Should Do First

1. Read these docs in order:
   - `docs/ANKIT_START_HERE.md`
   - `docs/CONTRIBUTOR_WORKFLOW.md`
   - `docs/PROJECT_BOUNDARIES.md`
   - `docs/DEMO_DASHBOARD.md`
   - `docs/WEBSITE_INTEGRATION.md`

2. Open the built demo:
   - Use `landing/dist/` from the handoff zip, or
   - Clone the repo and run `cd landing && npm ci && npm run dev`.

3. Confirm the visible dashboard:
   - WaverVanir logo renders.
   - Data-provider tiles render.
   - Market snapshot cards render.
   - Flow/risk cards render.
   - Sanitized portfolio summary renders.
   - Demo report toggle works.
   - Mobile viewport has no horizontal overflow.

4. Decide the website integration path:
   - Drop-in static build under `wavervanir.com/risk/`, or
   - Port React components into the existing website stack.

## What Is Safe For Ankit To Change

- Landing page layout and polish.
- Demo dashboard copy, spacing, responsive layout, and accessibility.
- Website integration docs.
- Handoff package docs and instructions.
- Waitlist UI integration with an operator-approved lead sink.
- Screenshots, preview instructions, and website QA checklists.

## What Ankit Must Not Change Without Operator Approval

- Pricing values.
- Stripe behavior.
- API authentication behavior.
- Provider security boundaries.
- Any claims about live trading, execution, broker integration, or guaranteed
  returns.
- Any private VolanX code or private subsystem names.
- CBSRM or derivatives-risk-framework internals.
- Real credentials or live API keys.

## Data Policy

Use fixture data first.

The public platform is intentionally provider-ready but not dependent on paid
data:

- `demo`: always available, deterministic fixture-like snapshots.
- `fmp`: disabled until `FMP_API_KEY` is configured.
- `bullflow`: disabled until an API key or local file is configured.
- `broker_snapshot`: upload-only sanitized JSON. No direct Tastytrade,
  Tastyworks, IBKR, Alpaca, or broker SDK imports are allowed in this repo.

If a real Tastyworks/Tastytrade export is used for testing, sanitize it before
upload. Never commit account numbers, tokens, refresh tokens, routing numbers,
 tax IDs, or private brokerage fields.

## Product Positioning

Use this framing:

- Risk intelligence.
- Audit-ready reporting.
- Process over prediction.
- Public methodology, hosted workflow.
- Fixture-data demo today, provider-ready integrations later.

Avoid this framing:

- Trading bot.
- Live execution.
- Broker integration.
- Guaranteed returns.
- Hedge fund or fund-manager language.
- P&L claims from private systems.

## Recommended Website Integration

For fastest handoff, use `landing/dist/` as a static drop-in under a preview
path such as:

```text
https://www.wavervanir.com/risk-preview/
```

After operator review, promote to the final path:

```text
https://www.wavervanir.com/risk/
```

If the existing website is React/Next/Astro, port the components instead. See
`docs/WEBSITE_INTEGRATION.md`.

## Handoff Package Contents

The package builder creates `_handoff/wavervanir-platform-handoff.zip`.

The zip includes:

- Built static landing app: `landing/dist/`
- Landing source reference: selected `landing/src/` files
- Brand asset: `landing/public/brand/wavervanir-logo.png`
- Docs for onboarding, providers, dashboard, and website integration
- API README and `.env.example` only
- GitHub PR/issue templates for contributor workflow reference

The zip excludes:

- `.git/`
- `node_modules/`
- `.venv/`
- real `.env` files
- SQLite/database files
- Python caches
- generated test caches
- private VolanX code

## Operator Notes

Before sending the package:

1. Run `tools/build_handoff.ps1` on Windows or `tools/build_handoff.sh` in a
   Unix shell.
2. Confirm the zip exists in `_handoff/`.
3. Send only the zip, not the full working directory.
4. Do not send real keys, live data credentials, or private VolanX repo access.

When Ankit is available later, invite him to the public GitHub repo and point
him to `docs/ANKIT_START_HERE.md`.
