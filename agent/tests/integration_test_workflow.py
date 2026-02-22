"""Integration test — simulate Ali calling the Telos library.

Runs each phase of the workflow against real Claude Code instances,
captures output, and writes traces to /tmp/telos-test-bakery/traces/.

Persona: Vibe-coder user who wants a bakery website but knows nothing
about tech. Ali has already interviewed them and sends us transcripts.
"""

import json
import os
import sys
import time
import traceback
from pathlib import Path

# ── Test config ──────────────────────────────────────────────────────
PROJECT_DIR = Path("/tmp/telos-test-bakery")
AGENT_DIR = Path(__file__).resolve().parent.parent  # agent/
TRACES_DIR = PROJECT_DIR / "traces"

TRACES_DIR.mkdir(parents=True, exist_ok=True)


def clean_project():
    """Clean project dir. Call explicitly, not on import."""
    for p in [PROJECT_DIR / "plan.md", PROJECT_DIR / "interview-context.txt"]:
        p.unlink(missing_ok=True)
    for d in [PROJECT_DIR / "prds"]:
        if d.exists():
            import shutil
            shutil.rmtree(d)

# ── Vibe-coder transcript (Round 1 — sparse, non-technical) ─────────
TRANSCRIPT_R1 = """\
North Star: Build a website for my bakery

Summary: Sarah wants a website for "Sweet Crumbs Bakery". She's not
technical at all — she just wants people to see her cakes and order them.
She currently takes orders via Instagram DMs.

Q: What do you want people to do on your website?
A: See my cakes and stuff, and like, order them? Right now people DM me
on Instagram and it's so messy. I want something more professional.

Q: Do you have any branding or design preferences?
A: I like pink and gold lol. My Instagram is @sweetcrumbs and everything
there is kinda pastel-y? I don't know about fonts and stuff, just make
it look cute.

Q: How do you currently handle orders and payments?
A: People DM me what they want, I tell them the price, they Venmo me.
It works but I lose track of orders sometimes.
"""

# ── Round 2 — Ali asked follow-ups from Round 1, user answered ──────
TRANSCRIPT_R2 = """\
North Star: Build a website for my bakery

Summary: Sarah wants a website for "Sweet Crumbs Bakery". She's not
technical at all — she just wants people to see her cakes and order them.
She currently takes orders via Instagram DMs. Budget is flexible but
she'd prefer something cheap. No existing codebase.

Q: What do you want people to do on your website?
A: See my cakes and stuff, and like, order them? Right now people DM me
on Instagram and it's so messy. I want something more professional.

Q: Do you have any branding or design preferences?
A: I like pink and gold lol. My Instagram is @sweetcrumbs and everything
there is kinda pastel-y? I don't know about fonts and stuff, just make
it look cute.

Q: How do you currently handle orders and payments?
A: People DM me what they want, I tell them the price, they Venmo me.
It works but I lose track of orders sometimes.

Q: Do you have a domain name or hosting set up?
A: What's hosting? I bought sweetcrumbsbakery.com on GoDaddy last year
but I never did anything with it.

Q: What items do you sell and how does your menu work?
A: I make custom cakes, cupcakes, cookies, and cake pops. The prices
depend on size and stuff. Like a 6-inch cake is $45 and 8-inch is $65.
Cupcakes are $3 each or $30 for a dozen. I change my menu sometimes
when I try new things.

Q: Do you need online payments or just order requests?
A: Honestly Venmo works fine for me. Can people just like, pick what
they want and submit an order and then I message them? I don't want
to deal with credit cards and stuff.

Q: Do you need a content management system to update your menu?
A: I don't know what that is. I just want to be able to change prices
and add new items without calling a developer every time. Is that
possible?
"""


def write_trace(name: str, data: dict) -> Path:
    """Write a trace file and return its path."""
    path = TRACES_DIR / f"{name}.json"
    path.write_text(json.dumps(data, indent=2, default=str) + "\n")
    print(f"  📝 Trace written: {path.name}")
    return path


