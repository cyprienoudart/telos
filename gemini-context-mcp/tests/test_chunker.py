"""Unit tests for chunker.py — sentence splitting, chunking, hashing."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the package root is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from chunker import Chunk, _split_sentences, build_all_chunks, chunk_file, context_hash


# ---------------------------------------------------------------------------
# _split_sentences
# ---------------------------------------------------------------------------

class TestSplitSentences:
    def test_simple_prose(self):
        result = _split_sentences("Hello world. How are you? Fine thanks!")
        assert result == ["Hello world.", "How are you?", "Fine thanks!"]

    def test_markdown_headings(self):
        text = "# Title\nSome text.\n## Subtitle\nMore text."
        result = _split_sentences(text)
        assert "# Title" in result
        assert "## Subtitle" in result
        assert "Some text." in result
        assert "More text." in result

    def test_markdown_table_rows(self):
        text = "| Name | Age |\n|------|-----|\n| Alice | 30 |"
        result = _split_sentences(text)
        assert "| Name | Age |" in result
        assert "|------|-----|" in result

    def test_empty_string(self):
        assert _split_sentences("") == []

    def test_blank_lines_flush(self):
        text = "First sentence.\n\nSecond sentence."
        result = _split_sentences(text)
        assert "First sentence." in result
        assert "Second sentence." in result


# ---------------------------------------------------------------------------
# chunk_file
# ---------------------------------------------------------------------------

class TestChunkFile:
    def test_single_chunk(self):
        text = "Short text."
        chunks = chunk_file("test.md", text)
        assert len(chunks) == 1
        assert chunks[0].source == "test.md"
        assert "Short text" in chunks[0].text

    def test_overlap(self):
        # Build text that exceeds CHUNK_MAX_WORDS (300) to force a split
        words = " ".join(f"word{i}." for i in range(400))
        chunks = chunk_file("big.md", words)
        assert len(chunks) >= 2
        # Overlap: last words of chunk 0 should appear in chunk 1
        last_words_chunk0 = set(chunks[0].text.split()[-20:])
        first_words_chunk1 = set(chunks[1].text.split()[:60])
        overlap = last_words_chunk0 & first_words_chunk1
        assert len(overlap) > 0, "Expected overlap between consecutive chunks"

    def test_empty_text(self):
        chunks = chunk_file("empty.md", "")
        assert chunks == []

    def test_returns_chunk_dataclass(self):
        chunks = chunk_file("f.py", "x = 1")
        assert all(isinstance(c, Chunk) for c in chunks)


# ---------------------------------------------------------------------------
# context_hash
# ---------------------------------------------------------------------------

class TestContextHash:
    def test_hash_is_hex_string(self, tmp_path):
        (tmp_path / "a.txt").write_text("hello")
        config.set_base_dir(tmp_path)
        h = context_hash()
        assert isinstance(h, str)
        assert len(h) == 32  # MD5 hex digest
        int(h, 16)  # should not raise

    def test_hash_changes_on_file_change(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("v1")
        config.set_base_dir(tmp_path)
        h1 = context_hash()

        f.write_text("v2222222222222")  # different size → different hash
        h2 = context_hash()
        assert h1 != h2

    def test_hash_stable_for_same_content(self, tmp_path):
        (tmp_path / "a.txt").write_text("stable")
        config.set_base_dir(tmp_path)
        assert context_hash() == context_hash()


# ---------------------------------------------------------------------------
# build_all_chunks
# ---------------------------------------------------------------------------

class TestBuildAllChunks:
    def test_chunks_from_text_files(self, tmp_path):
        (tmp_path / "readme.md").write_text("# Hello\nWorld.")
        (tmp_path / "main.py").write_text("print('hi')")
        config.set_base_dir(tmp_path)
        chunks = build_all_chunks()
        sources = {c.source for c in chunks}
        assert "readme.md" in sources
        assert "main.py" in sources

    def test_skips_binary_files(self, tmp_path):
        (tmp_path / "data.bin").write_bytes(b"\x00\x01")
        (tmp_path / "ok.txt").write_text("ok")
        config.set_base_dir(tmp_path)
        chunks = build_all_chunks()
        sources = {c.source for c in chunks}
        assert "ok.txt" in sources
        assert "data.bin" not in sources

    def test_skips_image_files(self, tmp_path):
        (tmp_path / "photo.png").write_bytes(b"\x89PNG")
        (tmp_path / "ok.txt").write_text("ok")
        config.set_base_dir(tmp_path)
        chunks = build_all_chunks()
        sources = {c.source for c in chunks}
        assert "photo.png" not in sources

    def test_skips_skip_dirs(self, tmp_path):
        d = tmp_path / "__pycache__"
        d.mkdir()
        (d / "cached.pyc").write_bytes(b"\x00")
        (tmp_path / "ok.txt").write_text("ok")
        config.set_base_dir(tmp_path)
        chunks = build_all_chunks()
        sources = {c.source for c in chunks}
        assert all("__pycache__" not in s for s in sources)

    def test_empty_dir(self, tmp_path):
        config.set_base_dir(tmp_path)
        assert build_all_chunks() == []
