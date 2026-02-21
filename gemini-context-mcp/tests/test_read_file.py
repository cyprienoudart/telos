"""Tests for tools.read_file()."""

import pytest

from tools import _MULTIMODAL_SENTINEL, read_file


class TestReadFileText:
    def test_returns_string_for_text_file(self, ctx):
        result = read_file("docs/readme.md")
        assert isinstance(result, str)

    def test_content_matches_file(self, ctx):
        result = read_file("docs/readme.md")
        assert "# Hello" in result
        assert "search_target" in result

    def test_multiline_content(self, ctx):
        result = read_file("docs/notes.txt")
        assert "line one" in result
        assert "line two" in result
        assert "line three" in result

    def test_python_file(self, ctx):
        result = read_file("code/main.py")
        assert "def hello():" in result
        assert "return 'world'" in result

    def test_markdown_file(self, ctx):
        result = read_file("docs/readme.md")
        assert result.startswith("# Hello")

    def test_truncation_at_80k_chars(self, ctx):
        result = read_file("large.txt")
        assert isinstance(result, str)
        assert "[...truncated at 80000 characters]" in result

    def test_truncated_content_length(self, ctx):
        """Result must be capped — not the full 90k chars."""
        result = read_file("large.txt")
        # 80k content + truncation message — well under 90k
        assert len(result) < 85_000

    def test_truncated_content_starts_correctly(self, ctx):
        """First 80k chars of the truncated file must be preserved."""
        result = read_file("large.txt")
        assert result.startswith("X" * 100)


class TestReadFileImage:
    def test_jpg_returns_tuple(self, ctx):
        result = read_file("docs/photo.jpg")
        assert isinstance(result, tuple)

    def test_jpg_sentinel_value(self, ctx):
        result = read_file("docs/photo.jpg")
        assert result[0] == _MULTIMODAL_SENTINEL

    def test_jpg_bytes(self, ctx):
        result = read_file("docs/photo.jpg")
        assert isinstance(result[1], bytes)
        assert len(result[1]) > 0

    def test_jpg_mime_type(self, ctx):
        result = read_file("docs/photo.jpg")
        assert result[2] == "image/jpeg"

    def test_jpg_path_preserved(self, ctx):
        result = read_file("docs/photo.jpg")
        assert result[3] == "docs/photo.jpg"

    def test_jpg_bytes_roundtrip(self, ctx):
        """Bytes in the sentinel must exactly match the bytes on disk."""
        expected = (ctx / "docs" / "photo.jpg").read_bytes()
        result = read_file("docs/photo.jpg")
        assert result[1] == expected

    def test_png_returns_sentinel(self, ctx):
        result = read_file("docs/photo.png")
        assert isinstance(result, tuple)
        assert result[0] == _MULTIMODAL_SENTINEL

    def test_png_mime_type(self, ctx):
        result = read_file("docs/photo.png")
        assert result[2] == "image/png"

    def test_png_bytes_roundtrip(self, ctx):
        expected = (ctx / "docs" / "photo.png").read_bytes()
        result = read_file("docs/photo.png")
        assert result[1] == expected

    def test_sentinel_tuple_has_four_elements(self, ctx):
        result = read_file("docs/photo.jpg")
        assert len(result) == 4


class TestReadFilePDF:
    def test_pdf_returns_sentinel(self, ctx):
        result = read_file("docs/report.pdf")
        assert isinstance(result, tuple)
        assert result[0] == _MULTIMODAL_SENTINEL

    def test_pdf_mime_type(self, ctx):
        result = read_file("docs/report.pdf")
        assert result[2] == "application/pdf"

    def test_pdf_path_preserved(self, ctx):
        result = read_file("docs/report.pdf")
        assert result[3] == "docs/report.pdf"

    def test_pdf_bytes_roundtrip(self, ctx):
        expected = (ctx / "docs" / "report.pdf").read_bytes()
        result = read_file("docs/report.pdf")
        assert result[1] == expected


class TestReadFileErrors:
    def test_nonexistent_file(self, ctx):
        result = read_file("docs/missing.txt")
        assert result.startswith("ERROR:")

    def test_directory_as_file(self, ctx):
        result = read_file("docs")
        assert result.startswith("ERROR:")

    def test_relative_traversal(self, ctx):
        result = read_file("../../etc/passwd")
        assert result.startswith("ERROR:")

    def test_absolute_path_outside(self, ctx):
        result = read_file("/etc/passwd")
        assert result.startswith("ERROR:")

    def test_dotdot_in_middle_of_path(self, ctx):
        result = read_file("docs/../../../etc/passwd")
        assert result.startswith("ERROR:")
