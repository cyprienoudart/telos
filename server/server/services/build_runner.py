"""Background Ralph loop executor.

Runs the Telos orchestrator (plan -> PRDs -> Ralph loop) in a background thread
and exposes status for polling / SSE streaming.
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class BuildState:
    id: str
    status: str = "running"  # running | completed | failed
    iteration: int = 0
    total_iterations: int = 0
    success: bool | None = None
    error: str | None = None
    progress_path: Path | None = None


class BuildRunner:
    """Manages background build jobs."""

    def __init__(self) -> None:
        self._builds: dict[str, BuildState] = {}

    def start(
        self,
        transcript: str,
        project_dir: str,
        context_dir: str | None = None,
        max_iterations: int = 10,
        model: str = "opus",
    ) -> BuildState:
        build_id = uuid.uuid4().hex[:12]
        proj = Path(project_dir).resolve()
        proj.mkdir(parents=True, exist_ok=True)

        state = BuildState(
            id=build_id,
            total_iterations=max_iterations,
            progress_path=proj / "progress.txt",
        )
        self._builds[build_id] = state

        thread = threading.Thread(
            target=self._run,
            args=(state, transcript, proj, context_dir, max_iterations, model),
            daemon=True,
            name=f"build-{build_id}",
        )
        thread.start()
        return state

    def get(self, build_id: str) -> BuildState | None:
        return self._builds.get(build_id)

    def _run(
        self,
        state: BuildState,
        transcript: str,
        project_dir: Path,
        context_dir: str | None,
        max_iterations: int,
        model: str,
    ) -> None:
        try:
            # Lazy import to avoid heavy deps at server startup
            from telos_agent.orchestrator import TelosOrchestrator

            orch = TelosOrchestrator(
                project_dir=project_dir,
                context_dir=Path(context_dir) if context_dir else None,
                max_iterations=max_iterations,
                model=model,
            )
            result = orch.plan_and_execute(transcript)
            state.status = "completed"
            state.success = result.success
            state.iteration = len(result.iterations)
        except Exception as exc:
            logger.exception("Build %s failed", state.id)
            state.status = "failed"
            state.success = False
            state.error = str(exc)
