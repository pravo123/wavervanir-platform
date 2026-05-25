# Tastyworks/Tastytrade snapshot schema (sanitized)

This document defines the **only** shape of broker-derived data that may
enter the public `wavervanir-platform` service.

The hard rules:

* **No Tastytrade/Tastyworks SDK call ever runs in this repo.**
* Brokers stay in your **private** workflow.
* Your private workflow exports a sanitized JSON (or CSV) file.
* The platform accepts that file via
  `POST /v1/data/broker-snapshot/{validate,risk-summary}`.

If a payload includes anything that looks like an account number, OAuth
token, refresh token, password, SSN, or other obvious credential shape,
the validator rejects it (HTTP 422). Sanitize upstream, then retry.

## JSON schema (v1.0)

```json
{
  "schema_version": "1.0",
  "snapshot_ts": "2026-05-24T18:00:00Z",
  "account_alias": "paper-main",
  "base_currency": "USD",
  "positions": [
    {
      "symbol": "AAPL",
      "asset_class": "equity",
      "quantity": 100,
      "mark_price": 195.50,
      "market_value": 19550.0,
      "unrealized_pnl": 312.5
    },
    {
      "symbol": "NVDA  240621C00800000",
      "asset_class": "option",
      "quantity": 2,
      "mark_price": 13.5,
      "market_value": 2700.0,
      "unrealized_pnl": 120.0
    }
  ]
}
```

### Field reference

| Field             | Type              | Notes                                                    |
|-------------------|-------------------|----------------------------------------------------------|
| `schema_version`  | literal `"1.0"`   | Bump only with coordinated server update.                |
| `snapshot_ts`     | ISO-8601 UTC      | Time the broker snapshot was captured.                   |
| `account_alias`   | string ≤ 64       | **Non-identifying label.** Never the real account number.|
| `base_currency`   | string (default USD) | ISO-4217 code.                                        |
| `positions[]`     | array             | Position rows. May be empty.                             |
| `positions[].symbol` | string ≤ 32    | Free-form symbol. OCC option string is fine.             |
| `positions[].asset_class` | enum    | equity, option, future, etf, crypto, fx, other.          |
| `positions[].quantity` | signed float | + = long, − = short.                                     |
| `positions[].mark_price` | ≥ 0      | Per-unit fair price.                                     |
| `positions[].market_value` | signed | Sign matches `quantity`. Currency = `base_currency`.    |
| `positions[].unrealized_pnl` | float | Currency = `base_currency`. Default 0.                  |

## Forbidden fields (rejected by the validator)

Any payload containing a leaf key matching ONE of these regexes is rejected:

```
account[_-]?number       account[_-]?id        ^cus_
^acc_                    customer[_-]?id       oauth[_-]?token
refresh[_-]?token        access[_-]?token      bearer[_-]?token
^password$               ^pwd$                 ^pin$
^ssn$                    tax[_-]?id            routing[_-]?number
sort[_-]?code            \bcvv\b               card[_-]?number
```

## Forbidden value shapes (rejected by the validator)

Any string leaf matching ONE of these regexes is rejected:

```
^sk_(test|live)_[A-Za-z0-9]{8,}$            # Stripe secret keys
^whsec_[A-Za-z0-9]{8,}$                     # Stripe webhook secrets
\beyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{10,}\b   # JWT
^[0-9]{8,12}$                               # bare numeric (account-number shape)
```

If a perfectly legitimate field of yours trips one of these rules, rename
it upstream. The validator's job is to fail loud.

## Producing the sanitized file (operator-side)

Run this in your private workflow — **NOT** in this repo:

```python
# Pseudocode — runs in the private trading repo, not here.
from your_private_broker_client import fetch_positions

def sanitize(account_id: str) -> dict:
    rows = fetch_positions(account_id)   # private
    return {
        "schema_version": "1.0",
        "snapshot_ts": datetime.now(timezone.utc).isoformat(),
        "account_alias": "live-cash-a",   # NOT the real account_id
        "base_currency": "USD",
        "positions": [
            {
                "symbol": r["symbol"],
                "asset_class": r["asset_class"],
                "quantity": r["qty"],
                "mark_price": r["mark"],
                "market_value": r["qty"] * r["mark"] * r["multiplier"],
                "unrealized_pnl": r["upnl"],
            }
            for r in rows
        ],
    }
```

Upload that JSON to the platform.

## Upload examples

```bash
# Validate only
curl -X POST -H "Authorization: Bearer wvk_xxx" \
     -H "Content-Type: application/json" \
     -d @sanitized.json \
     http://127.0.0.1:8000/v1/data/broker-snapshot/validate

# Validate + aggregate
curl -X POST -H "Authorization: Bearer wvk_xxx" \
     -H "Content-Type: application/json" \
     -d @sanitized.json \
     http://127.0.0.1:8000/v1/data/broker-snapshot/risk-summary
```

`risk-summary` response shape:

```json
{
  "schema_version": "1.0",
  "snapshot_ts": "…",
  "account_alias": "paper-main",
  "base_currency": "USD",
  "n_positions": 5,
  "total_gross_exposure_usd": 52334.0,
  "total_long_exposure_usd": 42134.0,
  "total_short_exposure_usd": 10200.0,
  "total_unrealized_pnl_usd": 343.5,
  "largest_position_pct_of_gross": 0.3736,
  "concentration_top5_pct_of_gross": 1.0,
  "by_asset_class": [
    { "asset_class": "crypto", "gross_exposure_usd": 3400.0,  "net_exposure_usd": 3400.0,  "n_positions": 1 },
    { "asset_class": "equity", "gross_exposure_usd": 36034.0, "net_exposure_usd": 36034.0, "n_positions": 2 },
    { "asset_class": "etf",    "gross_exposure_usd": 10200.0, "net_exposure_usd": -10200.0, "n_positions": 1 },
    { "asset_class": "option", "gross_exposure_usd": 2700.0,  "net_exposure_usd": 2700.0,  "n_positions": 1 }
  ]
}
```

## What this surface is NOT

* Not an execution path. There is no order-routing here.
* Not a position-history store. Every call is stateless — the platform
  validates and aggregates the supplied snapshot and returns. Nothing
  is persisted beyond the standard audit row (request hash, response
  hash, status, latency).
* Not a substitute for your private broker reconciliation. Truth still
  lives in the private workflow.