def test_interview_round1():
    """Phase 2a: First process_round() call — should generate follow-up questions."""
    print("\n" + "=" * 70)
    print("TEST 1: Interview Round 1 (sparse transcript, expect follow-up questions)")
    print("=" * 70)

    from telos_agent.interview import InterviewRunner

    runner = InterviewRunner(
        project_dir=PROJECT_DIR,
        agent_dir=AGENT_DIR,
    )

    start = time.time()
    result = runner.process_round(TRANSCRIPT_R1)
    elapsed = time.time() - start

    trace = {
        "test": "interview_round1",
        "transcript_length": len(TRANSCRIPT_R1),
        "elapsed_seconds": round(elapsed, 1),
        "result": {
            "ready": result.ready,
            "questions": result.questions,
            "num_questions": len(result.questions),
        },
    }
    write_trace("01_interview_round1", trace)

    # Assertions
    print(f"\n  ready={result.ready}, questions={len(result.questions)}")
    for i, q in enumerate(result.questions, 1):
        print(f"    {i}. {q}")

    if result.ready:
        print("\n  ⚠️  CONCERN: Marked ready after sparse Round 1 — might be too eager")
    if len(result.questions) == 0 and not result.ready:
        print("\n  ❌ BUG: No questions AND not ready — parsing issue?")
    if len(result.questions) > 0:
        print(f"\n  ✅ Generated {len(result.questions)} follow-up question(s)")

    return runner, result


def test_interview_round2():
    """Phase 2b: Second process_round() with richer transcript — should be ready or near-ready."""
    print("\n" + "=" * 70)
    print("TEST 2: Interview Round 2 (richer transcript, expect ready=True or few questions)")
    print("=" * 70)

    from telos_agent.interview import InterviewRunner

    runner = InterviewRunner(
        project_dir=PROJECT_DIR,
        agent_dir=AGENT_DIR,
    )

    start = time.time()
    result = runner.process_round(TRANSCRIPT_R2)
    elapsed = time.time() - start

    trace = {
        "test": "interview_round2",
        "transcript_length": len(TRANSCRIPT_R2),
        "elapsed_seconds": round(elapsed, 1),
        "result": {
            "ready": result.ready,
            "questions": result.questions,
            "num_questions": len(result.questions),
        },
    }
    write_trace("02_interview_round2", trace)

    print(f"\n  ready={result.ready}, questions={len(result.questions)}")
    for i, q in enumerate(result.questions, 1):
        print(f"    {i}. {q}")

    if result.ready:
        print("\n  ✅ Ready to proceed to planning")
    else:
        print(f"\n  ⚠️  Not ready yet — {len(result.questions)} more question(s)")

    return runner, result


def test_interview_force_ready():
    """Phase 2c: Force-proceed with no_more_questions=True."""
    print("\n" + "=" * 70)
    print("TEST 3: Interview Force Ready (no_more_questions=True)")
    print("=" * 70)

    from telos_agent.interview import InterviewRunner

    runner = InterviewRunner(
        project_dir=PROJECT_DIR,
        agent_dir=AGENT_DIR,
    )

    result = runner.process_round(TRANSCRIPT_R2, no_more_questions=True)

    assert result.ready is True, f"Expected ready=True, got {result.ready}"
    assert result.questions == [], f"Expected empty questions, got {result.questions}"
    assert runner.get_context() == TRANSCRIPT_R2, "get_context() should return transcript"

    print("  ✅ Force-ready works correctly (no Claude invocation)")
    return runner


