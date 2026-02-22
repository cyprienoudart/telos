# Telos Agent Workflow

## Overview

Telos is a multi-agent system where an external finetuned model ("Ali") interviews the user to understand what they want built, then hands off to our Python library (`telos-agent`) which plans, implements, and verifies the work using Claude Code subagents.

Our library is a **backend** — Ali is the frontend. Ali handles the conversational UX; we handle the engineering. Ali's Python harness imports our library directly.

## Actors

- **Ali** — External finetuned model with a Python harness. Conducts the user interview, decides when confidence is high enough, calls our library via Python import.
- **InterviewRunner** — Our library's entry point. Receives plain-text Q&A transcript from Ali, invokes Claude Code to explore the codebase + Gemini context, generates follow-up questions if needed.
- **Plan Agent** — Claude Code instance that writes a high-level implementation plan from interview data.
- **PRD Agent** — Claude Code instance that splits the plan into a list of discrete, actionable PRDs.
- **Ralph Loop** — Iterative execution engine. Picks the most important unfinished PRD, delegates to subagents, reviews, repeats.
- **Orchestrator** (inside Ralph) — Claude Code instance that reads PRDs and progress, picks the next item, delegates to the right subagent.
- **Subagents** — Coder, CRM, Marketing — specialists that do the actual work.
- **Reviewer** — Pedantic subagent that verifies work, gates completion with approve/deny MCP tools.
- **Gemini Context MCP** — Exposes two tools: `summarize()` and `answerQuestion(query)`. Provides beginner-friendly project context from multimodal sources (PDFs, images, etc.). Code lives in our codebase; we start it.

## Step-by-Step Flow

### Phase 1: User Interview (Ali-driven, outside our library)

```
Ali ←→ User
```

1. User tells Ali what they want: "I want to build a website", "edit this page", "complete this marketing campaign".
2. Ali generates clarifying questions, asks the user.
3. User responds.
4. Repeat until Ali's confidence is above threshold.

Ali owns this loop entirely. Our library is not involved yet.

### Phase 2: Handoff to InterviewRunner

```
Ali → InterviewRunner (via Python import)
```

5. Ali calls `runner.process_round()` with a **plain-text transcript**:

```
North Star: Build a website for my bakery

Summary: User wants a simple 3-page website
for their bakery with online menu ordering.

Q: What pages do you need?
A: Home, menu, and contact page

Q: Do you have a domain?
A: Yes, mybakery.com
```

   Plus an optional `no_more_questions=True` flag to force-proceed to planning.

6. InterviewRunner invokes Claude Code in **read-only mode** to:
   - Explore the existing codebase
   - Query Gemini Context MCP (`summarize()`, `answerQuestion()`) for project context
   - Assess whether there's enough information to generate a plan
   - If NOT enough info: **generate follow-up questions** (Claude Code formulates these directly)

7. InterviewRunner returns to Ali synchronously:
   - **questions**: List of follow-up question strings (empty if ready to proceed)
   - **ready**: Boolean — True if we have enough info for planning

8. If questions are returned, Ali asks the user, collects answers, calls `process_round()` again with the updated transcript (all Q&A accumulated).

9. Repeat steps 5-8 until either:
   - `ready=True` (InterviewRunner decides it has enough)
   - Ali calls with `no_more_questions=True` (Ali decides to force proceed)

### Phase 3: Planning (two steps)

```
InterviewRunner context → Plan Agent → PRD Agent
```

**Step 1: Generate Plan**

10. `orchestrator.generate_plan()` invokes a Claude Code instance that:
    - Reads the full interview transcript (all rounds)
    - Queries Gemini Context MCP for additional project context
    - Writes a high-level implementation plan (`plan.md` in project dir)
    - The plan covers architecture, approach, sequencing — but is NOT yet actionable tasks

**Step 2: Split into PRDs**

11. `orchestrator.generate_prds()` invokes a Claude Code instance that:
    - Reads `plan.md`
    - Splits the plan into a **list of discrete PRDs**, each with:
      - Clear scope (one logical unit of work)
      - Numbered acceptance criteria with checkboxes
      - Priority ordering
    - Writes PRDs to `prds/` directory in the project: `prds/01-setup.md`, `prds/02-auth.md`, etc.

