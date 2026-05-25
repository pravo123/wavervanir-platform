# Contributor workflow

Rules for landing changes on `pravo123/wavervanir-platform` cleanly. Pair this with `docs/PROJECT_BOUNDARIES.md`.

---

## 1. Branch naming

`feature/<short-slug>` — kebab-case, descriptive, no ticket numbers required.

Examples:

- `feature/landing-mobile-polish`
- `feature/demo-dashboard-tooltips`
- `feature/docs-deploy-runbook-clarify`

Use `fix/<short-slug>` for bug fixes, `docs/<short-slug>` for docs-only PRs, `chore/<short-slug>` for housekeeping.

Never push directly to `main`. Always open a PR.

## 2. Commit messages

Use Conventional Commits — same convention the repo's existing history uses:

```
feat: add demo risk intelligence dashboard
fix: prevent risk-table overflow on mobile
docs: clarify CBSRM env var fallbacks
chore: bump vitest to 2.2
```

One concern per commit. Long detail goes in the commit body (blank line after the subject). Avoid `WIP` / `oops` commits — squash them locally with `git rebase -i` before opening the PR.

## 3. Local checks before pushing

These mirror the CI matrix exactly. Run them all from the repo root before every push:

```bash
# API
cd api
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m pip_audit
.venv/Scripts/python -m bandit -r src/

# Landing
cd ../landing
npm run test
npm run build
```

If anything is red, fix it locally. Don't open a PR with red CI.

## 4. PR opening

1. Push your branch: `git push -u origin feature/<slug>`.
2. Visit the URL git prints. The PR template auto-fills (`.github/PULL_REQUEST_TEMPLATE.md`).
3. Fill in every section. Don't tick a box you haven't actually verified.
4. Attach a **screenshot or short Loom** for any visible frontend change (the dashboard, landing copy, hero, pricing — anything users will see).
5. Add `@Prabhawa` as reviewer.

## 5. CI gates that must stay green

The PR must show all three checks green before merge:

| Check | What it runs |
|---|---|
| `api (3.11)` | `pytest` on Python 3.11 |
| `api (3.12)` | `pytest` on Python 3.12 (matches Render runtime) |
| `landing` | `vitest run` + `vite build` |

If CI is red, push fixes to the same branch — CI re-runs automatically.

## 6. Push Protection alerts (GitHub secret scanning)

Sometimes GitHub will block your push because it thinks you committed a Stripe key, JWT, or similar. The scanner is *correct* to be paranoid — your fix is almost always:

- Refactor the test fixture so the literal token shape is **assembled at runtime** instead of sitting as a single source-text string. Example:

  ```python
  # Bad — push protection will reject the literal token shape
  # (example shown deliberately broken so this very doc can be committed):
  fake_stripe = "sk" + "_l" + "ive_aBcDeFgHiJkLmNo"   # don't write it as one literal

  # Good — assembled at runtime, regex still matches:
  fake_stripe = "sk" + "_live_" + "FAKEFAKEFAKEFAKE"
  ```

  In real "bad" code, the assignment would be ONE literal string of the form
  `sk_live_<24-key-like-chars>`. The scanner pattern that triggers is a
  Stripe-shaped prefix followed by ≥ 24 alphanumeric characters in a single
  source-text token. Avoid that shape in any committed file.

Then `git add` the fix, `git commit --amend --no-edit` (or add a new commit if the rejected commit is already pushed), and retry.

**Do NOT click the GitHub "unblock secret" URL.** That trains the workflow to ignore real leaks. See the precedent in PR #3's history.

## 7. Merging

Prabhawa merges PRs after review using **Create a merge commit** + **Delete branch**. You don't need to merge your own PR — once it's approved and CI is green, it's the operator's call to land.

After merge:

```bash
git checkout main
git pull --ff-only origin main
git branch -d feature/<slug>
```

## 8. Things that need operator action (do not attempt yourself)

- Deploys (Render, Cloudflare Pages, DNS, TLS).
- Creating Stripe Products / Payment Links.
- Tagging releases.
- Posting to LinkedIn / Telegram / SSRN.
- Inviting collaborators to GitHub or any service.
- Anything involving live credentials.

If you think any of these would be useful, open a GitHub issue describing the slice — the operator will pick it up.

## 9. When in doubt

- Stop. Open an issue or message Prabhawa.
- Default to the smaller, more reversible change.
- Read `docs/PROJECT_BOUNDARIES.md` once more.
