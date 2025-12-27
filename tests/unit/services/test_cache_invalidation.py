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
    cache_service.invalidate_trade_caches(include_depth=True)

    # Should use prefix invalidation
    mock_cache.invalidate_prefix.assert_called_once_with("recommendations:")

    # Should also invalidate specific LED ticker cache keys
    invalidated_keys = [call[0][0] for call in mock_cache.invalidate.call_args_list]
    assert "recommendations:3" in invalidated_keys
    assert "sell_recommendations:3" in invalidated_keys


def test_invalidate_trade_caches_no_depth(cache_service, mock_cache):
    """Test invalidating trade caches without depth-specific keys."""
    cache_service.invalidate_trade_caches(include_depth=False)

    # Should still use prefix invalidation
    mock_cache.invalidate_prefix.assert_called_once_with("recommendations:")

    # Should still invalidate LED ticker caches
    invalidated_keys = [call[0][0] for call in mock_cache.invalidate.call_args_list]
    assert "recommendations:3" in invalidated_keys
    assert "sell_recommendations:3" in invalidated_keys


def test_invalidate_recommendation_caches_defaults(cache_service, mock_cache):
    """Test invalidating recommendation caches with default parameters."""
    cache_service.invalidate_recommendation_caches()

    # Should use prefix invalidation
    mock_cache.invalidate_prefix.assert_called_once_with("recommendations:")

    # Should invalidate default limit keys
    invalidated_keys = [call[0][0] for call in mock_cache.invalidate.call_args_list]
    assert "recommendations:3" in invalidated_keys
    assert "sell_recommendations:3" in invalidated_keys


def test_invalidate_recommendation_caches_custom_limits(cache_service, mock_cache):
    """Test invalidating recommendation caches with custom limits."""
    cache_service.invalidate_recommendation_caches(limits=[5, 15])

    invalidated_keys = [call[0][0] for call in mock_cache.invalidate.call_args_list]
    assert "recommendations:5" in invalidated_keys
    assert "recommendations:15" in invalidated_keys
    assert "sell_recommendations:5" in invalidated_keys
    assert "sell_recommendations:15" in invalidated_keys


def test_invalidate_portfolio_caches(cache_service, mock_cache):
    """Test invalidating portfolio-related caches."""
    cache_service.invalidate_portfolio_caches()

    invalidated_keys = [call[0][0] for call in mock_cache.invalidate.call_args_list]
    assert "stocks_with_scores" in invalidated_keys
    assert "sparklines" in invalidated_keys


def test_invalidate_all_trade_related(cache_service, mock_cache):
    """Test invalidating all trade-related caches."""
    cache_service.invalidate_all_trade_related()

    # Should call both trade and portfolio invalidation
    assert mock_cache.invalidate.call_count > 0
    invalidated_keys = [call[0][0] for call in mock_cache.invalidate.call_args_list]
    assert "stocks_with_scores" in invalidated_keys
    assert "recommendations:3" in invalidated_keys


def test_get_cache_invalidation_service():
    """Test getting cache invalidation service instance."""
    from app.infrastructure.cache_invalidation import get_cache_invalidation_service

    service = get_cache_invalidation_service()
    assert isinstance(service, CacheInvalidationService)
