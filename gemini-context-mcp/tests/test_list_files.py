"""Tests for tools.list_files()."""

import pytest

from tools import list_files


class TestListFilesHappyPath:
    def test_root_lists_all_files(self, ctx):
        result = list_files(".")
        assert "docs/readme.md" in result
        assert "docs/notes.txt" in result
        assert "code/main.py" in result
        assert "code/utils.py" in result

    def test_root_includes_images(self, ctx):
        result = list_files(".")
        assert "docs/photo.jpg" in result
        assert "docs/photo.png" in result

    def test_root_includes_pdf(self, ctx):
        result = list_files(".")
        assert "docs/report.pdf" in result

    def test_subdirectory_scopes_output(self, ctx):
        result = list_files("docs")
        assert "docs/readme.md" in result
        assert "docs/photo.jpg" in result
        # Files from other directories must not appear
        assert "code/main.py" not in result

    def test_empty_directory(self, ctx):
        result = list_files("empty")
        assert result == "(empty directory)"

    def test_default_argument_equals_root(self, ctx):
        """list_files() with no argument should behave like list_files('.')."""
        assert list_files() == list_files(".")

    def test_output_uses_forward_slashes(self, ctx):
        """Windows backslashes must be normalised to forward slashes."""
        result = list_files(".")
        assert "\\" not in result

    def test_output_is_sorted(self, ctx):
        result = list_files(".")
        lines = result.splitlines()
        assert lines == sorted(lines)

    def test_nested_paths_include_full_relative_path(self, ctx):
        """Each entry must include directory prefix, not just filename."""
        result = list_files(".")
        assert "docs/readme.md" in result   # not just "readme.md"


class TestListFilesErrors:
    def test_relative_traversal(self, ctx):
        result = list_files("../../etc")
        assert result.startswith("ERROR:")

    def test_absolute_path_outside(self, ctx):
        result = list_files("/etc")
        assert result.startswith("ERROR:")

    def test_absolute_path_with_windows_style(self, ctx):
        result = list_files("C:/Windows/System32")
        assert result.startswith("ERROR:")

    def test_nonexistent_directory(self, ctx):
        result = list_files("does_not_exist")
        assert result.startswith("ERROR:")

    def test_file_passed_as_directory(self, ctx):
        result = list_files("docs/readme.md")
        assert result.startswith("ERROR:")

    def test_dotdot_in_middle_of_path(self, ctx):
        result = list_files("docs/../../../etc")
        assert result.startswith("ERROR:")
