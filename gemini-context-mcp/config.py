"""
All tuneable constants for gemini-context-mcp.
Override any value via the corresponding environment variable.
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Context store root
# ---------------------------------------------------------------------------

# Mutable via set_base_dir(). Tests/benchmark use that to switch projects.
BASE_DIR: Path = Path(os.environ.get("CONTEXT_DIR", "./context")).resolve()


def set_base_dir(path: str | Path) -> None:
    """Override BASE_DIR at runtime (e.g. for benchmarks or tests)."""
    global BASE_DIR
    BASE_DIR = Path(path).resolve()

# ---------------------------------------------------------------------------
# File-type filters
# ---------------------------------------------------------------------------

# Multimodal file types — processed via vision LLM, not plain-text chunking.
IMAGE_EXTS: frozenset[str] = frozenset({
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff",
})
PDF_EXTS: frozenset[str] = frozenset({".pdf"})

# True binaries — skipped entirely (no text, no vision value).
BINARY_EXTS: frozenset[str] = frozenset({
    # archives
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z",
    # compiled / native
    ".exe", ".dll", ".so", ".bin", ".wasm", ".pyc", ".class",
    # ML weights
    ".pt", ".pth", ".onnx", ".pb", ".tflite",
    ".h5", ".hdf5", ".safetensors", ".ckpt",
    ".npy", ".npz", ".pkl", ".joblib",
    # data / media
    ".parquet", ".feather", ".arrow",
    ".mp3", ".mp4", ".wav", ".avi", ".mov",
    ".ttf", ".otf", ".woff", ".woff2",
    ".ico", ".svgz",
})

SKIP_FILES: frozenset[str] = frozenset({
    # ignore / exclude manifests — list directory/pattern names, not real content
    ".gitignore", ".dockerignore", ".npmignore",
    ".eslintignore", ".prettierignore",
})

SKIP_DIRS: frozenset[str] = frozenset({
    "node_modules", ".venv", "venv", "env", ".env",
    ".git", "__pycache__",
    "dist", "build", ".next", ".nuxt", ".svelte-kit",
    "target",                          # Rust
    "vendor",                          # Go / PHP
    "coverage", "htmlcov", ".coverage",
    ".mypy_cache", ".ruff_cache", ".pytest_cache",
    ".tox", ".nox",
    "site-packages",
})

# ---------------------------------------------------------------------------
# LLM (OpenRouter)
# ---------------------------------------------------------------------------

LLM_BASE_URL       = "https://openrouter.ai/api/v1"
LLM_MODEL          = os.environ.get("OPENROUTER_MODEL", "google/gemini-2.0-flash-001")
VISION_MODEL       = os.environ.get("VISION_MODEL", LLM_MODEL)   # must support vision input
MAX_TOKENS_SUMMARY = 700
MAX_TOKENS_ANSWER  = 250
MAX_TOKENS_VISION  = 500   # per image / PDF description

# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

CHUNK_MAX_WORDS     = 300   # target chunk size in words
CHUNK_OVERLAP_WORDS = 50    # words carried over between consecutive chunks

# ---------------------------------------------------------------------------
# Embeddings + vector store
# ---------------------------------------------------------------------------

EMBED_MODEL      = os.environ.get("FASTEMBED_MODEL", "BAAI/bge-small-en-v1.5")
CHROMA_DIR       = Path(os.environ.get(
    "CHROMA_DIR", "~/.cache/gemini-context-mcp/chroma"
)).expanduser()
SEARCH_TOP_K     = 3     # chunks sent to the LLM per query
CACHE_SIMILARITY = 0.85  # minimum cosine similarity for a semantic cache hit
