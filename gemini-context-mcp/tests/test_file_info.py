"""Tests for tools.file_info()."""

import pytest

from tools import file_info


_EXPECTED_FIELDS = ["path:", "kind:", "size:", "modified:", "mime_type:", "content_class:"]


class TestFileInfoFields:
    def test_all_fields_present_for_text_file(self, ctx):
        result = file_info("docs/readme.md")
        for field in _EXPECTED_FIELDS:
            assert field in result, f"Missing field: {field}"

    def test_all_fields_present_for_image(self, ctx):
        result = file_info("docs/photo.jpg")
        for field in _EXPECTED_FIELDS:
            assert field in result, f"Missing field: {field}"

    def test_all_fields_present_for_directory(self, ctx):
        result = file_info("docs")
        for field in _EXPECTED_FIELDS:
            assert field in result, f"Missing field: {field}"


class TestFileInfoTextFile:
    def test_kind_is_file(self, ctx):
        result = file_info("docs/readme.md")
        assert "kind: file" in result

    def test_content_class_is_text(self, ctx):
        result = file_info("docs/readme.md")
        assert "content_class: text" in result

    def test_mime_type_markdown(self, ctx):
        result = file_info("docs/readme.md")
        assert "text/markdown" in result or "text/plain" in result  # OS-dependent

    def test_mime_type_python(self, ctx):
        result = file_info("code/main.py")
        assert "text/" in result or "application/" in result

    def test_path_field_matches_input(self, ctx):
        result = file_info("docs/readme.md")
        assert "path: docs/readme.md" in result

    def test_size_field_nonzero(self, ctx):
        result = file_info("docs/readme.md")
        assert "size: " in result
        # Size line must contain a non-zero number
        size_line = next(l for l in result.splitlines() if l.startswith("size:"))
        digits = "".join(c for c in size_line if c.isdigit())
        assert int(digits) > 0

    def test_size_matches_file_bytes(self, ctx):
        content = "hello world"
        (ctx / "sized.txt").write_text(content, encoding="utf-8")
        result = file_info("sized.txt")
        size_line = next(l for l in result.splitlines() if l.startswith("size:"))
        digits = "".join(c for c in size_line if c.isdigit())
        assert int(digits) == len(content.encode("utf-8"))

    def test_modified_field_is_iso_format(self, ctx):
        result = file_info("docs/readme.md")
        modified_line = next(l for l in result.splitlines() if l.startswith("modified:"))
        # ISO format: YYYY-MM-DDThh:mm:ss
        assert "T" in modified_line
        assert "-" in modified_line


class TestFileInfoImage:
    def test_jpg_content_class(self, ctx):
        result = file_info("docs/photo.jpg")
        assert "content_class: image (multimodal)" in result

    def test_jpg_mime_type(self, ctx):
        result = file_info("docs/photo.jpg")
        assert "mime_type: image/jpeg" in result

    def test_png_content_class(self, ctx):
        result = file_info("docs/photo.png")
        assert "content_class: image (multimodal)" in result

    def test_png_mime_type(self, ctx):
        result = file_info("docs/photo.png")
        assert "mime_type: image/png" in result

    def test_jpg_size_matches_bytes_on_disk(self, ctx):
        expected_size = len((ctx / "docs" / "photo.jpg").read_bytes())
        result = file_info("docs/photo.jpg")
        size_line = next(l for l in result.splitlines() if l.startswith("size:"))
        digits = "".join(c for c in size_line if c.isdigit())
        assert int(digits) == expected_size


class TestFileInfoPDF:
    def test_pdf_content_class(self, ctx):
        result = file_info("docs/report.pdf")
        assert "content_class: PDF (multimodal)" in result

    def test_pdf_mime_type(self, ctx):
        result = file_info("docs/report.pdf")
        assert "mime_type: application/pdf" in result


class TestFileInfoDirectory:
    def test_kind_is_directory(self, ctx):
        result = file_info("docs")
        assert "kind: directory" in result

    def test_directory_mime_type(self, ctx):
        result = file_info("docs")
        assert "mime_type: inode/directory" in result

    def test_directory_content_class_is_text(self, ctx):
        """Directories have no extension → classified as text."""
        result = file_info("docs")
        assert "content_class: text" in result

    def test_root_directory(self, ctx):
        result = file_info(".")
        assert "kind: directory" in result


class TestFileInfoErrors:
    def test_nonexistent_path(self, ctx):
        result = file_info("does_not_exist.txt")
        assert result.startswith("ERROR:")

    def test_relative_traversal(self, ctx):
        result = file_info("../../etc")
        assert result.startswith("ERROR:")

    def test_absolute_path_outside(self, ctx):
        result = file_info("/etc/passwd")
        assert result.startswith("ERROR:")
