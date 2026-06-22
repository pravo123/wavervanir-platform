# Cloudflare Pages — landing deploy settings

Exact dashboard settings for hosting the `landing/` Vite app on Cloudflare
Pages. Companion to `render.yaml` (API) and `DEPLOY_QUICKSTART.md`.

## Create the project

Cloudflare dashboard > **Workers & Pages** > **Create** > **Pages** >
**Connect to Git** > pick the `wavervanir-platform` repo.

## Build & deploy settings

| Field | Value |
| --- | --- |
| Project name | `wavervanir-platform` |
| Production branch | `cbsrm-golive` (or `main` once merged) |
| Framework preset | Vite |
| **Project root (root directory)** | repo root (leave blank / `/`) |
| **Build command** | `cd landing && npm ci && npm run build` |
| **Build output directory** | `landing/dist` |
| **Node version** | `20` |

> The build command `cd`'s into `landing/` itself, so the project root stays
> at the repo root. Do NOT also set the root directory to `landing` — that
> would double the path and the build fails.

### Pin Node 20

Cloudflare honors the `NODE_VERSION` build env var. Set it explicitly so
builds are reproducible:

| Build environment variable | Value |
| --- | --- |
| `NODE_VERSION` | `20` |

(Alternatively commit a `.nvmrc` / `.node-version` at repo root containing `20`.)

## VITE_* environment variables (Settings > Environment variables > Production)

These are **public** — Vite inlines them into the shipped JS bundle. Only put
values safe to publish (Stripe Payment Link URLs, public origins, anchors).
NEVER put `sk_*`, `whsec_*`, `cus_*`, bearer tokens, or `WAVERVANIR_*` secrets
in a `VITE_*` slot.

| Key | Value | Note |
| --- | --- | --- |
| `VITE_STRIPE_LINK_RESEARCHER` | `https://buy.stripe.com/test_...` | test-mode Payment Link; leave blank to fall back to `#waitlist` |
| `VITE_STRIPE_LINK_PRO` | `https://buy.stripe.com/test_...` | same fallback when blank |
| `VITE_INSTITUTIONAL_HREF` | `#waitlist` | where institutional/regulator CTAs route |
| `VITE_WAVERVANIR_API_URL` | leave blank (see below) | only needed if the dashboard calls the API cross-origin instead of via the same-origin proxy |

> Recommended: leave `VITE_WAVERVANIR_API_URL` **blank** and rely on the
> same-origin `_redirects` proxy below. A blank value makes the dashboard
> tiles fetch relative `/v1/...` paths, which the proxy forwards to Render —
> so the browser only ever sees one origin and there is no CORS to configure.

## Same-origin proxy — `landing/public/_redirects`

The file `landing/public/_redirects` forwards `/v1/*`, `/onboard`,
`/stripe/*`, and `/health` from the Pages host to the Render API, so the
browser sees a single origin (no CORS). It ships in `landing/dist`
automatically — no build config needed.

**It currently proxies to `https://wavervanir-api.onrender.com`.** When you
wire the custom `api.wavervanir.com` domain (see `DEPLOY_QUICKSTART.md` step 3),
make this **one-line change per rule** — swap the destination host from the
`onrender.com` URL to the custom domain. After the change the file reads:

```
/v1/*       https://api.wavervanir.com/v1/:splat      200
/onboard    https://api.wavervanir.com/onboard        200
/stripe/*   https://api.wavervanir.com/stripe/:splat  200
/health     https://api.wavervanir.com/health         200
```

Commit the edit; Cloudflare Pages redeploys on push and the new destination
takes effect. (Until you do, the `onrender.com` destination keeps working, so
this can wait until the custom API domain has valid TLS.)

## iframe / same-origin tradeoff

The `_redirects` proxy (HTTP 200 rewrite) is the right call here, and it has a
real security benefit over the alternatives:

- **Same-origin proxy (chosen):** the API responds as if it were served from
  the Pages origin. No CORS headers needed; cookies/credentials (if ever
  added) stay first-party; CSP can stay strict (`default-src 'self'`). The
  cost is that all API traffic transits Cloudflare's edge to Render — one
  extra hop, negligible for this workload.
- **Direct cross-origin fetch** (`VITE_WAVERVANIR_API_URL` pointing straight
  at Render): one less hop, but you must enable CORS on the API and the
  browser sees two origins.
- **iframe-embedding the API/docs:** AVOID. Cross-origin iframes break
  same-origin assumptions, complicate CSP (`frame-src`/`frame-ancestors`),
  and offer no benefit for a JSON API. Keep the API consumed via `fetch`
  through the proxy, not framed.

Bottom line: keep `VITE_WAVERVANIR_API_URL` blank, let `_redirects` do the
proxying, and do not embed the API in an iframe.

## Custom domain

In Cloudflare Pages > the project > **Custom domains** > add
`risk.wavervanir.com`. Cloudflare provisions managed TLS automatically. The
DNS record itself is added at the DNS host (Bluehost) — see
`DEPLOY_QUICKSTART.md` step 3.
