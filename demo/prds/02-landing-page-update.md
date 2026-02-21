# PRD 02 — Landing Page Update

## Overview

Update `demo/site/index.html` with three additive changes: an IWD banner strip at the top of the page, a hero image swap, and a new IWD content section. **No content may be removed.** All edits use targeted insertions into the existing file.

**Agent:** `coder`
**Phase:** 2a (parallel with PRD 03)
**Depends on:** PRD 01 — `demo/site/assets/iwd-hero.png` and `demo/site/assets/iwd-social.png` must exist before editing

---

## Tech Stack

| Concern | Detail |
|---|---|
| File | `demo/site/index.html` (~1048 lines) |
| Edit method | `Edit` tool — targeted string replacements only, no full rewrites |
| Styling | Vanilla CSS inserted into the existing `<style>` block |
| Image paths | Relative to `demo/site/` — use `assets/iwd-hero.png`, not absolute paths |
| Existing CSS vars | `--gold-accent: #c9a84c` and `--navy: #1a1a2e` already defined in `:root` |

---

## Page Structure Reference

Key insertion landmarks (read the file first to confirm line numbers):

| Landmark | Location | Used for |
|---|---|---|
| `</style>` (end of style block) | ~line 824 | Append new CSS rules |
| `<body>` | line 826 | Insert IWD banner immediately after |
| `<div class="hero-visual-box"></div>` | line 863 | Replace with `<img>` tag |
| Closing `</section>` of `.metrics` | line 898 | Insert IWD section after |
| `<!-- ─── Features` comment | line 900 | The line immediately after the insert point |

---

## Change 1: CSS Rules

Add the following CSS classes inside the existing `<style>` block, just before the closing `</style>` tag:

```css
/* ─── IWD Banner ──────────────────────── */
.iwd-banner {
  background: linear-gradient(90deg, #5a1a6e 0%, #7b2d8b 50%, #5a1a6e 100%);
  color: #c9a84c;
  text-align: center;
  padding: 12px 20px;
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 0.08em;
  position: relative;
  z-index: 101;
}

/* ─── IWD Section ─────────────────────── */
.iwd-section {
  padding: 100px 0;
  background: linear-gradient(160deg, #fdf6ff 0%, #f7f8fc 100%);
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
}

.iwd-card {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 72px;
  align-items: center;
}

.iwd-card-image {
  width: 100%;
  border-radius: 4px;
  box-shadow: 0 24px 64px -12px rgba(123, 45, 139, 0.2);
}

.iwd-card-content .section-eyebrow {
  color: #7b2d8b;
}

.iwd-card-content .section-eyebrow::before {
  background: #7b2d8b;
}

.iwd-cta {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-top: 32px;
  padding: 14px 28px;
  background: #7b2d8b;
  color: #fff;
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
  border-radius: var(--radius);
  transition: background 0.2s;
}

.iwd-cta:hover { background: #5a1a6e; }

@media (max-width: 1024px) {
  .iwd-card { grid-template-columns: 1fr; gap: 48px; }
}
```

---

## Change 2: IWD Banner Strip

Insert immediately after `<body>` (before `<!-- ─── Navigation`):

```html
<!-- ─── IWD Banner ─────────────────────────────── -->
<div class="iwd-banner">
  ✦ &nbsp; Happy International Women's Day — March 8th &nbsp; ✦
</div>
```

---

## Change 3: Hero Image Swap

Replace the CSS-only placeholder box:

```html
      <div class="hero-visual-box"></div>
```

with an actual image:

```html
      <img src="assets/iwd-hero.png" alt="International Women's Day — Apex Dynamics" class="hero-visual-box" style="object-fit:cover;">
```

The existing `.hero-visual-box` CSS (aspect-ratio, border-radius, box-shadow) will apply to the `<img>` element.

---

## Change 4: IWD Content Section

Insert between the closing `</section>` of `.metrics` and the `<!-- ─── Features` comment:

```html
<!-- ─── International Women's Day ──────────────── -->
<section class="iwd-section" id="iwd">
  <div class="container">
    <div class="iwd-card reveal">
      <img src="assets/iwd-social.png" alt="International Women's Day" class="iwd-card-image">
      <div class="iwd-card-content">
        <div class="section-eyebrow">International Women's Day</div>
        <h2 class="section-title">Celebrating the women who lead with vision</h2>
        <p class="section-desc">On March 8th, we pause to honour the extraordinary women in our client community — leaders who transform industries, inspire teams, and build legacies that outlast any single quarter.</p>
        <p class="section-desc" style="margin-top:16px;">To every woman we've had the privilege of partnering with: your ambition shapes what's possible. We celebrate you today and every day.</p>
        <a href="#contact" class="iwd-cta">Get in touch</a>
      </div>
    </div>
  </div>
</section>

```

---

## Acceptance Criteria

- [ ] Read `demo/site/index.html` in full to confirm the three insertion landmarks before making any edits
- [ ] Append IWD CSS rules (banner + section styles) inside the existing `<style>` block before `</style>`
- [ ] Insert `.iwd-banner` `<div>` as the first element inside `<body>`, before the navigation comment
- [ ] Replace `<div class="hero-visual-box"></div>` with the `<img>` tag pointing to `assets/iwd-hero.png`
- [ ] Insert the IWD `<section id="iwd">` block between the closing `</section>` of `.metrics` and `<!-- ─── Features`
- [ ] Verify `assets/iwd-social.png` is referenced in the new IWD section `<img>` tag
- [ ] Confirm all existing sections (nav, hero, metrics, features, trusted, CTA, footer) are intact after edits
- [ ] Confirm all `<img>` src paths are relative (`assets/iwd-hero.png`), not absolute filesystem paths
- [ ] Confirm the `.nav` element still has `z-index: 100` and the `.iwd-banner` has `z-index: 101` so the banner sits above the sticky nav

---

## Definition of Done

The page opens in a browser without layout breaks or broken image references. The IWD banner is visible at the top, the hero shows the generated image, and the IWD section appears between metrics and features. All pre-existing sections are visually unchanged.
