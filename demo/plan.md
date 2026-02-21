# Project Plan

## North Star

Launch an International Women's Day (IWD) campaign on March 8th that honors women business clients through AI-generated imagery, a celebratory landing page update, and personalized congratulatory emails — demonstrating the Telos multi-agent system's ability to coordinate tools, CRM data, and content generation into a coherent marketing workflow.

**Success Criteria:**
- Three visually consistent IWD images generated and saved to `demo/site/assets/`
- `demo/site/index.html` updated with IWD banner strip and new IWD section (existing content intact)
- Four personalized email HTML files rendered to `demo/emails/`, one per Won-deal woman contact

---

## Architecture Overview

Three agents execute in a coordinated pipeline:

```
┌─────────────────────────────────────────────────────────┐
│                    Telos Orchestrator                    │
└─────────────────────┬───────────────────────────────────┘
                      │
          ┌───────────▼────────────┐
          │   image-generator      │  Phase 1 (blocking)
          │  (3 images → assets/)  │
          └───────────┬────────────┘
                      │ images ready
          ┌───────────┴──────────────────────────────┐
          │                                          │
┌─────────▼──────────┐                   ┌──────────▼──────────┐
│       coder        │                   │        crm          │
│  (landing page     │  Phase 2 (parallel)│  (query Twenty CRM  │
│   HTML update)     │                   │  → contacts list)   │
└────────────────────┘                   └──────────┬──────────┘
                                                    │ contacts
                                         ┌──────────▼──────────┐
                                         │      coder          │
                                         │  (send_email tool   │  Phase 3
                                         │   × 4 recipients)   │
                                         └─────────────────────┘
```

Key architectural decisions:
- **Image-first sequencing**: All downstream tasks (landing page `<img>` src, email header) depend on generated file paths, so image generation is Phase 1 and blocks Phase 2.
- **CRM as source of truth**: Recipient list is not hardcoded — it is queried live from Twenty CRM filtered by `stage=WON` + women contacts, making the workflow data-driven.
- **File-based deliverables**: No live sending or deployment; all outputs are local files (`demo/site/`, `demo/emails/`) for easy browser/diff inspection.
- **Additive HTML editing**: The landing page is modified with `Edit` tool insertions only — no full rewrites — to preserve existing structure.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Agent runtime | `telos-agent` (Python, `uv`) |
| Image generation | OpenRouter API → `google/gemini-3-pro-image-preview` via `telos_agent.tools.image_gen` |
| Email rendering | `telos_agent.tools.send_email` (mock, outputs HTML to `demo/emails/`) |
| CRM | Twenty CRM (MCP tools preferred; REST fallback at `http://localhost:3000`) |
| Landing page | Static HTML (`demo/site/index.html`) — vanilla CSS, no build step |
| Asset storage | `demo/site/assets/` (PNG files) |
| Auth | `TWENTY_API_KEY` env var for CRM; `OPENROUTER_API_KEY` for image gen |

---

## Implementation Phases

### Phase 1: AI Image Generation

- [ ] Generate hero banner (16:9) — abstract, modern IWD design, purple/gold palette — save as `demo/site/assets/iwd-hero.png`
- [ ] Generate social media image (1:1) — shareable IWD graphic with brand feel — save as `demo/site/assets/iwd-social.png`
- [ ] Generate email header image (16:9, smaller) — warm congratulatory header — save as `demo/site/assets/iwd-email-header.png`
- [ ] Visually verify all three images are consistent in style before proceeding

### Phase 2a: Landing Page Update

- [ ] Read current `demo/site/index.html` to identify insertion points (top of `<body>`, hero section, end of main content)
- [ ] Insert IWD banner strip at top of page — purple gradient background, gold text, "Happy International Women's Day — March 8th"
- [ ] Replace hero section image placeholder `<src>` with `assets/iwd-hero.png`
- [ ] Add new "International Women's Day" section below hero — card layout with IWD message, `iwd-social.png`, and a CTA
- [ ] Validate page renders correctly in browser (no broken image refs, layout intact)

