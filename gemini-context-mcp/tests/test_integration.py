"""
Integration test for the full gemini-context-mcp stack.

Tests all three outer MCP tools by importing them directly from server.py —
no running server needed. Covers the complete path:

    server tool → agent loop → tools.py → OpenRouter API → response

Requires OPENROUTER_API_KEY in .env (or environment).
Run from gemini-context-mcp/:

    python tests/test_integration.py
    # or with PYTHONIOENCODING=utf-8 on Windows terminals
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Ensure project root is on the path when run directly
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()


# ── helpers ────────────────────────────────────────────────────────────────────

_PASS = "[PASS]"
_FAIL = "[FAIL]"
_results: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    status = _PASS if condition else _FAIL
    print(f"  {status} {name}")
    if detail and not condition:
        print(f"         → {detail}")
    _results.append((name, condition, detail))


def section(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


# ── import server tools (no server process needed) ─────────────────────────────

from server import get_context_file, list_context, query_context


# ── Test 1: list_context (no API call) ────────────────────────────────────────

section("1 · list_context  (filesystem only — no API)")

t0 = time.perf_counter()
listing = list_context()
elapsed = time.perf_counter() - t0

print(f"\n  Output ({elapsed*1000:.0f} ms):\n")
for line in listing.splitlines():
    print(f"    {line}")

print()
check("returns a non-empty string",        isinstance(listing, str) and len(listing) > 0)
check("does not start with ERROR",         not listing.startswith("ERROR"))
check("contains docs/ files",              "docs/" in listing)
check("contains codebase/ files",          "codebase/" in listing)
check("contains whiteboard.jpg",           "whiteboard.jpg" in listing)
check("no .venv or __pycache__ entries",   ".venv" not in listing and "__pycache__" not in listing)


# ── Test 2: get_context_file — text file ──────────────────────────────────────

section("2 · get_context_file  (text: docs/team.md)")

t0 = time.perf_counter()
team = get_context_file("docs/team.md")
elapsed = time.perf_counter() - t0

print(f"\n  Output ({elapsed*1000:.0f} ms, first 300 chars):\n")
print(f"    {team[:300].replace(chr(10), chr(10) + '    ')}")
print()

check("returns a string",                  isinstance(team, str))
check("does not start with ERROR",         not team.startswith("ERROR"))
check("contains team content",             any(kw in team for kw in ["Tech Lead", "Engineer", "Maya", "Lucas"]))


# ── Test 3: get_context_file — image (vision pipeline) ────────────────────────

section("3 · get_context_file  (image: docs/whiteboard.jpg)")

t0 = time.perf_counter()
vision = get_context_file("docs/whiteboard.jpg")
elapsed = time.perf_counter() - t0

print(f"\n  Output ({elapsed*1000:.0f} ms, first 400 chars):\n")
print(f"    {vision[:400].replace(chr(10), chr(10) + '    ')}")
print()

check("returns a string",                  isinstance(vision, str))
check("does not start with ERROR",         not vision.startswith("ERROR"))
check("non-trivial length (>100 chars)",   len(vision) > 100)
check("describes architecture or agents",  any(kw in vision.lower() for kw in
                                               ["agent", "orchestrat", "claude", "gemini", "diagram", "architecture"]))


# ── Test 4: get_context_file — focus parameter ────────────────────────────────

section("4 · get_context_file  (text with focus: priorities.md → P0 bugs)")

t0 = time.perf_counter()
focused = get_context_file("docs/priorities.md", focus="P0 critical bugs only")
elapsed = time.perf_counter() - t0

print(f"\n  Output ({elapsed*1000:.0f} ms, first 400 chars):\n")
print(f"    {focused[:400].replace(chr(10), chr(10) + '    ')}")
print()

check("returns a string",                  isinstance(focused, str))
check("does not start with ERROR",         not focused.startswith("ERROR"))
check("mentions AUTH-112 or INFRA-89",     "AUTH-112" in focused or "INFRA-89" in focused)


# ── Test 5: query_context — full agentic loop ─────────────────────────────────

section("5 · query_context  (full agentic loop)")

QUESTION = "Who is the tech lead and what are the two P0 bugs currently open?"

print(f"\n  Question: {QUESTION}\n")
t0 = time.perf_counter()
answer = query_context(QUESTION)
elapsed = time.perf_counter() - t0

print(f"  Answer ({elapsed:.1f} s):\n")
for line in answer.splitlines():
    print(f"    {line}")
print()

check("returns a string",                  isinstance(answer, str))
check("does not start with ERROR",         not answer.startswith("ERROR"))
check("names the tech lead (Maya Chen)",   "Maya" in answer or "Chen" in answer)
check("mentions AUTH-112",                 "AUTH-112" in answer)
check("mentions INFRA-89",                 "INFRA-89" in answer)


# ── Test 6: error handling ─────────────────────────────────────────────────────

section("6 · error handling  (bad paths, never raises)")

for label, fn, args in [
    ("list_context on missing tool",   get_context_file, ("does_not_exist.txt",)),
    ("path traversal attempt",         get_context_file, ("../../etc/passwd",)),
]:
    try:
        result = fn(*args)
        check(label, result.startswith("ERROR:"), f"expected ERROR:, got: {result[:80]}")
    except Exception as exc:
        check(label, False, f"raised {type(exc).__name__}: {exc}")


# ── Summary ────────────────────────────────────────────────────────────────────

passed = sum(1 for _, ok, _ in _results if ok)
total  = len(_results)
failed = total - passed

print(f"\n{'═' * 60}")
print(f"  Results: {passed}/{total} passed", end="")
if failed:
    print(f"  ({failed} FAILED)")
    print()
    for name, ok, detail in _results:
        if not ok:
            print(f"  {_FAIL} {name}")
            if detail:
                print(f"       → {detail}")
else:
    print("  — all good")
print(f"{'═' * 60}\n")

sys.exit(0 if failed == 0 else 1)
