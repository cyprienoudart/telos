"""Unit tests for ralph.py — iteration logic with mocked invoke_claude.

This is the BIGGEST gap in test coverage. Tests the full Ralph loop
including approval, denial, escalation, timeout, and error paths.
"""

import json
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock, call

import pytest

from telos_agent.ralph import RalphLoop, RalphResult, IterationResult


def _make_loop(tmp_path: Path, agent_dir: Path, max_iterations: int = 10) -> RalphLoop:
    """Create a RalphLoop with proper directory structure."""
    project = tmp_path / "project"
    project.mkdir(exist_ok=True)
    (project / "prds").mkdir(exist_ok=True)
    (project / "prds" / "01-main.md").write_text("# PRD\n- [ ] Build thing\n")

    return RalphLoop(
        project_dir=project,
        agent_dir=agent_dir,
        max_iterations=max_iterations,
    )


class TestFirstIterationApproved:
    """Golden path: 1 iteration → approved → success."""

    def test_first_iteration_approved(self, tmp_path: Path, agent_dir: Path):
        loop = _make_loop(tmp_path, agent_dir, max_iterations=5)

        def mock_invoke(**kwargs):
            # Write approved verdict
            verdict = {"approved": True, "summary": "All good"}
            loop.verdict_path.write_text(json.dumps(verdict))
            # Return output with COMPLETE promise
            return MagicMock(
                stdout=f"Done. {RalphLoop.PROMISE_MARKER}",
                stderr="",
                returncode=0,
                ok=True,
            )

        with patch("telos_agent.ralph.invoke_claude", side_effect=mock_invoke):
            result = loop.run()

        assert result.success is True
        assert result.iterations == 1
        assert result.final_verdict["approved"] is True


class TestDenialThenApproval:
    """Retry flow: denied → approved on 2nd try."""

    def test_denial_then_approval(self, tmp_path: Path, agent_dir: Path):
        loop = _make_loop(tmp_path, agent_dir, max_iterations=5)
        call_count = 0

        def mock_invoke(**kwargs):
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                # First call: denied
                verdict = {"approved": False, "reason": "Tests failing"}
                loop.verdict_path.write_text(json.dumps(verdict))
                return MagicMock(stdout="Tried my best", stderr="", returncode=0, ok=True)
            else:
                # Second call: approved
                verdict = {"approved": True, "summary": "Fixed"}
                loop.verdict_path.write_text(json.dumps(verdict))
                return MagicMock(
                    stdout=f"Fixed. {RalphLoop.PROMISE_MARKER}",
                    stderr="", returncode=0, ok=True,
                )

        with patch("telos_agent.ralph.invoke_claude", side_effect=mock_invoke):
            result = loop.run()

        assert result.success is True
        assert result.iterations == 2
        assert len(result.iteration_results) == 2
        assert result.iteration_results[0].status == "denied"
        assert result.iteration_results[1].status == "approved"


class TestMaxIterationsExhausted:
    """Loop exits with success=False at limit."""

    def test_max_iterations_exhausted(self, tmp_path: Path, agent_dir: Path):
        loop = _make_loop(tmp_path, agent_dir, max_iterations=3)

        def mock_invoke(**kwargs):
            # Always denied
            verdict = {"approved": False, "reason": "Still broken"}
            loop.verdict_path.write_text(json.dumps(verdict))
            return MagicMock(stdout="Tried", stderr="", returncode=0, ok=True)

        with patch("telos_agent.ralph.invoke_claude", side_effect=mock_invoke):
            result = loop.run()

        assert result.success is False
        assert result.iterations == 3
        assert "Max iterations" in result.error


class TestEscalationAt3Denials:
    """Escalation suffix injected after 3 consecutive denials."""

    def test_escalation_at_3_denials(self, tmp_path: Path, agent_dir: Path):
        loop = _make_loop(tmp_path, agent_dir, max_iterations=5)
        prompts_seen = []

        def mock_invoke(prompt, **kwargs):
            prompts_seen.append(prompt)
            verdict = {"approved": False, "reason": "Still wrong"}
            loop.verdict_path.write_text(json.dumps(verdict))
            return MagicMock(stdout="Tried", stderr="", returncode=0, ok=True)

        with patch("telos_agent.ralph.invoke_claude", side_effect=mock_invoke):
            loop.run()

        # First 3 iterations: no escalation suffix
        for i in range(3):
            assert "ESCALATION" not in prompts_seen[i], f"Iteration {i+1} shouldn't have escalation"

        # 4th iteration onwards: escalation suffix present
        assert "ESCALATION" in prompts_seen[3], "Iteration 4 should have escalation"


class TestNoVerdictFile:
    """Missing verdict.json → status "no-verdict", continues."""

    def test_no_verdict_file(self, tmp_path: Path, agent_dir: Path):
        loop = _make_loop(tmp_path, agent_dir, max_iterations=2)

        def mock_invoke(**kwargs):
            # Don't write verdict.json at all
            return MagicMock(stdout="Did stuff", stderr="", returncode=0, ok=True)

        with patch("telos_agent.ralph.invoke_claude", side_effect=mock_invoke):
            result = loop.run()

        assert result.success is False
        assert all(ir.status == "no-verdict" for ir in result.iteration_results)


