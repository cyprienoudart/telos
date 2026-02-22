"""Conversation API — drives the Ali interview loop."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from server.models import (
    ConversationAnswerRequest,
    ConversationAnswerResponse,
    ConversationStartRequest,
    ConversationStartResponse,
    ConversationStatusResponse,
)
from server.services.rag_bridge import pre_answer_elements
from server.services.session import SessionStore

router = APIRouter(prefix="/api/conversation", tags=["conversation"])

# Injected by main.py at startup
store: SessionStore | None = None


def _get_store() -> SessionStore:
    if store is None:
        raise RuntimeError("SessionStore not initialised")
    return store


@router.post("/start", response_model=ConversationStartResponse)
async def start_conversation(req: ConversationStartRequest):
    """First message → ConversationLoop.start() + optional RAG pre-answering."""
    s = _get_store()
    session = s.create()

    result = session.loop.start(
        req.message,
        additional_context=req.additional_context,
        github_url=req.github_url,
    )

    # Copy uploaded files into the session directory alongside context.md
    if req.files_dir:
        from server.routes.context import copy_files_to_session
        copy_files_to_session(req.files_dir, session.context_path.parent)

    session.question_info = result.get("_question_info") or {
        "targets": [],
        "question": result.get("first_question", ""),
    }

    # Parallel Gemini RAG pre-answering for undefined elements
    rag_answered_count = 0
    if not result["done"]:
        undefined = [
            e["description"]
            for e in session.loop.elements
            if e["status"] == "undefined"
        ]
        if undefined:
            rag_answers = await pre_answer_elements(undefined, req.context_dir)
            if rag_answers:
                rag_answered_count = session.loop.apply_rag_answers(rag_answers)

                # Recompute coverage after RAG answers
                coverage = session.loop.sft_model.get_coverage(session.loop.elements)
                threshold, _ = session.loop._compute_thresholds()
                result["initial_coverage"] = coverage
                result["done"] = coverage >= threshold

                # Regenerate first question if not done (targets may have changed)
                if not result["done"]:
                    candidates = session.loop.question_gen.generate_candidates(
                        session.loop.elements,
                        session.loop.clusters,
                        session.loop.conversation_history,
                        mission_task=session.loop.mission_task,
                    )
                    best = session.loop.question_gen.select_best(candidates)
                    result["first_question"] = best["question"] if best else None
                    session.question_info = best or {"targets": [], "question": ""}
                else:
                    result["first_question"] = None

    session.done = result["done"]

    return ConversationStartResponse(
        session_id=session.id,
        mission=result["mission"],
        categories=result["categories"],
        pre_answered_count=result["pre_answered_count"],
        rag_answered_count=rag_answered_count,
        total_elements=result["total_elements"],
        initial_coverage=result["initial_coverage"],
        first_question=result.get("first_question"),
        done=result["done"],
    )


@router.post("/{session_id}/answer", response_model=ConversationAnswerResponse)
async def answer_question(session_id: str, req: ConversationAnswerRequest):
    """User answer → process_answer() → next question or done."""
    session = _get_store().get(session_id)
    if session is None:
        raise HTTPException(404, f"Session {session_id} not found")
    if session.done:
        raise HTTPException(400, "Conversation already completed")

    result = session.loop.process_answer(req.answer, session.question_info)
    session.question_info = result.get("_question_info") or {
        "targets": [],
        "question": result.get("next_question", ""),
    }
    session.done = result["done"]

    # Cache transcript for build phase
    if session.done:
        session.transcript = session.loop.context_mgr.to_prompt()

    return ConversationAnswerResponse(
        resolved=result["resolved"],
        bonus=result["bonus"],
        coverage=result["coverage"],
        next_question=result.get("next_question"),
        done=result["done"],
        turn=result["turn"],
    )


@router.get("/{session_id}/status", response_model=ConversationStatusResponse)
async def get_status(session_id: str):
    """Current conversation coverage and element counts."""
    session = _get_store().get(session_id)
    if session is None:
        raise HTTPException(404, f"Session {session_id} not found")

    status = session.loop.get_status()
    return ConversationStatusResponse(**status)
