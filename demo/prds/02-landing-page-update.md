# PRD 02 — Landing Page Update

## Overview

Update `demo/site/index.html` with International Women's Day campaign content: a full-width banner strip, an updated hero image, and a new IWD campaign section. All existing page content must be preserved.

## Subagent

`coder`

## Dependencies

- **PRD 01 must complete first** — `demo/site/assets/iwd-hero.png` and `demo/site/assets/iwd-social.png` must exist before modifying the HTML

## Tech Stack

- Files: Read/Edit/Write tools on `demo/site/index.html`
- Images are referenced by relative path from `demo/site/` — use `assets/iwd-hero.png`, never absolute filesystem paths

## Existing Site Context

The page (`demo/site/index.html`) is a static marketing site for "Apex Dynamics — Strategic Technology Partners". It uses CSS variables including `--navy`, `--gold-accent: #c9a84c`, `--blue-accent: #4a6cf7`, and fonts `DM Serif Display` (headings) and `Outfit` (body). Do not alter these root variables.

## Acceptance Criteria

- [x] Read `demo/site/index.html` in full before making any edits — understand existing element IDs, class names, and section structure
- [x] Add an IWD banner strip as the **first element inside `<body>`** — full-width, purple-to-violet gradient background (e.g. `linear-gradient(135deg, #6b21a8, #7c3aed)`), gold text (`#c9a84c`), centered tagline: *"Celebrating Women Who Build — International Women's Day, March 8"*, padding `12px 24px`
- [x] Update the hero section's primary image to display `assets/iwd-hero.png`; use a relative path (`assets/iwd-hero.png` not `/demo/site/assets/iwd-hero.png`)
- [x] Add a new `<section id="iwd-campaign">` immediately after the existing hero section
- [x] The IWD campaign section must include `<img src="assets/iwd-social.png" alt="International Women's Day">` displayed responsively (max-width: 100%)
- [x] Include campaign copy inside the IWD section — 2–3 sentences honoring women clients who have achieved business milestones and announcing the IWD campaign
- [x] Include a call-to-action element inside the IWD section (e.g. `<a href="#" class="cta-btn">Celebrate With Us</a>`) styled to match the site's existing button aesthetic
- [x] Use only **relative** image paths for all three asset references — never absolute or filesystem paths
- [x] Preserve all existing page sections and content — verify no existing HTML is removed or structurally broken by the edits

## Definition of Done

Opening `demo/site/index.html` in a browser shows: (1) the purple IWD banner at the very top, (2) the hero image updated to the IWD hero asset, (3) the new IWD campaign section with social image, copy, and CTA below the hero. All pre-existing sections (nav, footer, any other content blocks) remain intact and visually correct.
