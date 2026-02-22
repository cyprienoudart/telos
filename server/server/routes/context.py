"""Context API — processes uploaded files via Gemini multimodal pipeline."""

from __future__ import annotations

import base64
import logging
import shutil
import tempfile
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, File, UploadFile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/context", tags=["context"])

# Supported MIME → extension mapping for the multimodal pipeline
_IMAGE_MIMES = {
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "image/bmp", "image/tiff",
}
_PDF_MIMES = {"application/pdf"}


def _get_mime(file: UploadFile) -> str:
    """Return the effective MIME type of an uploaded file."""
    if file.content_type:
        return file.content_type
    ext = Path(file.filename or "").suffix.lower()
    ext_map = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".gif": "image/gif",
        ".webp": "image/webp", ".bmp": "image/bmp",
        ".tiff": "image/tiff", ".pdf": "application/pdf",
    }
    return ext_map.get(ext, "application/octet-stream")


@router.post("/process")
async def process_files(files: List[UploadFile] = File(...)):
    """Accept uploaded files (images, PDFs) and return text descriptions.

    Uses the Gemini multimodal pipeline (OpenRouter) to convert each file
    to a searchable text description.  Also persists raw files to a temp
    directory so the conversation route can copy them to the session folder.

    Returns:
        { extracted_text, file_count, errors, files_dir }
    """
    descriptions: List[str] = []
    errors: List[str] = []

    # Persist raw files so they survive beyond this request
    files_dir = Path(tempfile.mkdtemp(prefix="telos_files_"))

    for file in files:
        mime = _get_mime(file)
        filename = file.filename or "unknown"

        try:
            content = await file.read()

            # Save the raw file to the temp directory
            dest = files_dir / filename
            dest.write_bytes(content)

            if mime in _IMAGE_MIMES:
                text = await _describe_image_bytes(content, mime, filename)
            elif mime in _PDF_MIMES:
                text = await _describe_pdf_bytes(content, filename)
            else:
                # Try to read as plain text
                try:
                    text = content.decode("utf-8", errors="replace")
                except Exception:
                    errors.append(f"Unsupported file type for {filename}: {mime}")
                    continue

            descriptions.append(f"[{filename}]\n{text}")

        except Exception as exc:
            logger.warning("Failed to process file %s: %s", filename, exc, exc_info=True)
            errors.append(f"Failed to process {filename}: {str(exc)}")

    extracted_text = "\n\n---\n\n".join(descriptions) if descriptions else ""

    return {
        "extracted_text": extracted_text,
        "file_count": len(descriptions),
        "errors": errors,
        "files_dir": str(files_dir),
    }


def copy_files_to_session(files_dir: str, session_dir: Path) -> None:
    """Copy uploaded files from the temp dir into the session directory."""
    src = Path(files_dir)
    if not src.exists():
        return
    dest = session_dir / "uploads"
    dest.mkdir(exist_ok=True)
    for f in src.iterdir():
        if f.is_file():
            shutil.copy2(str(f), str(dest / f.name))
    # Clean up the temp directory
    shutil.rmtree(str(src), ignore_errors=True)


async def _describe_image_bytes(content: bytes, mime: str, filename: str) -> str:
    """Describe an image using the Gemini vision model via OpenRouter."""
    import asyncio

    try:
        from telos_agent.mcp.gemini.multimodal import _vision_call
    except ImportError:
        # Fallback: use OpenRouter directly
        return await asyncio.to_thread(_vision_call_standalone, content, mime)

    b64 = base64.standard_b64encode(content).decode()
    return await asyncio.to_thread(_vision_call, mime, b64)


async def _describe_pdf_bytes(content: bytes, filename: str) -> str:
    """Describe a PDF using text extraction + vision fallback."""
    import asyncio

    try:
        from telos_agent.mcp.gemini.multimodal import _describe_pdf

        # Write to a temp file so the existing pipeline can process it
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)

        try:
            return await asyncio.to_thread(_describe_pdf, tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

    except ImportError:
        # Fallback: use OpenRouter file API directly
        return await asyncio.to_thread(_file_call_standalone, content, filename)


def _vision_call_standalone(content: bytes, mime: str) -> str:
    """Standalone vision call using OpenRouter (no telos_agent dependency)."""
    import os
    import openai

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return "(OPENROUTER_API_KEY not set — could not describe image)"

    client = openai.OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        default_headers={"X-Title": "telos-context"},
    )

    b64 = base64.standard_b64encode(content).decode()
    response = client.chat.completions.create(
        model="google/gemini-2.0-flash-001",
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                {"type": "text", "text": (
                    "Describe this in full detail for a searchable knowledge base index. "
                    "Include all visible text, labels, data, tables, diagrams, and key information."
                )},
            ],
        }],
        max_tokens=500,
        temperature=0.1,
    )
    return response.choices[0].message.content or "(no description returned)"


def _file_call_standalone(content: bytes, filename: str) -> str:
    """Standalone file call for PDFs using OpenRouter."""
    import os
    import openai

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return "(OPENROUTER_API_KEY not set — could not describe PDF)"

    client = openai.OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        default_headers={"X-Title": "telos-context"},
    )

    b64 = base64.standard_b64encode(content).decode()
    response = client.chat.completions.create(
        model="google/gemini-2.0-flash-001",
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "file",
                    "file": {
                        "filename": filename,
                        "file_data": f"data:application/pdf;base64,{b64}",
                    },
                },
                {"type": "text", "text": (
                    "Describe this document in full detail for a searchable knowledge base index. "
                    "Include all visible text, data, tables, and key information."
                )},
            ],
        }],
        max_tokens=500,
        temperature=0.1,
    )
    return response.choices[0].message.content or "(no description returned)"
