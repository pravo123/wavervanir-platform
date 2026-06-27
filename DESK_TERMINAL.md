# CBSRM Desk — paid-customer terminal

The authenticated terminal that an institution logs into after subscribing to the
**Desk** tier ($48,000/yr). It extends the existing `wavervanir-platform` API with
a user sign-in layer, an entitlement gate, premium data routes, and a
tamper-evident access ledger — and serves a single-page terminal UI. The public
Apache-2.0 `cbsrm` package is untouched.

## What it adds

| Area | Module | Notes |
|------|--------|-------|
| Sign-in class | `users.py` (`AuthService`) | register / login / refresh / token resolution / entitlement |
| Password + JWT | `security.py` | stdlib **scrypt** (argon2id-class) + stdlib **HS256 JWT** — zero new deps |
| Tamper-evident ledger | `access_audit.py` (`AccessEvent`) | SHA-256 hash-linked, portable across SQLite + Postgres |
| Auth routes | `routes/users.py` | `POST /auth/register\|login\|refresh`, `GET /auth/me` |
| Gated routes | `routes/desk.py` | `GET /v1/desk/whoami\|status\|methodology\|conditions\|lens/{id}\|audit/export` behind `require_desk` |
| BI analytics | `desk_analytics.py` | per-lens history + stats (min/max/mean/percentile/z) + regime bands; `GET /v1/desk/lens/{id}` |
| Advanced lenses | `desk_lenses.py` | from financialdata.net: **Diebold-Yilmaz cross-border spillover** (real VAR + generalized FEVD), options put/call vega skew, fund redemption pressure (real flows), ESG/climate transition risk |
| Entitlement | `db.py` (`User`), `plans.py` (`desk`) | default-deny: `plan ∈ {desk,institutional,regulator}` and `status ∈ {active,grace}` |
| Terminal UI | `web/index.html` | served same-origin at `/app` (no CORS) |
| Billing sync | `routes/stripe.py` | checkout → active, payment_failed → grace, subscription deleted → revoked |

## Access model

`www.wavervanir.com`'s **Sign In** is a hub that branches to two products —
**VolanX** (`volanx.wavervanir.com`) and **CBSRM** (`cbsrm.wavervanir.com`). The
Desk keeps its own institutional accounts with the same email→password→JWT
experience; it is not coupled to the retail VolanX account pool.

## Owner / admin access

The configured owner email(s) — `WAVERVANIR_ADMIN_EMAILS`, default
`prabhawa@wavervanir.com` — get **full admin** automatically on sign-up/login
(no separate grant). Admins have `is_admin = true`, bypass the subscription gate
(`has_terminal` is always true for them), and reach the `/v1/admin/*` console:

