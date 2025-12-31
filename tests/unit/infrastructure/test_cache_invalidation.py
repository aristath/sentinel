"""Tests for CacheInvalidationService.

These tests validate the cache invalidation service for managing cache invalidation patterns.
"""

from unittest.mock import MagicMock, patch

from app.core.cache.cache import SimpleCache
from app.infrastructure.cache_invalidation import (
    CacheInvalidationService,
    get_cache_invalidation_service,
)


class TestCacheInvalidationService:
    """Test CacheInvalidationService class."""

    def test_init_with_cache(self):
        """Test initializing CacheInvalidationService with a cache."""
        mock_cache = MagicMock(spec=SimpleCache)
        service = CacheInvalidationService(mock_cache)

        assert service._cache == mock_cache

    def test_invalidate_trade_caches(self):
        """Test invalidate_trade_caches method."""
        mock_cache = MagicMock(spec=SimpleCache)
        service = CacheInvalidationService(mock_cache)

        with patch("app.infrastructure.cache_invalidation.emit"):
            with patch("app.infrastructure.cache_invalidation.SystemEvent"):
                service.invalidate_trade_caches()

                mock_cache.invalidate_prefix.assert_called_once_with("recommendations:")

    def test_invalidate_recommendation_caches(self):
        """Test invalidate_recommendation_caches method."""
        mock_cache = MagicMock(spec=SimpleCache)
        service = CacheInvalidationService(mock_cache)

        with patch("app.infrastructure.cache_invalidation.emit"):
            with patch("app.infrastructure.cache_invalidation.SystemEvent"):
                service.invalidate_recommendation_caches()

                mock_cache.invalidate_prefix.assert_called_once_with("recommendations:")

    def test_invalidate_portfolio_caches(self):
        """Test invalidate_portfolio_caches method."""
        mock_cache = MagicMock(spec=SimpleCache)
        service = CacheInvalidationService(mock_cache)

        service.invalidate_portfolio_caches()

        assert mock_cache.invalidate.call_count == 2
        mock_cache.invalidate.assert_any_call("stocks_with_scores")
        mock_cache.invalidate.assert_any_call("sparklines")

    def test_invalidate_all_trade_related(self):
        """Test invalidate_all_trade_related method."""
        mock_cache = MagicMock(spec=SimpleCache)
        service = CacheInvalidationService(mock_cache)

        with patch("app.infrastructure.cache_invalidation.emit"):
            with patch("app.infrastructure.cache_invalidation.SystemEvent"):
                service.invalidate_all_trade_related()

                # Should call both invalidate_trade_caches and invalidate_portfolio_caches
                mock_cache.invalidate_prefix.assert_called_with("recommendations:")
                assert mock_cache.invalidate.call_count == 2


class TestGetCacheInvalidationService:
    """Test get_cache_invalidation_service function."""

    @patch("app.infrastructure.cache_invalidation.cache")
    def test_get_cache_invalidation_service_with_default_cache(
        self, mock_default_cache
    ):
        """Test get_cache_invalidation_service with default cache."""
        service = get_cache_invalidation_service()

        assert isinstance(service, CacheInvalidationService)
        assert service._cache == mock_default_cache

    def test_get_cache_invalidation_service_with_custom_cache(self):
        """Test get_cache_invalidation_service with custom cache."""
        mock_cache = MagicMock(spec=SimpleCache)
        service = get_cache_invalidation_service(cache=mock_cache)

        assert isinstance(service, CacheInvalidationService)
        assert service._cache == mock_cache
