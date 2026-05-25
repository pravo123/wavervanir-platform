# Staging verification — operator runbook

> **Scope:** WaverVanir staging only (`wavervanir-api.onrender.com` and
> `wavervanir-platform.pages.dev`). Live mode, custom domains, DNS, and
> production traffic are out of scope. This doc is the manual checklist the
> operator runs after provisioning Render + Cloudflare Pages dashboards by
> hand. Nothing here is automated.

## 0. Preconditions (operator-confirmed before starting)

- [ ] Render Web Service is up and healthy (per Render dashboard event log).
- [ ] Render Postgres is attached; `WAVERVANIR_DB_URL` is set in the API service.
- [ ] `WAVERVANIR_API_KEY_PEPPER` in Render is a fresh 48+-char random string,
      NOT the local-dev sentinel.
- [ ] `WAVERVANIR_ENV=staging` in Render.
- [ ] Cloudflare Pages project is deployed from `main`; build succeeded.
- [ ] Stripe test-mode keys (if registering the webhook yet) are pasted into
      Render env — never committed.
- [ ] No live Stripe keys (`sk_live_*`, `whsec_live_*`) anywhere.

If any precondition fails, STOP and fix it before proceeding. The verification
below assumes the staging infrastructure exists.

---

## 1. API health

```bash
curl -s https://wavervanir-api.onrender.com/health
```

Expected:

```json
{"status":"ok","service":"wavervanir-api","version":"0.1.0"}
```

If the response is 502/503: check Render service logs. If the response is 200
but `service` is wrong: confirm the build picked up the right repo + branch.

---

## 2. Landing renders

```bash
curl -sI https://wavervanir-platform.pages.dev/ | head -3
```

Expected: `HTTP/2 200`. Then open the URL in a browser and confirm:

- [ ] Nav logo + "WaverVanir" wordmark + "Process Over Prediction" tagline render.
- [ ] Hero logo renders.
- [ ] Pricing section shows 4 tiles (Researcher / Pro / Institutional / Regulator).
- [ ] DevTools console: zero errors.
- [ ] DevTools network: no 4xx / 5xx on the page load.

---

## 3. Same-origin proxy works (Cloudflare `_redirects`)

```bash
curl -s https://wavervanir-platform.pages.dev/health
```

Expected: identical JSON to step 1. This proves the Cloudflare Pages
`_redirects` rule for `/health` proxies to Render. If it returns 404 or
returns Cloudflare's HTML, the `_redirects` file was not picked up — confirm
it lives at `landing/public/_redirects` in `main`.

Repeat for `/v1/*`:

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://wavervanir-platform.pages.dev/v1/cbsrm/macro-composite/windows
```

Expected: `401` (auth required, but the route is reachable through the proxy).

---

## 4. Bootstrap an API key (Render shell)

In the Render dashboard, open the **Shell** tab on the `wavervanir-api`
service and run:

```bash
python -m wavervanir_api.tools.bootstrap_key \
    --plan researcher \
    --label "staging-smoke-$(date +%Y-%m-%d)"
```

Expected output (sample):

```
[bootstrap_key] OK
  api_key_id : 1
  plan       : researcher
  daily_cap  : 5000
  label      : staging-smoke-2026-05-25
  api_key    : wvk_XXXXXXXXXXXXXXXXXXXXXXXXXXXXX

This token will NOT be shown again. Copy it to a password manager now.
Audit fingerprint: request_sha256=...
```

**Immediately** copy the `wvk_…` token into your password manager. Then close
the Render shell so it does not sit in scrollback.

Failure modes:

- `REFUSED — WAVERVANIR_API_KEY_PEPPER is the default sentinel value` →
  rotate the pepper to a strong random string in Render env, redeploy, retry.
- `REFUSED — refusing to mint credentials with WAVERVANIR_ENV=prod` →
  staging service must have `WAVERVANIR_ENV=staging`, not `prod`.

---

## 5. Authenticated `/v1/cbsrm/macro-composite/windows`

```bash
WVK="wvk_PASTE_FROM_STEP_4"

curl -s https://wavervanir-api.onrender.com/v1/cbsrm/macro-composite/windows \
     -H "Authorization: Bearer $WVK"
