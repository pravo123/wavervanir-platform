# FMP setup

Wire Financial Modeling Prep as the `fmp` market-data provider.

## What this does and does not do

* **Does** turn `GET /v1/data/snapshot/{symbol}?provider=fmp&kind=market`
  into a live FMP `/api/v3/quote/{SYMBOL}` call when a key is set.
* **Does not** call FMP from tests. The adapter accepts an injectable
  client and CI uses a stub.
* **Does not** bundle the `fmp-python` SDK. The adapter uses `httpx`,
  which is already a project dependency.

## Step 1 — create an FMP account (test usage)

1. Sign up at <https://financialmodelingprep.com/>.
2. Copy the API key from your dashboard.
3. The free tier is rate-limited; for production move to a paid plan.

## Step 2 — set the env var locally

Add to `.env` (never committed):

```dotenv
FMP_API_KEY=YOUR_FMP_KEY_HERE
```

`.env` is gitignored. `.env.example` carries only a placeholder.

## Step 3 — verify locally

```bash
cd api
.venv/Scripts/python -m uvicorn wavervanir_api.app:create_app --factory --reload
# in another terminal, mint a key for testing
.venv/Scripts/python -m wavervanir_api.tools.bootstrap_key --plan researcher --label "fmp-smoke"
# then curl with the printed wvk_… token
curl -H "Authorization: Bearer wvk_xxx" \
  "http://127.0.0.1:8000/v1/data/snapshot/AAPL?provider=fmp&kind=market"
```

Expected response shape:

```json
{
  "provider": "fmp",
  "kind": "market",
  "snapshot": {
    "symbol": "AAPL",
    "snapshot_ts": "…",
    "price": …,
    "volume": …,
    "day_change_pct": …,
    "source": "fmp"
  }
}
```

## Step 4 — verify gracefully disabled state

With no key set:

```bash
curl -H "Authorization: Bearer wvk_xxx" \
  "http://127.0.0.1:8000/v1/data/snapshot/AAPL?provider=fmp&kind=market"
# -> 503 {"detail": {"error": "provider_unavailable", "provider": "fmp", "reason": "…"}}
```

## Security

* The API key sits in process env only, never logged, never persisted.
* No FMP secret ever crosses the trust boundary into the public repo or PRs.
* Rate-limit caps for paid plans are enforced by `wavervanir_api/rate_limit.py`
  independently of FMP's own limits.

## Limitations

* FMP is **not** an options-flow provider. `kind=flow` returns 503 with
  `provider_unavailable` and a hint to use `bullflow`.
* The adapter is intentionally minimal — single-quote per call, no batch
  endpoint, no historical bars. Add only when product needs them.
