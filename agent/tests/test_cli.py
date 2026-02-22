"""Unit tests for cli.py — argument parsing without invoking Claude.

Tests the argparse configuration and entry point wiring.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from telos_agent.cli import main


class TestCLIHelp:
    """Basic CLI entry point tests."""

    def test_help_succeeds(self):
        """Entry point wired up — --help exits 0."""
        with patch.object(sys, "argv", ["telos-agent", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0


class TestCLIInterview:
    """Interview subcommand parsing."""

    def test_interview_requires_project_dir(self):
        """Missing required --project-dir → exit 2."""
        with patch.object(sys, "argv", ["telos-agent", "interview"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2

    def test_interview_transcript_flag(self, tmp_path: Path):
        """--transcript parsed correctly."""
        transcript_file = tmp_path / "t.txt"
        transcript_file.write_text("test transcript")

        with patch.object(sys, "argv", [
            "telos-agent", "interview",
            "--project-dir", str(tmp_path),
            "--transcript", str(transcript_file),
        ]):
            # Patch the actual interview execution to avoid Claude calls
            with patch("telos_agent.cli.cmd_interview") as mock_cmd:
                main()
                args = mock_cmd.call_args[0][0]
                assert args.transcript == str(transcript_file)
                assert args.project_dir == tmp_path


class TestCLIExecute:
    """Execute subcommand parsing."""

    def test_execute_defaults(self, tmp_path: Path):
        """Default max_iterations=10, model=opus, timeout=900."""
        with patch.object(sys, "argv", [
            "telos-agent", "execute",
            "--project-dir", str(tmp_path),
        ]):
            with patch("telos_agent.cli.cmd_execute") as mock_cmd:
                main()
                args = mock_cmd.call_args[0][0]
                assert args.max_iterations == 10
                assert args.model == "opus"
                assert args.timeout == 900


class TestCLISubcommands:
    """All subcommands exist."""

    def test_all_subcommands_exist(self):
        """All 6 subcommands registered."""
        import argparse
        # Capture the parser by patching parse_args to inspect subparsers
        with patch.object(sys, "argv", ["telos-agent", "--help"]):
            with pytest.raises(SystemExit):
                main()

        # More direct: check that each subcommand doesn't fail with just --help
        subcommands = ["interview", "generate-plan", "generate-prds", "generate-prd", "execute", "run"]
        for cmd in subcommands:
            with patch.object(sys, "argv", ["telos-agent", cmd, "--help"]):
                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 0, f"Subcommand '{cmd}' --help failed"


class TestCLIRun:
    """Run subcommand parsing."""

    def test_run_all_flags(self, tmp_path: Path):
        """run subcommand parses all params."""
        transcript_file = tmp_path / "t.txt"
        transcript_file.write_text("test")

        with patch.object(sys, "argv", [
            "telos-agent", "run",
            "--project-dir", str(tmp_path),
            "--transcript", str(transcript_file),
            "--max-iterations", "5",
            "--model", "sonnet",
            "--timeout", "600",
        ]):
            with patch("telos_agent.cli.cmd_run") as mock_cmd:
                main()
                args = mock_cmd.call_args[0][0]
                assert args.transcript == str(transcript_file)
                assert args.max_iterations == 5
                assert args.model == "sonnet"
                assert args.timeout == 600

    def test_generate_prd_deprecated(self, tmp_path: Path):
        """Legacy subcommand still parses (deprecated)."""
        ctx_file = tmp_path / "ctx.json"
        ctx_file.write_text("[]")

        with patch.object(sys, "argv", [
            "telos-agent", "generate-prd",
            "--project-dir", str(tmp_path),
            "--context", str(ctx_file),
        ]):
            with patch("telos_agent.cli.cmd_generate_prd") as mock_cmd:
                main()
                args = mock_cmd.call_args[0][0]
                assert args.context == str(ctx_file)
