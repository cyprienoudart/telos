"""
Filesystem tools for the Gemini context agent.

All paths are resolved relative to BASE_DIR (the context store root).
Path traversal protection is enforced at a single chokepoint: _safe_resolve().
All public functions return strings or a multimodal sentinel tuple — they never raise.
"""

from __future__ import annotations

import mimetypes
import os
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_DIR: Path = Path(os.environ.get("CONTEXT_DIR", "./context")).resolve()

# File size limits
_MAX_TEXT_CHARS = 80_000
_MAX_GREP_RESULTS = 50

# Extensions treated as binary/multimodal (not grepped, read as bytes)
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff"}
_PDF_EXTS = {".pdf"}
_BINARY_EXTS = _IMAGE_EXTS | _PDF_EXTS | {
    ".zip", ".tar", ".gz", ".exe", ".dll", ".so", ".bin",
    ".pyc", ".class", ".wasm",
}


# ---------------------------------------------------------------------------
# Path safety
# ---------------------------------------------------------------------------

def _safe_resolve(path: str) -> Path | None:
    """
    Resolve *path* to an absolute Path that must be inside BASE_DIR.
    Returns None if the path escapes BASE_DIR or is otherwise invalid.
    Handles both absolute and relative inputs; follows symlinks.
    """
    try:
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = BASE_DIR / candidate
        resolved = candidate.resolve()          # follows symlinks
        resolved.relative_to(BASE_DIR)          # raises ValueError if outside
        return resolved
    except (ValueError, OSError):
        return None


def _outside_error(path: str) -> str:
    return f"ERROR: Path '{path}' is outside the context store or invalid."


# ---------------------------------------------------------------------------
# Tool: list_files
# ---------------------------------------------------------------------------

def list_files(directory: str = ".") -> str:
    """
    List all files in *directory* (relative to the context store root),
    recursively. Returns a newline-separated list of relative paths, or an
    error string.

    Args:
        directory: Path to list, relative to the context store root.
                   Defaults to the root itself (".").
    """
    resolved = _safe_resolve(directory)
    if resolved is None:
        return _outside_error(directory)

    if not resolved.exists():
        return f"ERROR: Directory '{directory}' does not exist."
    if not resolved.is_dir():
        return f"ERROR: '{directory}' is not a directory."

    try:
        entries: list[str] = []
        for p in sorted(resolved.rglob("*")):
            if p.is_file():
                rel = p.relative_to(BASE_DIR)
                entries.append(str(rel).replace("\\", "/"))
        if not entries:
            return "(empty directory)"
        return "\n".join(entries)
    except OSError as exc:
        return f"ERROR: Could not list '{directory}': {exc}"


# ---------------------------------------------------------------------------
# Tool: read_file
# ---------------------------------------------------------------------------

_MULTIMODAL_SENTINEL = "__MULTIMODAL__"


def read_file(path: str) -> str | tuple:
    """
    Read a file from the context store.

    For text files: returns the file content (capped at 80,000 characters).
    For images and PDFs: returns a sentinel tuple so the agent can describe
    the content using Gemini's vision capability instead of returning raw bytes.

    Args:
        path: File path relative to the context store root.
    """
    resolved = _safe_resolve(path)
    if resolved is None:
        return _outside_error(path)

    if not resolved.exists():
        return f"ERROR: File '{path}' does not exist."
    if not resolved.is_dir():
        pass  # fall through — it's a file
    if resolved.is_dir():
        return f"ERROR: '{path}' is a directory, not a file."

    suffix = resolved.suffix.lower()
    mime_type, _ = mimetypes.guess_type(str(resolved))

    # --- Multimodal files → sentinel tuple ---
    if suffix in _IMAGE_EXTS or suffix in _PDF_EXTS:
        try:
            data = resolved.read_bytes()
            return (_MULTIMODAL_SENTINEL, data, mime_type or "application/octet-stream", path)
        except OSError as exc:
            return f"ERROR: Could not read '{path}': {exc}"

    # --- Text files ---
    try:
        text = resolved.read_text(encoding="utf-8", errors="replace")
        if len(text) > _MAX_TEXT_CHARS:
            text = text[:_MAX_TEXT_CHARS] + f"\n\n[...truncated at {_MAX_TEXT_CHARS} characters]"
        return text
    except OSError as exc:
        return f"ERROR: Could not read '{path}': {exc}"


# ---------------------------------------------------------------------------
# Tool: grep
# ---------------------------------------------------------------------------

def grep(pattern: str, directory: str = ".") -> str:
    """
    Search for a regex pattern across all text files in *directory*
    (relative to the context store root), recursively.

    Skips binary files (images, PDFs, compiled binaries, etc.).
    Returns up to 50 results in the format ``path:line_number: matched_line``.

    Args:
        pattern: Regular expression to search for.
        directory: Directory to search, relative to the context store root.
                   Defaults to the root itself.
    """
    resolved = _safe_resolve(directory)
    if resolved is None:
        return _outside_error(directory)

    if not resolved.exists():
        return f"ERROR: Directory '{directory}' does not exist."
    if not resolved.is_dir():
        return f"ERROR: '{directory}' is not a directory."

    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as exc:
        return f"ERROR: Invalid regex pattern '{pattern}': {exc}"

    results: list[str] = []
    try:
        for p in sorted(resolved.rglob("*")):
            if not p.is_file():
                continue
            if p.suffix.lower() in _BINARY_EXTS:
                continue

            rel = str(p.relative_to(BASE_DIR)).replace("\\", "/")
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            for lineno, line in enumerate(text.splitlines(), start=1):
                if regex.search(line):
                    results.append(f"{rel}:{lineno}: {line.rstrip()}")
                    if len(results) >= _MAX_GREP_RESULTS:
                        results.append(f"[...results capped at {_MAX_GREP_RESULTS}]")
                        return "\n".join(results)
    except OSError as exc:
        return f"ERROR: Could not search '{directory}': {exc}"

    if not results:
        return f"No matches found for pattern '{pattern}' in '{directory}'."
    return "\n".join(results)


# ---------------------------------------------------------------------------
# Tool: file_info
# ---------------------------------------------------------------------------

def file_info(path: str) -> str:
    """
    Return metadata about a file or directory: size, modification time,
    MIME type, and whether it is a text or binary/multimodal file.

    Args:
        path: Path relative to the context store root.
    """
    resolved = _safe_resolve(path)
    if resolved is None:
        return _outside_error(path)

    if not resolved.exists():
        return f"ERROR: '{path}' does not exist."

    try:
        stat = resolved.stat()
        import datetime
        mtime = datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds")
        size_bytes = stat.st_size

        if resolved.is_dir():
            kind = "directory"
            mime = "inode/directory"
        else:
            kind = "file"
            mime, _ = mimetypes.guess_type(str(resolved))
            mime = mime or "application/octet-stream"

        suffix = resolved.suffix.lower()
        if suffix in _IMAGE_EXTS:
            content_class = "image (multimodal)"
        elif suffix in _PDF_EXTS:
            content_class = "PDF (multimodal)"
        elif suffix in _BINARY_EXTS:
            content_class = "binary"
        else:
            content_class = "text"

        return (
            f"path: {path}\n"
            f"kind: {kind}\n"
            f"size: {size_bytes:,} bytes\n"
            f"modified: {mtime}\n"
            f"mime_type: {mime}\n"
            f"content_class: {content_class}"
        )
    except OSError as exc:
        return f"ERROR: Could not stat '{path}': {exc}"