```

Expected:

```json
{"windows":["2008Q4","2020Q1","2023Q1"]}
```

(Window list may evolve with CBSRM upstream.) If 401: the pepper used at mint
time differs from the pepper the API is currently reading — restart the
service after a pepper rotation and re-mint.

Run the same call via the Cloudflare proxy to confirm both paths work:

```bash
curl -s https://wavervanir-platform.pages.dev/v1/cbsrm/macro-composite/windows \
     -H "Authorization: Bearer $WVK"
```

---

## 6. Authenticated macro-composite POST

```bash
curl -s -X POST https://wavervanir-api.onrender.com/v1/cbsrm/macro-composite \
     -H "Authorization: Bearer $WVK" \
     -H "Content-Type: application/json" \
     -d '{"window_id":"2008Q4"}'
```

Expected: `200` with `report` (dict) + `rendered_markdown` (string).

---

## 7. Waitlist POST (unauthenticated)

```bash
curl -s -X POST https://wavervanir-platform.pages.dev/v1/waitlist \
     -H "Content-Type: application/json" \
     -d '{"email":"smoke@wavervanir.com","tier_interest":"institutional"}'
```

Expected: `201` with `{"ok":true,"id":N,"deduplicated":false}`. Repeat the
same payload — expect `deduplicated: true` second time.

---

## 8. Stripe webhook + `/onboard` (only after Stripe test-mode is wired)

Order of operations:

1. Deploy API → record the Render URL.
2. In Stripe test dashboard, create the webhook endpoint at
   `https://wavervanir-api.onrender.com/stripe/webhook` (events listed in
   `docs/STRIPE_SETUP.md` §4).
3. Copy the `whsec_…` value into the Render env as `STRIPE_WEBHOOK_SECRET`.
4. Restart the Render service.
5. Trigger a fake checkout:

    ```bash
    stripe trigger checkout.session.completed \
        --add checkout_session:metadata.plan=researcher \
        --add checkout_session:id=cs_staging_smoke \
        --add checkout_session:customer=cus_staging_smoke \
        --add checkout_session:subscription=sub_staging_smoke
    ```

6. Render logs should show `200` on `POST /stripe/webhook`.
7. Fetch the disclosed key exactly once:

    ```bash
    curl -s 'https://wavervanir-platform.pages.dev/onboard?session_id=cs_staging_smoke'
    ```

    Expected: `{"api_key":"wvk_…","plan":"researcher",...}`.

8. Fetch again with the same `session_id`:

    Expected: `410 Gone`.

9. Unknown session_id:

    ```bash
    curl -s -o /dev/null -w "%{http_code}\n" \
         'https://wavervanir-platform.pages.dev/onboard?session_id=cs_does_not_exist'
    ```

    Expected: `404`.

10. Cancel the subscription and confirm revocation:

    ```bash
    stripe trigger customer.subscription.deleted \
        --add subscription:customer=cus_staging_smoke
    ```

    Next call with the disclosed key should return `401`.

---

## 9. Cleanup checklist (after smoke succeeds)

- [ ] Revoke the bootstrap key from step 4 (Render shell):

    ```bash
    python -c "
    from sqlmodel import Session, select
    from wavervanir_api.db import ApiKey, get_engine
    from wavervanir_api.config import get_settings
    s = get_settings()
    engine = get_engine(s.db_url)
    with Session(engine) as session:
        row = session.exec(select(ApiKey).where(ApiKey.id == <BOOTSTRAP_ID>)).first()
        row.status = 'revoked'
        session.add(row); session.commit()
    "
    ```

- [ ] Confirm subsequent calls with the bootstrap key return `401`.
- [ ] Confirm waitlist test entry was removed (or left for review):

    ```sql
    DELETE FROM waitlist WHERE email = 'smoke@wavervanir.com';
    ```

- [ ] Confirm `audit_log` rows for the smoke run are present (do NOT delete
      them — audit chain is append-only by policy).
- [ ] Confirm no Stripe live-mode events ever fired against this service
      (Stripe dashboard → Events → filter `livemode = false`).

---

## 10. What is NOT verified by this doc

- Custom domains (`risk-staging.wavervanir.com`, `api-staging.wavervanir.com`) — separate prompt.
- TLS pinning / HSTS — separate prompt.
- Production rate limit tuning — staging uses plan-catalog defaults.
- Observability (Sentry, Datadog, structured logs) — separate prompt.
- Live-mode Stripe — explicitly deferred until staging holds for ≥ 7 days.
