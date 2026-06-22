# Deploy quickstart — connect & go

The tight, operator-runnable version. For rationale and the full checklist see
`docs/DEPLOY.md`; for staging smoke detail see `docs/STAGING_VERIFICATION.md`.

Stack: **API** on Render (Blueprint), **landing** on Cloudflare Pages, **DNS**
at Bluehost.

```
risk.wavervanir.com  ──CNAME──►  Cloudflare Pages   (landing, Vite)
api.wavervanir.com   ──CNAME──►  Render web service (wavervanir-api, FastAPI)
                                       │
                                  Render Postgres (wavervanir-pg)
```

---

## Step 0 — Publish this branch (prerequisite)

Render and Cloudflare build from a branch **on GitHub**, so the `render.yaml`,
`deploy/`, and this file must be pushed before Steps 1–2 can find them. They
currently live only on the local `cbsrm-golive` branch.

```bash
git add render.yaml deploy/ DEPLOY_QUICKSTART.md site-integration/
git commit -m "feat: deploy-as-code + CBSRM site-integration kit"
git push -u origin cbsrm-golive     # or merge to main, then deploy from main
```

> If you deploy from `main` instead of `cbsrm-golive`, substitute `main`
> wherever a branch is selected below.

---

## Step 1 — Deploy the API (Render Blueprint)

This repo ships `render.yaml` at the root, so Render provisions the web service
+ Postgres in one shot.

1. Render dashboard > **New +** > **Blueprint**.
2. Connect this GitHub repo, pick the branch you pushed in Step 0
   (`cbsrm-golive` or `main`).
3. Render reads `render.yaml` and shows: web service `wavervanir-api` +
   database `wavervanir-pg`. Click **Apply**.
   - ⚠️ The blueprint sets the Postgres `plan: free`, which Render **deletes
     after 90 days** (taking minted API keys + waitlist rows with it). Before
     then, upgrade `wavervanir-pg` to the **$7 Starter** plan in the Render UI.
4. At Apply, Render prompts for the `sync: false` secrets — you can leave them
   blank now and paste in **Step 4**. (`WAVERVANIR_DB_URL` and
   `WAVERVANIR_API_KEY_PEPPER` are wired/generated automatically.)
5. Wait for the first deploy to go green. Note the service URL,
   `https://wavervanir-api.onrender.com`.

Start command (from `render.yaml`, matches the app factory):
`uvicorn wavervanir_api.app:create_app --factory --host 0.0.0.0 --port $PORT`

---

## Step 2 — Deploy the landing (Cloudflare Pages)

Full settings table: `deploy/landing.cloudflare-pages.md`. Short version:

1. Cloudflare > **Workers & Pages** > **Create** > **Pages** > connect this repo.
2. Settings:
   - Project root: repo root (blank)
   - Build command: `cd landing && npm ci && npm run build`
   - Build output directory: `landing/dist`
   - Build env var `NODE_VERSION` = `20`
3. Add VITE_* env vars (all public) — see Step 4.
4. Deploy. Note the Pages URL, `https://wavervanir-platform.pages.dev`.

The checked-in `landing/public/_redirects` proxies `/v1/*`, `/onboard`,
`/stripe/*`, `/health` to the Render API (no CORS).

---

## Step 3 — DNS records (at Bluehost)

Bluehost is the DNS host for `wavervanir.com`. Add these two CNAME records in
the Bluehost DNS zone editor:

| Type | Host / Name | Points to (Value) | TTL |
| --- | --- | --- | --- |
| CNAME | `risk` (= `risk.wavervanir.com`) | `wavervanir-platform.pages.dev` | Auto / 3600 |
| CNAME | `api`  (= `api.wavervanir.com`)  | `wavervanir-api.onrender.com`  | Auto / 3600 |

Then claim each host on its platform so TLS is issued:

- Cloudflare Pages > project > **Custom domains** > add `risk.wavervanir.com`.
- Render > `wavervanir-api` > **Settings > Custom Domains** > add
  `api.wavervanir.com` (Render will confirm the CNAME and issue a cert).

