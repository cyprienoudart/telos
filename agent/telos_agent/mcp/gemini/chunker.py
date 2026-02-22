"""
Text processing: file walking, sentence splitting, chunking, content hashing.

Public API
----------
  Chunk                    dataclass — source path + text
  context_hash()           MD5 over file sizes + mtimes; used as cache key
  build_all_chunks()       chunk every text file under settings.BASE_DIR
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from . import settings


# ---------------------------------------------------------------------------
# Data type
# ---------------------------------------------------------------------------

@dataclass
class Chunk:
    source: str   # relative file path, e.g. "docs/team.md"
    text:   str   # chunk text


# ---------------------------------------------------------------------------
# File traversal
# ---------------------------------------------------------------------------

def _walk_text_paths():
    """
    Yield every text-file Path under settings.BASE_DIR, pruning settings.SKIP_DIRS
    and skipping settings.BINARY_EXTS. Reads settings.BASE_DIR at call time so
    benchmark.py can switch projects by reassigning settings.BASE_DIR.
    """
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
            elif (entry.is_file()
                  and entry.suffix.lower() not in settings.BINARY_EXTS
                  and entry.suffix.lower() not in settings.IMAGE_EXTS
                  and entry.suffix.lower() not in settings.PDF_EXTS
                  and entry.name not in settings.SKIP_FILES):
                yield entry


def _iter_text_files():
    """Yield (rel_path, text) for every readable text file under settings.BASE_DIR."""
    for p in sorted(_walk_text_paths(), key=str):
        rel = str(p.relative_to(settings.BASE_DIR)).replace("\\", "/")
        try:
            yield rel, p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue


# ---------------------------------------------------------------------------
# Content hash
# ---------------------------------------------------------------------------

def context_hash() -> str:
    """
    Fast cache key: MD5 over each file's path + size + mtime_ns.
    Same approach as git's index — does not read file content, runs in
    microseconds even for large trees.
    """
    h = hashlib.md5()
    for p in sorted(_walk_text_paths()):
        try:
            st = p.stat()
            h.update(f"{p}:{st.st_size}:{st.st_mtime_ns}".encode())
        except OSError:
            continue
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Sentence splitter
# ---------------------------------------------------------------------------

def _split_sentences(text: str) -> list[str]:
    """
    Split *text* into atomic units:
      - Markdown heading lines  (kept whole)
      - Markdown table rows     (kept whole)
      - Regular prose sentences (split on . ! ?)
    """
    sentences: list[str] = []
    prose_buf: list[str] = []

    def _flush() -> None:
        if prose_buf:
            joined = " ".join(prose_buf)
            for s in re.split(r"(?<=[.!?])\s+", joined):
                s = s.strip()
                if s:
                    sentences.append(s)
            prose_buf.clear()

    for line in text.splitlines():
        s = line.strip()
        if not s:
            _flush()
        elif re.match(r"^#{1,6}\s", s):         # Markdown heading
            _flush()
            sentences.append(s)
        elif re.match(r"^[\|\-]", s):            # Markdown table row / separator
            _flush()
            sentences.append(s)
        else:
            prose_buf.append(s)

    _flush()
    return sentences


# ---------------------------------------------------------------------------
# Chunker
# ---------------------------------------------------------------------------

def chunk_file(source: str, text: str) -> list[Chunk]:
    """
    Split *text* into overlapping Chunks at sentence boundaries.
    Target size: settings.CHUNK_MAX_WORDS words, overlap: settings.CHUNK_OVERLAP_WORDS.
    """
    sentences = _split_sentences(text)
    chunks:  list[Chunk] = []
    window:  list[str]   = []
    w_words: int         = 0

    for sent in sentences:
        n = len(sent.split())
        if w_words + n > settings.CHUNK_MAX_WORDS and window:
            chunks.append(Chunk(source=source, text=" ".join(window)))
            overlap: list[str] = []
            ow = 0
            for s in reversed(window):
                sw = len(s.split())
                if ow + sw <= settings.CHUNK_OVERLAP_WORDS:
                    overlap.insert(0, s)
                    ow += sw
                else:
                    break
            window, w_words = overlap, ow
        window.append(sent)
        w_words += n

    if window:
        chunks.append(Chunk(source=source, text=" ".join(window)))

    return chunks


def build_all_chunks() -> list[Chunk]:
    """Chunk every text file under settings.BASE_DIR and return all Chunks."""
    chunks: list[Chunk] = []
    for rel, text in _iter_text_files():
        chunks.extend(chunk_file(rel, text))
    return chunks
