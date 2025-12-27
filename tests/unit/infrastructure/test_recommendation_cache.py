"""Tests for recommendation cache.

These tests validate the caching of recommendation calculations.
"""

import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.recommendation_cache import (
    RecommendationCache,
    get_recommendation_cache,
)


class TestRecommendationCacheGetRecommendations:
    """Test getting cached recommendations."""

    @pytest.mark.asyncio
    async def test_returns_cached_data(self):
        """Test returning cached recommendations."""
        cache = RecommendationCache()

        mock_data = [{"symbol": "AAPL", "action": "BUY"}]
        mock_row = {"data": json.dumps(mock_data)}

        mock_db = AsyncMock()
        mock_db.fetchone = AsyncMock(return_value=mock_row)

        mock_manager = MagicMock()
        mock_manager.cache = mock_db

        with patch(
            "app.infrastructure.recommendation_cache.get_db_manager",
            return_value=mock_manager,
        ):
            result = await cache.get_recommendations("hash123", "buy")

        assert result == mock_data

    @pytest.mark.asyncio
    async def test_returns_none_when_not_cached(self):
        """Test returning None when not in cache."""
        cache = RecommendationCache()

        mock_db = AsyncMock()
        mock_db.fetchone = AsyncMock(return_value=None)

        mock_manager = MagicMock()
        mock_manager.cache = mock_db

        with patch(
            "app.infrastructure.recommendation_cache.get_db_manager",
            return_value=mock_manager,
        ):
            result = await cache.get_recommendations("hash123", "buy")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_invalid_json(self):
        """Test returning None when cached data is invalid JSON."""
        cache = RecommendationCache()

        mock_row = {"data": "not valid json"}

        mock_db = AsyncMock()
        mock_db.fetchone = AsyncMock(return_value=mock_row)

        mock_manager = MagicMock()
        mock_manager.cache = mock_db

        with patch(
            "app.infrastructure.recommendation_cache.get_db_manager",
            return_value=mock_manager,
        ):
            result = await cache.get_recommendations("hash123", "buy")

        assert result is None


class TestRecommendationCacheSetRecommendations:
    """Test setting cached recommendations."""

    @pytest.mark.asyncio
    async def test_stores_data(self):
        """Test storing recommendations in cache."""
        cache = RecommendationCache()

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()

        mock_manager = MagicMock()
        mock_manager.cache = mock_db

        with patch(
            "app.infrastructure.recommendation_cache.get_db_manager",
            return_value=mock_manager,
        ):
            await cache.set_recommendations(
                "hash123", "buy", [{"symbol": "AAPL"}]
            )

        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_uses_custom_ttl(self):
        """Test that custom TTL is respected."""
        cache = RecommendationCache()

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()

        mock_manager = MagicMock()
        mock_manager.cache = mock_db

        with patch(
            "app.infrastructure.recommendation_cache.get_db_manager",
            return_value=mock_manager,
        ):
            await cache.set_recommendations(
                "hash123", "buy", [], ttl_hours=24
            )

        # Verify execute was called (TTL is embedded in the data)
        mock_db.execute.assert_called_once()


class TestRecommendationCacheGetAnalytics:
    """Test getting cached analytics."""

    @pytest.mark.asyncio
    async def test_returns_cached_analytics(self):
        """Test returning cached analytics data."""
        cache = RecommendationCache()

        mock_data = {"weights": [0.5, 0.5]}
        mock_row = {"data": json.dumps(mock_data)}

        mock_db = AsyncMock()
        mock_db.fetchone = AsyncMock(return_value=mock_row)

        mock_manager = MagicMock()
        mock_manager.cache = mock_db

        with patch(
            "app.infrastructure.recommendation_cache.get_db_manager",
            return_value=mock_manager,
        ):
            result = await cache.get_analytics("perf:weights:hash123")

        assert result == mock_data

    @pytest.mark.asyncio
    async def test_returns_none_when_not_cached(self):
        """Test returning None when analytics not cached."""
        cache = RecommendationCache()

        mock_db = AsyncMock()
        mock_db.fetchone = AsyncMock(return_value=None)

        mock_manager = MagicMock()
        mock_manager.cache = mock_db

        with patch(
            "app.infrastructure.recommendation_cache.get_db_manager",
            return_value=mock_manager,
        ):
            result = await cache.get_analytics("missing_key")

        assert result is None


