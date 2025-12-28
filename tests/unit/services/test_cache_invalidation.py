"""Unit tests for CacheInvalidationService."""

from unittest.mock import MagicMock

import pytest

from app.infrastructure.cache import SimpleCache
from app.infrastructure.cache_invalidation import CacheInvalidationService


@pytest.fixture
def mock_cache():
    """Mock SimpleCache."""
    cache = MagicMock(spec=SimpleCache)
    return cache


@pytest.fixture
def cache_service(mock_cache):
    """Create CacheInvalidationService instance."""
    return CacheInvalidationService(mock_cache)


def test_invalidate_trade_caches(cache_service, mock_cache):
    """Test invalidating trade-related caches."""
    cache_service.invalidate_trade_caches()

    # Should use prefix invalidation for all recommendation keys
    mock_cache.invalidate_prefix.assert_called_once_with("recommendations:")


def test_invalidate_recommendation_caches(cache_service, mock_cache):
    """Test invalidating recommendation caches."""
    cache_service.invalidate_recommendation_caches()

    # Should use prefix invalidation for all recommendation keys
    mock_cache.invalidate_prefix.assert_called_once_with("recommendations:")


def test_invalidate_portfolio_caches(cache_service, mock_cache):
    """Test invalidating portfolio-related caches."""
    cache_service.invalidate_portfolio_caches()

    invalidated_keys = [call[0][0] for call in mock_cache.invalidate.call_args_list]
    assert "stocks_with_scores" in invalidated_keys
    assert "sparklines" in invalidated_keys


def test_invalidate_all_trade_related(cache_service, mock_cache):
    """Test invalidating all trade-related caches."""
    cache_service.invalidate_all_trade_related()

    # Should call prefix invalidation for recommendations
    mock_cache.invalidate_prefix.assert_called_with("recommendations:")

    # Should also invalidate portfolio caches
    invalidated_keys = [call[0][0] for call in mock_cache.invalidate.call_args_list]
    assert "stocks_with_scores" in invalidated_keys


def test_get_cache_invalidation_service():
    """Test getting cache invalidation service instance."""
    from app.infrastructure.cache_invalidation import get_cache_invalidation_service

    service = get_cache_invalidation_service()
    assert isinstance(service, CacheInvalidationService)
