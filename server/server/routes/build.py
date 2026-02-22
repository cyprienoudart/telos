"""Build API — triggers and monitors the Ralph loop."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from server.models import (
    BuildStartRequest,
    BuildStartResponse,
    BuildStatusResponse,
    DebugBuildStartRequest,
)
from server.services.build_runner import BuildRunner
from server.services.session import SessionStore

router = APIRouter(prefix="/api/build", tags=["build"])

# Injected by main.py at startup
runner: BuildRunner | None = None
store: SessionStore | None = None


def _get_runner() -> BuildRunner:
    if runner is None:
        raise RuntimeError("BuildRunner not initialised")
    return runner


def _get_store() -> SessionStore:
    if store is None:
        raise RuntimeError("SessionStore not initialised")
    return store


@router.post("/start", response_model=BuildStartResponse)
async def start_build(req: BuildStartRequest):
    """Kick off plan_and_execute() in a background thread."""
    session = _get_store().get(req.session_id)
    if session is None:
        raise HTTPException(404, f"Session {req.session_id} not found")
    if not session.done:
        raise HTTPException(400, "Conversation not yet completed")

    transcript = session.transcript or session.loop.context_mgr.to_prompt()

    # Use cloned repo as build target; fall back to a temp dir
    project_dir = (
        str(session.repo_dir)
        if session.repo_dir
        else f"/tmp/telos-build-{session.id}"
    )

    state = _get_runner().start(
        transcript=transcript,
        project_dir=project_dir,
        context_dir=req.context_dir or (str(session.repo_dir) if session.repo_dir else None),
        max_iterations=req.max_iterations,
        model=req.model,
    )

    return BuildStartResponse(build_id=state.id, status="started")


# ── Debug shortcut — skip Ali interview, use fixture context ─────────

# Resolve fixture path relative to project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_DEFAULT_FIXTURE = _PROJECT_ROOT / "test" / "fixtures" / "debug_context.md"


@router.post("/debug-start", response_model=BuildStartResponse)
async def debug_start_build(req: DebugBuildStartRequest):
    """Skip the interview — read a fixture context file and start building."""
    fixture_path = Path(req.fixture_path) if req.fixture_path else _DEFAULT_FIXTURE

    if not fixture_path.exists():
        raise HTTPException(
            404,
            f"Fixture not found: {fixture_path}. "
            f"Create it at test/fixtures/debug_context.md",
        )

    transcript = fixture_path.read_text()
    if not transcript.strip():
        raise HTTPException(400, "Fixture file is empty")

    project_dir = req.project_dir or f"/tmp/telos-debug-build"

    state = _get_runner().start(
        transcript=transcript,
        project_dir=project_dir,
        context_dir=req.context_dir,
        max_iterations=req.max_iterations,
        model=req.model,
    )

    return BuildStartResponse(build_id=state.id, status="started")


@router.post("/reset")
async def reset_builds():
    """Delete all build state — used for demo resets."""
    r = _get_runner()
    count = len(r._builds)
    r._builds.clear()
    return {"deleted": count}


@router.get("/{build_id}/status", response_model=BuildStatusResponse)
async def build_status(build_id: str):
    """Poll build progress."""
    state = _get_runner().get(build_id)
    if state is None:
        raise HTTPException(404, f"Build {build_id} not found")

    return BuildStatusResponse(
        build_id=state.id,
        status=state.status,
        iteration=state.iteration,
        total_iterations=state.total_iterations,
        success=state.success,
        error=state.error,
    )


@router.get("/{build_id}/stream")
async def build_stream(build_id: str):
    """SSE stream — tails progress.txt every 2 seconds."""
    state = _get_runner().get(build_id)
    if state is None:
        raise HTTPException(404, f"Build {build_id} not found")

    async def event_generator():
        last_pos = 0
        while True:
            # Drain trajectory events from the thread-safe queue
            while state.event_queue:
                evt = state.event_queue.popleft()
                yield {"event": "trajectory", "data": json.dumps(evt)}

            # Check for new progress lines (kept for persistence/debugging)
            if state.progress_path and state.progress_path.exists():
                content = state.progress_path.read_text()
                if len(content) > last_pos:
                    new_text = content[last_pos:]
                    last_pos = len(content)
                    yield {"event": "progress", "data": new_text}

            # Send status heartbeat
            yield {
                "event": "status",
                "data": json.dumps({
                    "status": state.status,
                    "iteration": state.iteration,
                }),
            }

            if state.status in ("completed", "failed"):
                yield {
                    "event": "done",
                    "data": json.dumps({
                        "success": state.success,
                        "error": state.error,
                    }),
                }
                break

            await asyncio.sleep(0.2)

    return EventSourceResponse(event_generator())
