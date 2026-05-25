<!--
Thanks for the PR! Fill in every section honestly. Don't tick a box you
haven't actually verified. See docs/CONTRIBUTOR_WORKFLOW.md and
docs/PROJECT_BOUNDARIES.md.
-->

## Summary

<!-- 1–3 bullets. What does this change, and why? -->

-
-

## Scope

<!-- Which files / areas does this PR touch? -->

-

## Out of scope

<!-- Anything explicitly NOT in this PR. Helps reviewer focus. -->

-

## Screenshot / preview

<!-- REQUIRED for any visible frontend change (landing copy, dashboard, hero, pricing, etc.). -->

## Validation

<!-- Tick only what you actually ran locally AND saw green. -->

- [ ] `cd api && .venv/Scripts/python -m pytest -q` — all green
- [ ] `cd api && .venv/Scripts/python -m pip_audit` — clean
- [ ] `cd api && .venv/Scripts/python -m bandit -r src/` — 0 issues
- [ ] `cd landing && npm run test` — all green
- [ ] `cd landing && npm run build` — clean
- [ ] Manual preview (`npm run preview` or `npm run dev`) — no console errors
- [ ] Mobile viewport (375 × 812) — no horizontal overflow

## Boundary checklist

<!-- All must be true. See docs/PROJECT_BOUNDARIES.md. -->

- [ ] No live secrets committed (`sk_live_*`, `whsec_live_*`, real `FMP_API_KEY`, real `TASTYTRADE_*`, etc.)
- [ ] No broker SDK imports (`tastytrade`, `tastyworks`, `ib_insync`, `ibapi`, `alpaca_trade_api`)
- [ ] No private VolanX imports (`VOLANX.*`, `volanx.*`, `gauntlet`, `risk_army`, `truth_ledger`, `broker_router`, `place_order`, …)
- [ ] No "live trading" / "trading bot" / "guaranteed returns" / "live execution" copy
- [ ] No new runtime dependencies added without prior operator approval
- [ ] No CI workflow changes without prior operator approval
- [ ] No deploy configs added (`render.yaml`, `wrangler.toml`, `Dockerfile`, `fly.toml`)
- [ ] No tags created, no Releases drafted, no DNS / TLS / domain changes

## Linked issue

<!-- e.g. Closes #12 -->

## Reviewer notes

<!-- Anything the reviewer needs to know before approving. -->
