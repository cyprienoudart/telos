"""Ralph loop — iterative execution engine.

Runs Claude Code repeatedly as an orchestrator. Each iteration:
1. Copies agent definitions to the project
2. Seeds AGENTS.md from template (first run only)
3. Generates MCP config with resolved paths (Gemini + reviewer)
4. Pipes the build prompt to Claude Code
5. Reads the reviewer's verdict
6. Tracks denial streaks and escalates after consecutive failures
7. Loops until approved or max iterations reached

Works through a list of PRDs in prds/ directory, not a single file.

Named after the "Huntley pattern" — fresh instance per iteration,
state persists via files (progress.txt, git history, AGENTS.md).
"""

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from telos_agent.claude import invoke_claude
from telos_agent.mcp_config import generate_mcp_config


@dataclass
class IterationResult:
    """Result from a single Ralph iteration."""
    iteration: int
    status: str  # "approved", "denied", "approved-partial", "no-verdict", "error", "timeout"
    details: str
    timestamp: str
    verdict: dict | None = None


@dataclass
class RalphResult:
    """Result from the Ralph loop."""
    success: bool
    iterations: int
    final_verdict: dict | None = None
    error: str | None = None
    iteration_results: list[IterationResult] = field(default_factory=list)
    denial_streak: int = 0


