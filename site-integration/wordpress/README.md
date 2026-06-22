# CBSRM / AI model-risk governance — WordPress integration kit

Paste-ready assets to publish a CBSRM / AI model-risk governance section on **wavervanir.com**.

**Target stack:** WordPress 6.9.4 + Astra theme + Elementor Pro 3.33.4.
There is no React/Next source to edit — content goes live through an Elementor **HTML** widget.

## Files in this kit

| File | What it is |
|------|------------|
| `cbsrm-governance-page.html` | The full governance section. One self-contained HTML fragment (inline `<style>` + `<script>`, zero external dependencies, all CSS scoped under `.wv-cbsrm`). Paste this into an Elementor HTML widget. |
| `cbsrm-demo-embed.html` | A small responsive iframe snippet to embed the hosted CBSRM demo **after** `risk.wavervanir.com` is live. Optional. |
| `README.md` | This file. |

---

## 1. Publish the governance page (primary path)

1. **Create the page.** WordPress admin → **Pages → Add New**.
   - Title: `Model risk governance` (or `CBSRM`).
   - Suggested slug: **`/risk-governance/`** (alt: **`/cbsrm/`**). Set it under the Page settings / permalink.
2. **Open Elementor.** Click **Edit with Elementor**.
3. **Add a full-width section** so the hero bleeds edge to edge:
   - Drag a new Section, set its **Content Width → Full Width** and **Column/Section padding → 0** (the fragment manages its own internal spacing).
4. **Drop an HTML widget.** From the widget panel search **HTML**, drag the **HTML** widget into the column.
5. **Paste the fragment.** Open `cbsrm-governance-page.html`, copy the **entire** file contents, and paste into the HTML widget's code box.
6. **Preview first (do not publish straight to live).**
   - Click the up-arrow next to **Publish/Update** → **Save Draft**, or set the page to **Draft** in WordPress.
   - Use Elementor **Preview** and the responsive toggle (desktop / tablet / mobile, check ~360px) to review.
   - Confirm: hero renders dark, the four lens cards expand on click, the self-check computes a score, and both CTA buttons point to the right URLs.
7. **Go live.** When it looks right, set the page to **Published** and **Update**.

### Notes on the fragment
- It is **theme-safe**: every style is scoped under `.wv-cbsrm`, so it cannot leak into or be overridden by Astra/Elementor globals, and it sets its own background and colors.
- It is **offline-safe**: no external CSS/JS/fonts/CDN. Nothing to allow-list, nothing that breaks if a CDN is down.
- The **"Explore the platform"** button points to `https://risk.wavervanir.com`, which is **pending DNS**. Until that subdomain resolves, either leave it (it will simply fail to load when clicked) or edit the two `href="https://risk.wavervanir.com"` occurrences in the fragment (search the file; both are flagged with a comment) to point elsewhere or remove the button.
- The **"Book a readiness audit"** button points to `https://wavervanir.com/consultation/` — confirm that page exists, or repoint it.

---

## 2. Add a primary-nav menu item ("Governance")

Pick whichever matches how the site's header is built:

**A. Classic WordPress menu (Astra default):**
1. **Appearance → Menus**.
2. Select the **Primary / Main** menu.
3. Left panel → **Pages** → check the new governance page → **Add to Menu** (or add a **Custom Link** to `/risk-governance/` with label **Governance**).
4. Drag it to the desired position → **Save Menu**.

**B. Elementor header template (if the header is a Theme Builder template):**
1. **Templates → Theme Builder → Header** → edit the active header.
2. Select the **Nav Menu / WordPress Menu** widget. If it renders a WP menu, edit that menu as in option A. If it's an Elementor Nav Menu, add the item in its widget settings.
3. **Update** the template.

Use label **Governance** for the nav item regardless of the page slug.

---

## 3. Embedding the live CBSRM demo (optional, off-site)

The interactive demo lives at `risk.wavervanir.com` — a **different origin** from wavervanir.com.

**Recommendation:** keep the *narrative* (hero, pillars, CBSRM explainer, self-check, offer ladder, CTAs) on the **same-origin Elementor page** from step 1. That content is SEO-indexable, fast, theme-consistent, and works today. **Iframe only the live demo**, and only once it is up — do not try to reproduce the whole story inside an iframe.

To embed once `risk.wavervanir.com` is live:
1. Add another **HTML** widget (on the same page, lower down, or a separate `/cbsrm-demo/` page).
2. Paste the contents of `cbsrm-demo-embed.html`.
3. **CSP / frame-ancestors check (required):** the demo host must permit being framed by wavervanir.com. If `risk.wavervanir.com` sends `X-Frame-Options: DENY/SAMEORIGIN` or `Content-Security-Policy: frame-ancestors` that excludes `https://wavervanir.com`, the frame will be blocked (blank). Set on the demo host:
   ```
   Content-Security-Policy: frame-ancestors 'self' https://wavervanir.com https://*.wavervanir.com;
   ```
   and remove any conflicting `X-Frame-Options`. Verify with `curl -I https://risk.wavervanir.com` or the browser devtools Network tab. Details are in the comment at the top of `cbsrm-demo-embed.html`.

---

## Quick QA checklist before going live
- [ ] Page saved as **Draft** and previewed at desktop + ~360px mobile.
- [ ] Lens cards expand/collapse; self-check produces a score and band.
- [ ] "Book a readiness audit" → `https://wavervanir.com/consultation/` resolves.
- [ ] Decide what to do with "Explore the platform" while `risk.wavervanir.com` is pending DNS.
- [ ] **Governance** menu item added to primary nav.
- [ ] Publish.
