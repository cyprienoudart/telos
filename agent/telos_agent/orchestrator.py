"""Top-level orchestrator — ties interview, planning, PRD generation, and Ralph loop together.

This is the main API that library consumers (Ali) use. It provides a simple
interface for running the Telos workflow:

    interview (transcript rounds) → plan.md → prds/ → execute (Ralph loop)
"""
from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)

from telos_agent.claude import invoke_claude, invoke_claude_stream
from telos_agent.interview import InterviewRunner
from telos_agent.mcp_config import generate_mcp_config
from telos_agent.ralph import IterationResult, RalphLoop, RalphResult

# Event types forwarded from stream-json to on_event
_STREAM_EVENTS = {"assistant", "tool_use", "tool_result", "result", "system"}


class TelosOrchestrator:
    """Main entry point for the Telos agent system."""

    def __init__(
        self,
        project_dir: Path,
        agent_dir: Path | None = None,
        context_dir: Path | None = None,
        max_iterations: int = 10,
        model: str = "opus",
        timeout: int = 900,
    ):
        self.project_dir = Path(project_dir).resolve()
        # Default agent_dir to the installed package location
        if agent_dir is None:
            self.agent_dir = Path(__file__).resolve().parent.parent
        else:
            self.agent_dir = Path(agent_dir).resolve()
        self.context_dir = Path(context_dir).resolve() if context_dir else None
        self.max_iterations = max_iterations
        self.model = model
        self.timeout = timeout

    def interview(self) -> InterviewRunner:
        """Create an InterviewRunner for the interview phase."""
        return InterviewRunner(
            project_dir=self.project_dir,
            agent_dir=self.agent_dir,
            context_dir=self.context_dir,
        )

    def _invoke_with_events(
        self,
        on_event: Callable[[dict], None],
        **kwargs,
    ) -> str:
        """Invoke Claude with streaming, forwarding trajectory events.

        Wraps invoke_claude_stream(), parses NDJSON, pushes relevant events
        to on_event, and returns the final result text (equivalent to
        ClaudeResult.stdout from the non-streaming path).
        """
        t0 = time.monotonic()
        logger.info("invoke_with_events: spawning claude subprocess...")
        _tlog = lambda msg: open("/tmp/telos-build-timing.log", "a").write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        _tlog("invoke_with_events: spawning subprocess...")
        stream = invoke_claude_stream(**kwargs)
        _tlog(f"invoke_with_events: subprocess spawned at {time.monotonic() - t0:.2f}s")
        first_event = True
        result_text = ""

        for line in stream.lines:
            try:
                evt = json.loads(line)
            except json.JSONDecodeError:
                continue

            evt_type = evt.get("type", "")

            # Capture the final result text for callers that need it
            if evt_type == "result" and isinstance(evt.get("result"), str):
                result_text = evt["result"]

            # Forward relevant events
            if evt_type in _STREAM_EVENTS:
                if first_event:
                    elapsed = time.monotonic() - t0
                    logger.info("invoke_with_events: first event after %.2fs", elapsed)
                    _tlog(f"invoke_with_events: FIRST EVENT at {elapsed:.2f}s (type={evt_type})")
                    first_event = False
                on_event(evt)

        stream.wait()
        elapsed = time.monotonic() - t0
        logger.info("invoke_with_events: done in %.2fs", elapsed)
        _tlog(f"invoke_with_events: done in {elapsed:.2f}s")
        return result_text

    def generate_plan(
        self,
        interview_context: str,
        on_event: Callable[[dict], None] | None = None,
    ) -> Path:
        """Generate a project plan from interview context.

        Uses Claude with Gemini MCP to synthesize the interview transcript
        into a structured plan following templates/plan-template.md.

        Args:
            interview_context: Plain-text interview transcript from Ali.
            on_event: Optional callback for real-time trajectory streaming.

        Returns:
            Path to the generated plan.md in the project directory.
        """
        template_path = self.agent_dir / "templates" / "plan-template.md"
        template = template_path.read_text() if template_path.exists() else ""

        mcp_config_path = generate_mcp_config(
            agent_dir=self.agent_dir,
            project_dir=self.project_dir,
            context_dir=self.context_dir,
            include_gemini=True,
        )

        prompt = (
            "You are generating a project plan from an interview transcript.\n\n"
            "## Interview Transcript\n\n"
            f"{interview_context}\n\n"
            "## Plan Template\n\n"
            f"{template}\n\n"
            "Generate a complete project plan based on the interview data. Follow the template structure.\n"
            "- North Star: capture the core vision and success criteria\n"
            "- Architecture: high-level system design and key decisions\n"
            "- Tech Stack: specific technologies and frameworks\n"
            "- Implementation Phases: ordered work breakdown with concrete tasks\n"
            "- Sequencing: dependencies between phases\n"
            "- Risks: technical and project risks with mitigations\n"
            "- Open Questions: anything that needs clarification\n\n"
            "Use the Gemini context tools if you need additional project information.\n\n"
            "Output ONLY the plan content in markdown format, nothing else."
        )

        claude_kwargs = dict(
            prompt=prompt,
            working_dir=self.project_dir,
            mcp_config=mcp_config_path,
            allowed_tools=["mcp__gemini-context__summarize", "mcp__gemini-context__answer_question"],
            model="sonnet",
        )

        if on_event:
            result_text = self._invoke_with_events(on_event, **claude_kwargs)
        else:
            result_text = invoke_claude(**claude_kwargs).stdout

        plan_path = self.project_dir / "plan.md"
        plan_path.write_text(result_text)
        return plan_path

    def generate_prds(
        self,
        on_event: Callable[[dict], None] | None = None,
    ) -> Path:
        """Generate multiple PRDs from plan.md.

        Reads the plan, invokes Claude with Gemini MCP and write tools to
        create individual PRD files in prds/ directory (01-xxx.md, 02-xxx.md, etc.).

        Args:
            on_event: Optional callback for real-time trajectory streaming.

        Returns:
            Path to the prds/ directory.
        """
        plan_path = self.project_dir / "plan.md"
        if not plan_path.exists():
            raise FileNotFoundError(f"No plan.md found at {plan_path}. Run generate_plan() first.")

        plan_content = plan_path.read_text()
        prds_dir = self.project_dir / "prds"
        prds_dir.mkdir(exist_ok=True)

        mcp_config_path = generate_mcp_config(
            agent_dir=self.agent_dir,
            project_dir=self.project_dir,
            context_dir=self.context_dir,
            include_gemini=True,
        )

        prompt = (
            "You are splitting a project plan into individual PRD (Product Requirements Document) files.\n\n"
            "## Project Plan\n\n"
            f"{plan_content}\n\n"
            "## Your Task\n\n"
            "Create individual PRD files in the `prds/` directory. Each PRD should:\n"
            "- Be named with a number prefix: `prds/01-xxx.md`, `prds/02-xxx.md`, etc.\n"
            "- Cover one logical phase or work unit from the plan\n"
            "- Include specific, testable acceptance criteria as checkbox items: `- [ ] criterion`\n"
            "- Be self-contained — a developer should be able to implement it without reading other PRDs\n"
            "- Reference the plan's architecture decisions and tech stack choices\n\n"
            "## Sizing Rules\n\n"
            "- **Target 8-15 acceptance criteria checkboxes per PRD.** If a phase has more than 15 "
            "checkable items, split it into separate PRDs.\n"
            "- Only use `- [ ]` checkboxes for items that require **implementation work** "
            "(writing code, creating files, configuring services).\n"
            "- QA verification steps (e.g., 'test on mobile', 'check for console errors') "
            "belong in a prose 'Definition of Done' section, not as individual checkboxes — "
            "the reviewer agent handles verification.\n"
            "- Launch checklists and handoff steps are also prose, not checkboxes.\n\n"
            "The numbering should reflect implementation order (01 = do first).\n"
            "Use the Gemini context tools if you need additional project information.\n\n"
            "Write each PRD file using the Write tool. After creating all PRDs, "
            "output a summary listing the files you created."
        )

        claude_kwargs = dict(
            prompt=prompt,
            working_dir=self.project_dir,
            mcp_config=mcp_config_path,
            allowed_tools=[
                "Read", "Write", "Glob", "Grep",
                "mcp__gemini-context__summarize",
                "mcp__gemini-context__answer_question",
            ],
            model="sonnet",
        )

        if on_event:
            self._invoke_with_events(on_event, **claude_kwargs)
        else:
            invoke_claude(**claude_kwargs)

        # Post-check: verify PRDs were created
        prd_files = sorted(prds_dir.glob("*.md"))
        if not prd_files:
            raise RuntimeError(f"No PRD files were created in {prds_dir}")

        return prds_dir

    def execute(self, on_event: Callable[[dict], None] | None = None) -> RalphResult:
        """Execute the Ralph loop to implement all PRDs in prds/.

        Args:
            on_event: Optional callback for real-time trajectory streaming.
        """
        loop = RalphLoop(
            project_dir=self.project_dir,
            agent_dir=self.agent_dir,
            context_dir=self.context_dir,
            max_iterations=self.max_iterations,
            model=self.model,
            timeout=self.timeout,
        )
        return loop.run(on_event=on_event)

    def plan_and_execute(
        self,
        context: str,
        on_event: Callable[[dict], None] | None = None,
    ) -> RalphResult:
        """Convenience wrapper: generate plan → generate PRDs → execute.

        Args:
            context: Plain-text interview transcript from Ali.
            on_event: Optional callback for real-time trajectory streaming.
        """
        t0 = time.monotonic()

        if on_event:
            on_event({"type": "phase", "phase": "planning", "message": "Generating project plan..."})

        logger.info("plan_and_execute: starting generate_plan...")
        self.generate_plan(context, on_event=on_event)
        logger.info("plan_and_execute: plan done in %.2fs", time.monotonic() - t0)

        if on_event:
            on_event({"type": "phase", "phase": "splitting", "message": "Splitting plan into PRDs..."})

        logger.info("plan_and_execute: starting generate_prds...")
        self.generate_prds(on_event=on_event)
        logger.info("plan_and_execute: PRDs done in %.2fs", time.monotonic() - t0)

        if on_event:
            on_event({"type": "phase", "phase": "building", "message": "Starting build loop..."})

        logger.info("plan_and_execute: starting execute...")
        result = self.execute(on_event=on_event)
        logger.info("plan_and_execute: total %.2fs", time.monotonic() - t0)
        return result

    def run(
        self,
        transcript: str | None = None,
        # Legacy params
        questions: list[list[str]] | None = None,
        user_answers_callback=None,
    ) -> RalphResult:
        """Run the full workflow: interview → plan → PRDs → execute.

        New flow (transcript-based):
            Pass a transcript string. Generates plan, splits into PRDs, executes.

        Legacy flow (question-based):
            Pass questions list + callback. Generates single PRD, executes.
        """
        if transcript is not None:
            return self.plan_and_execute(transcript)

        # Legacy flow
        if questions is None:
            raise ValueError("Either transcript or questions must be provided")

        runner = self.interview()

        for round_num, round_questions in enumerate(questions, 1):
            agent_answers = runner.ask_agent(round_questions, round_num=round_num)

            if user_answers_callback:
                user_answers = user_answers_callback(round_num, round_questions, agent_answers)
                runner.add_user_answers(round_num, user_answers)

        # Legacy: single PRD
        prd_path = self.generate_prd(runner.get_context())

        # Legacy: need prds/ dir for Ralph
        prds_dir = self.project_dir / "prds"
        prds_dir.mkdir(exist_ok=True)
        import shutil
        shutil.copy2(prd_path, prds_dir / "01-main.md")

        return self.execute()

    # --- Deprecated (kept for backwards compat) ---

    def generate_prd(self, interview_context: list[dict] | str) -> Path:
        """Generate a single PRD from interview context.

        Deprecated: Use generate_plan() + generate_prds() instead.
        """
        template_path = self.agent_dir / "templates" / "prd-template.md"
        template = template_path.read_text() if template_path.exists() else ""

        if isinstance(interview_context, str):
            context_str = interview_context
        else:
            context_str = json.dumps(interview_context, indent=2)

        prompt = (
            "You are generating a Product Requirements Document (PRD) from interview data.\n\n"
            "## Interview Transcript\n\n"
            f"{context_str}\n\n"
            "## PRD Template\n\n"
            f"{template}\n\n"
            "Generate a complete PRD based on the interview data. Follow the template structure. "
            "Each user story must have specific, testable acceptance criteria. "
            "Be precise and actionable — this PRD will be used by an AI agent to implement the project.\n\n"
            "Output ONLY the PRD content in markdown format, nothing else."
        )

        result = invoke_claude(
            prompt=prompt,
            working_dir=self.project_dir,
            model="sonnet",
        )

        prd_path = self.project_dir / "prd.md"
        prd_path.write_text(result.stdout)
        return prd_path
