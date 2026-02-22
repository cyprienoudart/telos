"""Tests for both MCP servers — reviewer.py and gemini/.

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
        """summarize() wraps pipeline.summarize(); test via monkeypatching pipeline."""
        monkeypatch.setattr(
            "telos_agent.mcp.gemini.pipeline.summarize",
            lambda: "15 bullet summary here",
        )
        from telos_agent.mcp.gemini.server import summarize
        result = summarize()
        assert result == "15 bullet summary here"

    def test_gemini_summarize_error_handling(self, monkeypatch):
        """summarize() catches exceptions and returns ERROR string."""
        def boom():
            raise RuntimeError("test boom")
        monkeypatch.setattr("telos_agent.mcp.gemini.pipeline.summarize", boom)
        from telos_agent.mcp.gemini.server import summarize
        result = summarize()
        assert result.startswith("ERROR:")
        assert "test boom" in result

    def test_gemini_answer_question(self, monkeypatch):
        """answer_question() wraps pipeline.answer_question()."""
        monkeypatch.setattr(
            "telos_agent.mcp.gemini.pipeline.answer_question",
            lambda q: f"Answer to: {q}",
        )
        from telos_agent.mcp.gemini.server import answer_question
        result = answer_question(query="What framework should we use?")
        assert "What framework should we use?" in result

    def test_gemini_answer_error_handling(self, monkeypatch):
        """answer_question() catches exceptions."""
        def boom(q):
            raise RuntimeError("api down")
        monkeypatch.setattr("telos_agent.mcp.gemini.pipeline.answer_question", boom)
        from telos_agent.mcp.gemini.server import answer_question
        result = answer_question(query="test")
        assert result.startswith("ERROR:")
        assert "api down" in result

    def test_gemini_tool_registration(self):
        """FastMCP has summarize and answer_question tools."""
        from telos_agent.mcp.gemini import mcp

        tool_names = [tool.name for tool in mcp._tool_manager.list_tools()]
        assert "summarize" in tool_names
        assert "answer_question" in tool_names
