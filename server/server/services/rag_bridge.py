"""Parallel Gemini RAG pre-answering for unknown elements.

Queries the Gemini context pipeline for each unknown element description
in parallel via asyncio.to_thread (the pipeline is synchronous).
Only returns answers where the model was confident (not "I don't know").
"""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


async def pre_answer_elements(
    unknown_descriptions: list[str],
    context_dir: str | None = None,
) -> dict[str, str]:
    """Query the RAG pipeline for each unknown element in parallel.

    Args:
        unknown_descriptions: List of element descriptions to query.
        context_dir: Path to context files (used to set CONTEXT_DIR env var
                     before pipeline calls — must be set before server start).

    Returns:
        Mapping of {description: answer} for elements the RAG could answer.
        "I don't know" responses are filtered out.
    """
    if not unknown_descriptions:
        return {}

    # Set context dir if provided (pipeline reads from settings.CONTEXT_DIR)
    if context_dir:
        import os
        os.environ.setdefault("CONTEXT_DIR", context_dir)

    # Lazy import to avoid chromadb import at server startup
    try:
        from telos_agent.mcp.gemini.pipeline import _is_idk, answer_question
    except Exception:
        logger.warning("Gemini RAG pipeline not available, skipping pre-answering", exc_info=True)
        return {}

    answers: dict[str, str] = {}
    for desc in unknown_descriptions:
        try:
            result = await asyncio.to_thread(answer_question, desc)
            if isinstance(result, str) and not _is_idk(result):
                answers[desc] = result
        except Exception:
            logger.warning("RAG query failed for: %s", desc[:80], exc_info=True)

    return answers