class TestMalformedVerdict:
    """Invalid JSON in verdict.json → safe fallback."""

    def test_malformed_verdict(self, tmp_path: Path, agent_dir: Path):
        loop = _make_loop(tmp_path, agent_dir, max_iterations=2)

        def mock_invoke(**kwargs):
            loop.verdict_path.write_text("not valid json {{{")
            return MagicMock(stdout="Done", stderr="", returncode=0, ok=True)

        with patch("telos_agent.ralph.invoke_claude", side_effect=mock_invoke):
            result = loop.run()

        assert result.success is False
        assert all(ir.status == "no-verdict" for ir in result.iteration_results)


class TestTimeoutHandling:
    """TimeoutExpired → status "timeout", continues."""

    def test_timeout_handling(self, tmp_path: Path, agent_dir: Path):
        loop = _make_loop(tmp_path, agent_dir, max_iterations=2)

        def mock_invoke(**kwargs):
            raise subprocess.TimeoutExpired(cmd="claude", timeout=900)

        with patch("telos_agent.ralph.invoke_claude", side_effect=mock_invoke):
            result = loop.run()

        assert result.success is False
        assert all(ir.status == "timeout" for ir in result.iteration_results)


class TestErrorExitCode:
    """Non-zero exit → status "error", continues."""

    def test_error_exit_code(self, tmp_path: Path, agent_dir: Path):
        loop = _make_loop(tmp_path, agent_dir, max_iterations=2)

        def mock_invoke(**kwargs):
            return MagicMock(stdout="", stderr="segfault", returncode=1, ok=False)

        with patch("telos_agent.ralph.invoke_claude", side_effect=mock_invoke):
            result = loop.run()

        assert result.success is False
        assert all(ir.status == "error" for ir in result.iteration_results)


class TestApprovedWithoutPromise:
    """Verdict approved but no <promise>COMPLETE</promise> → partial."""

    def test_approved_without_promise(self, tmp_path: Path, agent_dir: Path):
        loop = _make_loop(tmp_path, agent_dir, max_iterations=2)

        def mock_invoke(**kwargs):
            verdict = {"approved": True, "summary": "Partial work done"}
            loop.verdict_path.write_text(json.dumps(verdict))
            # No PROMISE_MARKER in stdout
            return MagicMock(stdout="Some work done", stderr="", returncode=0, ok=True)

        with patch("telos_agent.ralph.invoke_claude", side_effect=mock_invoke):
            result = loop.run()

        assert result.success is False
        assert all(ir.status == "approved-partial" for ir in result.iteration_results)


class TestCopiesAgentDefinitions:
    """Config agents copied to project/.claude/agents/."""

    def test_copies_agent_definitions(self, tmp_path: Path, agent_dir: Path):
        loop = _make_loop(tmp_path, agent_dir)
        loop._copy_agent_definitions()

        dest = loop.agents_dest
        assert dest.exists()
        copied = [f.name for f in dest.glob("*.md")]
        # Should have at least the known agent files
        assert len(copied) > 0
        # Check specific known agents from config/agents/
        source_agents = [f.name for f in (agent_dir / "config" / "agents").glob("*.md")]
        for name in source_agents:
            assert name in copied, f"Agent definition {name} not copied"


class TestProgressAppended:
    """progress.txt grows with each iteration."""

    def test_progress_appended(self, tmp_path: Path, agent_dir: Path):
        loop = _make_loop(tmp_path, agent_dir, max_iterations=3)

        def mock_invoke(**kwargs):
            verdict = {"approved": False, "reason": "Not done"}
            loop.verdict_path.write_text(json.dumps(verdict))
            return MagicMock(stdout="Tried", stderr="", returncode=0, ok=True)

        with patch("telos_agent.ralph.invoke_claude", side_effect=mock_invoke):
            loop.run()

        progress = loop.progress_path.read_text()
        assert progress.count("## Iteration") == 3
        assert "denied" in progress


class TestSeedsAgentsMd:
    """AGENTS.md created from template on first run."""

    def test_seeds_agents_md(self, tmp_path: Path, agent_dir: Path):
        loop = _make_loop(tmp_path, agent_dir, max_iterations=1)
        # Ensure no AGENTS.md exists
        loop.agents_md_path.unlink(missing_ok=True)

        def mock_invoke(**kwargs):
            verdict = {"approved": False, "reason": "nope"}
            loop.verdict_path.write_text(json.dumps(verdict))
            return MagicMock(stdout="x", stderr="", returncode=0, ok=True)

        with patch("telos_agent.ralph.invoke_claude", side_effect=mock_invoke):
            loop.run()

        assert loop.agents_md_path.exists()
        content = loop.agents_md_path.read_text()
        assert "AGENTS.md" in content or "Cross-Iteration" in content


class TestPreservesAgentsMd:
    """Existing AGENTS.md not overwritten."""

    def test_preserves_agents_md(self, tmp_path: Path, agent_dir: Path):
        loop = _make_loop(tmp_path, agent_dir, max_iterations=1)
        # Write custom AGENTS.md
        loop.agents_md_path.write_text("# My Custom AGENTS.md\nDo not overwrite me.\n")

        def mock_invoke(**kwargs):
            verdict = {"approved": False, "reason": "nope"}
            loop.verdict_path.write_text(json.dumps(verdict))
            return MagicMock(stdout="x", stderr="", returncode=0, ok=True)

        with patch("telos_agent.ralph.invoke_claude", side_effect=mock_invoke):
            loop.run()

        content = loop.agents_md_path.read_text()
        assert "Do not overwrite me" in content
