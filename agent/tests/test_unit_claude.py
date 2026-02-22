"""Unit tests for claude.py — command building and result handling.

All tests mock subprocess.run so no Claude CLI is needed.
"""

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from telos_agent.claude import ClaudeResult, _build_command, invoke_claude


class TestBuildCommand:
    """Tests for _build_command()."""

    def test_build_command_minimal(self, tmp_path: Path):
        """Base command structure: claude -p <prompt> --no-session-persistence."""
        cmd = _build_command(prompt="hello", working_dir=tmp_path)
        assert cmd[0] == "claude"
        assert cmd[1] == "-p"
        assert "hello" in cmd
        assert "--no-session-persistence" in cmd

    def test_build_command_all_flags(self, tmp_path: Path):
        """Every flag is present when all options provided."""
        sys_file = tmp_path / "sys.md"
        sys_file.write_text("system prompt")
        mcp_file = tmp_path / "mcp.json"
        mcp_file.write_text("{}")

        cmd = _build_command(
            prompt="test",
            working_dir=tmp_path,
            system_prompt_file=sys_file,
            mcp_config=mcp_file,
            strict_mcp=True,
            allowed_tools=["Read", "Write"],
            output_format="json",
            model="sonnet",
            max_turns=5,
        )

        assert "--append-system-prompt-file" in cmd
        assert str(sys_file) in cmd
        assert "--mcp-config" in cmd
        assert str(mcp_file) in cmd
        assert "--strict-mcp-config" in cmd
        assert "--allowedTools" in cmd
        assert "Read,Write" in cmd
        assert "--output-format" in cmd
        assert "json" in cmd
        assert "--model" in cmd
        assert "sonnet" in cmd
        assert "--max-turns" in cmd
        assert "5" in cmd

    def test_build_command_pipe_stdin(self, tmp_path: Path):
        """Prompt NOT in args when pipe_stdin=True."""
        cmd = _build_command(prompt="secret", working_dir=tmp_path, pipe_stdin=True)
        assert "secret" not in cmd
        # Still has claude -p and --no-session-persistence
        assert cmd[0] == "claude"
        assert "-p" in cmd


class TestClaudeResult:
    """Tests for ClaudeResult dataclass."""

    def test_claude_result_ok(self):
        """ok returns True for returncode 0, False otherwise."""
        assert ClaudeResult(stdout="", stderr="", returncode=0).ok is True
        assert ClaudeResult(stdout="", stderr="", returncode=1).ok is False
        assert ClaudeResult(stdout="", stderr="", returncode=127).ok is False

    def test_claude_result_json(self):
        """json() parses stdout, raises on invalid JSON."""
        r = ClaudeResult(stdout='{"ready": true}', stderr="", returncode=0)
        assert r.json() == {"ready": True}

        r_bad = ClaudeResult(stdout="not json", stderr="", returncode=0)
        with pytest.raises(json.JSONDecodeError):
            r_bad.json()


class TestInvokeClaude:
    """Tests for invoke_claude() with mocked subprocess."""

    @patch("telos_agent.claude.subprocess.run")
    def test_strips_claudecode_env(self, mock_run: MagicMock, tmp_path: Path):
        """CLAUDECODE removed from subprocess env (Bug 1 regression)."""
        mock_run.return_value = MagicMock(stdout="ok", stderr="", returncode=0)

        with patch.dict(os.environ, {"CLAUDECODE": "1", "HOME": "/home/test"}):
            invoke_claude(prompt="test", working_dir=tmp_path)

        call_kwargs = mock_run.call_args[1]
        env = call_kwargs["env"]
        assert "CLAUDECODE" not in env
        assert "HOME" in env

    @patch("telos_agent.claude.subprocess.run")
    def test_timeout_propagates(self, mock_run: MagicMock, tmp_path: Path):
        """TimeoutExpired is not swallowed."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=30)

        with pytest.raises(subprocess.TimeoutExpired):
            invoke_claude(prompt="test", working_dir=tmp_path, timeout=30)

    @patch("telos_agent.claude.subprocess.run")
    def test_skip_permissions_flag(self, mock_run: MagicMock, tmp_path: Path):
        """--dangerously-skip-permissions presence controlled by flag."""
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

        # Default: skip_permissions=True
        invoke_claude(prompt="test", working_dir=tmp_path)
        cmd_with = mock_run.call_args[0][0]
        assert "--dangerously-skip-permissions" in cmd_with

        mock_run.reset_mock()

        # Explicit: skip_permissions=False
        invoke_claude(prompt="test", working_dir=tmp_path, skip_permissions=False)
        cmd_without = mock_run.call_args[0][0]
        assert "--dangerously-skip-permissions" not in cmd_without
