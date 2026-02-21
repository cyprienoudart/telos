"""
Tests for _safe_resolve() — the single path-safety chokepoint.

This is a private function but it's the core security mechanism, so it
gets its own test module with exhaustive attack-pattern coverage.
"""

import pytest
from pathlib import Path

import tools
from tools import _safe_resolve


class TestSafeResolveValidPaths:
    def test_dot_resolves_to_base_dir(self, ctx):
        result = _safe_resolve(".")
        assert result == ctx

    def test_relative_file_inside(self, ctx):
        result = _safe_resolve("docs/readme.md")
        assert result == ctx / "docs" / "readme.md"

    def test_nested_relative_path(self, ctx):
        result = _safe_resolve("docs")
        assert result == ctx / "docs"

    def test_absolute_path_inside_base_dir(self, ctx):
        absolute = str(ctx / "docs" / "readme.md")
        result = _safe_resolve(absolute)
        assert result is not None
        assert result == ctx / "docs" / "readme.md"

    def test_returns_path_object(self, ctx):
        result = _safe_resolve("docs")
        assert isinstance(result, Path)


class TestSafeResolveTraversalAttacks:
    def test_double_dot_relative(self, ctx):
        assert _safe_resolve("../../etc") is None

    def test_double_dot_inside_path(self, ctx):
        assert _safe_resolve("docs/../../etc") is None

    def test_triple_dot_segments(self, ctx):
        assert _safe_resolve("docs/../../../etc/passwd") is None

    def test_absolute_path_outside(self, ctx):
        assert _safe_resolve("/etc/passwd") is None

    def test_absolute_windows_path_outside(self, ctx):
        assert _safe_resolve("C:/Windows/System32") is None

    def test_absolute_path_to_base_dir_parent(self, ctx):
        parent = str(ctx.parent)
        assert _safe_resolve(parent) is None

    def test_path_normalised_before_check(self, ctx):
        """docs/./readme.md should normalise to a safe path."""
        result = _safe_resolve("docs/./readme.md")
        assert result is not None
        assert result == ctx / "docs" / "readme.md"


class TestSafeResolveReturnType:
    def test_valid_path_returns_path(self, ctx):
        result = _safe_resolve("docs")
        assert result is not None

    def test_invalid_path_returns_none(self, ctx):
        result = _safe_resolve("../../etc")
        assert result is None

    def test_never_raises(self, ctx):
        """_safe_resolve must never raise, even for wild inputs."""
        for bad in ["", "\x00", "a" * 10_000, "/../", "//etc/passwd"]:
            try:
                _safe_resolve(bad)  # should return None, not raise
            except Exception as exc:
                pytest.fail(f"_safe_resolve raised {type(exc).__name__} for input {bad!r}")
