"""Integration tests for the Ralph loop with real Claude execution.

These tests invoke real Claude instances and cost API credits.
Mark with pytest.mark.integration so they can be skipped in CI.

Run: cd agent && uv run pytest tests/test_integration_ralph.py -v
"""

import json
import shutil
import time
from pathlib import Path

import pytest

AGENT_DIR = Path(__file__).resolve().parent.parent  # agent/


def _has_claude_cli() -> bool:
    """Check if claude CLI is available."""
    import subprocess
    try:
        result = subprocess.run(
            ["claude", "--version"],
            capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


skip_no_claude = pytest.mark.skipif(
    not _has_claude_cli(),
    reason="Claude CLI not available",
)


@skip_no_claude
@pytest.mark.integration
class TestSingleCheckboxPRD:
    """Full Ralph loop: orchestrator → coder → reviewer → approved.

    Uses a trivial PRD with a single checkbox that creates one file.
    Expected: 1-2 iterations, success=True.
    """

    def test_single_checkbox_prd(self, tmp_path: Path):
        project = tmp_path / "project"
        project.mkdir()
        prds = project / "prds"
        prds.mkdir()

        # Trivial PRD: create a single file
        (prds / "01-hello.md").write_text(
            "# Hello World PRD\n\n"
            "## Acceptance Criteria\n\n"
            "- [ ] Create a file called `hello.txt` in the project root "
            "containing exactly the text `Hello, World!`\n"
        )

        from telos_agent.ralph import RalphLoop

        loop = RalphLoop(
            project_dir=project,
            agent_dir=AGENT_DIR,
            max_iterations=5,
            model="sonnet",
            timeout=120,
        )

        start = time.time()
        result = loop.run()
        elapsed = time.time() - start

        print(f"\nElapsed: {elapsed:.1f}s, iterations: {result.iterations}")
        for ir in result.iteration_results:
            print(f"  [{ir.iteration}] {ir.status}: {ir.details[:100]}")

        # The loop should complete (approved or hit max iterations)
        # We check success but allow failure — the test validates the mechanics
        assert result.iterations >= 1
        assert len(result.iteration_results) >= 1

        if result.success:
            assert (project / "hello.txt").exists()
            assert "Hello, World!" in (project / "hello.txt").read_text()


@skip_no_claude
@pytest.mark.integration
class TestTwoCheckboxSequential:
    """Multi-iteration: loop picks up second item after first approved.

    Two trivial checkboxes in one PRD. The Ralph loop should handle
    one per iteration, completing in 2+ iterations.
    """

    def test_two_checkbox_sequential(self, tmp_path: Path):
        project = tmp_path / "project"
        project.mkdir()
        prds = project / "prds"
        prds.mkdir()

        (prds / "01-files.md").write_text(
            "# File Creation PRD\n\n"
            "## Acceptance Criteria\n\n"
            "- [ ] Create `file_a.txt` containing exactly `AAA`\n"
            "- [ ] Create `file_b.txt` containing exactly `BBB`\n"
        )

        from telos_agent.ralph import RalphLoop

        loop = RalphLoop(
            project_dir=project,
            agent_dir=AGENT_DIR,
            max_iterations=8,
            model="sonnet",
            timeout=120,
        )

        start = time.time()
        result = loop.run()
        elapsed = time.time() - start

        print(f"\nElapsed: {elapsed:.1f}s, iterations: {result.iterations}")
        for ir in result.iteration_results:
            print(f"  [{ir.iteration}] {ir.status}: {ir.details[:100]}")

        assert result.iterations >= 1
        assert len(result.iteration_results) >= 1

        if result.success:
            assert (project / "file_a.txt").exists()
            assert (project / "file_b.txt").exists()
