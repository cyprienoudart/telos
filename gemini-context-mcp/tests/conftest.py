"""
Shared pytest fixtures for tools.py tests.

All tests operate on a temporary directory that is patched in as tools.BASE_DIR,
so no real files are read or written and the actual context/ store is untouched.

Fixture layout created by `ctx`:
    <tmp_path>/
    ├── docs/
    │   ├── readme.md       text — contains "# Hello" and "search_target"
    │   ├── notes.txt       text — three numbered lines
    │   ├── photo.jpg       image — minimal valid JPEG bytes
    │   ├── photo.png       image — minimal valid PNG bytes (generated)
    │   └── report.pdf      PDF   — minimal PDF header bytes
    ├── code/
    │   ├── main.py         text — "def hello():" ...
    │   └── utils.py        text — "def helper():" ...
    ├── empty/              empty directory
    └── large.txt           text — 90 000 × "X" (triggers 80k truncation)
"""

from __future__ import annotations

import struct
import zlib

import pytest

import tools


# ---------------------------------------------------------------------------
# Minimal synthetic image bytes (no external deps)
# ---------------------------------------------------------------------------

def _make_png_1x1_white() -> bytes:
    """Generate a minimal but valid 1×1 white PNG."""
    sig = b"\x89PNG\r\n\x1a\n"

    def chunk(tag: bytes, data: bytes) -> bytes:
        payload = tag + data
        crc = zlib.crc32(payload) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + payload + struct.pack(">I", crc)

    # IHDR: width=1, height=1, bit_depth=8, color_type=2 (RGB), rest=0
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    # IDAT: filter-byte=0 + white pixel R=255 G=255 B=255
    idat = chunk(b"IDAT", zlib.compress(b"\x00\xff\xff\xff"))
    iend = chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


# Real minimal JPEG (SOI + JFIF APP0 marker + EOI) — 20 bytes, renders as white 1×1
_MINIMAL_JPEG = (
    b"\xff\xd8"                          # SOI
    b"\xff\xe0\x00\x10"                  # APP0 marker, length=16
    b"JFIF\x00"                          # identifier
    b"\x01\x01"                          # version 1.1
    b"\x00"                              # aspect ratio units: 0=no units
    b"\x00\x01\x00\x01"                  # Xdensity=1, Ydensity=1
    b"\x00\x00"                          # no thumbnail
    b"\xff\xd9"                          # EOI
)

SAMPLE_JPEG_BYTES: bytes = _MINIMAL_JPEG
SAMPLE_PNG_BYTES: bytes = _make_png_1x1_white()
SAMPLE_PDF_BYTES: bytes = b"%PDF-1.4\n1 0 obj<</Type /Catalog>>endobj\n%%EOF\n"


# ---------------------------------------------------------------------------
# Primary fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def ctx(tmp_path, monkeypatch):
    """
    Build a temporary context store and patch tools.BASE_DIR to point at it.

    Returns the tmp_path Path object so individual tests can inspect or add
    files as needed (all additions are automatically inside BASE_DIR).
    """
    # --- directories ---
    docs = tmp_path / "docs"
    docs.mkdir()
    code = tmp_path / "code"
    code.mkdir()
    (tmp_path / "empty").mkdir()

    # --- text files ---
    (docs / "readme.md").write_text(
        "# Hello\n\nThis is a test document.\n\nsearch_target appears here.\n",
        encoding="utf-8",
    )
    (docs / "notes.txt").write_text(
        "line one\nline two\nline three\n",
        encoding="utf-8",
    )
    (code / "main.py").write_text(
        "def hello():\n    return 'world'\n",
        encoding="utf-8",
    )
    (code / "utils.py").write_text(
        "def helper():\n    pass\n",
        encoding="utf-8",
    )

    # --- image files ---
    (docs / "photo.jpg").write_bytes(SAMPLE_JPEG_BYTES)
    (docs / "photo.png").write_bytes(SAMPLE_PNG_BYTES)

    # --- PDF file ---
    (docs / "report.pdf").write_bytes(SAMPLE_PDF_BYTES)

    # --- large text file (exceeds 80 000 char cap) ---
    (tmp_path / "large.txt").write_text("X" * 90_000, encoding="utf-8")

    # --- patch BASE_DIR ---
    monkeypatch.setattr(tools, "BASE_DIR", tmp_path)

    return tmp_path
