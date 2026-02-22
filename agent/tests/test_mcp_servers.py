"""Tests for both MCP servers — reviewer.py and gemini.py.

Calls the tool functions directly (no stdio transport needed).
Uses monkeypatch to set VERDICT_PATH and CONTEXT_DIR.
"""

import json
from datetime import datetime
from pathlib import Path

import pytest


class TestReviewerServer:
    """Tests for the reviewer MCP server tools."""

    def test_reviewer_approve(self, tmp_path: Path, monkeypatch):
        """Writes {"approved": true} to verdict.json."""
        verdict_path = tmp_path / "verdict.json"
        monkeypatch.setattr("telos_agent.mcp.reviewer.VERDICT_PATH", verdict_path)

        from telos_agent.mcp.reviewer import approve
        result = approve(summary="All tests pass")

        assert "APPROVED" in result
        verdict = json.loads(verdict_path.read_text())
        assert verdict["approved"] is True
        assert verdict["summary"] == "All tests pass"

    def test_reviewer_deny(self, tmp_path: Path, monkeypatch):
        """Writes {"approved": false} to verdict.json."""
        verdict_path = tmp_path / "verdict.json"
        monkeypatch.setattr("telos_agent.mcp.reviewer.VERDICT_PATH", verdict_path)

        from telos_agent.mcp.reviewer import deny
        result = deny(reason="Missing error handling")

        assert "DENIED" in result
        verdict = json.loads(verdict_path.read_text())
        assert verdict["approved"] is False
        assert verdict["reason"] == "Missing error handling"

    def test_reviewer_overwrites(self, tmp_path: Path, monkeypatch):
        """Last call wins — deny then approve overwrites."""
        verdict_path = tmp_path / "verdict.json"
        monkeypatch.setattr("telos_agent.mcp.reviewer.VERDICT_PATH", verdict_path)

        from telos_agent.mcp.reviewer import approve, deny
        deny(reason="Bad")
        approve(summary="Fixed")

        verdict = json.loads(verdict_path.read_text())
        assert verdict["approved"] is True

    def test_reviewer_has_timestamp(self, tmp_path: Path, monkeypatch):
        """ISO 8601 timestamp in verdict."""
        verdict_path = tmp_path / "verdict.json"
        monkeypatch.setattr("telos_agent.mcp.reviewer.VERDICT_PATH", verdict_path)

        from telos_agent.mcp.reviewer import approve
        approve(summary="Good")

        verdict = json.loads(verdict_path.read_text())
        assert "timestamp" in verdict
        # Should be parseable as ISO 8601
        datetime.fromisoformat(verdict["timestamp"])

    def test_reviewer_tool_registration(self):
        """FastMCP has approve and deny tools."""
        from telos_agent.mcp.reviewer import mcp

        tool_names = [tool.name for tool in mcp._tool_manager.list_tools()]
        assert "approve" in tool_names
        assert "deny" in tool_names


class TestGeminiServer:
    """Tests for the gemini context MCP server tools."""

    def test_gemini_summarize_with_files(self, tmp_path: Path, monkeypatch):
        """Lists filenames from context dir."""
        monkeypatch.setattr("telos_agent.mcp.gemini.CONTEXT_DIR", tmp_path)
        (tmp_path / "design.png").write_text("fake")
        (tmp_path / "spec.pdf").write_text("fake")

        from telos_agent.mcp.gemini import summarize
        result = summarize()

        assert "design.png" in result
        assert "spec.pdf" in result

    def test_gemini_summarize_empty_dir(self, tmp_path: Path, monkeypatch):
        """Returns "empty" message for empty dir."""
        monkeypatch.setattr("telos_agent.mcp.gemini.CONTEXT_DIR", tmp_path)

        from telos_agent.mcp.gemini import summarize
        result = summarize()

        assert "empty" in result.lower()

    def test_gemini_summarize_missing_dir(self, tmp_path: Path, monkeypatch):
        """Returns "not found" message for missing dir."""
        missing = tmp_path / "nonexistent"
        monkeypatch.setattr("telos_agent.mcp.gemini.CONTEXT_DIR", missing)

        from telos_agent.mcp.gemini import summarize
        result = summarize()

        assert "no context" in result.lower() or "not found" in result.lower()

    def test_gemini_answer_question(self, monkeypatch, tmp_path: Path):
        """Echoes query, signals placeholder."""
        monkeypatch.setattr("telos_agent.mcp.gemini.CONTEXT_DIR", tmp_path)

        from telos_agent.mcp.gemini import answer_question
        result = answer_question(query="What framework should we use?")

        assert "What framework should we use?" in result
        assert "placeholder" in result.lower()

    def test_gemini_tool_registration(self):
        """FastMCP has summarize and answer_question tools."""
        from telos_agent.mcp.gemini import mcp

        tool_names = [tool.name for tool in mcp._tool_manager.list_tools()]
        assert "summarize" in tool_names
        assert "answer_question" in tool_names
