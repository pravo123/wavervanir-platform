# Ankit — start here

Welcome. This is the front door for collaborating on `pravo123/wavervanir-platform`.

Read this doc first. It links the two others you'll need:

- **`docs/CONTRIBUTOR_WORKFLOW.md`** — branch / commit / PR rules.
- **`docs/PROJECT_BOUNDARIES.md`** — what you can and cannot touch.

If anything below is unclear, ask Prabhawa before touching code.

---

## 1. What this project is

WaverVanir Platform = the public SaaS surface for WaverVanir International. Two parts:

| Dir | Purpose | Public? |
|---|---|---|
| `api/` | FastAPI service `wavervanir-api` — authenticated, rate-limited, audit-chained wrapper over the public `cbsrm` package. | yes |
| `landing/` | Vite + React static site (the future `risk.wavervanir.com`) — hero, demo dashboard, pricing, waitlist. | yes |
| `docs/` | All architecture + boundary + onboarding docs. | yes |
| `.github/workflows/` | CI — runs `pytest` for API and `vitest` + `vite build` for landing on every PR. | yes |

There is also a **private** repo (`pravo123/volanx`) that holds proprietary trading logic. That repo is OFF-LIMITS to this project; this repo must never import or reference it. The boundary is enforced by an AST guard test (`api/tests/test_no_private_imports.py`).

## 2. What's already shipped on `main`

- PR #2 — landing + API scaffold (hero, pricing, waitlist, health endpoint, CBSRM macro-composite route).
- PR #3 — provider-ready data ingestion: `demo`, `fmp`, `bullflow`, `broker_snapshot`.
- PR #4 — demo Risk Intelligence Dashboard on the landing page (fixture-only, no backend dependency).

Open `https://github.com/pravo123/wavervanir-platform` for the merged history.

## 3. Clone + local setup

You'll need:

- **Git**, **Python 3.11 or 3.12**, **Node 20+**, **npm 10+**.

```bash
git clone https://github.com/pravo123/wavervanir-platform.git
cd wavervanir-platform
```

### 3a. API (FastAPI)

```bash
cd api
python -m venv .venv
.venv/Scripts/activate              # Windows  (or:  source .venv/bin/activate  on macOS/Linux)
pip install --upgrade pip
pip install -e .

cp .env.example .env                # then edit — keep secrets OUT of git

# Run tests
.venv/Scripts/python -m pytest -q

# Run locally
.venv/Scripts/python -m uvicorn wavervanir_api.app:create_app --factory --reload
# → http://127.0.0.1:8000
# → http://127.0.0.1:8000/docs        (FastAPI Swagger)
# → http://127.0.0.1:8000/health      (200 + JSON)
```

To exercise an authenticated endpoint locally, mint a paid key:

```bash
.venv/Scripts/python -m wavervanir_api.tools.bootstrap_key --plan researcher --label "ankit-local"
# → prints wvk_… exactly once. Use as Bearer token.
```

### 3b. Landing (Vite + React)

```bash
cd ../landing
npm ci

# Run tests
npm run test

# Run dev server
npm run dev
# → http://127.0.0.1:5173

# Or build + preview the production bundle
npm run build
npm run preview
```

The current landing renders:

- Brand-fixed Nav + Hero (logo + tagline already wired).
- **Demo Risk Intelligence Dashboard** (`#demo` section) — provider tiles, market grid, flow signals, sanitized portfolio preview, in-browser report.
- Pricing tiles (Researcher / Pro / Institutional / Regulator).
- Institutional waitlist form.

The dashboard is **fixture-only** today. The fixture data lives at `landing/src/data/demoRisk.ts` and mirrors the live API response shapes — so when a future slice wires it to real `/v1/data/*` fetches, only the data source changes, not the components.

## 4. What you can safely work on

A short list of slices that are explicitly yours to pick up:

1. **Landing UI polish** — typography, spacing, dark-theme refinements, copy tightening, accessibility (alt text, contrast, focus rings).
2. **Website integration** — port `landing/dist` content into `wavervanir.com` (or recreate the same React components there). Preserve the logo + tagline + disclaimer copy.
3. **Demo dashboard UX** — better empty states, better tablet/mobile layout, hover tooltips on metric tiles, micro-animations.
4. **Docs** — clarity edits, README polish, screenshots for `docs/DEMO_DASHBOARD.md`, fixing any broken links.
5. **Handoff package** — the old `docs/ANKIT_HANDOFF.md` / `docs/LOCAL_DEMO.md` / `tools/build_handoff.*` are currently *untracked* drafts. If you want to revive them, raise a PR that revises them and adds tests where appropriate.
6. **Cloudflare Pages prep** — the deploy is operator-driven (`docs/DEPLOY.md` + `docs/STAGING_VERIFICATION.md`), but you can prepare any landing-side build settings, robots/_redirects refinements, or pre-deploy checklists.

## 5. What you must NOT touch

Read `docs/PROJECT_BOUNDARIES.md` for the authoritative list. Headlines:

- No private VolanX modules. No `VOLANX.*`, `volanx.*` imports anywhere.
- No broker SDKs: `tastytrade`, `tastyworks`, `ib_insync`, `ibapi`, `alpaca_trade_api`.
- No live Stripe secrets (`sk_live_…`, `whsec_live_…`). Test mode only.
- No live data credentials (`FMP_API_KEY`, `BULLFLOW_API_KEY`, `TASTYTRADE_*`).
- No claims of live trading / guaranteed returns / trading bots / live execution copy.
- No CBSRM internals unless Prabhawa explicitly assigns it.
- No deploys. No DNS. No tags. No public posts.

The AST guard test and the secret scanner will reject pushes that violate any of the above.

## 6. Your first PR

Pick the smallest slice you're confident in, then follow `docs/CONTRIBUTOR_WORKFLOW.md`. The PR template (`.github/PULL_REQUEST_TEMPLATE.md`) will appear automatically on GitHub when you open the PR — fill it in honestly.

## 7. How to ask for help

- Open a **GitHub issue** with the `task` template for anything that needs scoping before code.
- Mention `@Prabhawa` (operator GitHub handle) on PRs and issues — that's the review path.
- Don't push to `main` directly. Always work on a feature branch and open a PR.
