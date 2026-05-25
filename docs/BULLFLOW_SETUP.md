# Bullflow setup

Wire Bullflow-style options-flow data as the `bullflow` provider.

The adapter supports **two** modes, picked in this order:

1. **File mode** — set `BULLFLOW_DATA_FILE` to a local JSON or CSV path.
2. **API mode** — set `BULLFLOW_API_KEY` and the adapter calls the API.

If both are set, file mode wins. If neither is set the provider self-disables.

## File mode (recommended for local dev / no-cost smoke)

Use file mode whenever you want to demo, test, or develop without paying
for or hammering the live API.

### Format (JSON)

`landing/whatever.json`:

```json
{
  "rows": [
    {
      "symbol": "AAPL",
      "snapshot_ts": "2026-05-24T18:00:00Z",
      "call_premium_usd": 12500000.0,
      "put_premium_usd": 4800000.0,
      "smart_money_ratio": 0.62,
      "n_trades": 412
    }
  ]
}
```

A bare list `[{…}, {…}]` is also accepted.

### Format (CSV)

```csv
symbol,snapshot_ts,call_premium_usd,put_premium_usd,smart_money_ratio,n_trades
AAPL,2026-05-24T18:00:00Z,12500000,4800000,0.62,412
NVDA,2026-05-24T18:00:00Z,38000000,22000000,0.71,1108
```

### Activate

```dotenv
BULLFLOW_DATA_FILE=/absolute/path/to/your_bullflow.json
```

Then:

```bash
curl -H "Authorization: Bearer wvk_xxx" \
  "http://127.0.0.1:8000/v1/data/snapshot/AAPL?provider=bullflow&kind=flow"
```

The response will carry `"source": "bullflow_file"`.

## API mode

```dotenv
BULLFLOW_API_KEY=YOUR_KEY_HERE
```

The adapter uses an injectable httpx-like client. Tests never hit the
network. The default base URL is `https://api.bullflow.example/v1` — adjust
in `wavervanir_api/providers/bullflow.py` to your provider's real base when
you wire a real account.

## Verify gracefully disabled state

With neither env set:

```bash
curl -H "Authorization: Bearer wvk_xxx" \
  "http://127.0.0.1:8000/v1/data/snapshot/SPY?provider=bullflow&kind=flow"
# -> 503 provider_unavailable
```

## Security

* Both keys and file paths sit in process env only.
* Files are read at request time — they are never copied into the request
  body or returned in responses.
* The adapter does NOT modify the source file.

## Limitations

* Bullflow is flow-only. `kind=market` returns 503 with a hint to use
  `fmp` or `demo`.
* File mode is point-in-time: it returns whatever row matches `symbol`.
  Add timestamp filtering only when product needs it.