class RalphLoop:
    """Iterative execution loop that delegates work through Claude Code."""

    PROMISE_MARKER = "<promise>COMPLETE</promise>"

    def __init__(
        self,
        project_dir: Path,
        agent_dir: Path,
        context_dir: Path | None = None,
        max_iterations: int = 10,
        model: str = "opus",
        timeout: int = 900,
    ):
        self.project_dir = Path(project_dir).resolve()
        self.agent_dir = Path(agent_dir).resolve()
        self.context_dir = Path(context_dir).resolve() if context_dir else None
        self.max_iterations = max_iterations
        self.model = model
        self.timeout = timeout

        # Paths within agent_dir
        self.config_dir = self.agent_dir / "config"
        self.agents_source = self.config_dir / "agents"
        self.orchestrator_prompt = self.config_dir / "orchestrator.md"
        self.build_prompt = self.agent_dir / "prompts" / "build.md"

        # AGENTS.md template
        self.agents_md_template = self.agent_dir / "templates" / "agents-md-template.md"

        # Paths within project_dir
        self.prds_dir = self.project_dir / "prds"
        self.agents_dest = self.project_dir / ".claude" / "agents"
        self.verdict_path = self.project_dir / "verdict.json"
        self.progress_path = self.project_dir / "progress.txt"
        self.agents_md_path = self.project_dir / "AGENTS.md"

        # Denial tracking
        self._denial_streak = 0
        self._last_denial_reason: str | None = None
        self._iteration_results: list[IterationResult] = []

    def run(self) -> RalphResult:
        """Execute the Ralph loop until completion or max iterations.

        Reads PRDs from the prds/ directory in the project. If a legacy
        prd.md exists and prds/ doesn't, it continues to work.
        """
        # Ensure progress.txt exists
        if not self.progress_path.exists():
            self.progress_path.write_text("# Progress Log\n\n")

        # Seed AGENTS.md from template if not exists
        if not self.agents_md_path.exists() and self.agents_md_template.exists():
            shutil.copy2(self.agents_md_template, self.agents_md_path)

        for iteration in range(1, self.max_iterations + 1):
            print(f"\n{'='*60}")
            print(f"Ralph Loop — Iteration {iteration}/{self.max_iterations}")
            if self._denial_streak > 0:
                print(f"  Denial streak: {self._denial_streak}")
            print(f"{'='*60}\n")

            result = self._run_iteration(iteration)

            if result is not None:
                result.iteration_results = list(self._iteration_results)
                result.denial_streak = self._denial_streak
                return result

        return RalphResult(
            success=False,
            iterations=self.max_iterations,
            error=f"Max iterations ({self.max_iterations}) reached without completion",
            iteration_results=list(self._iteration_results),
            denial_streak=self._denial_streak,
        )

    def _run_iteration(self, iteration: int) -> RalphResult | None:
        """Run a single iteration. Returns RalphResult if done, None to continue."""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        # 1. Copy agent definitions to project
        self._copy_agent_definitions()

        # 2. Generate resolved MCP config (Gemini + reviewer)
        mcp_config_path = generate_mcp_config(
            agent_dir=self.agent_dir,
            project_dir=self.project_dir,
            context_dir=self.context_dir,
            include_gemini=True,
            include_reviewer=True,
        )

        # 3. Delete previous verdict
        if self.verdict_path.exists():
            self.verdict_path.unlink()

        # 4. Build the prompt (with escalation suffix if needed)
        build_prompt = self.build_prompt.read_text()
        if self._denial_streak >= 3:
            build_prompt += self._escalation_suffix()

        # 5. Invoke Claude Code
        try:
            result = invoke_claude(
                prompt=build_prompt,
                working_dir=self.project_dir,
                system_prompt_file=self.orchestrator_prompt,
                mcp_config=mcp_config_path,
                strict_mcp=True,
                output_format="text",
                model=self.model,
                pipe_stdin=True,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired:
            details = f"Claude process timed out after {self.timeout}s"
            self._append_progress(iteration, "timeout", details)
            self._iteration_results.append(IterationResult(
                iteration=iteration,
                status="timeout",
                details=details,
                timestamp=timestamp,
            ))
            print(f"  Timeout: {details}")
            return None  # Continue to next iteration

        if not result.ok:
            details = f"Claude exited with code {result.returncode}: {result.stderr[:500]}"
            self._append_progress(iteration, "error", details)
            self._iteration_results.append(IterationResult(
                iteration=iteration,
                status="error",
                details=details,
                timestamp=timestamp,
            ))
            return None  # Continue to next iteration

        # 6. Check for completion promise
        has_promise = self.PROMISE_MARKER in result.stdout

        # 7. Read verdict and update tracking
        verdict = self._read_verdict()

        if verdict and verdict.get("approved") and has_promise:
            self._denial_streak = 0
            details = verdict.get("summary", "All items complete")
            self._append_progress(iteration, "approved", details)
            self._iteration_results.append(IterationResult(
                iteration=iteration,
                status="approved",
                details=details,
                timestamp=timestamp,
                verdict=verdict,
            ))
            return RalphResult(
                success=True,
                iterations=iteration,
                final_verdict=verdict,
            )

        if verdict and not verdict.get("approved"):
            reason = verdict.get("reason", "No reason provided")
            self._denial_streak += 1
            self._last_denial_reason = reason
            self._append_progress(iteration, "denied", reason)
            self._iteration_results.append(IterationResult(
                iteration=iteration,
                status="denied",
                details=reason,
                timestamp=timestamp,
                verdict=verdict,
            ))
            print(f"  Reviewer denied: {reason}")
        elif not verdict:
            self._append_progress(iteration, "no-verdict", "Reviewer did not produce a verdict")
            self._iteration_results.append(IterationResult(
                iteration=iteration,
                status="no-verdict",
                details="Reviewer did not produce a verdict",
                timestamp=timestamp,
            ))
            print("  Warning: No verdict.json found after iteration")
        else:
            # Approved but no promise marker — not all items done yet
            self._denial_streak = 0
            details = verdict.get("summary", "Partial progress")
            self._append_progress(iteration, "approved-partial", details)
            self._iteration_results.append(IterationResult(
                iteration=iteration,
                status="approved-partial",
                details=details,
                timestamp=timestamp,
                verdict=verdict,
            ))
            print(f"  Approved but not all items complete yet")

        return None  # Continue

    def _escalation_suffix(self) -> str:
        """Generate escalation text appended to the build prompt after repeated denials."""
        reason_quote = ""
        if self._last_denial_reason:
            reason_quote = f"\nMost recent denial reason:\n> {self._last_denial_reason}\n"
        return (
            f"\n\n## ESCALATION — {self._denial_streak} consecutive denials\n\n"
            f"The reviewer has denied the last {self._denial_streak} iterations.{reason_quote}\n"
            "Your previous approach is NOT working. Try a fundamentally different strategy:\n"
            "- Re-read the denial reason carefully — address it literally, not approximately\n"
            "- Reduce scope: focus ONLY on fixing the denied items before attempting new work\n"
            "- Simplify: if the implementation is complex, try a simpler approach\n"
            "- Check AGENTS.md Gotchas for patterns that have already failed\n"
        )

    def _copy_agent_definitions(self) -> None:
        """Copy agent definitions from config to project."""
        self.agents_dest.mkdir(parents=True, exist_ok=True)
        if self.agents_source.exists():
            for agent_file in self.agents_source.glob("*.md"):
                shutil.copy2(agent_file, self.agents_dest / agent_file.name)

    def _read_verdict(self) -> dict | None:
        """Read the verdict.json file if it exists."""
        if not self.verdict_path.exists():
            return None
        try:
            return json.loads(self.verdict_path.read_text())
        except (json.JSONDecodeError, OSError):
            return None

    def _append_progress(self, iteration: int, status: str, details: str) -> None:
        """Append an entry to progress.txt."""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        entry = (
            f"\n## Iteration {iteration} — {timestamp}\n"
            f"- Status: {status}\n"
            f"- Details: {details}\n"
        )
        with open(self.progress_path, "a") as f:
            f.write(entry)
