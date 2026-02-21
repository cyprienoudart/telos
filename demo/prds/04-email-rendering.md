# PRD 04 — Personalized Email Rendering

## Overview

Render four personalized HTML email files — one per woman contact — using the `telos_agent.tools.send_email` CLI tool. Each email has a personalized greeting, a shared subject line, and an embedded IWD header image. All output is local HTML files; nothing is actually sent.

**Agent:** `coder`
**Phase:** 3 (must run after both PRD 01 and PRD 03 complete)
**Depends on:**
- PRD 01 — `demo/site/assets/iwd-email-header.png` must exist
- PRD 03 — `demo/emails/recipients.json` must exist

---

## Tech Stack

| Concern | Detail |
|---|---|
| Tool | `uv run python -m telos_agent.tools.send_email` |
| Image embedding | Base64 data URI (embedded inline — no external URL needed) |
| Output dir | `demo/emails/` (created automatically by the tool) |
| Output filename | `{sanitized_email}.html` — special chars replaced with `_`, `@` and `.` preserved |
| Batch mode | `--batch demo/emails/recipients.json` sends to all four recipients in one invocation |

The tool signature:

```
uv run python -m telos_agent.tools.send_email \
  --batch demo/emails/recipients.json \
  --subject "Celebrating You This International Women's Day!" \
  --body "<body text>" \
  --image <path-to-iwd-email-header.png> \
  --output-dir demo/emails/
```

---

## Email Content Spec

### Subject

```
Celebrating You This International Women's Day!
```

### Body

Write one body template, then personalize the first name for each recipient. The body should:
- Open with `Dear {FirstName},` (use first name only — e.g., "Dear Sarah,")
- Express genuine celebration of the recipient's achievements and leadership
- Reference the International Women's Day theme (March 8th)
- Include a warm sign-off from the Apex Dynamics team
- Be 3–4 short paragraphs; conversational but professional in tone

Because `send_email --batch` applies a single body string to all recipients, **use `--to` mode individually** (one call per recipient) if you need distinct first-name interpolation per email. Alternatively, write the body with a generic "Dear {name}," that works for all four — but ensure the actual first name is interpolated.

Recommended approach: invoke `send_email --to` four times, once per recipient, each with a personalized `--body` that uses the recipient's first name.

### Image path

Pass the absolute path to avoid CWD ambiguity:

```
--image /path/to/telos/demo/site/assets/iwd-email-header.png
```

Or confirm that the working directory when invoking the command is the repo root (`/path/to/telos`), then use:

```
--image demo/site/assets/iwd-email-header.png
```

---

## Expected Output Files

| Recipient | Expected filename |
|---|---|
| Sarah Johnson | `sarah.johnson@apextech.io.html` |
| Priya Patel | `priya.patel@<domain>.html` |
| Olivia Chen | `olivia.chen@<domain>.html` |
| Amara Okafor | `amara.okafor@<domain>.html` |

Filenames are derived by the tool from the email address: `re.sub(r'[^\w@.\-]', '_', email)`.

---

## Acceptance Criteria

- [ ] Confirm `demo/emails/recipients.json` exists and contains 4 entries (output from PRD 03)
- [ ] Confirm `demo/site/assets/iwd-email-header.png` exists (output from PRD 01)
- [ ] Resolve the correct invocation path for `send_email` (confirm CWD or use absolute `--image` path)
- [ ] Invoke `send_email` for Sarah Johnson with personalized body ("Dear Sarah,")
- [ ] Invoke `send_email` for Priya Patel with personalized body ("Dear Priya,")
- [ ] Invoke `send_email` for Olivia Chen with personalized body ("Dear Olivia,")
- [ ] Invoke `send_email` for Amara Okafor with personalized body ("Dear Amara,")
- [ ] Confirm four `.html` files exist in `demo/emails/`
- [ ] Verify the email HTML for one recipient contains the correct first name in the greeting, the IWD subject line, and an embedded image (non-empty `<img>` src starting with `data:image/png;base64,`)

---

## Definition of Done

Four HTML files exist in `demo/emails/`, one per recipient. Each file opens in a browser showing: the IWD header image rendered inline, a personalized greeting with the correct first name, the subject as the heading, and the Apex Dynamics footer. No broken images or placeholder text.
