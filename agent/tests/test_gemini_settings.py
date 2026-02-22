"""Unit tests for telos_agent.mcp.gemini.settings — env var overrides and set_base_dir."""

from __future__ import annotations

import importlib
from pathlib import Path


class TestConfigDefaults:
    def test_base_dir_is_path(self):
        from telos_agent.mcp.gemini import settings
        assert isinstance(settings.BASE_DIR, Path)

    def test_base_dir_is_absolute(self):
        from telos_agent.mcp.gemini import settings
        assert settings.BASE_DIR.is_absolute()

    def test_default_model(self):
        from telos_agent.mcp.gemini import settings
        assert "gemini" in settings.LLM_MODEL.lower() or "flash" in settings.LLM_MODEL.lower()

    def test_chunk_constants(self):
        from telos_agent.mcp.gemini import settings
        assert settings.CHUNK_MAX_WORDS > 0
        assert settings.CHUNK_OVERLAP_WORDS > 0
        assert settings.CHUNK_OVERLAP_WORDS < settings.CHUNK_MAX_WORDS


class TestSetBaseDir:
    def test_set_base_dir_string(self, tmp_path):
        from telos_agent.mcp.gemini import settings
        settings.set_base_dir(str(tmp_path))
        assert settings.BASE_DIR == tmp_path.resolve()

    def test_set_base_dir_path(self, tmp_path):
        from telos_agent.mcp.gemini import settings
        settings.set_base_dir(tmp_path)
        assert settings.BASE_DIR == tmp_path.resolve()

    def test_set_base_dir_resolves(self, tmp_path):
        from telos_agent.mcp.gemini import settings
        settings.set_base_dir(tmp_path / "subdir" / "..")
        assert settings.BASE_DIR == tmp_path.resolve()


class TestEnvOverrides:
    def test_context_dir_override(self, monkeypatch, tmp_path):
        monkeypatch.setenv("CONTEXT_DIR", str(tmp_path))
        from telos_agent.mcp.gemini import settings
        importlib.reload(settings)
        assert settings.BASE_DIR == tmp_path.resolve()

    def test_model_override(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_MODEL", "test/model-123")
        from telos_agent.mcp.gemini import settings
        importlib.reload(settings)
        assert settings.LLM_MODEL == "test/model-123"

    def test_embed_model_override(self, monkeypatch):
        monkeypatch.setenv("FASTEMBED_MODEL", "custom/embed")
        from telos_agent.mcp.gemini import settings
        importlib.reload(settings)
        assert settings.EMBED_MODEL == "custom/embed"