def test_generate_plan():
    """Phase 3a: Generate plan from interview transcript."""
    print("\n" + "=" * 70)
    print("TEST 4: Generate Plan (transcript → plan.md)")
    print("=" * 70)

    from telos_agent.orchestrator import TelosOrchestrator

    orchestrator = TelosOrchestrator(
        project_dir=PROJECT_DIR,
        agent_dir=AGENT_DIR,
    )

    start = time.time()
    plan_path = orchestrator.generate_plan(TRANSCRIPT_R2)
    elapsed = time.time() - start

    plan_content = plan_path.read_text()

    trace = {
        "test": "generate_plan",
        "elapsed_seconds": round(elapsed, 1),
        "plan_path": str(plan_path),
        "plan_length_chars": len(plan_content),
        "plan_length_lines": len(plan_content.splitlines()),
        "plan_content": plan_content,
    }
    write_trace("03_generate_plan", trace)

    print(f"\n  Plan written to: {plan_path}")
    print(f"  Length: {len(plan_content)} chars, {len(plan_content.splitlines())} lines")

    # Quality checks
    issues = []
    plan_lower = plan_content.lower()

    # Does it reference the bakery?
    if "bakery" not in plan_lower and "sweet crumbs" not in plan_lower:
        issues.append("Plan doesn't mention the bakery — may be generic")

    # Does it have key sections?
    for section in ["north star", "architecture", "tech stack", "phase", "risk"]:
        if section not in plan_lower:
            issues.append(f"Missing expected section: '{section}'")

    # Does it mention ordering (core feature)?
    if "order" not in plan_lower:
        issues.append("Plan doesn't mention ordering — core feature missing")

    # Is it unreasonably short or long?
    if len(plan_content) < 500:
        issues.append(f"Plan is very short ({len(plan_content)} chars) — may be truncated")
    if len(plan_content) > 20000:
        issues.append(f"Plan is very long ({len(plan_content)} chars) — may be over-engineered")

    # Check if it respects the user's non-technical constraints
    if "credit card" in plan_lower and "venmo" not in plan_lower:
        issues.append("Plan includes credit cards but user explicitly said no")

    if issues:
        print("\n  ⚠️  Quality issues:")
        for issue in issues:
            print(f"    - {issue}")
    else:
        print("\n  ✅ Plan passes quality checks")

    # Print first 30 lines as preview
    lines = plan_content.splitlines()
    print(f"\n  --- Plan preview (first 30/{len(lines)} lines) ---")
    for line in lines[:30]:
        print(f"  | {line}")
    if len(lines) > 30:
        print(f"  | ... ({len(lines) - 30} more lines)")

    return plan_path


def test_generate_prds():
    """Phase 3b: Generate PRDs from plan.md."""
    print("\n" + "=" * 70)
    print("TEST 5: Generate PRDs (plan.md → prds/)")
    print("=" * 70)

    from telos_agent.orchestrator import TelosOrchestrator

    orchestrator = TelosOrchestrator(
        project_dir=PROJECT_DIR,
        agent_dir=AGENT_DIR,
    )

    start = time.time()
    prds_dir = orchestrator.generate_prds()
    elapsed = time.time() - start

    prd_files = sorted(prds_dir.glob("*.md"))

    prd_contents = {}
    for f in prd_files:
        prd_contents[f.name] = f.read_text()

    trace = {
        "test": "generate_prds",
        "elapsed_seconds": round(elapsed, 1),
        "prds_dir": str(prds_dir),
        "num_prds": len(prd_files),
        "prd_files": [f.name for f in prd_files],
        "prd_contents": prd_contents,
    }
    write_trace("04_generate_prds", trace)

    print(f"\n  PRDs directory: {prds_dir}")
    print(f"  Number of PRDs: {len(prd_files)}")

    issues = []

    if len(prd_files) == 0:
        issues.append("No PRD files created!")
    elif len(prd_files) == 1:
        issues.append("Only 1 PRD — plan wasn't actually split")
    elif len(prd_files) > 10:
        issues.append(f"Too many PRDs ({len(prd_files)}) — over-split")

    for f in prd_files:
        content = prd_contents[f.name]
        print(f"\n  📄 {f.name} ({len(content)} chars, {len(content.splitlines())} lines)")

        # Check naming convention
        if not f.name[0:2].isdigit():
            issues.append(f"{f.name}: Doesn't start with number prefix")

        # Check for checkboxes (acceptance criteria)
        checkboxes = content.count("- [ ]")
        if checkboxes == 0:
            issues.append(f"{f.name}: No acceptance criteria checkboxes (- [ ])")
        else:
            print(f"    Acceptance criteria: {checkboxes} items")

        # Preview first 10 lines
        for line in content.splitlines()[:10]:
            print(f"    | {line}")

    if issues:
        print("\n  ⚠️  Quality issues:")
        for issue in issues:
            print(f"    - {issue}")
    else:
        print("\n  ✅ PRDs pass quality checks")

    return prds_dir


