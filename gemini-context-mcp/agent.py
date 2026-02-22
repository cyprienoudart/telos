"""
Context agent — public API.

  summarize()              → 15-bullet plain-English overview, cached in memory
  answer_question(query)   → 1-5 sentence plain-English answer, semantically cached

answer_question() pipeline
--------------------------
  1. Embed query with FastEmbed (store.embed_texts).
  2. Semantic cache lookup  → instant return on hit (≥ 0.85 cosine similarity).
  3. Dense retrieval        → top 3 chunks from ChromaDB (store.retrieve).
  4. LLM call               → answer in 1-5 plain-English sentences.
  5. Store answer in semantic cache.

summarize() pipeline
--------------------
  First chunk per file → single LLM call.
  Cached in memory until files change (detected via chunker.context_hash).
"""

from __future__ import annotations

import os

import openai
from dotenv import load_dotenv

import config
from chunker import Chunk, build_all_chunks, context_hash
from store import cache_lookup, cache_store, embed_texts, retrieve

load_dotenv()


# ---------------------------------------------------------------------------
# OpenAI / OpenRouter client — lazy singleton
# ---------------------------------------------------------------------------

_client: openai.OpenAI | None = None


def _get_client() -> openai.OpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY is not set. Copy .env.example → .env and add your key."
            )
        _client = openai.OpenAI(
            base_url=config.LLM_BASE_URL,
            api_key=api_key,
            default_headers={"X-Title": "gemini-context-mcp"},
        )
    return _client


def _llm(prompt: str, max_tokens: int, temperature: float) -> str:
    """Single-turn LLM call via OpenRouter. Returns the response text."""
    response = _get_client().chat.completions.create(
        model=config.LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return response.choices[0].message.content or ""


# ---------------------------------------------------------------------------
# summarize() — first chunk per file, in-memory cache
# ---------------------------------------------------------------------------

_summary_cache: str | None = None
_summary_hash:  str | None = None


def summarize() -> str:
    """
    Produce a 15-bullet plain-English overview of the entire context store.
    Written for a non-technical reader. Cached in memory until files change.

    Note: uses only the first chunk per file, so very large files may not
    be fully represented in the summary.
    """
    global _summary_cache, _summary_hash

    h = context_hash()
    if _summary_cache is not None and _summary_hash == h:
        return _summary_cache

    all_chunks = build_all_chunks()
    seen: set[str] = set()
    per_file: list[Chunk] = []
    for c in all_chunks:
        if c.source not in seen:
            seen.add(c.source)
            per_file.append(c)

    context = "\n\n---\n\n".join(f"[{c.source}]\n{c.text}" for c in per_file)
    prompt  = (
        "Below is a knowledge base. Summarise it in exactly 15 bullet points.\n"
        "Rules:\n"
        "- Write for someone who has never programmed before.\n"
        "- Each bullet must be one plain-English sentence.\n"
        "- No technical jargon, no code, no file names, no low-level details.\n"
        "- Focus on what the project is, who is involved, and what matters.\n\n"
        f"Knowledge base:\n{context}\n\n"
        "Your 15-bullet summary:"
    )
    _summary_cache = _llm(prompt, config.MAX_TOKENS_SUMMARY, temperature=0.3) \
                     or "(no summary returned)"
    _summary_hash  = h
    return _summary_cache


# ---------------------------------------------------------------------------
# answer_question() — semantic cache → dense retrieval → LLM
# ---------------------------------------------------------------------------

def answer_question(query: str) -> str:
    """
    Answer *query* using retrieved context.
    Returns 1-5 plain-English sentences for a non-technical reader.
    Checks the semantic cache before calling the LLM.
    """
    # Embed once — reused for both cache lookup and retrieval.
    query_emb = embed_texts([query])[0]

    cached = cache_lookup(query_emb)
    if cached:
        return cached

    context = retrieve(query, query_emb)
    prompt  = (
        "You are a friendly assistant. Answer the question below using only the "
        "retrieved excerpts provided. Do not make anything up.\n"
        "Rules:\n"
        "- Answer in 1 to 5 plain-English sentences.\n"
        "- Imagine you are explaining to someone who is not technical at all.\n"
        "- No bullet points, no markdown, no code snippets.\n"
        "- If the answer is not in the excerpts, say so in one simple sentence.\n\n"
        f"Retrieved excerpts:\n{context}\n\n"
        f"Question: {query}\n\n"
        "Answer:"
    )
    answer = _llm(prompt, config.MAX_TOKENS_ANSWER, temperature=0.2) \
             or "I couldn't find an answer to that."

    cache_store(query, query_emb, answer)
    return answer