### Phase 2b: CRM Contact Lookup

- [ ] Connect to Twenty CRM via MCP tools (fallback: REST `GET http://localhost:3000/rest/opportunities?filter=stage:WON`)
- [ ] Retrieve all opportunities with `stage = "WON"`
- [ ] Resolve `pointOfContact` linked contact records for each Won opportunity
- [ ] Filter contacts to women (by name/gender field); confirm expected set: Sarah Johnson, Priya Patel, Olivia Chen, Amara Okafor
- [ ] Build recipient list: `[{name, email}, ...]`

### Phase 3: Personalized Email Rendering

- [ ] For each contact in the recipient list, invoke `send_email` tool with personalized `--body` (first name interpolation), subject "Celebrating You This International Women's Day!", `--image demo/site/assets/iwd-email-header.png`, `--output-dir demo/emails/`
- [ ] Confirm four HTML files created: `sarah.johnson@apextech.io.html`, `priya.patel@*.html`, `olivia.chen@*.html`, `amara.okafor@*.html`
- [ ] Spot-check one email file in browser to verify image embed, personalization, and formatting

---

## Sequencing

```
Phase 1  ──────────────────────────────►  DONE
              │
              ├──── Phase 2a (landing page) ──►  DONE
              │                                      │
              └──── Phase 2b (CRM lookup)  ──►  DONE ──► Phase 3 (emails)
```

- **Phase 1 must complete before anything else** — image paths are referenced by both the landing page (`iwd-hero.png`, `iwd-social.png`) and the email tool (`iwd-email-header.png`).
- **Phase 2a and 2b are parallel** — landing page editing and CRM querying have no shared dependencies once images exist.
- **Phase 3 depends on Phase 2b** — the recipient list must be resolved before `send_email` is invoked.
- Phase 3 also depends on Phase 1 completing (email header image path needed), but that is already satisfied before 2b begins.

---

## Risks

- **Image generation API failure**: OpenRouter may be unavailable or rate-limited. Mitigation: retry with a simplified prompt; have a fallback placeholder PNG ready so landing page and email tasks are not fully blocked.
- **Inconsistent visual style across images**: Three separate generation calls may produce mismatched styles. Mitigation: use a shared, detailed style prefix in all three prompts ("modern flat illustration, purple #7B2D8B and gold #C9A84C palette, white background, professional, IWD 2025") and inspect before proceeding.
- **CRM MCP connectivity**: Twenty CRM MCP server may not be running. Mitigation: agent falls back to direct REST calls with `TWENTY_API_KEY`; confirm `http://localhost:3000` is reachable before Phase 2b.
- **Contact gender filtering ambiguity**: CRM may not have an explicit gender field. Mitigation: filter by first name heuristics or a known list (`Sarah`, `Priya`, `Olivia`, `Amara`); interview confirms the expected set.
- **HTML edit regressions**: Inserting markup into `index.html` could break existing layout if insertion points are misidentified. Mitigation: read file first, use targeted `Edit` tool insertions with surrounding context, not full rewrites.
- **Email image path**: `send_email --image` expects a path relative to invocation CWD. Mitigation: use absolute path or confirm CWD is repo root before calling the tool.

---

## Open Questions

- Does `send_email` support `--aspect-ratio` or fixed-width image embedding, or does it use the raw PNG dimensions? (Affects email header display fidelity.)
- Is there a gender field on Twenty CRM Contact records, or should filtering rely on the known first-name list from the interview?
- Should the IWD landing page section be hidden/shown based on date (e.g., only visible March 8th), or always visible after deployment?
- What is the exact `stage` value in Twenty CRM for Won deals — is it `"WON"`, `"Won"`, or a UUID enum? (Affects the CRM filter query.)
- Is `demo/emails/` directory pre-created, or does `send_email` create it if missing?
