# Project boundaries

This is the authoritative do/don't list for `pravo123/wavervanir-platform`.

If anything you're about to do conflicts with this doc, **stop and ask**. The boundary is not a guideline — it is enforced by automated tests, secret scanning, and review.

---

## 1. Public / private split

| Repo | Public? | Contains |
|---|---|---|
| `pravo123/cbsrm` | yes (Apache-2.0) | Open systemic-risk methodology. May be imported. |
| `pravo123/derivatives-risk-framework` | yes (Apache-2.0) | Open framework primitives. May be imported. |
| **`pravo123/wavervanir-platform`** (this repo) | **yes** | API + landing + docs. May import the two above. |
| `pravo123/volanx` | **PRIVATE** | Proprietary trading / execution / strategy code. **NEVER imported, NEVER referenced.** |

The AST guard at `api/tests/test_no_private_imports.py` walks every `api/src/**/*.py` and fails CI if it sees any of these patterns in an import:

```
volanx, volanx.brokers, volanx.execution, volanx.routing, volanx.options_intel,
risk_army, gauntlet, truth_ledger, bayesian_gate, broker_router, order_spec,
place_order, tastytrade, tastyworks, ib_insync, ibapi, alpaca_trade_api
```

Don't add new forbidden patterns to that list without operator approval — extending it tightens the boundary, but loosening it requires a separate discussion.

## 2. What you CAN safely work on

| Area | Notes |
|---|---|
| `landing/src/components/*` | UI polish, new visual components for the demo dashboard. |
| `landing/src/data/demoRisk.ts` | Fixture data (additions OK; do not commit anything claiming "live"). |
| `landing/src/styles.css` | Visual / dark-theme refinements. |
| `landing/public/*` | Static assets — logo, `robots.txt`, `_redirects`. Don't add binaries > 1 MB without operator OK. |
| `landing/tests/*` | New `vitest` tests for any UI you add. |
| `docs/*` | All documentation. Keep it honest — never claim live trading / live data unless it actually IS live. |
| `.github/*` (templates) | PR/issue templates. CI workflows are operator-owned. |
| `README.md` | Updates that match the actual state of the repo. |
| `api/src/wavervanir_api/routes/*` | New endpoints, ONLY when explicitly assigned in an issue. |
| `api/tests/*` | New tests are always welcome. |

## 3. What you must NOT touch

| Area | Reason |
|---|---|
| Anything under `VOLANX/`, `volanx/`, or in the private `pravo123/volanx` repo | Proprietary. Off-limits even by reference. |
| Tastytrade / Tastyworks / IBKR / Alpaca / Tradier SDKs | Broker SDKs are forbidden — broker data enters only via the sanitized `broker_snapshot` upload path. |
| `api/src/wavervanir_api/providers/broker_snapshot.py` validator regexes | Tightening is welcome via issue + PR; loosening is forbidden. |
| Live Stripe keys (`sk_live_…`, `whsec_live_…`) | Test mode only. Real billing is operator-driven and lives in hosted secret managers, never in the repo. |
| Live data credentials (`FMP_API_KEY`, `BULLFLOW_API_KEY`, real `TASTYTRADE_*`) | Never commit. Even in `.env`. `.env` is gitignored — keep it that way. |
| `.github/workflows/*.yml` | CI is operator-owned. Suggest changes via issue. |
| `cbsrm/` source or version pin | The version in `api/pyproject.toml` is intentional. Bumping requires operator approval. |
| Deploy configs (`render.yaml`, `wrangler.toml`, `Dockerfile`, `fly.toml`) | None exist yet, and none should be added until the operator approves the deploy slice. |
| DNS, TLS, custom domains | Operator-only. |
| Tags + GitHub Releases | Operator-only. |
| Anything in `dist/`, `node_modules/`, `.venv/` | Generated. Never commit. |

## 4. Forbidden marketing copy

Anywhere on the landing site or in docs, **do not** write any of these:

- "live trading"
- "trading bot"
- "guaranteed returns"
- "live execution"
- "automated investing"
- "we trade for you"
- any claim implying advice, fiduciary status, or a regulated financial service

The dashboard tests in `landing/tests/demo-risk-dashboard.test.tsx` will fail CI if any of those substrings appear in the rendered App.

Honest framing the project does use:

- "audit-friendly systemic-risk intelligence"
- "process over prediction"
- "public methodology"
- "research API"
- "sanitized snapshot"
- "demo / fixture data"

## 5. Things that need explicit operator approval

In doubt? It's probably one of these:

- New runtime dependencies (`pip install …` / `npm install …` of a new package).
- New API endpoints.
- Schema changes to `api/src/wavervanir_api/db.py`.
- Anything in `api/src/wavervanir_api/auth.py` or `routes/stripe.py`.
- Wiring the landing to a live API URL.
- Touching the CBSRM repo directly.

Open a GitHub issue with the proposal first, get a thumbs-up, then code.

## 6. Failure modes (and recoveries)

| If you see… | Do this |
|---|---|
| Push Protection rejecting your push | Refactor the test fixture per `docs/CONTRIBUTOR_WORKFLOW.md` §6. **Do not click the unblock URL.** |
| `test_no_private_imports.py` failing | Remove the offending import. Do not weaken the guard. |
| `pip-audit` flagging a CVE | Open an issue. Don't bump packages without operator review. |
| `bandit` flagging an issue | Fix the underlying code; don't `# nosec` it away. |
| Mobile layout broken | Add an `overflow-x: auto` wrapper, not a `min-width` removal — preserve the table content. |

## 7. Reminder

Privacy, secret hygiene, and the public/private boundary are the most valuable assets this repo has. Code review, CI gates, and these docs all exist to keep them intact. When in doubt, choose the smaller, more reversible action — and ask.
