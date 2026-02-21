# PRD 03 — CRM Contact Lookup

## Overview

Query Twenty CRM to retrieve all Won-deal contacts, filter to women, and produce a `recipients.json` file that PRD 04 consumes for email rendering. This task is data-gathering only — no HTML or images are written.

**Agent:** `crm`
**Phase:** 2b (parallel with PRD 02)
**Depends on:** PRD 01 (none of its outputs are needed here — this PRD can start as soon as images are done, alongside PRD 02)
**Output:** `demo/emails/recipients.json`

---

## Tech Stack

| Concern | Detail |
|---|---|
| Primary | Twenty CRM MCP tools (`twenty-mcp-server` via npx, 29 tools) |
| Fallback | REST API at `http://localhost:3000` with `Authorization: Bearer $TWENTY_API_KEY` |
| GraphQL | `http://localhost:3000/graphql` (alternative if REST endpoints are unclear) |
| Auth env var | `TWENTY_API_KEY` |
| Output file | `demo/emails/recipients.json` |

---

## Expected Result

The known set of women contacts from Won deals (confirmed by the project interview):

| Name | Company | Email |
|---|---|---|
| Sarah Johnson | Apex Tech | `sarah.johnson@apextech.io` |
| Priya Patel | (TBD from CRM) | (resolve from CRM) |
| Olivia Chen | (TBD from CRM) | (resolve from CRM) |
| Amara Okafor | (TBD from CRM) | (resolve from CRM) |

Treat the CRM as the source of truth for exact email addresses — do not hardcode from this table.

---

## Query Strategy

### MCP-first approach (preferred)

Use Twenty CRM MCP tools. Likely useful tools from the `twenty-mcp-server`:
- A search/filter tool for opportunities filtered by `stage = "WON"` (or equivalent)
- A people/contact lookup tool to resolve contact records linked to each opportunity

### REST fallback

If MCP is unavailable, use the REST API:

```
GET http://localhost:3000/rest/opportunities?filter=stage:WON
Authorization: Bearer <TWENTY_API_KEY>
```

Then for each opportunity, resolve the contact via:

```
GET http://localhost:3000/rest/people/<contactId>
Authorization: Bearer <TWENTY_API_KEY>
```

### Stage value

The exact `stage` filter value may be `"WON"`, `"Won"`, or a UUID enum — try the MCP search first and inspect returned records to determine the correct string before filtering.

### Gender filtering

Twenty CRM may not have an explicit gender field. Filter women contacts by first name:
- Match first names: `Sarah`, `Priya`, `Olivia`, `Amara`
- If additional contacts appear in Won deals that don't match these names, exclude them

---

## Output Format

Write a JSON array to `demo/emails/recipients.json`:

```json
[
  {"name": "Sarah Johnson", "email": "sarah.johnson@apextech.io"},
  {"name": "Priya Patel",   "email": "priya.patel@<domain>"},
  {"name": "Olivia Chen",   "email": "olivia.chen@<domain>"},
  {"name": "Amara Okafor",  "email": "amara.okafor@<domain>"}
]
```

This format is consumed directly by `send_email --batch demo/emails/recipients.json` in PRD 04.

---

## Acceptance Criteria

- [ ] Verify Twenty CRM is reachable — either confirm `twenty-mcp-server` MCP tools are available, or confirm `http://localhost:3000` responds to a GET request
- [ ] Query all opportunities and identify those with a Won stage (try MCP search tool first; fall back to REST if needed)
- [ ] Inspect at least one Won opportunity record to determine the correct stage filter value (`"WON"`, `"Won"`, or other)
- [ ] Retrieve the linked contact/person record for each Won opportunity
- [ ] Filter resolved contacts to women using the known first-name list: Sarah, Priya, Olivia, Amara
- [ ] Confirm all four expected contacts are present with valid email addresses
- [ ] Create `demo/emails/` directory if it does not exist
- [ ] Write `demo/emails/recipients.json` as a JSON array of `{"name", "email"}` objects
- [ ] Confirm the output file contains exactly 4 entries

---

## Definition of Done

`demo/emails/recipients.json` exists, is valid JSON, contains exactly four entries, and each entry has a non-empty `name` and a properly-formed email address. The file is ready for `send_email --batch` in PRD 04.
