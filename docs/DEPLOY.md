# Deployment runbook — recommendations only

> **Read-only.** This doc documents the chosen deployment targets and the
> manual steps to ship them. It does NOT contain deploy automation. No
> infrastructure has been provisioned by the assistant. DNS, TLS, and
> live-mode secrets are operator-driven and deferred to a separate slice.

## TL;DR

| Surface | Host | Plan | $/mo (MVP) |
|---|---|---|---|
| API (`wavervanir-api`) | **Render** (Web Service, Hobby) | Hobby | ~$7 |
| Landing (`wavervanir-landing`) | **Cloudflare Pages** | Free | $0 |
| DB | **Render Postgres** (same provider) | Free → Starter | $0–$7 |

Total: **~$7–$14/mo** for the whole MVP stack.

## Why Render for the API

| Criterion | Render | Fly.io | Railway |
|---|---|---|---|
| Setup time | very low | medium (Dockerfile) | very low |
| MVP price | $0–$7 + $0–$7 PG | $0–$5 + external PG | $5–$15 usage-based |
| Managed Postgres first-party | ✅ | ⚠ via Fly PG | ✅ |
| Auto-deploy from GitHub | ✅ on push | ✅ via GH Action | ✅ |
| Cold start on Hobby | none | scale-to-zero (1–3 s) | low |
| Secret UI | ✅ | ✅ | ✅ |

Render wins on **lowest setup time + first-party managed Postgres + no cold start
on the $7 tier**. Fly is the strong runner-up if we later want global edge.

## Why Cloudflare Pages for the landing

| Criterion | Cloudflare Pages | Vercel Hobby |
|---|---|---|
| MVP price | $0 | $0 |
| Bandwidth limit (free) | **unlimited** | 100 GB / mo |
| Commercial use OK on free tier | ✅ | ⚠ Hobby = personal-use only per ToS |
| GitHub auto-deploy | ✅ | ✅ |
| Custom domain free | ✅ | ✅ |

Cloudflare wins on **commercial-use clarity + unlimited bandwidth at $0**.

## Render — manual setup steps (operator-driven)

| Field | Value |
| --- | --- |
| Service type | Web Service |
| Source | `pravo123/wavervanir-platform`, branch `main`, auto-deploy ON |
| Root Directory | `api` |
| Runtime | Python 3.12 |
| Build command | `pip install --upgrade pip && pip install -e .` |
| Start command | `uvicorn wavervanir_api.app:create_app --factory --host 0.0.0.0 --port $PORT` |
| Health check path | `/health` |
| Health check expected status | `200` |
| Instance type | Hobby ($7/mo) — Free OK only for first 10-min smoke (15-min idle → cold) |
| Disk | none (all state in Postgres) |

### Render env vars (paste under **Environment** in the UI — never commit)

| Key | Value | Source |
| --- | --- | --- |
| `WAVERVANIR_ENV` | `staging` | informational |
| `WAVERVANIR_DB_URL` | internal connection string from Render Postgres | auto-filled when both services share the env group |
| `WAVERVANIR_API_KEY_PEPPER` | operator generates with `python -c "import secrets; print(secrets.token_urlsafe(48))"` and pastes | rotates entire keyspace if changed — do NOT reuse the local-dev sentinel |
| `WAVERVANIR_RATE_LIMIT_FREE` | `100` | matches local default |
| `WAVERVANIR_RATE_LIMIT_PAID` | leave blank | plan-catalog caps apply |
| `STRIPE_API_KEY` | `sk_test_…` (test-mode restricted key with Webhooks R/W) | Stripe test dashboard |
| `STRIPE_WEBHOOK_SECRET` | `whsec_…` (test-mode) | obtained AFTER registering the webhook URL — see `STRIPE_SETUP.md` §9 |
| `STRIPE_PRICE_RESEARCHER` | leave blank in first deploy | populate once the Product exists |
| `STRIPE_PRICE_PRO` | leave blank in first deploy | populate once the Product exists |

### Render Postgres provisioning

| Field | Value |
| --- | --- |
| Name | `wavervanir-staging-pg` |
| Plan | Free (90 days) → upgrade to $7 Starter before expiry |
| Database | `wavervanir_staging` |
| Connect to Web Service | YES — Render pastes the internal URL into `WAVERVANIR_DB_URL` automatically |

## Cloudflare Pages — manual setup steps (operator-driven)

| Field | Value |
| --- | --- |
| Project name | `wavervanir-platform` |
| Production branch | `main` |
| Framework preset | Vite |
| Project root | repo root |
| Build command | `cd landing && npm ci && npm run build` |
| Build output directory | `landing/dist` |
| Node version | 20 (matches CI) |

### Cloudflare Pages env vars (Settings → Environment variables → Production)

| Key | Value | Note |
| --- | --- | --- |
| `VITE_STRIPE_LINK_RESEARCHER` | leave blank for first deploy | CTA falls back safely to `#waitlist` |
| `VITE_STRIPE_LINK_PRO` | leave blank for first deploy | same fallback |
| `VITE_INSTITUTIONAL_HREF` | `#waitlist` | matches `.env.example` |

> `VITE_*` env vars are **public** — they are inlined into the JS bundle.
> Never put `sk_*` / `whsec_*` into a `VITE_*` slot.

### Same-origin proxy via `landing/public/_redirects`

To avoid CORS, the landing's `/v1/*`, `/onboard`, `/stripe/*`, and `/health`
paths proxy to the Render API. The file is checked in at
`landing/public/_redirects` and ships in `landing/dist` automatically. Update
the destination host once a custom domain is wired (deferred).

### Custom domain decision

**Defer** to a later prompt. First staging deploy uses
`wavervanir-platform.pages.dev` + `wavervanir-api.onrender.com`. Operator-
driven DNS (`risk-staging.wavervanir.com`, `api-staging.wavervanir.com`)
lands after the staging surface holds for ≥ 24h.

## DNS / TLS

Deferred. When ready:

- `risk.wavervanir.com` → Cloudflare Pages (landing).
- `api.wavervanir.com`  → Render Web Service (api).

Both get TLS via the host's managed cert. No manual cert work.

## What is explicitly NOT in this slice

- Provisioning any cloud resource (Render service, Cloudflare project, Postgres instance).
- DNS records.
- TLS certs.
- Live-mode Stripe keys.
- Production-grade observability (Sentry, Datadog) — added in a later slice.
- Multi-region or autoscaling — premature for MVP.

## Readiness checklist (toward live deploy)

- [ ] Operator creates Stripe test-mode Products + Prices + Payment Links (see `STRIPE_SETUP.md`).
- [ ] Operator provisions Render Web Service + Render Postgres.
- [ ] Operator provisions Cloudflare Pages project.
- [ ] Operator wires env vars (no secrets committed to repo).
- [ ] First end-to-end test-mode checkout succeeds on staging.
- [ ] Separate prompt requests live-mode promotion.
