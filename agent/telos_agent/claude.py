"""Low-level wrapper around the `claude` CLI.

All Claude Code invocations go through this module. It builds the
appropriate CLI command with flags for isolation, MCP config, and
permissions, then runs it as a subprocess.
"""

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Generator


@dataclass
class ClaudeResult:
    """Result from a claude CLI invocation."""
    stdout: str
    stderr: str
    returncode: int

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    def json(self) -> dict:
        return json.loads(self.stdout)


@dataclass
class StreamResult:
    """Wraps a stream generator with access to the final return code.

    Unlike a Generator return value (only accessible via StopIteration.value),
    this gives callers direct access to the subprocess for exit code and cleanup.
    """
    lines: Generator[str, None, None]
    process: subprocess.Popen

    def wait(self, timeout: int | None = None) -> int:
        self.process.wait(timeout=timeout)
        return self.process.returncode


def _build_command(
    prompt: str | None,
    working_dir: Path,
    system_prompt_file: Path | None = None,
    mcp_config: Path | None = None,
    strict_mcp: bool = False,
    allowed_tools: list[str] | None = None,
    output_format: str = "text",
    model: str | None = None,
    max_turns: int | None = None,
    pipe_stdin: bool = False,
) -> list[str]:
    """Build the claude CLI command with appropriate flags."""
    cmd = ["claude", "-p"]

    if not pipe_stdin and prompt:
        cmd.append(prompt)

    if system_prompt_file:
        cmd.extend(["--append-system-prompt-file", str(system_prompt_file)])

    if mcp_config:
        cmd.extend(["--mcp-config", str(mcp_config)])

    if strict_mcp:
        cmd.append("--strict-mcp-config")

    if allowed_tools:
        cmd.extend(["--allowedTools", ",".join(allowed_tools)])

    if output_format != "text":
        cmd.extend(["--output-format", output_format])

    if model:
        cmd.extend(["--model", model])

    if max_turns:
        cmd.extend(["--max-turns", str(max_turns)])

    # Always fresh — no session persistence
    cmd.append("--no-session-persistence")

    return cmd


def invoke_claude(
    prompt: str,
    working_dir: Path,
    system_prompt_file: Path | None = None,
    mcp_config: Path | None = None,
    strict_mcp: bool = False,
    allowed_tools: list[str] | None = None,
    output_format: str = "text",
    model: str | None = None,
    max_turns: int | None = None,
    pipe_stdin: bool = False,
    timeout: int | None = None,
    skip_permissions: bool = True,
) -> ClaudeResult:
    """Invoke the claude CLI and return the result.

    Args:
        prompt: The prompt text. Passed as argument unless pipe_stdin=True.
        working_dir: Directory to run claude in (project directory).
        system_prompt_file: Path to system prompt file (--append-system-prompt-file).
        mcp_config: Path to MCP servers config (--mcp-config).
        strict_mcp: If True, adds --strict-mcp-config.
        allowed_tools: List of allowed tools (--allowedTools).
        output_format: Output format: "text", "json", "stream-json".
        model: Model to use (--model).
        max_turns: Maximum agentic turns (--max-turns).
        pipe_stdin: If True, prompt is piped via stdin instead of as an argument.
        timeout: Subprocess timeout in seconds.
        skip_permissions: If True, adds --dangerously-skip-permissions.
    """
    cmd = _build_command(
        prompt=prompt,
        working_dir=working_dir,
        system_prompt_file=system_prompt_file,
        mcp_config=mcp_config,
        strict_mcp=strict_mcp,
        allowed_tools=allowed_tools,
        output_format=output_format,
        model=model,
        max_turns=max_turns,
        pipe_stdin=pipe_stdin,
    )

    if skip_permissions:
        cmd.append("--dangerously-skip-permissions")

    # Clear CLAUDECODE env var to avoid nested-session detection.
    # Our child Claude instances are independent — not nested.
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

    result = subprocess.run(
        cmd,
        cwd=working_dir,
        input=prompt if pipe_stdin else None,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )

    return ClaudeResult(
        stdout=result.stdout,
        stderr=result.stderr,
        returncode=result.returncode,
    )


def invoke_claude_stream(
    prompt: str,
    working_dir: Path,
    system_prompt_file: Path | None = None,
    mcp_config: Path | None = None,
    strict_mcp: bool = False,
    allowed_tools: list[str] | None = None,
    model: str | None = None,
    max_turns: int | None = None,
    pipe_stdin: bool = False,
    skip_permissions: bool = True,
) -> StreamResult:
    """Invoke claude CLI with stream-json output, returning a StreamResult.

    The StreamResult contains a line generator and the subprocess handle.
    Callers iterate .lines for NDJSON output, then call .wait() for exit code.
    """
    cmd = _build_command(
        prompt=prompt,
        working_dir=working_dir,
        system_prompt_file=system_prompt_file,
        mcp_config=mcp_config,
        strict_mcp=strict_mcp,
        allowed_tools=allowed_tools,
        output_format="stream-json",
        model=model,
        max_turns=max_turns,
        pipe_stdin=pipe_stdin,
    )

    # --verbose is required for stream-json with -p to emit full trajectory
    cmd.append("--verbose")

    if skip_permissions:
        cmd.append("--dangerously-skip-permissions")

    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

    proc = subprocess.Popen(
        cmd,
        cwd=working_dir,
        stdin=subprocess.PIPE if pipe_stdin else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )

    if pipe_stdin:
        proc.stdin.write(prompt)
        proc.stdin.close()

    def _line_generator():
        # Use readline() instead of `for line in proc.stdout` —
        # the iterator uses a readahead buffer that delays line delivery,
        # causing streaming events to arrive in batches instead of real-time.
        while True:
            line = proc.stdout.readline()
            if not line:
                break
            stripped = line.rstrip("\n")
            if stripped:
                yield stripped

    return StreamResult(lines=_line_generator(), process=proc)
