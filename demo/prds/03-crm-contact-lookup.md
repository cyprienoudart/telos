# PRD 03 — CRM Contact Lookup

## Overview

Query Twenty CRM for all Won-stage opportunities, resolve their linked contacts, filter to the four women clients, and write the results to `demo/emails/recipients.json`. This file is the handoff artifact consumed by PRD 04.

## Subagent

`crm`

## Dependencies

- **PRD 01 must complete first** (image assets should be in place before triggering downstream PRDs)
- This PRD is **independent of PRD 02** — landing page and CRM lookup may run in any order after PRD 01

## Tech Stack

- **Preferred**: Twenty CRM MCP tools (`twenty-mcp-server`) — use `search_objects`, list people/companies/opportunities tools
- **Fallback**: REST API at `http://localhost:3000` — endpoint `GET /rest/opportunities?filter=stage[eq]=WON` with `Authorization: Bearer $TWENTY_API_KEY` header
- Auth: `TWENTY_API_KEY` env var

## Acceptance Criteria

- [x] Verify `TWENTY_API_KEY` environment variable is set; log a warning and attempt connection anyway (the token may be embedded in the MCP config), but if CRM is unreachable exit with a clear error
- [x] Query all opportunities with stage `WON` via MCP tools (preferred) or REST fallback at `GET http://localhost:3000/rest/opportunities?filter=stage[eq]=WON`
- [x] For each WON opportunity, retrieve the linked point-of-contact person record (name, email address)
- [x] Also retrieve the associated company name or deal name for each contact to use in personalized email copy
- [x] Filter the full contact list to women clients — match by name against: Sarah Johnson, Priya Patel, Olivia Chen, Amara Okafor (the CRM seed data uses these exact names; do not rely on a gender field)
- [x] Log a warning to stdout if fewer or more than four contacts are found — proceed with whichever contacts were actually identified
- [x] Create the `demo/emails/` directory if it does not already exist
- [x] Write the identified contacts to `demo/emails/recipients.json` as a JSON array — each element must include: `"name"` (full name), `"email"` (email address), `"company"` (company name), `"deal_name"` (opportunity/deal name or title)

## Output Format

`demo/emails/recipients.json` must be valid JSON matching this structure:

```json
[
  {
    "name": "Sarah Johnson",
    "email": "sarah.johnson@example.com",
    "company": "Acme Corp",
    "deal_name": "Acme Corp — Q4 Expansion"
  }
]
```

## Definition of Done

`demo/emails/recipients.json` exists, is valid JSON, and contains between one and four contact records (ideally exactly four). Each record has non-empty `name`, `email`, `company`, and `deal_name` fields. The file is readable by the next PRD without any additional CRM access.