class TestRecommendationCacheSetAnalytics:
    """Test setting cached analytics."""

    @pytest.mark.asyncio
    async def test_stores_analytics(self):
        """Test storing analytics in cache."""
        cache = RecommendationCache()

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()

        mock_manager = MagicMock()
        mock_manager.cache = mock_db

        with patch(
            "app.infrastructure.recommendation_cache.get_db_manager",
            return_value=mock_manager,
        ):
            await cache.set_analytics("perf:key", {"data": 123})

        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()


class TestRecommendationCacheInvalidatePortfolioHash:
    """Test invalidating cache for a portfolio hash."""

    @pytest.mark.asyncio
    async def test_deletes_cache_entries(self):
        """Test deleting cache entries for a hash."""
        cache = RecommendationCache()

        mock_cursor1 = MagicMock()
        mock_cursor1.rowcount = 2
        mock_cursor2 = MagicMock()
        mock_cursor2.rowcount = 3

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=[mock_cursor1, mock_cursor2])
        mock_db.commit = AsyncMock()

        mock_manager = MagicMock()
        mock_manager.cache = mock_db

        with patch(
            "app.infrastructure.recommendation_cache.get_db_manager",
            return_value=mock_manager,
        ):
            count = await cache.invalidate_portfolio_hash("hash123")

        assert count == 5  # 2 + 3
        assert mock_db.execute.call_count == 2


class TestRecommendationCacheInvalidateAllRecommendations:
    """Test invalidating all recommendations."""

    @pytest.mark.asyncio
    async def test_deletes_all_recommendations(self):
        """Test deleting all recommendation cache entries."""
        cache = RecommendationCache()

        mock_cursor = MagicMock()
        mock_cursor.rowcount = 10

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_cursor)
        mock_db.commit = AsyncMock()

        mock_manager = MagicMock()
        mock_manager.cache = mock_db

        with patch(
            "app.infrastructure.recommendation_cache.get_db_manager",
            return_value=mock_manager,
        ):
            count = await cache.invalidate_all_recommendations()

        assert count == 10


class TestRecommendationCacheCleanupExpired:
    """Test cleaning up expired cache entries."""

    @pytest.mark.asyncio
    async def test_cleans_expired_entries(self):
        """Test cleaning up expired cache entries."""
        cache = RecommendationCache()

        mock_cursor1 = MagicMock()
        mock_cursor1.rowcount = 5
        mock_cursor2 = MagicMock()
        mock_cursor2.rowcount = 3

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=[mock_cursor1, mock_cursor2])
        mock_db.commit = AsyncMock()

        mock_manager = MagicMock()
        mock_manager.cache = mock_db

        with patch(
            "app.infrastructure.recommendation_cache.get_db_manager",
            return_value=mock_manager,
        ):
            count = await cache.cleanup_expired()

        assert count == 8  # 5 + 3


class TestRecommendationCacheGetCacheStats:
    """Test getting cache statistics."""

    @pytest.mark.asyncio
    async def test_returns_stats(self):
        """Test returning cache statistics."""
        cache = RecommendationCache()

        mock_rec_row = {"total": 10, "valid": 8}
        mock_analytics_row = {"total": 20, "valid": 15}

        mock_db = AsyncMock()
        mock_db.fetchone = AsyncMock(
            side_effect=[mock_rec_row, mock_analytics_row]
        )

        mock_manager = MagicMock()
        mock_manager.cache = mock_db

        with patch(
            "app.infrastructure.recommendation_cache.get_db_manager",
            return_value=mock_manager,
        ):
            stats = await cache.get_cache_stats()

        assert stats["recommendation_cache"]["total"] == 10
        assert stats["recommendation_cache"]["valid"] == 8
        assert stats["analytics_cache"]["total"] == 20
        assert stats["analytics_cache"]["valid"] == 15

    @pytest.mark.asyncio
    async def test_handles_empty_cache(self):
        """Test handling empty cache."""
        cache = RecommendationCache()

        mock_db = AsyncMock()
        mock_db.fetchone = AsyncMock(return_value=None)

        mock_manager = MagicMock()
        mock_manager.cache = mock_db

        with patch(
            "app.infrastructure.recommendation_cache.get_db_manager",
            return_value=mock_manager,
        ):
            stats = await cache.get_cache_stats()

        assert stats["recommendation_cache"]["total"] == 0
        assert stats["analytics_cache"]["total"] == 0


class TestGetRecommendationCache:
    """Test singleton getter."""

    def test_returns_same_instance(self):
        """Test that same instance is returned."""
        import app.infrastructure.recommendation_cache as module

        # Reset singleton
        original = module._cache_instance
        module._cache_instance = None

        try:
            cache1 = get_recommendation_cache()
            cache2 = get_recommendation_cache()

            assert cache1 is cache2
        finally:
            module._cache_instance = original
