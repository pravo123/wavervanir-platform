# WaverVanir Platform

Hosted SaaS surface for **WaverVanir International**'s public risk-intelligence stack.

This repo contains:

| Dir | Purpose |
| --- | --- |
| `api/` | FastAPI service (`wavervanir-api`) — authenticated, rate-limited, audit-chained wrappers over the public **CBSRM** (`cbsrm`) library. |
| `landing/` | Vite + React static marketing site (`risk.wavervanir.com`) — methodology section, pricing, waitlist form. |
| `docs/` | Architecture and public/private boundary documentation. |
| `.github/workflows/` | CI placeholders (lint + test) — no deploy automation in MVP. |

## Mission

Convert WaverVanir's public credibility (CBSRM v0.9.0, derivatives-risk-framework v0.1.0) into a hosted research API
with a clean waitlist funnel into higher-tier institutional offerings.

## Public / private boundary

This repo is **public**. It is allowed to import the public `cbsrm` package only. It is **never** permitted to
import any internal VolanX module, mirror any VolanX UI surface, or reference internal strategy names.

See `docs/PRIVACY_BOUNDARY.md` for the enforced ruleset. An AST-based unit test fails CI if any forbidden import
becomes reachable.

## Status

MVP scaffold — not yet deployed. No production secrets in repo. Stripe wired in test mode only.

## Pricing tiers (test mode)

| plan | price (test) | daily calls | self-serve |
| --- | --- | --- | --- |
| Researcher | $49/mo | 5,000 | Stripe Payment Link |
| Pro | $499/mo | 15,000 | Stripe Payment Link |
| Institutional | from $4,999/mo | 50,000+ | sales-assisted |
| Regulator / Central Bank | bespoke | configurable | sales-assisted |

See `docs/STRIPE_SETUP.md` for the end-to-end test-mode wiring.
See `docs/DEPLOY.md` for the planned hosting targets (Render + Cloudflare Pages).

## License

Apache-2.0. See `LICENSE`.
