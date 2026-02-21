"""
Integration test for the gemini-context-mcp stack.

Tests both public tools by importing from server.py directly — no running
server needed. Covers the complete path:

    server tool → agent → context loader → OpenRouter → response

Requires OPENROUTER_API_KEY in .env.
Run from gemini-context-mcp/:

    python tests/test_integration.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

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


# ── import server tools ────────────────────────────────────────────────────────

from server import answer_question, summarize


# ── Test 1: summarize() ───────────────────────────────────────────────────────

section("1 · summarize()  — 15-bullet overview")

t0 = time.perf_counter()
summary = summarize()
t1 = time.perf_counter()
elapsed1 = t1 - t0

print(f"\n  Output ({elapsed1:.1f} s):\n")
for line in summary.splitlines():
    print(f"    {line}")
print()

bullets = [l.strip() for l in summary.splitlines() if l.strip().startswith(("-", "•", "*", "–")) or
           (len(l.strip()) > 2 and l.strip()[0].isdigit() and l.strip()[1] in ".):")]

check("returns a string",                isinstance(summary, str))
check("does not start with ERROR",       not summary.startswith("ERROR"))
check("non-trivial length (>200 chars)", len(summary) > 200)
check("~15 bullet points found",         len(bullets) >= 12,
      f"found {len(bullets)} bullets — expected ~15")
check("under 10 seconds",               elapsed1 < 10,
      f"took {elapsed1:.1f} s")


# ── Test 2: summarize() cache — second call must be instant ──────────────────

section("2 · summarize()  — cache (second call)")

t0 = time.perf_counter()
summary2 = summarize()
elapsed2 = time.perf_counter() - t0

print(f"\n  Second call: {elapsed2*1000:.0f} ms  (first was {elapsed1:.1f} s)\n")

check("returns identical result",  summary2 == summary)
check("cache hit is instant (<100 ms)", elapsed2 < 0.1,
      f"took {elapsed2*1000:.0f} ms — cache may not be working")


# ── Test 3: answer_question() — factual query ─────────────────────────────────

section("3 · answer_question()  — factual query")

q1 = "Who is the tech lead of the project?"
print(f"\n  Question: {q1}")

t0 = time.perf_counter()
a1 = answer_question(q1)
elapsed3 = time.perf_counter() - t0

print(f"  Answer ({elapsed3:.1f} s): {a1}\n")

check("returns a string",              isinstance(a1, str))
check("does not start with ERROR",     not a1.startswith("ERROR"))
check("mentions Maya Chen",            "Maya" in a1 or "Chen" in a1,
      f"got: {a1[:120]}")
check("under 10 seconds",             elapsed3 < 10,
      f"took {elapsed3:.1f} s")
check("plain prose (no markdown headers)", "##" not in a1 and "```" not in a1)


# ── Test 4: answer_question() — bug / priority query ─────────────────────────

section("4 · answer_question()  — priority / bug query")

q2 = "What are the most urgent problems the team is working on right now?"
print(f"\n  Question: {q2}")

t0 = time.perf_counter()
a2 = answer_question(q2)
elapsed4 = time.perf_counter() - t0

print(f"  Answer ({elapsed4:.1f} s): {a2}\n")

check("returns a string",          isinstance(a2, str))
check("does not start with ERROR", not a2.startswith("ERROR"))
check("non-trivial length",        len(a2) > 50)
check("mentions a known issue",    any(kw in a2 for kw in
                                       ["token", "database", "pool", "auth", "refresh", "connection"]),
      f"got: {a2[:120]}")
check("under 10 seconds",         elapsed4 < 10, f"took {elapsed4:.1f} s")


# ── Test 5: answer_question() — question not in context ──────────────────────

section("5 · answer_question()  — out-of-scope question")

q3 = "What is the weather in Paris today?"
print(f"\n  Question: {q3}")

t0 = time.perf_counter()
a3 = answer_question(q3)
elapsed5 = time.perf_counter() - t0

print(f"  Answer ({elapsed5:.1f} s): {a3}\n")

check("returns a string",          isinstance(a3, str))
check("does not start with ERROR", not a3.startswith("ERROR"))
check("admits it doesn't know",    any(kw in a3.lower() for kw in
                                       ["not", "don't", "cannot", "no information", "knowledge base"]),
      f"got: {a3}")


# ── Test 6: callable directly from Python (no MCP) ───────────────────────────

section("6 · direct Python import  (no MCP layer)")

import agent as _agent

t0 = time.perf_counter()
direct_summary = _agent.summarize()
elapsed6 = time.perf_counter() - t0

t0 = time.perf_counter()
direct_answer = _agent.answer_question("Who is on the on-call rotation this week?")
elapsed7 = time.perf_counter() - t0

print(f"\n  agent.summarize()       → {elapsed6*1000:.0f} ms (cached)")
print(f"  agent.answer_question() → {elapsed7:.1f} s")
print(f"  answer: {direct_answer[:200]}\n")

check("agent.summarize() returns string",       isinstance(direct_summary, str))
check("agent.answer_question() returns string", isinstance(direct_answer, str))
check("answer mentions a team member",          any(n in direct_answer for n in
                                                    ["Lucas", "Priya", "Tomás", "Sam", "Maya"]),
      f"got: {direct_answer[:120]}")


# ── Summary ────────────────────────────────────────────────────────────────────

passed = sum(1 for _, ok, _ in _results if ok)
total  = len(_results)
failed = total - passed

print(f"\n{'═' * 60}")
print(f"  Results: {passed}/{total} passed", end="")
if failed:
    print(f"  ({failed} FAILED)\n")
    for name, ok, detail in _results:
        if not ok:
            print(f"  {_FAIL} {name}")
            if detail:
                print(f"       → {detail}")
else:
    print("  — all good")
print(f"{'═' * 60}\n")

sys.exit(0 if failed == 0 else 1)
