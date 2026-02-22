"""Unit tests for telos_agent.mcp.gemini.store — embedding, cache hit/miss logic.

ChromaDB has a pydantic v1 incompatibility with Python 3.14+, so we mock
the chromadb module entirely and test the logic in isolation.
"""

from __future__ import annotations

import importlib
import sys
from unittest.mock import MagicMock, patch

from telos_agent.mcp.gemini import settings


# ---------------------------------------------------------------------------
# Mock chromadb before importing store
# ---------------------------------------------------------------------------

def _setup_chromadb_mock():
    """Create a mock chromadb module so store.py can be imported on Python 3.14+."""
    mock_chromadb = MagicMock()
    mock_chromadb.PersistentClient = MagicMock
    mock_chromadb.Collection = MagicMock
    sys.modules.setdefault("chromadb", mock_chromadb)


_setup_chromadb_mock()


class TestEmbedTexts:
    def test_returns_list_of_lists(self):
        import numpy as np
        from telos_agent.mcp.gemini import store
        importlib.reload(store)

        mock_model = MagicMock()
        mock_model.embed.return_value = [
            np.array([0.1, 0.2, 0.3]),
            np.array([0.4, 0.5, 0.6]),
        ]
        store._embed_model = mock_model
        result = store.embed_texts(["hello", "world"])
        assert len(result) == 2
        assert isinstance(result[0], list)
        assert isinstance(result[0][0], float)
        store._embed_model = None  # reset

    def test_embed_empty_list(self):
        from telos_agent.mcp.gemini import store
        importlib.reload(store)

        mock_model = MagicMock()
        mock_model.embed.return_value = []
        store._embed_model = mock_model
        result = store.embed_texts([])
        assert result == []
        store._embed_model = None  # reset


class TestCacheLookupLogic:
    """Test cache threshold logic without a real ChromaDB instance."""

    def setup_method(self):
        """Reset settings to defaults before each test."""
        importlib.reload(settings)

    def test_cache_returns_none_for_empty_collection(self):
        """When cache count is 0, cache_lookup returns None."""
        from telos_agent.mcp.gemini import store
        importlib.reload(store)

        mock_cache = MagicMock()
        mock_cache.count.return_value = 0

        with patch.object(store, "_get_cache_collection", return_value=mock_cache):
            result = store.cache_lookup([0.1, 0.2, 0.3])
        assert result is None

    def test_cache_hit_when_distance_below_threshold(self):
        """When distance is small enough (high similarity), return the cached doc."""
        from telos_agent.mcp.gemini import store
        importlib.reload(store)

        mock_cache = MagicMock()
        mock_cache.count.return_value = 1
        mock_cache.query.return_value = {
            "distances": [[0.05]],  # distance = 1 - similarity; 0.05 means 0.95 similarity
            "documents": [["cached answer"]],
        }

        with patch.object(store, "_get_cache_collection", return_value=mock_cache):
            result = store.cache_lookup([0.1, 0.2, 0.3])
        assert result == "cached answer"

    def test_cache_miss_when_distance_above_threshold(self):
        """When distance is too large (low similarity), return None."""
        from telos_agent.mcp.gemini import store
        importlib.reload(store)

        mock_cache = MagicMock()
        mock_cache.count.return_value = 1
        mock_cache.query.return_value = {
            "distances": [[0.5]],  # distance 0.5 means similarity 0.5 — below 0.85 threshold
            "documents": [["stale answer"]],
        }

        with patch.object(store, "_get_cache_collection", return_value=mock_cache):
            result = store.cache_lookup([0.1, 0.2, 0.3])
        assert result is None

    def test_cache_boundary_exact_threshold(self):
        """At exactly the threshold boundary, it should be a hit (<=)."""
        from telos_agent.mcp.gemini import store
        importlib.reload(store)

        threshold_distance = 1.0 - settings.CACHE_SIMILARITY  # 0.15

        mock_cache = MagicMock()
        mock_cache.count.return_value = 1
        mock_cache.query.return_value = {
            "distances": [[threshold_distance]],
            "documents": [["boundary answer"]],
        }

        with patch.object(store, "_get_cache_collection", return_value=mock_cache):
            result = store.cache_lookup([0.1, 0.2, 0.3])
        assert result == "boundary answer"
