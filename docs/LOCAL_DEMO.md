# Local Demo

This guide runs the WaverVanir platform locally with no paid services.

## Requirements

- Python 3.11 or 3.12
- Node.js 20+
- Git

## Landing Demo

```bash
cd landing
npm ci
npm run dev
```

Open the Vite URL, usually:

```text
http://127.0.0.1:5173/
```

or:

```text
http://127.0.0.1:5174/
```

You should see:

- WaverVanir logo.
- Hero section.
- Demo Risk Intelligence Dashboard.
- Data-provider tiles.
- Market snapshots.
- Flow/risk preview.
- Sanitized portfolio summary.
- Demo report toggle.
- Pricing.
- Waitlist.

## Landing Tests

```bash
cd landing
npm run test
npm run build
```

Expected at the time of handoff:

```text
15/15 landing tests pass
build clean
```

## API Demo

```bash
cd api
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pytest -q
uvicorn wavervanir_api.app:create_app --factory --reload --port 8000
```

macOS/Linux:

```bash
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pytest -q
uvicorn wavervanir_api.app:create_app --factory --reload --port 8000
```

Expected at the time of handoff:

```text
92/92 API tests pass
```

## API Smoke Checks

```bash
curl -s http://127.0.0.1:8000/health
```

Expected:

```json
{"status":"ok","service":"wavervanir-api","version":"0.1.0"}
```

Unauthenticated protected endpoints should return `401`.

## Provider Routes

These routes require bearer auth:

```text
GET  /v1/data/providers
GET  /v1/data/snapshot/{symbol}?provider=demo&kind=market
GET  /v1/data/snapshot/{symbol}?provider=demo&kind=flow
POST /v1/data/broker-snapshot/validate
POST /v1/data/broker-snapshot/risk-summary
```

Use `demo` first. FMP and Bullflow self-disable until configured.

## Sanitized Broker Snapshot

The upload-only broker snapshot route is for sanitized JSON. It must never
contain:

- Account numbers.
- Customer IDs.
- OAuth tokens.
- Refresh tokens.
- Passwords or PINs.
- Tax IDs.
- Routing numbers.
- Card numbers.
- Stripe key-shaped values.

See `docs/TASTYWORKS_SNAPSHOT_SCHEMA.md`.

## No Live Claims

The local demo is a product preview. It is not a live trading system and does
not place orders.
