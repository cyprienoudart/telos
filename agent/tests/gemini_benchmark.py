"""
Benchmark the FastEmbed → ChromaDB → LLM pipeline across projects of different sizes.

For each project, runs 14 generic questions through the full answer_question()
pipeline and prints every answer so you can assess quality alongside timing.

Usage:
    python tests/gemini_benchmark.py
"""

from __future__ import annotations

import os
import sys
import textwrap
import time
from pathlib import Path
from statistics import mean

# Ensure the package root is on sys.path for standalone invocation.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from telos_agent.mcp.gemini import pipeline, settings
from telos_agent.mcp.gemini import store
from telos_agent.mcp.gemini import chunker

# ---------------------------------------------------------------------------
# Tee stdout → file
# ---------------------------------------------------------------------------

_OUTPUT_FILE = Path(__file__).parent / "benchmark_results.txt"


class _Tee:
    def __init__(self, stream, path: Path):
        self._stream = stream
        self._file   = path.open("w", encoding="utf-8")

    def write(self, data: str) -> int:
        self._stream.write(data)
        self._file.write(data)
        return len(data)

    def flush(self) -> None:
        self._stream.flush()
        self._file.flush()

    def __getattr__(self, name):
        return getattr(self._stream, name)


sys.stdout = _Tee(sys.stdout, _OUTPUT_FILE)
print(f"  (output also saved to {_OUTPUT_FILE})")

# ---------------------------------------------------------------------------
# Projects to benchmark
# ---------------------------------------------------------------------------
# Set BENCHMARK_PROJECTS as colon-separated "label=path" pairs, e.g.:
#   BENCHMARK_PROJECTS="my-app=/path/to/app:other=/path/to/other"
# Falls back to the bundled context/ sample data.

_DEFAULT_CONTEXT = Path(__file__).parent.parent / "context"


def _parse_projects() -> list[tuple[str, Path]]:
    raw = os.environ.get("BENCHMARK_PROJECTS", "").strip()
    if not raw:
        return [("context (bundled sample)", _DEFAULT_CONTEXT)]
    projects: list[tuple[str, Path]] = []
    for entry in raw.split(":"):
        if "=" not in entry:
            continue
        label, path_str = entry.split("=", 1)
        projects.append((label.strip(), Path(path_str.strip())))
    return projects or [("context (bundled sample)", _DEFAULT_CONTEXT)]


PROJECTS = _parse_projects()

# ---------------------------------------------------------------------------
# Questions (generic — work across any codebase)
# ---------------------------------------------------------------------------

QUESTIONS: list[str] = [
    "What does this project do and what problem does it solve?",
    "What programming languages and frameworks are used?",
    "What are the main external dependencies?",
    "How do you install and run this project?",
    "What is the folder or module structure?",
    "How is authentication or access control handled?",
    "What database or storage technology is used?",
    "How are errors and exceptions handled?",
    "What tests exist and how do you run them?",
    "What environment variables or config files are required?",
    "What are the main classes or components and what do they do?",
    "How is the core data-processing or inference pipeline implemented?",
    # Multimodal-specific (hit whiteboard.jpg in telos/context; 'not found' elsewhere)
    "What is shown on the whiteboard or diagram in the context store?",
    "Describe the system architecture diagram including all components and connections.",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _corpus_stats() -> tuple[int, int, int]:
    chunks = chunker.build_all_chunks()
    total_words = sum(len(c.text.split()) for c in chunks)
    return len({c.source for c in chunks}), len(chunks), total_words


def _fmt_ms(seconds: float) -> str:
    ms = seconds * 1000
    return f"{ms/1000:.2f} s" if ms >= 1000 else f"{ms:.0f} ms"


def _wrap(text: str, width: int = 66, indent: str = "       ") -> str:
    return textwrap.fill(text, width=width, subsequent_indent=indent)


# ---------------------------------------------------------------------------
# Main benchmark loop
# ---------------------------------------------------------------------------

print(f"\n{'═' * 70}")
print(f"  FastEmbed → ChromaDB → LLM  quality + timing benchmark")
print(f"  {len(PROJECTS)} projects · {len(QUESTIONS)} questions each")
print(f"{'═' * 70}")

summary_rows: list[tuple[str, int, int, int, float, float, float]] = []

for label, project_path in PROJECTS:

    print(f"\n{'─' * 70}")
    print(f"  {label}")
    print(f"  {project_path}")
    print(f"{'─' * 70}")

    if not project_path.exists():
        print(f"  [SKIP] path does not exist")
        continue

    settings.set_base_dir(project_path)

    # ── Corpus stats ────────────────────────────────────────────────────────
    print("  Scanning corpus...", end="", flush=True)
    t0 = time.perf_counter()
    file_count, chunk_count, total_words = _corpus_stats()
    print(f"\r  Corpus: {file_count:,} files · {chunk_count:,} chunks · {total_words:,} words"
          f"  ({_fmt_ms(time.perf_counter() - t0)})")

    # ── ChromaDB index (warm if cached, cold on first run) ───────────────────
    print("  Loading ChromaDB index...", end="", flush=True)
    t0 = time.perf_counter()
    store.warm_index()
    build_time = time.perf_counter() - t0
    print(f"\r  ChromaDB index: {_fmt_ms(build_time):<10}  {chunk_count:,} chunks")

    # ── Q&A loop ────────────────────────────────────────────────────────────
    print()
    llm_times: list[float] = []

    for i, q in enumerate(QUESTIONS):
        print(f"  Q{i+1:>2}: {q}")
        t0 = time.perf_counter()
        answer = pipeline.answer_question(q)
        elapsed = time.perf_counter() - t0
        llm_times.append(elapsed)
        print(f"   A: {_wrap(answer)}")
        print(f"      ⏱ {_fmt_ms(elapsed)}")
        print()

    avg_t = mean(llm_times)
    min_t = min(llm_times)
    max_t = max(llm_times)
    print(f"  Timing — min {_fmt_ms(min_t)}  ·  avg {_fmt_ms(avg_t)}  ·  max {_fmt_ms(max_t)}")

    summary_rows.append((label, file_count, chunk_count, total_words, build_time, avg_t, max_t))

# ---------------------------------------------------------------------------
# Summary table
# ---------------------------------------------------------------------------

print(f"\n\n{'═' * 70}")
print(f"  Summary")
print(f"{'═' * 70}")
print(f"  {'Project':<26}  {'Files':>6}  {'Chunks':>7}  {'Words':>9}  {'Build':>8}  {'Avg':>7}  {'Max':>7}")
print(f"  {'─'*26}  {'─'*6}  {'─'*7}  {'─'*9}  {'─'*8}  {'─'*7}  {'─'*7}")

for label, files, chunks, words, build, avg_r, max_r in summary_rows:
    print(
        f"  {label:<26}  {files:>6,}  {chunks:>7,}  {words:>9,}"
        f"  {_fmt_ms(build):>8}  {_fmt_ms(avg_r):>7}  {_fmt_ms(max_r):>7}"
    )

print(f"{'═' * 70}\n")