def test_mcp_config_generation():
    """Verify MCP config generation for different phases."""
    print("\n" + "=" * 70)
    print("TEST 6: MCP Config Generation (unit test)")
    print("=" * 70)

    from telos_agent.mcp_config import generate_mcp_config

    # Interview phase: gemini only
    p = generate_mcp_config(AGENT_DIR, PROJECT_DIR, include_gemini=True)
    config = json.loads(p.read_text())
    assert "gemini-context" in config["mcpServers"]
    assert "reviewer" not in config["mcpServers"]
    print("  ✅ Interview config: gemini-context only")

    # Ralph phase: gemini + reviewer
    p = generate_mcp_config(AGENT_DIR, PROJECT_DIR, include_gemini=True, include_reviewer=True)
    config = json.loads(p.read_text())
    assert "gemini-context" in config["mcpServers"]
    assert "reviewer" in config["mcpServers"]
    print("  ✅ Ralph config: gemini-context + reviewer")

    # Verify reviewer env var points to project dir
    reviewer_env = config["mcpServers"]["reviewer"]["env"]
    assert str(PROJECT_DIR) in reviewer_env["VERDICT_PATH"]
    print("  ✅ Reviewer VERDICT_PATH points to project dir")

    # Verify gemini context dir defaults to project dir
    gemini_env = config["mcpServers"]["gemini-context"]["env"]
    assert str(PROJECT_DIR) in gemini_env["CONTEXT_DIR"]
    print("  ✅ Gemini CONTEXT_DIR defaults to project dir")

    # Custom context dir
    custom_ctx = Path("/tmp/custom-ctx")
    p = generate_mcp_config(AGENT_DIR, PROJECT_DIR, context_dir=custom_ctx, include_gemini=True)
    config = json.loads(p.read_text())
    assert str(custom_ctx) in config["mcpServers"]["gemini-context"]["env"]["CONTEXT_DIR"]
    print("  ✅ Custom context_dir propagates correctly")


def test_ralph_machinery():
    """Test Ralph loop setup without running a full iteration."""
    print("\n" + "=" * 70)
    print("TEST 7: Ralph Loop Machinery (setup, no execution)")
    print("=" * 70)

    from telos_agent.ralph import RalphLoop

    loop = RalphLoop(
        project_dir=PROJECT_DIR,
        agent_dir=AGENT_DIR,
        context_dir=None,
        max_iterations=3,
    )

    # Verify paths (resolve PROJECT_DIR for macOS /tmp → /private/tmp)
    resolved_project = PROJECT_DIR.resolve()
    assert loop.prds_dir == resolved_project / "prds"
    assert loop.verdict_path == resolved_project / "verdict.json"
    assert loop.progress_path == resolved_project / "progress.txt"
    print("  ✅ Paths configured correctly")

    # Verify agent definitions can be copied
    loop._copy_agent_definitions()
    agents_dest = PROJECT_DIR / ".claude" / "agents"
    agent_files = list(agents_dest.glob("*.md"))
    assert len(agent_files) > 0, "No agent definitions copied"
    print(f"  ✅ Copied {len(agent_files)} agent definition(s): {[f.name for f in agent_files]}")

    # Verify MCP config is generated with both servers
    # (we can't call _generate_mcp_config anymore — it's removed)
    # Instead verify the loop would use generate_mcp_config from mcp_config.py
    from telos_agent.mcp_config import generate_mcp_config
    mcp_path = generate_mcp_config(
        AGENT_DIR, PROJECT_DIR, include_gemini=True, include_reviewer=True
    )
    config = json.loads(mcp_path.read_text())
    assert "gemini-context" in config["mcpServers"]
    assert "reviewer" in config["mcpServers"]
    print("  ✅ MCP config includes gemini-context and reviewer")

    # Verify build prompt exists
    assert loop.build_prompt.exists(), f"Build prompt not found at {loop.build_prompt}"
    print(f"  ✅ Build prompt exists: {loop.build_prompt}")

    # Verify orchestrator prompt exists
    assert loop.orchestrator_prompt.exists()
    print(f"  ✅ Orchestrator prompt exists: {loop.orchestrator_prompt}")