> Render may display the canonical CNAME target as
> `wavervanir-api.onrender.com`; use whatever exact target the Render Custom
> Domains panel shows if it differs.

After `api.wavervanir.com` has valid TLS, update `landing/public/_redirects`
to point at it (one-line-per-rule change) — see
`deploy/landing.cloudflare-pages.md`. Until then the `onrender.com` destination
keeps working.

---

## Step 4 — Paste secrets

**Render** (`wavervanir-api` > Environment) — paste real values for the
`sync: false` vars from `render.yaml`. Reference: `deploy/API.env.example`.

| Key | Value |
| --- | --- |
| `STRIPE_API_KEY` | `sk_test_...` (test-mode restricted key) |
| `STRIPE_WEBHOOK_SECRET` | `whsec_...` (after registering the webhook; then restart) |
| `STRIPE_PRICE_RESEARCHER` | `price_...` (Researcher $49 Price id) |
| `STRIPE_PRICE_PRO` | `price_...` (Pro $499 Price id) |
| `FMP_API_KEY` | optional — leave blank to disable the FMP feed |

Already set automatically by the blueprint — do not change:
`WAVERVANIR_ENV=staging`, `WAVERVANIR_RATE_LIMIT_FREE=100`,
`WAVERVANIR_API_KEY_PEPPER` (generated), `WAVERVANIR_DB_URL` (from DB).

**Cloudflare Pages** (Settings > Environment variables > Production) — all
public `VITE_*`:

| Key | Value |
| --- | --- |
| `VITE_STRIPE_LINK_RESEARCHER` | `https://buy.stripe.com/test_...` (or blank → `#waitlist`) |
| `VITE_STRIPE_LINK_PRO` | `https://buy.stripe.com/test_...` (or blank → `#waitlist`) |
| `VITE_INSTITUTIONAL_HREF` | `#waitlist` |
| `VITE_WAVERVANIR_API_URL` | leave blank (use the `_redirects` proxy) |

Never put `sk_*` / `whsec_*` in a `VITE_*` var.

---

## Step 5 — Smoke test

Run after both deploys are green. (Full matrix: `docs/STAGING_VERIFICATION.md`.)

```bash
# 1. API health (direct)
curl -s https://wavervanir-api.onrender.com/health
# expect: {"status":"ok","service":"wavervanir-api","version":"0.1.0"}

# 2. Same-origin proxy health (via Cloudflare Pages)
curl -s https://wavervanir-platform.pages.dev/health
# expect: identical JSON to #1

# 3. CBSRM windows route is reachable through the proxy (401 = auth required, route live)
curl -s -o /dev/null -w "%{http_code}\n" \
  https://wavervanir-platform.pages.dev/v1/cbsrm/macro-composite/windows
# expect: 401
```

Mint a key in the Render **Shell** tab, then exercise the authenticated CBSRM
calls:

```bash
# In the Render shell — mint a researcher key (copy the wvk_... once):
python -m wavervanir_api.tools.bootstrap_key \
  --plan researcher --label "smoke-$(date +%Y-%m-%d)"
```

```bash
WVK="wvk_PASTE_FROM_SHELL"

# 4. Authenticated: list macro-composite windows
curl -s https://wavervanir-api.onrender.com/v1/cbsrm/macro-composite/windows \
  -H "Authorization: Bearer $WVK"
# expect: {"windows":["2008Q4","2020Q1","2023Q1"]}  (list may evolve upstream)

# 5. Authenticated: macro-composite report for one window
curl -s -X POST https://wavervanir-api.onrender.com/v1/cbsrm/macro-composite \
  -H "Authorization: Bearer $WVK" \
  -H "Content-Type: application/json" \
  -d '{"window_id":"2008Q4"}'
# expect: 200 with `report` (dict) + `rendered_markdown` (string)
```

Once custom domains are live, repeat #1 against `https://api.wavervanir.com/health`
and load `https://risk.wavervanir.com/` in a browser (zero console errors).
