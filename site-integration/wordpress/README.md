# CBSRM / AI model-risk governance — WordPress integration kit

Paste-ready assets to publish a CBSRM / AI model-risk governance section on **wavervanir.com**.

**Target stack:** WordPress 6.9.4 + Astra theme + Elementor Pro 3.33.4.
There is no React/Next source to edit — content goes live through an Elementor **HTML** widget.

**Theme match:** the fragment binds to the live Elementor *global* CSS variables
(`--e-global-color-astglobalcolor*`, `--e-global-typography-*-font-family`) with the
site's current values as fallbacks. So it inherits the live palette (blue `#046bd2`,
slate `#1e293b`/`#334155`, light `#F0F5FA`) and fonts (Roboto / Roboto Slab) automatically,
and still renders correctly anywhere the globals are absent (e.g. preview).

## Files in this kit

| File | What it is |
|------|------------|
| `cbsrm-governance-page.html` | The full governance section. One self-contained HTML fragment (inline `<style>` + `<script>`, zero external dependencies, all CSS scoped under `.wv-cbsrm`). Paste into an Elementor HTML widget. |
| `cbsrm-demo-embed.html` | A small responsive iframe snippet to embed the hosted CBSRM demo **after** `risk.wavervanir.com` is live. Optional. |
| `README.md` | This file. |

---

## 1. Publish it — remake the **Consultation** tab (primary path)

This section is the productized successor to the existing Consultation page
(`/consultation/`, Elementor page id **7009**), which already sells the audit/advisory
offers. Remaking that tab keeps the nav unchanged and the URL's SEO history intact.

1. **Open the Consultation page.** WordPress admin → **Pages** → open **Consultation**
   (`/consultation/`) → **Edit with Elementor**.
2. **Clear the old body.** Remove the existing Consultation sections (or keep any you
   still want above/below). Tip: right-click the section handles → **Delete**, or use
   **Navigator** to select and remove them.
3. **Add a full-width section.** Drag a new Section → set **Content Width → Full Width**
   and **Section padding → 0** (the fragment manages its own spacing).
4. **Drop an HTML widget.** Search **HTML** in the widget panel, drag it into the column.
5. **Paste the fragment.** Copy the **entire** contents of `cbsrm-governance-page.html`
   into the HTML widget code box.
6. **(Optional) rename the tab to "Governance".** If you want the nav label to read
   *Governance* instead of *Consultation*, change it in **Appearance → Menus** (edit the
   menu item's Navigation Label) — this does not change the `/consultation/` URL. Leave it
   as *Consultation* if you'd rather not touch the nav.
7. **Preview first.** Save as **Draft** / use Elementor **Preview** + the responsive
   toggle (desktop / tablet / ~360px mobile). Confirm: hero is light/on-brand, the four
   lens cards expand on click, the self-check computes a score, both CTAs resolve.
8. **Go live.** **Update** the page.

### Alternative: publish as a brand-new page instead
If you'd rather not touch Consultation: **Pages → Add New**, title *Model risk governance*,
slug **`/risk-governance/`**, then do steps 3–8 above, and add a **Governance** nav item
(**Appearance → Menus** → add the page or a Custom Link → Save Menu).

### Notes on the fragment
- **Theme-safe & offline-safe:** every style is scoped under `.wv-cbsrm`; no external
  CSS/JS/fonts/CDN. Nothing to allow-list.
- **CTAs:** "Book a readiness audit" → `https://wavervanir.com/contact-us/`;
  "Explore the platform" → `https://risk.wavervanir.com` (**pending DNS** — both
  occurrences are flagged with a comment in the file; repoint or remove until Path B is live).

---

## 2. Embedding the live CBSRM demo (optional, off-site)

The interactive demo lives at `risk.wavervanir.com` — a **different origin** from wavervanir.com.

**Recommendation:** keep the *narrative* (hero, pillars, CBSRM explainer, self-check, offer
ladder, CTAs) on the **same-origin** page from step 1 — SEO-indexable, fast, theme-consistent,
works today. **Iframe only the live demo**, and only once it is up.

To embed once `risk.wavervanir.com` is live:
1. Add another **HTML** widget (lower on the page, or a separate `/cbsrm-demo/` page).
2. Paste the contents of `cbsrm-demo-embed.html`.
3. **CSP / frame-ancestors check (required):** the demo host must permit being framed by
   wavervanir.com. Set on the demo host:
   ```
   Content-Security-Policy: frame-ancestors 'self' https://wavervanir.com https://*.wavervanir.com;
   ```
   and remove any conflicting `X-Frame-Options`. Verify with `curl -I https://risk.wavervanir.com`.

---

## Quick QA checklist before going live
- [ ] Page saved as **Draft** and previewed at desktop + ~360px mobile.
- [ ] Hero/buttons/accents render in the site blue `#046bd2`; headings in slate; fonts = Roboto.
- [ ] Lens cards expand/collapse; self-check produces a score and band.
- [ ] "Book a readiness audit" → `https://wavervanir.com/contact-us/` resolves.
- [ ] Decide what to do with "Explore the platform" while `risk.wavervanir.com` is pending DNS.
- [ ] Nav reads as you want (Consultation kept, or renamed to Governance).
- [ ] Publish / Update.
