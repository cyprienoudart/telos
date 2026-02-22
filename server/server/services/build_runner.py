"""Background Ralph loop executor.

Runs the Telos orchestrator (plan -> PRDs -> Ralph loop) in a background thread
and exposes status for polling / SSE streaming.
"""

from __future__ import annotations

import logging
import re
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# File-based timing log for debugging build startup latency
_TIMING_LOG = Path("/tmp/telos-build-timing.log")


def _ts(start: float) -> str:
    """Elapsed seconds since start, formatted."""
    return f"{time.monotonic() - start:.2f}s"


def _tlog(msg: str) -> None:
    """Append a timestamped line to the timing log file."""
    with open(_TIMING_LOG, "a") as f:
        f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")


@dataclass
class BuildState:
    id: str
    status: str = "running"  # running | completed | failed
    iteration: int = 0
    total_iterations: int = 0
    success: bool | None = None
    error: str | None = None
    progress_path: Path | None = None
    event_queue: deque = field(default_factory=deque)  # thread-safe trajectory events
    project_dir: Path | None = None
    build_phase: str = "planning"  # planning | planned | executing
    prd_count: int = 0  # actual PRD count from disk after generation
    transcript_len: int = 0  # cached for cost estimation
    confirmed_model: str | None = None  # set by confirm endpoint, unblocks thread


# ── PRD progress parsing ─────────────────────────────────────────────────

_RE_CHECKED = re.compile(r"^- \[x\] (.+)$", re.IGNORECASE)
_RE_UNCHECKED = re.compile(r"^- \[ \] (.+)$")
_RE_HEADING = re.compile(r"^#\s+(.+)$")


def parse_prd_progress(prds_dir: Path) -> list[dict]:
    """Parse checkbox progress from PRD markdown files.

    Returns a list of dicts with keys: filename, title, items, total, done, percent.
    Returns [] if prds_dir doesn't exist (e.g. during planning phase).
    """
    if not prds_dir.exists():
        return []

    results = []
    for md_file in sorted(prds_dir.glob("*.md")):
        title = md_file.stem
        items: list[dict] = []

        for line in md_file.read_text().splitlines():
            # Extract first H1 as title
            if title == md_file.stem:
                heading = _RE_HEADING.match(line)
                if heading:
                    title = heading.group(1).strip()

            checked = _RE_CHECKED.match(line)
            if checked:
                items.append({"text": checked.group(1).strip(), "checked": True})
                continue

            unchecked = _RE_UNCHECKED.match(line)
            if unchecked:
                items.append({"text": unchecked.group(1).strip(), "checked": False})

        total = len(items)
        done = sum(1 for i in items if i["checked"])
        results.append({
            "filename": md_file.name,
            "title": title,
            "items": items,
            "total": total,
            "done": done,
            "percent": round((done / total) * 100, 1) if total > 0 else 0.0,
        })

    return results


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

        # Clear stale progress from previous builds
        (proj / "progress.txt").unlink(missing_ok=True)

        state = BuildState(
            id=build_id,
            total_iterations=max_iterations,
            progress_path=proj / "progress.txt",
            project_dir=proj,
            transcript_len=len(transcript),
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
        t0 = time.monotonic()

        def _emit(evt: dict) -> None:
            """Push event to the thread-safe deque."""
            if evt.get("type") == "iteration_start":
                state.iteration = evt.get("iteration", state.iteration)
            state.event_queue.append(evt)

        def _step(step: str, message: str) -> None:
            """Emit a setup step event + log timing."""
            elapsed = _ts(t0)
            logger.info("Build %s [%s] step: %s — %s", state.id, elapsed, step, message)
            _tlog(f"Build {state.id} [{elapsed}] step: {step} — {message}")
            _emit({"type": "setup_step", "step": step, "message": message})

        try:
            # ── Phase 1: Plan + PRD generation (always uses sonnet) ────────
            _step("import", "Loading agent modules...")

            from telos_agent.orchestrator import TelosOrchestrator

            _tlog(f"Build {state.id} [{_ts(t0)}] import complete")
            logger.info("Build %s [%s] import complete", state.id, _ts(t0))
            _step("config", "Configuring build environment...")

            plan_orch = TelosOrchestrator(
                project_dir=project_dir,
                context_dir=Path(context_dir) if context_dir else None,
                max_iterations=max_iterations,
                model="sonnet",  # planning always uses sonnet
            )

            _tlog(f"Build {state.id} [{_ts(t0)}] orchestrator ready")
            logger.info("Build %s [%s] orchestrator ready", state.id, _ts(t0))
            _step("connect", "Connecting to Claude...")

            _emit({"type": "phase", "phase": "planning", "message": "Generating project plan..."})
            plan_orch.generate_plan(transcript, on_event=_emit)
            _tlog(f"Build {state.id} [{_ts(t0)}] plan generated")
            logger.info("Build %s [%s] plan generated", state.id, _ts(t0))

            _emit({"type": "phase", "phase": "splitting", "message": "Splitting plan into PRDs..."})
            plan_orch.generate_prds(on_event=_emit)
            _tlog(f"Build {state.id} [{_ts(t0)}] PRDs generated")
            logger.info("Build %s [%s] PRDs generated", state.id, _ts(t0))

            # Count actual PRD files on disk
            prds_dir = project_dir / "prds"
            prd_files = sorted(prds_dir.glob("*.md")) if prds_dir.exists() else []
            state.prd_count = len(prd_files)
            state.build_phase = "planned"
            _emit({"type": "planning_complete", "prd_count": state.prd_count})
            logger.info("Build %s [%s] planning complete — %d PRDs", state.id, _ts(t0), state.prd_count)

            # ── Phase 2: Wait for user confirmation ────────────────────────
            _tlog(f"Build {state.id} [{_ts(t0)}] waiting for confirmation...")
            timeout_s = 600  # 10 minute timeout
            waited = 0.0
            while state.confirmed_model is None and waited < timeout_s:
                time.sleep(1.0)
                waited += 1.0

            if state.confirmed_model is None:
                raise TimeoutError("Build confirmation timed out after 10 minutes")

            # ── Phase 3: Execute Ralph loop with user's chosen model ───────
            state.build_phase = "executing"
            confirmed_model = state.confirmed_model
            confirmed_iters = state.total_iterations
            _tlog(f"Build {state.id} [{_ts(t0)}] confirmed — model={confirmed_model}, iters={confirmed_iters}")
            logger.info("Build %s [%s] confirmed — model=%s, iters=%d", state.id, _ts(t0), confirmed_model, confirmed_iters)

            _emit({"type": "phase", "phase": "building", "message": "Starting build loop..."})

            exec_orch = TelosOrchestrator(
                project_dir=project_dir,
                context_dir=Path(context_dir) if context_dir else None,
                max_iterations=confirmed_iters,
                model=confirmed_model,
            )

            result = exec_orch.execute(on_event=_emit)
            _tlog(f"Build {state.id} [{_ts(t0)}] finished — success={result.success}")
            logger.info("Build %s [%s] finished — success=%s", state.id, _ts(t0), result.success)
            state.status = "completed"
            state.success = result.success
            state.iteration = result.iterations
        except Exception as exc:
            _tlog(f"Build {state.id} [{_ts(t0)}] FAILED: {exc}")
            logger.exception("Build %s [%s] failed", state.id, _ts(t0))
            state.status = "failed"
            state.success = False
            state.error = str(exc)
