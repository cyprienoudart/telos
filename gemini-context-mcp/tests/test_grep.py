"""Tests for tools.grep()."""

import pytest

from tools import grep


class TestGrepHappyPath:
    def test_basic_match_found(self, ctx):
        result = grep("hello", ".")
        assert "code/main.py" in result

    def test_match_includes_line_content(self, ctx):
        result = grep("hello", ".")
        assert "def hello():" in result

    def test_match_format_is_path_lineno_content(self, ctx):
        """Each result line must be in `path:lineno: content` format."""
        result = grep("def hello", ".")
        match_line = next(l for l in result.splitlines() if "hello" in l)
        # Must start with path
        assert match_line.startswith("code/main.py:")
        # Second field must be a line number
        parts = match_line.split(":", 2)
        assert parts[1].isdigit()

    def test_case_insensitive(self, ctx):
        result = grep("HELLO", ".")
        assert "code/main.py" in result

    def test_regex_dot_star(self, ctx):
        result = grep(r"def \w+\(", ".")
        assert "main.py" in result
        assert "utils.py" in result

    def test_regex_anchors(self, ctx):
        result = grep(r"^def hello", ".")
        assert "main.py" in result

    def test_subdirectory_scope(self, ctx):
        result = grep("hello", "code")
        assert "main.py" in result
        # docs/ content should not appear
        assert "readme.md" not in result

    def test_no_match_returns_message(self, ctx):
        result = grep("xyz_not_found_12345", ".")
        assert "No matches found" in result

    def test_no_match_message_includes_pattern(self, ctx):
        pattern = "xyz_not_found_12345"
        result = grep(pattern, ".")
        assert pattern in result

    def test_multiple_files_matched(self, ctx):
        # "def" appears in both main.py and utils.py
        result = grep("def ", "code")
        assert "main.py" in result
        assert "utils.py" in result

    def test_multiple_lines_in_same_file(self, ctx):
        # notes.txt has three lines; grep for "line" should match all three
        result = grep("^line", "docs")
        lines = [l for l in result.splitlines() if "notes.txt" in l]
        assert len(lines) == 3


class TestGrepSkipsBinaryFiles:
    def test_skips_jpg(self, ctx):
        result = grep(".", "docs")   # "." matches any character
        assert "photo.jpg" not in result

    def test_skips_png(self, ctx):
        result = grep(".", "docs")
        assert "photo.png" not in result

    def test_skips_pdf(self, ctx):
        result = grep("PDF", "docs")
        assert "report.pdf" not in result

    def test_text_files_in_same_dir_still_matched(self, ctx):
        """Skipping binary files must not suppress text matches in the same dir."""
        result = grep("search_target", "docs")
        assert "docs/readme.md" in result


class TestGrepCap:
    def test_cap_at_50_results(self, ctx):
        """Create 60 single-line files; result must include the cap notice."""
        many = ctx / "many"
        many.mkdir()
        for i in range(60):
            (many / f"file{i:03d}.txt").write_text("match_me\n", encoding="utf-8")
        result = grep("match_me", "many")
        assert "[...results capped at 50]" in result

    def test_cap_exactly_50_results_before_notice(self, ctx):
        many = ctx / "many"
        many.mkdir()
        for i in range(60):
            (many / f"file{i:03d}.txt").write_text("match_me\n", encoding="utf-8")
        result = grep("match_me", "many")
        match_lines = [l for l in result.splitlines() if "match_me" in l]
        assert len(match_lines) == 50


class TestGrepErrors:
    def test_invalid_regex(self, ctx):
        result = grep("[invalid(", ".")
        assert result.startswith("ERROR:")

    def test_invalid_regex_mentions_pattern(self, ctx):
        result = grep("[invalid(", ".")
        assert "[invalid(" in result

    def test_relative_traversal(self, ctx):
        result = grep("hello", "../../etc")
        assert result.startswith("ERROR:")

    def test_absolute_path_outside(self, ctx):
        result = grep("hello", "/etc")
        assert result.startswith("ERROR:")

    def test_nonexistent_directory(self, ctx):
        result = grep("hello", "nonexistent")
        assert result.startswith("ERROR:")

    def test_file_passed_as_directory(self, ctx):
        result = grep("hello", "docs/readme.md")
        assert result.startswith("ERROR:")
