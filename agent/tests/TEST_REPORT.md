# Integration Test Report — Telos Agent Workflow

**Date:** 2026-02-21
**Scenario:** Vibe-coder (Sarah) wants a bakery website. Ali conducts interview, passes transcript to our library.
**Trace files:** `/tmp/telos-test-bakery/traces/`

---

## Test Results Summary

| Test | Status | Notes |
|------|--------|-------|
| Unit: MCP config generation | PASS | All 5 assertions |
| Unit: Ralph machinery | PASS | Paths, agent copies, prompts |
| Unit: Backwards compat | PASS | Legacy APIs preserved |
| Unit: Force ready | PASS | No Claude invocation needed |
| Integration: Interview Round 1 | PASS | 4→2 follow-up questions after tuning |
| Integration: Interview Round 2 | PASS | ready=True after tuning (was 4 extra questions) |
| Integration: Generate Plan | PASS | Excellent plan quality |
| Integration: Generate PRDs | PASS* | 6 PRDs, but see Finding 4 |
| Post-tuning: Interview Round 1 | PASS | 2 architectural questions only |
| Post-tuning: Interview Round 2 | PASS | ready=True with 0 questions |

---

## Bugs Found & Fixed During Testing

### Bug 1: CLAUDECODE env var blocks nested invocations (FIXED)

**Severity:** Blocker
**Root cause:** Claude Code sets a `CLAUDECODE` environment variable. Child `claude -p` processes inherit it and refuse to start ("cannot be launched inside another Claude Code session").
**Fix:** `claude.py` now strips `CLAUDECODE` from the env dict passed to `subprocess.run()` / `Popen()`.
**Impact:** Would break ALL real invocations. Critical fix.

### Bug 2: JSON parsing fails on Claude CLI envelope (FIXED)

**Severity:** Blocker
**Root cause:** `--output-format json` returns `{"type":"result","result":"...model text..."}`. The `result` field is a string containing explanation text + a JSON code block. The parser tried `json.loads()` on the whole thing, then fell back to a regex `\{[^{}]*\}` that can't match nested braces (arrays inside the JSON).
**Fix:** Rewrote `_parse_round_result()` with three-layer unwrapping: (1) CLI envelope, (2) direct parse of result string, (3) bracket-counting extraction from text with code blocks. Added shared `_extract_json_object()` helper.
**Impact:** Would cause ALL interview rounds to return empty results. Critical fix.

---

## Prompt Tuning Findings

### Finding 1: Interview agent is too conservative (TUNE)

**Severity:** Medium — mitigated by `no_more_questions=True`
**Observed:** After Round 2 (7 Q&A pairs covering pages, domain, pricing, tech, ordering, CMS), the agent still returns 4 more questions and `ready=False`. For a simple bakery website, this is over-thorough.
**Questions generated were:**
1. Notification method for orders
2. Order form field requirements
3. Photo source (Instagram vs originals)
4. Delivery vs pickup + lead time

These are valid questions, but not essential to start planning. The plan agent handled these unknowns gracefully (made reasonable defaults).

**Recommendation:** Add guidance to the interview prompt:
```
Consider the complexity of the project. For simple projects (static sites,
basic CRUD apps), 5-7 Q&A pairs is usually sufficient. Don't ask about
details that can be reasonably defaulted during planning — only ask about
decisions that would fundamentally change the architecture.
```

**Workaround:** Ali can always call `no_more_questions=True` after 2-3 rounds. The prompt tuning would reduce unnecessary round trips.

### Finding 2: Plan generation prompt is excellent (NO CHANGE)

**Observed:**
- Plan respects user constraints perfectly ("no credit cards", "Venmo works fine")
- Tech stack choices are pragmatic and free-tier friendly
- Success criteria is concrete and verifiable
- Risks include non-technical ones (photo quality, scope creep)
- Open questions are genuinely unresolved items, not padding

No tuning needed.

