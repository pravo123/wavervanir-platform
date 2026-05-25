# Stripe setup — test mode only

> **Test mode only.** Live mode is a separate, future operator-approved step.
> No real money. No live secrets. Never commit any Stripe key.

This doc walks through wiring `wavervanir-api` to a Stripe **test-mode** account so
the full Researcher / Pro checkout → key-issuance loop works end-to-end on localhost.

## 0. Plan catalog (canonical)

| plan name | price (test) | tier (DB) | self-serve checkout | rate cap (default) |
|---|---|---|---|---|
| `free` | $0 | `free` | no | 100/day |
| `researcher` | $49/mo | `paid` | ✅ Payment Link | 5,000/day |
| `pro` | $499/mo | `paid` | ✅ Payment Link | 15,000/day |
| `institutional` | from $4,999/mo | `paid` | ❌ — provisioned manually | 50,000/day default |
| `regulator` | bespoke | `paid` | ❌ — provisioned manually | 50,000/day default |

Source of truth: `api/src/wavervanir_api/plans.py`.

## 1. Create the test-mode account workspace

1. Open https://dashboard.stripe.com/ and toggle to **Test mode** (top-right).
2. Generate a restricted key with scopes: Webhooks (R/W), Products (W), Payment Links (W).

## 2. Create Products + Prices

In the Stripe dashboard:

- **Product:** "Researcher Paid"
  - Price: **$49.00 USD / monthly**, recurring
  - Price metadata: `plan = researcher`
- **Product:** "Pro"
  - Price: **$499.00 USD / monthly**, recurring
  - Price metadata: `plan = pro`

The webhook reads `metadata.plan` to choose the API plan. If it is missing
or unknown, the webhook defaults to `researcher`.

## 3. Create Payment Links

For each Price above, create a Payment Link with:

- `success_url` = `http://localhost:5174/onboard?session_id={CHECKOUT_SESSION_ID}` (dev)
                 / `https://risk.wavervanir.com/onboard?session_id={CHECKOUT_SESSION_ID}` (later)
- `cancel_url`  = `http://localhost:5174/#pricing`

Copy the resulting URLs and put them in `landing/.env` as:

```
VITE_STRIPE_LINK_RESEARCHER=https://buy.stripe.com/test_xxx
VITE_STRIPE_LINK_PRO=https://buy.stripe.com/test_yyy
```

These are **public** values; they end up in the bundle. Never put `sk_*` /
`whsec_*` into a `VITE_*` var.

## 4. Register the webhook

- Endpoint URL (dev): `http://localhost:8000/stripe/webhook` (use `stripe listen` to forward)
- Endpoint URL (later prod): `https://api.wavervanir.com/stripe/webhook`
- Events:
  - `checkout.session.completed`
  - `customer.subscription.created`
  - `customer.subscription.updated`
  - `customer.subscription.deleted`
  - `invoice.payment_failed`
- Copy the resulting `whsec_test_*` into your local `api/.env`. **Never commit.**

## 5. Local dev cycle

Three terminals:

```bash
# Terminal 1 — API
cd api
.venv/Scripts/activate              # or `source .venv/bin/activate` on macOS/Linux
uvicorn wavervanir_api.app:create_app --factory --reload --port 8000

# Terminal 2 — stripe-cli forwarder (install separately; never committed)
stripe listen --forward-to localhost:8000/stripe/webhook

# Terminal 3 — landing
cd landing
npm run dev
```

## 6. Local verification

```bash
# Drive a fake checkout
stripe trigger checkout.session.completed \
    --add checkout_session:metadata.plan=researcher \
    --add checkout_session:id=cs_test_local_demo \
    --add checkout_session:customer=cus_test_local \
    --add checkout_session:subscription=sub_test_local

# 1) Webhook should respond 200 + {"handled":"checkout.session.completed","idempotent":false,...}

# 2) Fetch the API key exactly once
curl 'http://localhost:8000/onboard?session_id=cs_test_local_demo'
# → {"api_key":"wvk_xxx","plan":"researcher",...}

# 3) Second fetch should fail
curl -i 'http://localhost:8000/onboard?session_id=cs_test_local_demo'
# → HTTP/1.1 410 Gone

# 4) Use the key
curl -s -X POST http://localhost:8000/v1/cbsrm/macro-composite \
     -H "Authorization: Bearer wvk_xxx" \
     -H "Content-Type: application/json" \
     -d '{"window_id":"2008Q4"}'

# 5) Plan-change replay
stripe trigger customer.subscription.updated \
    --add subscription:id=sub_test_local \
    --add subscription:metadata.plan=pro

# 6) Cancellation
stripe trigger customer.subscription.deleted \
    --add subscription:customer=cus_test_local
# Subsequent calls with the same key should now return 401.
```

## 7. Env vars (`.env`, gitignored)

```dotenv
WAVERVANIR_ENV=dev
WAVERVANIR_API_KEY_PEPPER=<long random local string>
STRIPE_API_KEY=sk_test_REPLACE
STRIPE_WEBHOOK_SECRET=whsec_REPLACE
# Optional — leave blank to inherit plan defaults from plans.py
STRIPE_PRICE_RESEARCHER=price_test_REPLACE
STRIPE_PRICE_PRO=price_test_REPLACE
```

## 8. Promotion to live mode (deferred)

Out of scope for this slice. Live mode will require, at minimum:

- Live keys stored in the hosted secret manager (Render env / Cloudflare Pages env).
- Live webhook endpoint at `https://api.wavervanir.com/stripe/webhook` with rotated secret.
- A `livemode=true` guard flip in `routes/stripe.py` (currently refused).
- DPA + ToS review (Stripe is a sub-processor).

Track via the platform readiness checklist (see `docs/DEPLOY.md`).
