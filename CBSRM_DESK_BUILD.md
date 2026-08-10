# CBSRM Desk — Reproducible Build & Operations Guide

**Product:** CBSRM Desk — an institutional systemic-risk terminal by WaverVanir International.
**Live:** [app.cbsrm.wavervanir.com](https://app.cbsrm.wavervanir.com/app/) · **Marketing:** [cbsrm.wavervanir.com](https://cbsrm.wavervanir.com)
**Repo:** `github.com/pravo123/wavervanir-platform` · **Branch:** `cbsrm-golive`

> The moat is **governance, not alpha**: every number is computed from public data,
> content-addressed (SHA-256), written to a tamper-evident audit chain, and
> version-stamped to clear an **SR 26-2** model-risk review. "Reproduce, audit, defend."

This document is a from-scratch guide: clone → run → test → deploy → bill → operate.
**No secrets appear here — only environment-variable names.**

---

## 1. What's in the product

The authenticated terminal (served at `/app`) has these surfaces, all behind a
default-deny entitlement gate:

| Tab | What it is |
|---|---|
| **Conditions** | 13 live systemic-risk lenses (ECB CISS US/EA/UK, Fed financial stress, yield-curve recession prob, Sahm rule, HY credit, macro regime, VIX, Diebold-Yilmaz cross-border spillover, options tail-skew, fund-redemption fragility, ESG transition) — each with a BI drill-down (history + z-score/percentile/bands). |
| **Risk Desk** (Quant Cockpit) | Global cross-asset risk on **any symbol the feed supports** (world indices, FX, commodities, US mega-caps, crypto) + curated watchlist groups. Per instrument: Sharpe/Sortino, ann & EWMA vol, beta-to-S&P, VaR/CVaR table, drawdown, 50/200-DMA trend — plus a **TradingView-style candlestick chart** with VaR levels, MAs, and a forward ±σ volatility cone (statistical, not an ML forecast). |
| **Pipeline** | **Governed PipelineRecords** for three crisis windows (2008Q4/2020Q1/2023Q1): a reproducible, content-addressed crisis dossier (system-stress gauge, DebtRank network contagion, cross-crisis comparison, narrative) + a **live SRISK Σ capital-shortfall + ΔCoVaR** panel over major banks + a **SR 26-2 Model Validation binder** (the MRM package). Every record is verifiable (rebuild → same SHA-256). |
| **Portfolio** | Sanitized broker-snapshot risk analyzer (positions in → exposure/concentration/per-asset-class out; rejects anything resembling a credential). |
| **Methodology** | Click-through catalog of all 13 lenses (what/how/interpret/reference). |
| **Access ledger** | The caller's tamper-evident access trail + a live chain-verification. |
| **Admin** (owner-only) | User list + entitlement grant/revoke + ledger verify. |

Pre-login: a **landing page** showcasing the offering + a **7-day free trial** (no card).

---

## 2. Architecture

```
wavervanir.com (Sign In hub) ──> CBSRM Desk (cbsrm.wavervanir.com)
                                      │
                                 Sign in / Register (email + password)
                                      │
                                 AuthService  (scrypt · stdlib HS256 JWT 15m/7d)
                                      │
                                 Entitlement gate (default-deny · Desk active?)
                                      │
                                 Premium API  /v1/desk/*  (gated routes)
                                      │
                                 CBSRM Terminal SPA (/app)

Stripe $48k/yr ── webhook ──> entitle user (desk·active)
Every sign-in + access ──> tamper-evident SHA-256 audit chain
cbsrm engines + financialdata/FRED/ECB ──> the lenses, cockpit, SRISK, dossiers
```

**Hard boundary:** the paid layer (`wavervanir_api`) may import **only** the public
`cbsrm` package, **never** any internal VolanX module. Enforced by an AST test
(`tests/test_no_private_imports.py`) that fails CI on violation.

---

## 3. Tech stack

- **API:** FastAPI + SQLModel (SQLite dev / Postgres prod), Python 3.14.
- **Auth:** stdlib `hashlib.scrypt` passwords + a hand-rolled stdlib HS256 JWT
  (no argon2/jose/bcrypt — the venv lacked the wheels, and "no third-party crypto
  in the auth path" is an institutional selling point). Access 15m / refresh 7d.
- **Systemic-risk engines:** the public **`cbsrm`** package (Apache-2.0) — SRISK
  (Brownlees-Engle), ΔCoVaR (Adrian-Brunnermeier), MES, DebtRank (Battiston),
  CISS (Holló-Kremer-LoDuca), Diebold-Yilmaz, crisis dossiers, replication scorer,
  audit chain, governed reporting. Pure-numpy internals (no arch/statsmodels).
- **Market data:** financialdata.net (Enterprise), FRED, ECB SDMX.
- **Frontend:** a single zero-dependency `web/index.html` SPA (vanilla JS + inline SVG charts), served same-origin at `/app`.
- **Deploy:** Render (Blueprint) + free Postgres; custom domain via CNAME + auto-TLS.

---

## 4. Repository layout

```
wavervanir-platform/
├─ render.yaml                      # Render Blueprint (web service + Postgres + env)
├─ CBSRM_DESK_BUILD.md              # ← this file
├─ docs/                            # STRIPE_SETUP, ARCHITECTURE, DATA_PROVIDERS, PRIVACY_BOUNDARY, ...
└─ api/
   ├─ pyproject.toml                # deps: fastapi, sqlmodel, cbsrm, numpy, pandas, psycopg2-binary, stripe, httpx
   ├─ _serve_preview.py             # GITIGNORED — local preview bootstrap (seeds users, sets keys)
   ├─ src/wavervanir_api/
   │  ├─ app.py                     # create_app() — mounts routers + StaticFiles(/app) + "/"→"/app/"
   │  ├─ config.py                  # Settings (env aliases): jwt, pepper, db, stripe_*, *_api_key, admin_emails
   │  ├─ db.py                      # SQLModel tables: User, AccessEvent, SnapshotCache, ApiKey, OnboardSession
   │  ├─ security.py                # scrypt hash/verify + stdlib HS256 JWT
   │  ├─ users.py                   # AuthService (register/login/refresh/start_trial/set_entitlement) + require_user/require_desk/require_admin
   │  ├─ access_audit.py            # tamper-evident hash-chained AccessEvent ledger
   │  ├─ desk_conditions.py         # 13-lens live conditions snapshot (+ cache, methodology, last-good fallback)
   │  ├─ desk_lenses.py             # 4 advanced financialdata lenses (DY spillover, options tail, fund fragility, ESG)
   │  ├─ desk_analytics.py          # per-lens BI analytics (series + stats + bands)
   │  ├─ desk_riskdesk.py           # Quant Cockpit: watchlist groups + any-symbol + institutional metrics + candlestick chart
   │  ├─ desk_pipeline.py           # Governed PipelineRecord + crisis dossier + live SRISK/ΔCoVaR systemic panel
   │  ├─ desk_validation.py         # SR 26-2 Model Validation binder (MRM package)
   │  ├─ providers/financialdata.py # financialdata.net client (index_prices, get_json, ...)
   │  ├─ providers/broker_snapshot.py # portfolio risk engine (validate + risk_summary + scrub)
   │  ├─ routes/{users,desk,stripe,admin,...}.py
   │  └─ web/index.html             # the terminal SPA
   └─ tests/                        # pytest suite (214 tests, incl. test_no_private_imports.py)
```

---

## 5. Local development (reproducible)

```bash
cd api
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -e .          # Windows; use .venv/bin/python on *nix

# minimal env to boot (SQLite dev DB, throwaway secrets):
export WAVERVANIR_DB_URL="sqlite:///dev.db"
export WAVERVANIR_JWT_SECRET="dev-jwt-secret-min-32-chars-长长长长"
export WAVERVANIR_API_KEY_PEPPER="dev-pepper-min-32-chars-..."
export WAVERVANIR_ENV="dev"
# live data needs these (lenses/cockpit/SRISK); omit for demo-only:
export FINANCIALDATA_API_KEY="<your financialdata.net key>"
export FRED_API_KEY="<your FRED key>"

# run:
./.venv/Scripts/python.exe -m uvicorn wavervanir_api.app:create_app --factory --reload
# open http://127.0.0.1:8000/app/  → register → use the 7-day trial to unlock
```

**Preview convenience (this repo):** `api/_serve_preview.py` (gitignored) seeds an
entitled user + the owner-admin and injects the data keys, so the local terminal is
fully populated. Drive it with the Claude **Preview** MCP (`launch.json` config
`cbsrm-desk`, port 8137) — the browser MCP blocks `localhost`, the Preview MCP doesn't.

**Demo mode (no keys, no network):** every data route accepts `?source=demo` and
returns deterministic synthetic readings — useful for offline UI work and tests.

---

## 6. Testing

```bash
cd api
./.venv/Scripts/python.exe -m pytest tests/ -q          # 214 passing
./.venv/Scripts/python.exe -m pytest tests/test_no_private_imports.py -q   # the import boundary
./.venv/Scripts/python.exe -m compileall src/wavervanir_api -q
```

**Gotcha:** always scope to `api/tests` — running bare `pytest` from a parent dir can
walk sibling projects and crash a capture plugin.

Key test files: `test_desk_data` (conditions/methodology), `test_desk_cache`
(snapshot cache + last-good fallback), `test_desk_riskdesk` (cockpit + chart),
`test_desk_pipeline` (governed records + dossier + systemic gate), `test_desk_validation`
(MRM binder), `test_trial` (7-day trial lifecycle), `test_stripe_webhook` +
`test_desk_stripe_sync` (billing → entitlement), `test_no_private_imports` (boundary).

---

## 7. Auth & entitlement model

- **Register/login** → `AuthService` (scrypt password hash, stdlib HS256 access+refresh JWT).
- **Statuses:** `inactive` (new) · `trialing` (free trial, time-boxed) · `active` (paid) ·
  `grace` (dunning window after a failed payment — access retained) · `revoked`.
- **`require_desk`** (default-deny): grants the terminal only when
  `plan ∈ {desk, institutional, regulator}` **and** the status is entitled
  (`active`/`grace`, or `trialing` while `grace_until` is in the future). Admins bypass.
- **Owner admin by email:** `WAVERVANIR_ADMIN_EMAILS` (default `prabhawa@wavervanir.com`) —
  that email auto-gets admin on register/login.
- **7-day free trial:** `POST /auth/start-trial` (requires login) sets
  `plan=desk/status=trialing/grace_until=now+7d`. No card, one per account, lazy
  expiry (no sweep job). The grant is written to the access ledger.
- **Every access** (and every sign-in) is appended to a **tamper-evident SHA-256
  hash chain** (`access_audit.py`); `verify_access_chain()` re-hashes top-to-bottom to
  prove no row was altered. Surfaced in the **Access ledger** tab.

---

## 8. Data sources & the import boundary

- **financialdata.net (Enterprise):** `index-prices`, `stock-prices`, `etf-prices`,
  `forex-prices`, `commodity-prices`, `crypto-prices`, `index-quotes`, `option-chain`,
  `option-greeks`, `mutual-fund-statistics`, `industry-esg-scores`, `balance-sheet-statements`,
  `market-cap`, `solvency-ratios`, `institutional-holdings` (13F), `short-interest`,
  `index-constituents`, and more. Base `https://financialdata.net/api/v1/`, auth `?key=`.
  Gotchas: `index-quotes` is real-time/market-hours-only (use `index-prices` daily close);
  `option-greeks`/`option-prices` are keyed by OCC `contract_name` (walk `option-chain` first);
  several endpoints need an `identifier`/`date` param. Key env: `FINANCIALDATA_API_KEY`.
- **FRED** (St. Louis Fed): the FRED-backed lenses (financial stress, yield curve, Sahm,
  credit spread, macro regime). Key env: `FRED_API_KEY`.
- **ECB SDMX:** the CISS family (US/EA/UK), via `cbsrm` — no key.
- **`cbsrm` (public, Apache-2.0):** all the systemic-risk math + governance. The paid
  layer imports **only** `cbsrm` — never internal VolanX. Enforced by
  `tests/test_no_private_imports.py`.

---

## 9. The premium API (gated by `require_desk`)

```
GET  /auth/me                          # entitlement + trial_days_left
POST /auth/start-trial                 # self-serve 7-day trial

GET  /v1/desk/whoami | status | methodology
GET  /v1/desk/conditions?source=live|demo[&fresh=true]    # 13-lens snapshot (cached)
GET  /v1/desk/lens/{lens_id}?source=...                    # per-lens BI drill-down
GET  /v1/desk/riskdesk?group=us-benchmarks|global-indices|fx-majors|commodities|us-megacaps|crypto
GET  /v1/desk/riskdesk/symbol/{symbol}                     # institutional any-symbol profile + chart
GET  /v1/desk/pipeline/catalog
GET  /v1/desk/pipeline/{window_id}                         # 2008Q4|2020Q1|2023Q1 governed record + dossier
POST /v1/desk/pipeline/verify                              # rebuild → confirm SHA-256 reproduces
GET  /v1/desk/pipeline/systemic                            # live SRISK Σ + per-firm + ΔCoVaR (major banks)
GET  /v1/desk/pipeline/validation                          # SR 26-2 MRM binder (inventory/conceptual/sensitivity/MC/attestation)
GET  /v1/desk/portfolio/sample  ·  POST /v1/desk/portfolio # portfolio risk analyzer
GET  /v1/desk/audit/export                                 # the caller's access trail + chain_ok

GET  /stripe/config                    # public — the Desk Payment Link URL for the Subscribe button
POST /stripe/webhook                   # Stripe → entitlement sync (POST only; GET returns 405 by design)
GET  /v1/admin/{users,entitlement,set-admin,audit,audit/verify}   # owner-only
```

**MCP server (agent-callable):** the same engines are exposed as Model Context Protocol
tools in `api/src/wavervanir_api/mcp_server.py` (`pip install -e '.[mcp]'` → `cbsrm-mcp`),
so an institution's AI copilot can query governed systemic risk — every response carries
the reproducibility SHA-256. See **`docs/MCP_SERVER.md`**.

The flagship **SRISK panel** runs the NYU-V-Lab engines on the current major-bank panel
(JPM/BAC/C/WFC/GS/MS): LRMES via `LRMESMonteCarlo` (a single shared LRMES, default
GARCH-DCC, documented caveat), market cap + `balance-sheet-statements.total_liabilities` →
`srisk_panel`, plus `DeltaCoVaREstimator`. It is a **live** read (own timestamp, not in
the governed record hash). The **MRM binder** adds an SRISK parameter-sensitivity sweep
(k × crisis threshold, rank-stability) and an honest, data-driven Monte-Carlo convergence
verdict; replication/backtest render "pending data connection" rather than a fabricated score.

---

## 10. Stripe billing — go-live runbook

Env vars (all `sync:false` in `render.yaml`):
`STRIPE_API_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PAYMENT_LINK_DESK`,
`STRIPE_PRICE_DESK` (optional), `STRIPE_DEFAULT_PLAN` (defaults to `desk` in code).

**Webhook flow** (`routes/stripe.py`): `checkout.session.completed` →
`entitle_from_checkout` (sets the referenced user — via `client_reference_id` — to
`desk/active`); `customer.subscription.updated|deleted` → plan sync / revoke;
`invoice.payment_failed` → 3-day grace. **Both test- and live-mode events are processed —
the verified `Stripe-Signature` HMAC is the security boundary.** If a checkout arrives
without `metadata.plan`, the code defaults to `STRIPE_DEFAULT_PLAN` (`desk`), so a Desk
payment always grants the terminal.

**Operator steps** (do **Test mode first** — it's an isolated sandbox that does NOT
affect other live services on the account):

1. **Stripe → Product catalog → Create product:** `CBSRM Desk`, Recurring, **48000 USD**, Yearly.
2. **Payment Links → New →** select CBSRM Desk → Create → **copy the URL** (`https://buy.stripe.com/…`).
   (Optional: add metadata `plan=desk` — not required, the code defaults to desk.)
3. **Developers → Webhooks → Add endpoint:** URL `https://app.cbsrm.wavervanir.com/stripe/webhook`,
   events `checkout.session.completed`, `customer.subscription.updated`,
   `customer.subscription.deleted`, `invoice.payment_failed`. Copy the **signing secret** (`whsec_…`).
4. **Developers → API keys:** copy the **Secret key** (`sk_test_…`, later `sk_live_…`).
5. **Render → wavervanir-api → Environment:** set `STRIPE_API_KEY`, `STRIPE_WEBHOOK_SECRET`,
   `STRIPE_PAYMENT_LINK_DESK` → **Manual Deploy → Deploy latest commit**.
6. **Test:** register on the terminal → Subscribe → pay with test card `4242 4242 4242 4242` →
   pill flips to `desk · active`. Or from the webhook page, **Send test event**
   (`checkout.session.completed`) → **Event deliveries** should show `200 OK`.

**Verify the deployed wiring without a payment:**
```bash
curl https://app.cbsrm.wavervanir.com/health          # 200
curl https://app.cbsrm.wavervanir.com/stripe/config   # {"payment_link_desk":"...","configured":true}
curl https://app.cbsrm.wavervanir.com/stripe/webhook  # 405 Method Not Allowed = endpoint live (POST-only)
```

**Phase B (go live):** repeat steps 1–4 in **Live mode**, swap the three Render env values
to live (`sk_live_…`, live `whsec_…`, live Payment Link) → Manual Deploy.

> The end-to-end flow (register → live checkout → `desk·active` → grace → revoke) is
> covered by `test_desk_stripe_sync.py` and was verified against a signed live-mode payload.

---

## 11. Deployment (Render)

- **Blueprint:** `render.yaml` — a Starter web service (`wavervanir-api`) + a `basic-256mb`
  Postgres (`wavervanir-pg`). `get_engine` normalizes `postgres://` → `postgresql://`. All
  secrets are `sync:false` (pasted at Apply, never in the repo).
- **Build/start:** `pip install` the `api/` package; start with
  `uvicorn wavervanir_api.app:create_app --factory`.
- **Custom domain:** `app.cbsrm.wavervanir.com` via a CNAME → `wavervanir-api.onrender.com`;
  Render issues TLS automatically.
- **Redeploy after any commit or env change:** Render → wavervanir-api →
  **Manual Deploy → Deploy latest commit** (not "Restart", which keeps the old build).
- **Never run `wavervanir-pg` on the free plan.** A free instance expires 30 days after
  creation; Render then gives a 14-day grace period to upgrade before deleting it and all its
  data. An expired database refuses every connection, so Desk sign-in and all authenticated
  routes return "internal server error". Free instances also have no backups or point-in-time
  recovery — those start at the paid tiers. Check the database's page in Render for its status
  and deletion date.
- **Optional cron:** `python -m wavervanir_api.tools.refresh_conditions` warms the
  conditions cache off the hot path.

---

## 12. The public marketing site

- **Repo:** `github.com/pravo123/cbsrm` → `site/index.html`, deployed by **Netlify** from `main`.
- **Live:** `cbsrm.wavervanir.com`. The "See it now" section + methodology reflect the full
  offering and link to `https://app.cbsrm.wavervanir.com/app/`.
- **Note:** that repo's worktree also carries uncommitted L3-composer work — commit **only**
  `site/index.html` for site changes.

---

## 13. Pricing & positioning

- **Desk — $48,000/yr:** single risk desk / fund — the full terminal (conditions, cockpit,
  pipeline, SRISK, MRM binder), 7-day free trial.
- **Fund / Pro — mid-six-figures:** + portfolio stress on the client book, API, more seats.
- **Institution / Central-bank — $1M+:** on-prem / air-gapped, SR 26-2 Validation Pack as a
  signed deliverable, custom jurisdictions, SLA. (The MRM binder is the highest-margin,
  least-replicable asset — consider unbundling it as a per-model line, $25–100k.)

---

## 14. Operations cheat-sheet

| Task | How |
|---|---|
| Deploy latest code | Render → wavervanir-api → Manual Deploy → Deploy latest commit |
| Rotate a key | Update the value in Render Environment → Manual Deploy |
| Check what's live | `curl …/health`, `…/stripe/config`, `…/stripe/webhook` (405) |
| Grant/revoke a user manually | Admin tab (owner login) or `AuthService.set_entitlement` |
| Verify the audit chain | Access-ledger tab → "chain verified ✓", or `/v1/admin/audit/verify` |
| Reproduce a governed record | Pipeline tab → Build → "Verify reproducibility" (SHA-256 matches) |

---

## 15. Conventions & guardrails

- **Import boundary:** paid layer imports only public `cbsrm`. Never VolanX. (AST-tested.)
- **No secrets in git:** keys live only in Render env + the gitignored `api/_serve_preview.py`.
  Scan diffs before committing.
- **Reproducibility:** governed numbers are content-addressed; the SR 26-2 binder is the
  documented validation package. Honesty over polish — the binder flags its own
  Monte-Carlo non-convergence rather than hiding it.
- **Commit style:** branch → commit → push to `cbsrm-golive`; co-author line on commits.

---

*Built across one session on 2026-06-27. Commit map of the build:*
`4b17255` auth/desk foundations → `…` → `ce46bdc` unavailable-fix + clickable methodology →
`b79b09d` governed PipelineRecord → `ecbd732` 13/13 lenses → `d1cf2de` 7-day trial →
`049fc53` Quant Cockpit → `2022abe` candlestick chart → `563ac9a` crisis dossier + SRISK
flagship → `6db24a4` SVG visuals → `a662253` tab order → `08d3a7f` SR 26-2 MRM binder →
`4643da2` landing page → `1eec336` Stripe production-ready → `a0b7b42` default-desk safeguard.
