"""Unit tests for config.py — env var overrides and set_base_dir."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestConfigDefaults:
    def test_base_dir_is_path(self):
        import config
        assert isinstance(config.BASE_DIR, Path)

    def test_base_dir_is_absolute(self):
        import config
        assert config.BASE_DIR.is_absolute()

    def test_default_model(self):
        import config
        assert "gemini" in config.LLM_MODEL.lower() or "flash" in config.LLM_MODEL.lower()

    def test_chunk_constants(self):
        import config
        assert config.CHUNK_MAX_WORDS > 0
        assert config.CHUNK_OVERLAP_WORDS > 0
        assert config.CHUNK_OVERLAP_WORDS < config.CHUNK_MAX_WORDS


class TestSetBaseDir:
    def test_set_base_dir_string(self, tmp_path):
        import config
        config.set_base_dir(str(tmp_path))
        assert config.BASE_DIR == tmp_path.resolve()

    def test_set_base_dir_path(self, tmp_path):
        import config
        config.set_base_dir(tmp_path)
        assert config.BASE_DIR == tmp_path.resolve()

    def test_set_base_dir_resolves(self, tmp_path):
        import config
        config.set_base_dir(tmp_path / "subdir" / "..")
        assert config.BASE_DIR == tmp_path.resolve()


class TestEnvOverrides:
    def test_context_dir_override(self, monkeypatch, tmp_path):
        monkeypatch.setenv("CONTEXT_DIR", str(tmp_path))
        import config
        importlib.reload(config)
        assert config.BASE_DIR == tmp_path.resolve()

    def test_model_override(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_MODEL", "test/model-123")
        import config
        importlib.reload(config)
        assert config.LLM_MODEL == "test/model-123"

    def test_embed_model_override(self, monkeypatch):
        monkeypatch.setenv("FASTEMBED_MODEL", "custom/embed")
        import config
        importlib.reload(config)
        assert config.EMBED_MODEL == "custom/embed"