- `GET /v1/admin/users` — every account (no password material).
- `POST /v1/admin/entitlement` — grant/revoke any user's plan + status.
- `POST /v1/admin/set-admin` — promote/demote another account (can't self-demote).
- `GET /v1/admin/audit/verify` — re-hash and verify the whole access ledger.
- `GET /v1/admin/audit?subject=user:<id>` — any account's access trail.

The terminal shows an **Admin** tab for admins. Every admin action is written to
the tamper-evident ledger as `ADMIN_ACTION`.

Provision the owner account securely (password typed at a hidden prompt, never on
the command line or in chat):

```bash
python -m wavervanir_api.tools.bootstrap_admin --email prabhawa@wavervanir.com
# or non-interactively:
CBSRM_ADMIN_PASSWORD=… python -m wavervanir_api.tools.bootstrap_admin --email prabhawa@wavervanir.com
```

Because the owner is admin *by email*, simply registering `prabhawa@wavervanir.com`
through `/auth/register` with any password also makes it admin — the bootstrap
tool is for first-time/headless setup against the deployed Postgres.

## Environment

| Var | Source | Purpose |
|-----|--------|---------|
| `WAVERVANIR_JWT_SECRET` | Render `generateValue` | signs access/refresh JWTs (rotate off the dev sentinel before serving real users) |
| `WAVERVANIR_ADMIN_EMAILS` | optional | comma-separated owner emails granted admin (default `prabhawa@wavervanir.com`) |
| `WAVERVANIR_API_KEY_PEPPER` | Render `generateValue` | existing API-key pepper |
| `WAVERVANIR_DB_URL` | Render Postgres | dev defaults to SQLite |
| `STRIPE_API_KEY` / `STRIPE_WEBHOOK_SECRET` | operator | Stripe (test mode in MVP) |
| `STRIPE_PRICE_DESK` | operator | Stripe Price id for the $48k/yr Desk |
| `FRED_API_KEY` | operator (optional) | enables the FRED lenses in `/v1/desk/conditions?source=live` |
| `FINANCIALDATA_API_KEY` | operator (optional) | enables the financialdata.net provider + the equity-volatility (VIX) lens |
| `WAVERVANIR_ACCESS_TTL_MIN` / `WAVERVANIR_REFRESH_TTL_DAYS` | optional | default 15 min / 7 days |

## Stripe Payment Link wiring (the one operator detail that matters)

For a paid checkout to entitle the right account, the Desk Payment Link must:
1. carry **`metadata.plan = desk`** on its Price (so the webhook sets `plan=desk`), and
2. receive **`client_reference_id`** = the user's id. The terminal already appends
   this: the "Subscribe → $48k/yr" button links to
   `https://buy.stripe.com/…?client_reference_id=<user_id>`.

On `checkout.session.completed` the webhook calls
`AuthService.entitle_from_checkout(...)` → the user flips to `desk / active`.

## Run locally

```bash
cd api
pip install -e .
uvicorn wavervanir_api.app:create_app --factory --reload
# terminal UI:  http://127.0.0.1:8000/app/
# API docs:     http://127.0.0.1:8000/docs
pytest -q            # 136 passing
```

## Verify the gate end-to-end

```
register → 201 (plan=free, status=inactive)
GET /v1/desk/whoami        → 403  desk_subscription_required   (default-deny)
# simulate Stripe checkout.session.completed (client_reference_id=user id, metadata.plan=desk)
GET /v1/desk/whoami        → 200  terminal_access=true
GET /v1/desk/audit/export  → chain_ok=true   (sign-in + every access hash-linked)
```

## Operator follow-ups (not code)

1. **Render** — Apply the Blueprint, paste `STRIPE_*` + `FRED_API_KEY`; Render
   generates `WAVERVANIR_JWT_SECRET`.
2. **Stripe** — confirm the Desk Payment Link/Price has `metadata.plan=desk`, and
   register the webhook endpoint (`/stripe/webhook`) to obtain `STRIPE_WEBHOOK_SECRET`.
   Verify the link is in **Live** mode before inviting real institutions.
3. **WordPress hub** (`www.wavervanir.com`, Bluehost) — make **Sign In** a 2-way
   chooser: VolanX (`volanx.wavervanir.com/login`) | CBSRM (`<api>/app/`). Drive
   via the shared browser; the operator logs in (no credentials handled in chat).

## Live-conditions cache

`GET /v1/desk/conditions?source=live` is served from a short-TTL DB cache
(`SnapshotCache`, default 1 h) so the slow multi-upstream build (~15-20 s for 13
lenses) is paid once, not per request — cached reads return in ~1 ms. Force a
recompute with `?fresh=true`. Keep the cache warm with the refresh tool on a
scheduler (Render Cron / GitHub Action / cron, every ~30-60 min):

```bash
python -m wavervanir_api.tools.refresh_conditions   # needs DB + FRED + FINANCIALDATA keys
```

## Known limits (MVP)

- The cache is per-process/DB-backed; a multi-worker deploy shares it via Postgres.
  The first request after TTL expiry (with no scheduled refresh) still pays the
  full build cost — run the refresh tool to avoid that.
- The hash-linked ledger serializes appends with a process lock (single-worker
  correct); multi-worker deployments need a DB-level sequence.
- Verifiable `PipelineRecord` routes are deferred until `cbsrm.composer` is
  published to the pinned tag.