### Phase 4: Ralph Loop (Execution)

```
RalphLoop → Orchestrator → Subagents → Reviewer
```

12. Ralph loop starts. Each iteration:
    - Fresh Claude Code instance (orchestrator) reads `prds/` directory and `progress.txt`
    - Picks the **highest-priority incomplete PRD**
    - Picks the highest-priority unchecked item within that PRD
    - Delegates to the appropriate subagent (coder, CRM, marketing)
    - After subagent completes, delegates to the reviewer

13. Reviewer verifies the work:
    - Reads diffs, runs tests, checks acceptance criteria
    - Calls `approve(summary)` → item is marked done on the PRD
    - Calls `deny(reason)` → reason and learnings logged, Ralph loop retries

14. Loop continues while:
    - There are unchecked PRD items remaining across any PRD
    - We haven't hit the max iteration limit
    - We haven't hit rate limits

15. Loop exits when:
    - All PRD items across all PRDs are checked off → **success**
    - Max iterations reached → **failure** (returns partial progress)
    - Unrecoverable error → **failure**

## Gemini Context MCP

Exposes exactly two tools:
- `summarize()` — 15-line bullet-point summary of project context, written for a programming beginner
- `answerQuestion(query)` — 1-5 line answer to a specific question, non-technical language

The server code lives in our codebase. We are responsible for starting it (stdio, spawned as subprocess).

### Access Control

| Actor | Gemini MCP | Why |
|-------|-----------|-----|
| InterviewRunner agent | Yes | Needs project context to assess information gaps |
| Plan Agent | Yes | Needs context to write informed plan |
| PRD Agent | Yes | Needs context to write actionable PRDs |
| Ralph orchestrator | Yes | Needs to understand project state each iteration |
| Coder subagent | **No** | Gets context from PRD; gathers what it needs from code |
| CRM subagent | **No** | Gets instructions from orchestrator |
| Marketing subagent | **No** | Gets instructions from orchestrator |
| Reviewer subagent | **No** | Works with code, tests, and acceptance criteria |

## Data Flow

```
Ali plain-text transcript
    ↓
InterviewRunner (explores codebase, queries Gemini, generates follow-up questions)
    ↓  ← loop with Ali until ready
Plan Agent (writes high-level plan from transcript + Gemini context)
    ↓
    plan.md
    ↓
PRD Agent (splits plan into discrete PRDs)
    ↓
    prds/01-xxx.md, prds/02-xxx.md, ...
    ↓
Ralph Loop (iterates over PRDs)
    ↓
    Each iteration: orchestrator → subagent → reviewer
    ↓
    progress.txt (append-only log)
    verdict.json (per-iteration reviewer verdict)
    PRD checkboxes updated
```

## API Surface (for Ali's Python harness)

```python
from telos_agent import TelosOrchestrator

orchestrator = TelosOrchestrator(project_dir="./myproject")
runner = orchestrator.interview()

# Round 1: Ali sends initial interview data as plain text
result = runner.process_round(
    transcript="""North Star: Build a bakery website

Summary: User wants a 3-page website for their bakery.

Q: What pages do you need?
A: Home, menu, and contact page

Q: Do you have a domain?
A: Yes, mybakery.com
""",
)
# result.questions = ["What tech stack...", "Do you need online ordering?"]
# result.ready = False

# Round 2: Ali appends new Q&A to transcript, sends again
result = runner.process_round(
    transcript="""North Star: Build a bakery website

Summary: User wants a 3-page website for their bakery.

Q: What pages do you need?
A: Home, menu, and contact page

Q: Do you have a domain?
A: Yes, mybakery.com

Q: What tech stack do you prefer?
A: Whatever you recommend

Q: Do you need online ordering?
A: Yes, simple menu ordering
""",
)
# result.questions = []
# result.ready = True

# Phase 3: Plan and split into PRDs
orchestrator.generate_plan(runner.get_context())
orchestrator.generate_prds()

# Phase 4: Execute all PRDs
ralph_result = orchestrator.execute()
# ralph_result.success = True
# ralph_result.iterations = 7

# Or do it all in one call after interview is ready:
# ralph_result = orchestrator.plan_and_execute(runner.get_context())
```
