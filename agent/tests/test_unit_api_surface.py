"""Contract tests validating the API matches docs/workflow.md.

Ensures the public API surface is stable — import paths, constructor
signatures, method names, and dataclass fields.
"""

import inspect
from pathlib import Path

import pytest


class TestTopLevelImports:
    """Verify top-level imports work as documented."""

    def test_top_level_imports(self):
        """from telos_agent import TelosOrchestrator etc."""
        from telos_agent import (
            TelosOrchestrator,
            InterviewRunner,
            InterviewResult,
            RalphLoop,
            RalphResult,
            IterationResult,
        )
        # All should be classes/types
        assert inspect.isclass(TelosOrchestrator)
        assert inspect.isclass(InterviewRunner)
        assert inspect.isclass(RalphLoop)


class TestOrchestratorConstructor:
    """Verify constructor required/optional params and defaults."""

    def test_orchestrator_constructor(self, tmp_path: Path):
        from telos_agent import TelosOrchestrator

        # Required: project_dir only
        orch = TelosOrchestrator(project_dir=tmp_path)
        assert orch.project_dir == tmp_path.resolve()

        # Defaults
        assert orch.max_iterations == 10
        assert orch.model == "opus"
        assert orch.timeout == 900
        assert orch.agent_dir is not None  # auto-detected
        assert orch.context_dir is None

    def test_orchestrator_methods(self, tmp_path: Path):
        """All methods exist with correct signatures."""
        from telos_agent import TelosOrchestrator

        orch = TelosOrchestrator(project_dir=tmp_path)

        # Method existence
        assert callable(orch.interview)
        assert callable(orch.generate_plan)
        assert callable(orch.generate_prds)
        assert callable(orch.execute)
        assert callable(orch.plan_and_execute)
        assert callable(orch.run)
        assert callable(orch.generate_prd)  # deprecated but present

        # Signature checks
        plan_sig = inspect.signature(orch.generate_plan)
        assert "interview_context" in plan_sig.parameters

        run_sig = inspect.signature(orch.run)
        assert "transcript" in run_sig.parameters
        assert "questions" in run_sig.parameters


class TestInterviewRunnerAPI:
    """Verify InterviewRunner public API."""

    def test_interview_runner_api(self, tmp_path: Path):
        from telos_agent import InterviewRunner

        runner = InterviewRunner(project_dir=tmp_path)

        # Method existence
        assert callable(runner.process_round)
        assert callable(runner.get_context)

        # process_round signature
        sig = inspect.signature(runner.process_round)
        assert "transcript" in sig.parameters
        assert "no_more_questions" in sig.parameters

        # Legacy methods
        assert callable(runner.ask_agent)
        assert callable(runner.add_user_answers)


class TestRalphResultDataclass:
    """All fields on RalphResult and IterationResult."""

    def test_ralph_result_dataclass(self):
        from telos_agent import RalphResult, IterationResult

        # RalphResult fields
        r = RalphResult(success=True, iterations=3)
        assert r.success is True
        assert r.iterations == 3
        assert r.final_verdict is None
        assert r.error is None
        assert r.iteration_results == []
        assert r.denial_streak == 0

        # IterationResult fields
        ir = IterationResult(
            iteration=1,
            status="approved",
            details="All good",
            timestamp="2024-01-01 00:00:00 UTC",
        )
        assert ir.iteration == 1
        assert ir.status == "approved"
        assert ir.details == "All good"
        assert ir.verdict is None


class TestInitExports:
    """__all__ matches expected exports."""

    def test_init_exports(self):
        import telos_agent

        expected = {
            "InterviewResult",
            "InterviewRunner",
            "IterationResult",
            "RalphLoop",
            "RalphResult",
            "TelosOrchestrator",
        }
        assert set(telos_agent.__all__) == expected


class TestPromptTuningApplied:
    """Readiness guidance + PRD sizing rules present in source."""

    def test_prompt_tuning_applied(self, agent_dir: Path):
        interview_src = (agent_dir / "telos_agent" / "interview.py").read_text()
        assert "Readiness Guidance" in interview_src
        assert "Simple projects" in interview_src

        orchestrator_src = (agent_dir / "telos_agent" / "orchestrator.py").read_text()
        assert "Sizing Rules" in orchestrator_src
        assert "8-15 acceptance criteria" in orchestrator_src


class TestErrorPaths:
    """Error paths raise correct exceptions."""

    def test_generate_prds_without_plan(self, tmp_path: Path):
        """Raises FileNotFoundError when plan.md missing."""
        from telos_agent import TelosOrchestrator

        orch = TelosOrchestrator(project_dir=tmp_path)
        with pytest.raises(FileNotFoundError, match="plan.md"):
            orch.generate_prds()

    def test_run_without_args(self, tmp_path: Path):
        """Raises ValueError when neither transcript nor questions provided."""
        from telos_agent import TelosOrchestrator

        orch = TelosOrchestrator(project_dir=tmp_path)
        with pytest.raises(ValueError, match="transcript or questions"):
            orch.run()