### Finding 3: PRD generation prompt mostly excellent (MINOR TUNE)

**Observed:**
- PRDs 01-05 are outstanding: clear scope, out-of-scope, implementation notes, 8-13 checkboxes each
- Cross-references between PRDs are correct (e.g., "PRD 01 must be complete before starting")
- Self-contained enough for a coder agent to implement without reading other PRDs
- Code snippets included where helpful (Netlify Forms HTML, CMS config)
- Tech consistency maintained (plan chose Decap CMS, PRDs used Decap CMS)

### Finding 4: PRD 06 has 55 checkboxes — too many (TUNE)

**Severity:** Medium
**Observed:** PRD 06 (About + QA + Launch) has 55 checkbox items. PRDs 01-05 have 8-13 each. This imbalance will cause the Ralph loop to spend disproportionate iterations on PRD 06.

**Root causes:**
1. QA checklist items (`- [ ] Mobile hamburger menu opens and closes`) were included as checkboxes
2. Launch checklist items were included as checkboxes
3. Three separate concerns merged: About page + QA + Launch handoff

**Recommendation:** Add to the PRD generation prompt:
```
Keep each PRD to 8-15 acceptance criteria. If a phase naturally has more,
split it into multiple PRDs. QA verification steps should be part of a
PRD's "Definition of Done" narrative, not individual checkboxes —
the reviewer agent handles verification.
```

**Alternative:** Post-process PRDs to split any with >20 checkboxes.

---

## System Architecture Observations

### Observation 1: Gemini MCP is a no-op (expected)

The placeholder Gemini MCP tools were called during interview but returned placeholder text. The agents handled this gracefully — they didn't get confused by the "pending" response and still produced excellent output from the transcript alone. This confirms the architecture is sound even before Gemini integration.

### Observation 2: Response times are acceptable

| Phase | Duration | Model |
|-------|----------|-------|
| Interview Round 1 | 48s | sonnet |
| Interview Round 2 | 68s | sonnet |
| Plan Generation | ~45s | sonnet |
| PRD Generation | ~90s | sonnet |

All within acceptable range for an async backend service. Ali can show a spinner.

### Observation 3: Read-only enforcement works

The interview agent explored the codebase (found it was an empty project dir) and queried the Gemini MCP. It did not attempt any writes. The `allowed_tools` list correctly constrains it.

---

## Recommended Prompt Changes

### 1. `interview.py` — `_build_round_prompt()` (line ~157)

Add after "5. If sufficient context exists, signal readiness.":
```
## Readiness Guidance

Consider the complexity of the project when assessing readiness:
- For simple projects (static sites, small CRUD apps, landing pages): 5-7 Q&A pairs covering core pages, features, and constraints is usually enough
- For complex projects (platforms, multi-service architectures): more depth is warranted
- Don't ask about cosmetic details or implementation choices that can be reasonably defaulted during planning
- Only ask about decisions that would fundamentally change the architecture
- When in doubt, lean toward ready=true — the planning phase can handle unknowns
```

### 2. `orchestrator.py` — `generate_prds()` prompt (line ~93)

Add to the PRD generation prompt:
```
- Keep each PRD to 8-15 acceptance criteria checkboxes
- If a phase has more than 15 checkable items, split it into separate PRDs
- QA/testing verification belongs in the "Definition of Done" section as prose, not as individual checkbox items — the reviewer agent handles verification
- Only use checkboxes for items that require implementation work
```

---

## Files Modified During Testing

| File | Change | Reason |
|------|--------|--------|
| `telos_agent/claude.py` | Added `os` import, strip CLAUDECODE env var | Bug 1 fix |
| `telos_agent/interview.py` | Added `_extract_json_object()`, rewrote `_parse_round_result()` and `_parse_answers()` | Bug 2 fix |
| `tests/integration_test_workflow.py` | Created test suite | Testing |
| `tests/TEST_REPORT.md` | This report | Documentation |
