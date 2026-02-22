"""
Vector store: FastEmbed embeddings + ChromaDB context index + semantic cache.

Public API
----------
  embed_texts(texts)               embed a list of strings → float vectors
  retrieve(query, query_emb=None)  top-K context chunks for a query
  cache_lookup(query_emb)          return cached answer or None
  cache_store(query, emb, answer)  persist a new cache entry
  warm_index()                     ensure the index is built (used by benchmark)
"""

from __future__ import annotations

import hashlib

import chromadb
from fastembed import TextEmbedding

import config
from chunker import build_all_chunks, context_hash
import multimodal


# ---------------------------------------------------------------------------
# FastEmbed — lazy singleton
# ---------------------------------------------------------------------------

_embed_model: TextEmbedding | None = None


def _get_embed_model() -> TextEmbedding:
    global _embed_model
    if _embed_model is None:
        _embed_model = TextEmbedding(config.EMBED_MODEL)
    return _embed_model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed *texts* and return one float vector per text."""
    return [e.tolist() for e in _get_embed_model().embed(texts, batch_size=32)]


# ---------------------------------------------------------------------------
# ChromaDB client — lazy singleton
# ---------------------------------------------------------------------------

_chroma_client: chromadb.PersistentClient | None = None


def _get_chroma_client() -> chromadb.PersistentClient:
    global _chroma_client
    if _chroma_client is None:
        config.CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
    return _chroma_client


def _project_id() -> str:
    """Short hash of config.BASE_DIR used to namespace collections per project."""
    return hashlib.md5(str(config.BASE_DIR).encode()).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Context index
# ---------------------------------------------------------------------------

def _full_hash() -> str:
    """Combined hash of all text files + all multimodal files."""
    combined = context_hash() + multimodal.multimodal_hash()
    return hashlib.md5(combined.encode()).hexdigest()


def _get_context_collection() -> chromadb.Collection:
    """
    Return the ChromaDB collection for the current project.
    Rebuilds automatically when any text, image, or PDF file changes.
    """
    client = _get_chroma_client()
    name   = f"ctx_{_project_id()}"
    h      = _full_hash()

    try:
        col = client.get_collection(name)
        if col.metadata.get("content_hash") == h:
            return col                   # index still valid — reuse it
        client.delete_collection(name)   # files changed — rebuild
    except Exception:
        pass

    chunks = build_all_chunks() + multimodal.build_multimodal_chunks()
    col    = client.create_collection(
        name,
        metadata={"content_hash": h, "hnsw:space": "cosine"},
    )
    if not chunks:
        return col

    texts      = [f"[{c.source}]\n{c.text}" for c in chunks]
    ids        = [str(i) for i in range(len(chunks))]
    metadatas  = [{"source": c.source} for c in chunks]
    embeddings = embed_texts(texts)

    for i in range(0, len(chunks), 500):     # ChromaDB safe batch size
        col.add(
            ids=ids[i:i+500],
            documents=texts[i:i+500],
            embeddings=embeddings[i:i+500],
            metadatas=metadatas[i:i+500],
        )
    return col


def warm_index() -> None:
    """Ensure the context index is built. Used by benchmark for timing cold builds."""
    _get_context_collection()


def retrieve(query: str, query_emb: list[float] | None = None) -> str:
    """
    Return the top config.SEARCH_TOP_K chunks for *query* as a context string.
    Pass *query_emb* to skip re-embedding when already computed by the caller.
    """
    col = _get_context_collection()
    if col.count() == 0:
        return "(no relevant content found in the context store)"
    if query_emb is None:
        query_emb = embed_texts([query])[0]
    results = col.query(
        query_embeddings=[query_emb],
        n_results=min(config.SEARCH_TOP_K, col.count()),
        include=["documents"],
    )
    return "\n\n---\n\n".join(results["documents"][0])


# ---------------------------------------------------------------------------
# Semantic cache
# ---------------------------------------------------------------------------

def _get_cache_collection() -> chromadb.Collection:
    """
    Persistent cache: query_embedding → LLM answer.
    Wiped automatically when context files change so stale answers are never
    returned after an edit.
    """
    client = _get_chroma_client()
    name   = f"cache_{_project_id()}"
    h      = _full_hash()

    try:
        col = client.get_collection(name)
        if col.metadata.get("content_hash") == h:
            return col
        client.delete_collection(name)   # files changed — stale answers
    except Exception:
        pass

    return client.create_collection(
        name,
        metadata={"content_hash": h, "hnsw:space": "cosine"},
    )


def cache_lookup(query_emb: list[float]) -> str | None:
    """
    Return a stored answer if a similar-enough query exists, else None.
    Similarity threshold: config.CACHE_SIMILARITY (cosine).
    """
    cache = _get_cache_collection()
    if cache.count() == 0:
        return None
    hit = cache.query(
        query_embeddings=[query_emb],
        n_results=1,
        include=["documents", "distances"],
    )
    # ChromaDB cosine space: distance = 1 - similarity, so 0 = identical.
    if hit["distances"][0][0] <= (1.0 - config.CACHE_SIMILARITY):
        return hit["documents"][0][0]
    return None


def cache_store(query: str, query_emb: list[float], answer: str) -> None:
    """Persist *answer* in the semantic cache keyed by *query_emb*."""
    cache = _get_cache_collection()
    cache.upsert(
        ids=[hashlib.md5(query.encode()).hexdigest()],
        documents=[answer],
        embeddings=[query_emb],
        metadatas=[{"query": query[:200]}],
    )
