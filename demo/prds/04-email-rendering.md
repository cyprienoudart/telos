# PRD 04 — Personalized Email Rendering

## Overview

Read the contact list from `demo/emails/recipients.json` (produced by PRD 03) and render a personalized HTML email for each woman client using the `send_email` CLI tool. Emails are saved locally as HTML files — nothing is sent over the network.

## Subagent

`coder`

## Dependencies

- **PRD 01 must complete first** — `demo/site/assets/iwd-email-header.png` must exist
- **PRD 03 must complete first** — `demo/emails/recipients.json` must exist with contact records

## Tech Stack

- CLI: `uv run python -m telos_agent.tools.send_email` (from the `agent/` directory or any directory where `telos_agent` is installed)
- Batch mode: `--batch demo/emails/recipients.json` (if body is the same for all) **or** individual `--to` invocations (preferred for per-recipient personalization)
- Output: `--output-dir demo/emails/` — the tool writes one `.html` file per recipient, named by email address

## CLI Reference

Single-recipient invocation:
```
uv run python -m telos_agent.tools.send_email \
  --to "First Last <email@example.com>" \
  --subject "Celebrating You This International Women's Day!" \
  --body "Dear First, ..." \
  --image demo/site/assets/iwd-email-header.png \
  --output-dir demo/emails/
```

## Acceptance Criteria

- [x] Read and parse `demo/emails/recipients.json`; exit with a clear error if the file is missing or contains invalid JSON
- [x] Verify `demo/site/assets/iwd-email-header.png` exists before rendering; exit with a clear error if it is missing
- [x] Render a personalized HTML email for **Sarah Johnson** via the `send_email` CLI — body must open with *"Dear Sarah,"*
- [x] Render a personalized HTML email for **Priya Patel** via the `send_email` CLI — body must open with *"Dear Priya,"*
- [x] Render a personalized HTML email for **Olivia Chen** via the `send_email` CLI — body must open with *"Dear Olivia,"*
- [x] Render a personalized HTML email for **Amara Okafor** via the `send_email` CLI — body must open with *"Dear Amara,"*
- [x] Each email body must reference the recipient's company or deal name from `recipients.json` (e.g. *"your team at Acme Corp"*) — copy must not be identical across all four emails
- [x] All four emails must use subject line: `"Celebrating You This International Women's Day!"`
- [x] All four emails must include `demo/site/assets/iwd-email-header.png` as the `--image` argument

## Email Copy Guidelines

Each personalized body should:
1. Open with `"Dear <FirstName>,"`
2. Celebrate the recipient's specific business milestone (reference their company/deal from the JSON)
3. Include a 1–2 sentence IWD campaign message: something warm and empowering about women in business
4. Close with gratitude for the partnership and a sign-off from the Apex Dynamics team

Keep each email to 3–5 short paragraphs. Tone: warm, professional, celebratory.

## Definition of Done

Four HTML files exist in `demo/emails/`, one per recipient, named by email address (e.g. `sarah.johnson@example.com.html`). Opening any file in a browser shows a properly rendered email: IWD header image at top, personalized greeting, campaign body copy, and a styled layout matching the tool's built-in template. No recipient's email is a duplicate of another's body copy.
