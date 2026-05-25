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

1. https://dashboard.render.com → New → **Web Service** → connect `pravo123/wavervanir-platform`.
2. Build command: `pip install -e api/`
3. Start command: `uvicorn wavervanir_api.app:create_app --factory --host 0.0.0.0 --port $PORT`
4. Plan: **Hobby ($7/mo)**.
5. Region: closest to expected first users.
6. Env vars (paste from local `api/.env`, **TEST MODE ONLY** for first deploy):
   - `WAVERVANIR_ENV=staging`
   - `WAVERVANIR_API_KEY_PEPPER=<rotate from local>`
   - `STRIPE_API_KEY=sk_test_…`
   - `STRIPE_WEBHOOK_SECRET=whsec_…` (use the prod-endpoint secret from Stripe dashboard)
   - `WAVERVANIR_DB_URL=` … set after Postgres step
7. Add **Render Postgres** → copy the internal connection URL into `WAVERVANIR_DB_URL`.
8. Save & deploy.

## Cloudflare Pages — manual setup steps (operator-driven)

1. https://dash.cloudflare.com → Pages → Connect to Git → `pravo123/wavervanir-platform`.
2. Build settings:
   - Framework preset: **Vite**
   - Build command: `cd landing && npm install && npm run build`
   - Build output directory: `landing/dist`
3. Env vars (public — these end up in the bundle):
   - `VITE_STRIPE_LINK_RESEARCHER=https://buy.stripe.com/test_…`
   - `VITE_STRIPE_LINK_PRO=https://buy.stripe.com/test_…`
   - `VITE_INSTITUTIONAL_HREF=#waitlist`
4. Save & deploy.
5. (Later) Custom domain `risk.wavervanir.com` via Cloudflare DNS.

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
