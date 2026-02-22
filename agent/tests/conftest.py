"""Shared test fixtures for the telos-agent test suite."""

import json
from dataclasses import dataclass
from pathlib import Path

import pytest


@pytest.fixture
def tmp_project_dir(tmp_path: Path) -> Path:
    """Create a temporary project directory with standard structure."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "prds").mkdir()
    (project / "prds" / "01-main.md").write_text(
        "# Main PRD\n\n- [ ] Create index.html\n- [ ] Add CSS styling\n"
    )
    (project / "progress.txt").write_text("# Progress Log\n\n")
    return project


@pytest.fixture
def mock_claude_result():
    """Factory fixture for ClaudeResult objects."""
    from telos_agent.claude import ClaudeResult

    def _make(stdout: str = "", stderr: str = "", returncode: int = 0) -> ClaudeResult:
        return ClaudeResult(stdout=stdout, stderr=stderr, returncode=returncode)

    return _make


@pytest.fixture
def sample_transcript() -> str:
    """Reusable bakery interview transcript."""
    return (
        "North Star: Build a website for my bakery\n\n"
        "Summary: Sarah wants a website for Sweet Crumbs Bakery.\n\n"
        "Q: What do you want people to do on your website?\n"
        "A: See my cakes and order them.\n\n"
        "Q: Do you have branding preferences?\n"
        "A: Pink and gold, pastel-y.\n\n"
        "Q: How do you handle orders?\n"
        "A: People DM me, I tell them the price, they Venmo me.\n"
    )


@pytest.fixture
def agent_dir() -> Path:
    """Path to the agent package root (agent/)."""
    return Path(__file__).resolve().parent.parent
