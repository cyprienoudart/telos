"""Build API — triggers and monitors the Ralph loop."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from server.models import (
    BuildStartRequest,
    BuildStartResponse,
    BuildStatusResponse,
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

    state = _get_runner().start(
        transcript=transcript,
        project_dir=req.project_dir,
        context_dir=req.context_dir,
        max_iterations=req.max_iterations,
        model=req.model,
    )

    return BuildStartResponse(build_id=state.id, status="started")


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
            # Check for new progress lines
            if state.progress_path and state.progress_path.exists():
                content = state.progress_path.read_text()
                if len(content) > last_pos:
                    new_text = content[last_pos:]
                    last_pos = len(content)
                    yield {"event": "progress", "data": new_text}

            # Send status heartbeat
            yield {
                "event": "status",
                "data": f'{{"status":"{state.status}","iteration":{state.iteration}}}',
            }

            if state.status in ("completed", "failed"):
                yield {
                    "event": "done",
                    "data": f'{{"success":{str(state.success).lower()},"error":{repr(state.error)}}}',
                }
                break

            await asyncio.sleep(2)

    return EventSourceResponse(event_generator())
