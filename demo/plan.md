# Project Plan

## North Star

Launch an International Women's Day (March 8th) marketing campaign that honors women clients who have achieved business milestones, expressed through three AI-generated visual assets, a refreshed landing page, and personalized congratulatory emails — demonstrating the Telos multi-agent system's ability to coordinate tools across image generation, CRM data retrieval, web content authoring, and email rendering in a single orchestrated workflow.

**Success criteria:**
- Three visually consistent IWD images generated and saved to `demo/site/assets/`
- Landing page (`demo/site/index.html`) updated with IWD banner, hero image, and new campaign section
- Personalized HTML emails rendered to `demo/emails/` for each qualifying woman contact (Sarah Johnson, Priya Patel, Olivia Chen, Amara Okafor)

---

## Architecture Overview

Three specialized subagents execute in dependency order, coordinated by the Ralph loop orchestrator:

1. **image-generator** — Runs first (blocking). Produces all three assets that downstream agents depend on.
2. **coder** — Updates `demo/site/index.html` once hero and social images are available.
3. **crm + marketing** — Query Twenty CRM for Won-stage deals linked to women contacts, then render emails using the email header image.

Phases 2 and 3 are independent of each other and can run in parallel after Phase 1 completes. State is shared via the filesystem (`demo/site/assets/` for images, `demo/emails/` for rendered output).

---

## Tech Stack

| Layer | Tool / Technology |
|---|---|
| Image generation | `telos_agent.tools.image_gen` CLI → OpenRouter `google/gemini-3-pro-image-preview` |
| Landing page | Static HTML/CSS (`demo/site/index.html`) — Read/Write/Edit tools |
| CRM data | Twenty CRM MCP tools (preferred) or REST API at `http://localhost:3000` |
| Email rendering | `telos_agent.tools.send_email` CLI → HTML output in `demo/emails/` |
| Orchestration | Telos Ralph loop, multi-PRD execution |
| Auth | `TWENTY_API_KEY` env var for CRM; `OPENROUTER_API_KEY` for image gen |

---

## Implementation Phases

### Phase 1: AI Image Generation

- [ ] Generate hero banner (16:9) — elegant abstract IWD design, purple/gold palette — save to `demo/site/assets/iwd-hero.png`
- [ ] Generate social media image (1:1) — shareable IWD graphic with brand feel — save to `demo/site/assets/iwd-social.png`
- [ ] Generate email header image (16:9, smaller) — warm congratulatory header — save to `demo/site/assets/iwd-email-header.png`
- [ ] Verify all three files exist and are valid PNGs before proceeding

### Phase 2: Landing Page Update

- [ ] Read existing `demo/site/index.html` to understand current structure
- [ ] Add IWD banner strip at top of `<body>` — purple gradient background, gold text, IWD tagline
- [ ] Replace hero section image placeholder with `assets/iwd-hero.png`
- [ ] Add new "International Women's Day" section below hero — card layout containing: IWD message copy, `assets/iwd-social.png`, and a call-to-action element
- [ ] Verify page renders correctly in browser (all existing content intact)

### Phase 3: CRM Query & Personalized Emails

- [ ] Query Twenty CRM for all opportunities with stage `WON` (via MCP tools or REST `GET /rest/opportunities?filter=stage[eq]=WON`)
- [ ] Resolve linked `pointOfContact` for each Won opportunity
- [ ] Filter to women contacts — expected: Sarah Johnson, Priya Patel, Olivia Chen, Amara Okafor
- [ ] For each contact, render personalized email via `send_email` CLI:
  - Personalized greeting using first name
  - Subject: `"Celebrating You This International Women's Day!"`
  - Warm body copy thanking them for partnership and celebrating their achievements
  - Attach `demo/site/assets/iwd-email-header.png` as header image
  - Output to `demo/emails/<email-address>.html`
- [ ] Verify four HTML email files exist in `demo/emails/`

---

## Sequencing

```
Phase 1 (images)
    └── blocks both Phase 2 and Phase 3
         ├── Phase 2 (landing page) — requires iwd-hero.png, iwd-social.png
         └── Phase 3 (emails)      — requires iwd-email-header.png
              └── also requires Phase 1 CRM query to complete before rendering
```

Phases 2 and 3 are independent of each other and may run concurrently once Phase 1 is complete.

---

## Risks

- **Image generation API failure** — `OPENROUTER_API_KEY` missing or OpenRouter quota exceeded. Mitigation: verify env var before starting Phase 1; fail fast with a clear error rather than producing broken downstream assets.
- **CRM connectivity** — Twenty CRM Docker container not running or `TWENTY_API_KEY` invalid. Mitigation: crm agent should attempt REST fallback if MCP tools fail; log the raw response for debugging.
- **Incorrect gender filtering** — CRM contacts may lack a gender field; the filter may need to rely on contact names or a custom field. Mitigation: the demo seed data includes the expected four contacts — match by name if no gender field exists.
- **Landing page structure drift** — If `index.html` has changed significantly, CSS injection points may differ. Mitigation: coder agent must read the file before editing; do not assume element IDs or class names.
- **Image path references** — HTML must reference images with relative paths (`assets/iwd-hero.png`) that resolve correctly when opened from `demo/site/`. Mitigation: use relative paths only, never absolute filesystem paths.

---

## Open Questions

- Does the Twenty CRM contacts schema include a gender or gender-indicator field, or must filtering rely solely on contact names from the seed data?
- Should the IWD landing page section remain visible indefinitely or include a date-gating mechanism to auto-hide after March 8th?
- Are there brand guidelines (logo, font, specific hex values for purple/gold) that image prompts should reference for visual consistency?
- Should the `send_email` CLI tool be invoked once per recipient or does it support batch mode with multiple `--to` flags?
