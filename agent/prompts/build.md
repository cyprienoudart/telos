Read all PRD files in the `prds/` directory. Check progress.txt for what's been done so far — pay attention to both accomplishments and denial reasons.
Read `AGENTS.md` for accumulated project conventions, gotchas, and patterns.
Check `git log --oneline -20` for recent changes.

If the last iteration was denied, your FIRST priority is addressing the denial reason. Do not move on to new work until the denied items are fixed. When fixing a denial, pass the exact denial reason to the subagent.

Pick the NEXT SINGLE unchecked checkbox (`- [ ]`) in the highest-priority incomplete PRD (lowest-numbered file). One checkbox per iteration — do not attempt multiple items.

Delegate implementation to the appropriate subagent. Require the coder to:
- Run all tests after implementation and fix any failures
- Run linting/formatting and fix violations
- Run type checking if applicable and fix errors
- Iterate until all checks pass before finishing

Do NOT send work to the reviewer until the coder confirms all checks are green.

After the coder finishes clean, delegate to the reviewer subagent for verification.

After the reviewer's verdict:
- Update `progress.txt` with what happened this iteration.
- If approved: check off the completed item in the PRD file (`- [ ]` → `- [x]`).
- If denied: record the denial reason in `AGENTS.md` under Gotchas so future iterations avoid the same mistake.

If the reviewer approves and all items across ALL PRDs in `prds/` are complete, output:
<promise>COMPLETE</promise>

If the reviewer denies, note the reason and continue fixing.
Do NOT implement anything yourself. ALL work goes through subagents.
