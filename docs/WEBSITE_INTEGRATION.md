# Website Integration

This guide explains how to merge the WaverVanir Risk Intelligence Platform into
the existing WaverVanir website without buying hosting or commercial data.

## Recommended v1

Ship the demo platform as a static preview first:

```text
https://www.wavervanir.com/risk-preview/
```

After review, promote it to:

```text
https://www.wavervanir.com/risk/
```

Keep `volanx.wavervanir.com` as a future product subdomain if the operator
chooses to split the product surface later.

## Option A - Drop In `landing/dist/`

Use this when the existing site can host static files.

1. Build:

   ```bash
   cd landing
   npm ci
   npm run build
   ```

2. Copy the full `landing/dist/` directory into the website under a preview
   path.

3. Confirm these files are served:

   ```text
   index.html
   assets/index-<hash>.js
   assets/index-<hash>.css
   brand/wavervanir-logo.png
   robots.txt
   _redirects
   ```

4. Link the existing WaverVanir site to the preview path.

5. Do not wire paid Stripe links or paid data until the operator provides
   explicit values.

## Option B - Port React Components

Use this when the existing website is React, Next.js, Astro, Remix, or another
component-based app.

Port these components:

- `landing/src/components/Nav.tsx`
- `landing/src/components/Hero.tsx`
- `landing/src/components/DataProviderStatus.tsx`
- `landing/src/components/MarketSnapshotGrid.tsx`
- `landing/src/components/RiskIntelligencePreview.tsx`
- `landing/src/components/PortfolioRiskPreview.tsx`
- `landing/src/components/DemoReportPreview.tsx`
- `landing/src/components/Pricing.tsx`
- `landing/src/components/PricingCta.tsx`
- `landing/src/components/Waitlist.tsx`
- `landing/src/data/demoRisk.ts`
- `landing/src/styles.css`

Copy the logo:

```text
landing/public/brand/wavervanir-logo.png
```

Serve it at:

```text
/brand/wavervanir-logo.png
```

If the existing app is Next.js, adapt `import.meta.env` usage in
`PricingCta.tsx` to the host app's public env convention.

## Waitlist Handling

The current form posts to `/v1/waitlist`. If the API is not hosted yet, use one
of these:

- Existing website lead-capture endpoint.
- Formspree or equivalent form endpoint.
- A temporary `mailto:` or contact flow.
- Keep the form disabled on preview until the operator chooses the sink.

Do not create a new paid service without operator approval.

## Data Handling

The demo dashboard uses fixture data. That is intentional.

For now:

- No commercial market data is required.
- No Polygon integration is required.
- No Tastyworks/Tastytrade SDK is used.
- Broker data may only enter through sanitized upload snapshots.
- FMP and Bullflow are provider-ready but disabled until credentials or local
  files are configured.

## Copy Guardrails

Use:

- Risk intelligence.
- Audit-ready reporting.
- Cross-border systemic-risk monitoring.
- Provider-ready integrations.
- Fixture-data demo.
- Public methodology.
- Process over prediction.

Avoid:

- Trading bot.
- Auto-trader.
- Live execution.
- Broker integration.
- Order routing.
- Guaranteed returns.
- Fund or hedge-fund claims.
- Private subsystem names.
- Real P&L or strategy performance claims.

## Preview Checklist

Before publishing any public URL:

- [ ] Logo renders.
- [ ] Demo dashboard renders.
- [ ] Provider tiles render.
- [ ] Market cards render.
- [ ] Flow cards render.
- [ ] Portfolio summary renders.
- [ ] Demo report toggle works.
- [ ] Pricing tiles render.
- [ ] Waitlist behavior is intentional.
- [ ] Mobile viewport has no horizontal overflow.
- [ ] No console errors.
- [ ] No secrets in built assets.
- [ ] Operator signs off on copy.

## Final Handoff Rule

Preview first. Production only after operator sign-off.