def test_backwards_compat():
    """Verify legacy APIs still work."""
    print("\n" + "=" * 70)
    print("TEST 8: Backwards Compatibility")
    print("=" * 70)

    from telos_agent.interview import InterviewRunner

    runner = InterviewRunner(project_dir=PROJECT_DIR, agent_dir=AGENT_DIR)

    # Legacy get_context returns list when using ask_agent path
    # (we can't actually call ask_agent without Claude, but we can test the flow)
    ctx = runner.get_context()
    assert isinstance(ctx, list), f"Legacy get_context should return list, got {type(ctx)}"
    print("  ✅ Legacy get_context() returns list (no transcript set)")

    # After process_round, get_context returns string
    runner.process_round("test", no_more_questions=True)
    ctx = runner.get_context()
    assert isinstance(ctx, str), f"New get_context should return str, got {type(ctx)}"
    print("  ✅ New get_context() returns string (transcript set)")

    # Orchestrator still has generate_prd
    from telos_agent.orchestrator import TelosOrchestrator
    orch = TelosOrchestrator(project_dir=PROJECT_DIR, agent_dir=AGENT_DIR)
    assert hasattr(orch, "generate_prd"), "generate_prd missing"
    assert hasattr(orch, "generate_plan"), "generate_plan missing"
    assert hasattr(orch, "generate_prds"), "generate_prds missing"
    assert hasattr(orch, "plan_and_execute"), "plan_and_execute missing"
    print("  ✅ All expected methods exist on TelosOrchestrator")

    # run() accepts both transcript and questions params
    import inspect
    sig = inspect.signature(orch.run)
    assert "transcript" in sig.parameters
    assert "questions" in sig.parameters
    print("  ✅ run() accepts both transcript and questions params")


# ── Main ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    tests = [
        ("Unit: MCP config generation", test_mcp_config_generation),
        ("Unit: Ralph machinery", test_ralph_machinery),
        ("Unit: Backwards compat", test_backwards_compat),
        ("Unit: Force ready", test_interview_force_ready),
        ("Integration: Interview Round 1", test_interview_round1),
        ("Integration: Interview Round 2", test_interview_round2),
        ("Integration: Generate Plan", test_generate_plan),
        ("Integration: Generate PRDs", test_generate_prds),
    ]

    # Check if user wants only unit tests (fast) or full integration
    only_unit = "--unit-only" in sys.argv
    only_integration = "--integration-only" in sys.argv

    results = []
    for name, fn in tests:
        is_unit = name.startswith("Unit:")
        if only_unit and not is_unit:
            continue
        if only_integration and is_unit:
            continue

        try:
            fn()
            results.append((name, "PASS", None))
        except Exception as e:
            tb = traceback.format_exc()
            results.append((name, "FAIL", str(e)))
            print(f"\n  ❌ FAILED: {e}")
            print(f"  {tb}")

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    for name, status, error in results:
        icon = "✅" if status == "PASS" else "❌"
        suffix = f" — {error}" if error else ""
        print(f"  {icon} {name}{suffix}")

    passed = sum(1 for _, s, _ in results if s == "PASS")
    total = len(results)
    print(f"\n  {passed}/{total} tests passed")

    if any(s == "FAIL" for _, s, _ in results):
        sys.exit(1)
