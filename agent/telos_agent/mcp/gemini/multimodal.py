"""
Multimodal processing: images and PDFs → text descriptions → Chunks.

Images are described by a vision LLM (settings.VISION_MODEL) via a single
API call. PDFs are first processed with pypdf for text extraction; pages
with very little text (likely scanned/image pages) are sent to the vision
model for description.

Public API
----------
  build_multimodal_chunks()   describe every image + PDF → list[Chunk]
  multimodal_hash()           MD5 over image/PDF file sizes + mtimes
"""

from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path

import openai
from dotenv import load_dotenv

from . import settings
from .chunker import Chunk, chunk_file

load_dotenv()

# Minimum extracted words for a PDF page to be considered text-based.
# Pages below this threshold are sent to the vision model instead.
_PDF_PAGE_MIN_WORDS = 30

_VISION_PROMPT = (
    "Describe this in full detail for a searchable knowledge base index. "
    "Include all visible text, labels, data, tables, diagrams, and key information. "
    "Be comprehensive and specific."
)

# MIME types for OpenRouter vision API
_IMAGE_MIME: dict[str, str] = {
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png":  "image/png",
    ".gif":  "image/gif",
    ".webp": "image/webp",
    ".bmp":  "image/bmp",
    ".tiff": "image/tiff",
}


# ---------------------------------------------------------------------------
# Vision client — lazy singleton (same OpenRouter key as pipeline.py)
# ---------------------------------------------------------------------------

_vision_client: openai.OpenAI | None = None


def _get_vision_client() -> openai.OpenAI:
    global _vision_client
    if _vision_client is None:
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY is not set. Copy .env.example → .env and add your key."
            )
        _vision_client = openai.OpenAI(
            base_url=settings.LLM_BASE_URL,
            api_key=api_key,
            default_headers={"X-Title": "gemini-context-mcp"},
        )
    return _vision_client


def _vision_call(mime: str, b64_data: str) -> str:
    """Send a base64-encoded image to the vision model and return the description."""
    response = _get_vision_client().chat.completions.create(
        model=settings.VISION_MODEL,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64_data}"}},
                {"type": "text", "text": _VISION_PROMPT},
            ],
        }],
        max_tokens=settings.MAX_TOKENS_VISION,
        temperature=0.1,
    )
    return response.choices[0].message.content or "(no description returned)"


def _file_call(filename: str, b64_data: str) -> str:
    """Send a base64-encoded file (e.g. PDF) via OpenRouter's file content type."""
    response = _get_vision_client().chat.completions.create(
        model=settings.VISION_MODEL,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "file",
                    "file": {
                        "filename": filename,
                        "file_data": f"data:application/pdf;base64,{b64_data}",
                    },
                },
                {"type": "text", "text": _VISION_PROMPT},
            ],
        }],
        max_tokens=settings.MAX_TOKENS_VISION,
        temperature=0.1,
    )
    return response.choices[0].message.content or "(no description returned)"


# ---------------------------------------------------------------------------
# Image processing
# ---------------------------------------------------------------------------

def _describe_image(path: Path) -> str:
    mime  = _IMAGE_MIME.get(path.suffix.lower(), "image/jpeg")
    b64   = base64.standard_b64encode(path.read_bytes()).decode()
    return _vision_call(mime, b64)


# ---------------------------------------------------------------------------
# PDF processing
# ---------------------------------------------------------------------------

def _describe_pdf(path: Path) -> str:
    """
    Extract text from *path* with pypdf.
    Pages with fewer than _PDF_PAGE_MIN_WORDS words are flagged as image
    pages. If any image pages exist, the whole PDF is sent to the vision
    model via the file content type. Text pages are included as-is.
    If pypdf fails entirely, the whole file is sent to vision as fallback.
    """
    try:
        import pypdf
        reader     = pypdf.PdfReader(str(path))
        page_texts: list[str] = []
        has_image_pages = False

        for i, page in enumerate(reader.pages):
            text = (page.extract_text() or "").strip()
            if len(text.split()) >= _PDF_PAGE_MIN_WORDS:
                page_texts.append(f"[Page {i + 1}]\n{text}")
            else:
                has_image_pages = True

        if has_image_pages:
            b64 = base64.standard_b64encode(path.read_bytes()).decode()
            desc = _file_call(path.name, b64)
            page_texts.append(f"[Image pages — vision]\n{desc}")

        if page_texts:
            return "\n\n".join(page_texts)
    except Exception:
        pass

    # Fallback: send the whole file to vision
    b64 = base64.standard_b64encode(path.read_bytes()).decode()
    return _file_call(path.name, b64)


# ---------------------------------------------------------------------------
# File traversal
# ---------------------------------------------------------------------------

def _walk_multimodal_paths():
    """Yield every image and PDF path under settings.BASE_DIR."""
    stack = [settings.BASE_DIR]
    while stack:
        current = stack.pop()
        try:
            entries = sorted(current.iterdir(), key=lambda e: e.name)
        except OSError:
            continue
        for entry in entries:
            if entry.is_dir():
                if entry.name not in settings.SKIP_DIRS:
                    stack.append(entry)
            elif entry.is_file():
                ext = entry.suffix.lower()
                if ext in settings.IMAGE_EXTS or ext in settings.PDF_EXTS:
                    yield entry


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def multimodal_hash() -> str:
    """MD5 over image/PDF file sizes + mtimes. Used alongside context_hash()."""
    h = hashlib.md5()
    for p in sorted(_walk_multimodal_paths()):
        try:
            st = p.stat()
            h.update(f"{p}:{st.st_size}:{st.st_mtime_ns}".encode())
        except OSError:
            continue
    return h.hexdigest()


def build_multimodal_chunks() -> list[Chunk]:
    """
    Describe every image and PDF under settings.BASE_DIR via vision LLM / pypdf.
    Returns Chunks whose text is the generated description, ready to embed.
    """
    chunks: list[Chunk] = []
    for path in _walk_multimodal_paths():
        rel = str(path.relative_to(settings.BASE_DIR)).replace("\\", "/")
        try:
            if path.suffix.lower() in settings.IMAGE_EXTS:
                text = _describe_image(path)
            else:
                text = _describe_pdf(path)
            chunks.extend(chunk_file(rel, text))
        except Exception as exc:
            # Don't abort the whole index if one file fails
            chunks.append(Chunk(source=rel, text=f"(could not process: {exc})"))
    return chunks
