# wavervanir-landing

Vite + React static marketing site for the WaverVanir Risk Intelligence Platform.

## Quick start

```bash
cd landing
npm install
npm run dev      # http://127.0.0.1:5174
npm run test     # vitest component tests
npm run build    # production bundle in dist/
```

## Brand assets

Drop the logo at:

```
landing/public/brand/wavervanir-logo.png
```

The Nav and Hero components reference exactly that path. Alt text is fixed to
`WaverVanir — Process Over Prediction` and asserted in `tests/brand.test.tsx`.

## Theme

Dark theme (`#000` background) so the gold + blue logo marks remain legible.
Responsive sizing: 40px in nav, 220px / 60vw in hero.

## Demo dashboard

The landing app includes a fixture-only Risk Intelligence dashboard:

- Provider status tiles for demo, FMP, Bullflow, and broker snapshot.
- Market snapshot cards.
- Flow/risk intelligence preview.
- Sanitized portfolio summary.
- Demo report toggle.

No commercial data is required. The dashboard is intentionally fixture-backed
until a hosted API URL and provider credentials exist.

## API integration

The waitlist form posts to `/v1/waitlist` of the same origin. In dev, point the API at
`http://127.0.0.1:8000` and proxy via Vite, or run the API behind the same reverse proxy.

Provider tiles are currently fixture-backed. Future work can wire them to
`GET /v1/data/providers` when `VITE_WAVERVANIR_API_URL` or equivalent host-app
configuration is available.
