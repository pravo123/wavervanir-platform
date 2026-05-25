# Handoff Checklist

Use this before sending the project to Ankit.

## Operator Pre-Send

- [ ] Current branch is the handoff branch.
- [ ] `main` is merged and current.
- [ ] `npm run test` passes in `landing/`.
- [ ] `npm run build` passes in `landing/`.
- [ ] `pytest -q` passes in `api/`.
- [ ] Built landing exists at `landing/dist/`.
- [ ] Logo exists at `landing/public/brand/wavervanir-logo.png`.
- [ ] No real `.env` files are included.
- [ ] No SQLite/database files are included.
- [ ] No `node_modules/` is included.
- [ ] No `.venv/` is included.
- [ ] No live secrets are present.
- [ ] No private VolanX code is present.
- [ ] Handoff zip exists at `_handoff/wavervanir-platform-handoff.zip`.

## Package Build

Windows:

```powershell
tools\build_handoff.ps1
```

Unix shell:

```bash
tools/build_handoff.sh
```

The scripts build the landing app, scan for risky strings, stage the safe
handoff directory, and zip it.

## Ankit Post-Receive

- [ ] Extract the zip into a clean directory.
- [ ] Open `docs/ANKIT_HANDOFF.md`.
- [ ] Open `docs/ANKIT_START_HERE.md`.
- [ ] Open `landing/dist/index.html` or serve `landing/dist/`.
- [ ] Confirm logo renders.
- [ ] Confirm demo dashboard renders.
- [ ] Confirm mobile layout has no horizontal scroll.
- [ ] Decide static drop-in vs component port.
- [ ] Decide waitlist lead sink with operator.
- [ ] Stage on preview URL.
- [ ] Get operator sign-off before production.

## What Not To Send Separately

- Live Stripe keys.
- Live FMP keys.
- Bullflow credentials.
- Tastyworks/Tastytrade credentials.
- Private VolanX repo access.
- Brokerage account numbers.
- Screenshots with account numbers.

## Operator Sign-Off

```text
Package built:
Package scanned:
Package sent:
Preview URL:
Operator approval:
Production URL:
```
