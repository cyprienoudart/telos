"""Build API — triggers and monitors the Ralph loop."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from server.models import (
    BuildConfirmRequest,
    BuildEstimateRequest,
    BuildStartRequest,
    BuildStartResponse,
    BuildStatusResponse,
    CostEstimateResponse,
    DebugBuildStartRequest,
    PhaseEstimateSchema,
    PrdCheckboxItem,
    PrdProgress,
    PrdProgressResponse,
)
from server.services.build_runner import BuildRunner, parse_prd_progress
from server.services.estimator import CostEstimate, estimate_build_cost
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


def _estimate_to_response(est: CostEstimate) -> CostEstimateResponse:
    """Convert a CostEstimate dataclass to the API response schema."""
    return CostEstimateResponse(
        low_usd=est.low_usd,
        typical_usd=est.typical_usd,
        high_usd=est.high_usd,
        model=est.model,
        max_iterations=est.max_iterations,
        estimated_prd_count=est.estimated_prd_count,
        breakdown=[
            PhaseEstimateSchema(
                phase=p.phase,
                input_tokens=p.input_tokens,
                output_tokens=p.output_tokens,
                model=p.model,
                cost_usd=p.cost_usd,
            )
            for p in est.breakdown
        ],
    )


@router.post("/estimate", response_model=CostEstimateResponse)
async def estimate_build(req: BuildStartRequest):
    """Return a cost estimate without starting the build."""
    session = _get_store().get(req.session_id)
    if session is None:
        raise HTTPException(404, f"Session {req.session_id} not found")
    if not session.done:
        raise HTTPException(400, "Conversation not yet completed")

    transcript = session.transcript or session.loop.context_mgr.to_prompt()
    total_elements = len(session.loop.elements)

    est = estimate_build_cost(
        transcript_len=len(transcript),
        total_elements=total_elements,
        max_iterations=req.max_iterations,
        model=req.model,
    )

    return _estimate_to_response(est)


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


@router.post("/debug-estimate", response_model=CostEstimateResponse)
async def debug_estimate_build(req: DebugBuildStartRequest):
    """Return a cost estimate for a debug build without starting it."""
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

    # No Ali session — estimate element count from fixture size
    estimated_elements = max(5, len(transcript) // 200)

    est = estimate_build_cost(
        transcript_len=len(transcript),
        total_elements=estimated_elements,
        max_iterations=req.max_iterations,
        model=req.model,
    )

    return _estimate_to_response(est)


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
        build_phase=state.build_phase,
        iteration=state.iteration,
        total_iterations=state.total_iterations,
        success=state.success,
        error=state.error,
    )


@router.get("/{build_id}/prds", response_model=PrdProgressResponse)
async def build_prd_progress(build_id: str):
    """Poll per-PRD checkbox progress."""
    state = _get_runner().get(build_id)
    if state is None:
        raise HTTPException(404, f"Build {build_id} not found")

    prds_dir = state.project_dir / "prds" if state.project_dir else None
    raw = parse_prd_progress(prds_dir) if prds_dir else []

    prds = [
        PrdProgress(
            filename=p["filename"],
            title=p["title"],
            items=[PrdCheckboxItem(**i) for i in p["items"]],
            total=p["total"],
            done=p["done"],
            percent=p["percent"],
        )
        for p in raw
    ]

    total_items = sum(p.total for p in prds)
    total_done = sum(p.done for p in prds)

    return PrdProgressResponse(
        build_id=build_id,
        prds=prds,
        total_items=total_items,
        total_done=total_done,
        overall_percent=round((total_done / total_items) * 100, 1) if total_items > 0 else 0.0,
    )


@router.post("/{build_id}/estimate", response_model=CostEstimateResponse)
async def build_estimate(build_id: str, req: BuildEstimateRequest):
    """Return a cost estimate for a build that has finished planning."""
    state = _get_runner().get(build_id)
    if state is None:
        raise HTTPException(404, f"Build {build_id} not found")
    if state.build_phase != "planned":
        raise HTTPException(400, f"Build is in '{state.build_phase}' phase, not 'planned'")

    est = estimate_build_cost(
        transcript_len=state.transcript_len,
        total_elements=0,  # not used when prd_count is provided
        max_iterations=req.max_iterations,
        model=req.model,
        prd_count=state.prd_count,
    )

    return _estimate_to_response(est)


@router.post("/{build_id}/confirm")
async def build_confirm(build_id: str, req: BuildConfirmRequest):
    """Confirm a planned build — unblocks the waiting thread."""
    state = _get_runner().get(build_id)
    if state is None:
        raise HTTPException(404, f"Build {build_id} not found")
    if state.build_phase != "planned":
        raise HTTPException(400, f"Build is in '{state.build_phase}' phase, not 'planned'")

    state.total_iterations = req.max_iterations
    state.confirmed_model = req.model
    return {"status": "confirmed"}


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
                    "build_phase": state.build_phase,
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
