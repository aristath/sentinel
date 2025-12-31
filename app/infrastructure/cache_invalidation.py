"""Cache invalidation service - centralizes cache invalidation patterns."""

import logging

from app.core.cache.cache import SimpleCache

logger = logging.getLogger(__name__)


class CacheInvalidationService:
    """Service for managing cache invalidation patterns."""

    def __init__(self, cache: SimpleCache):
        self._cache = cache

    def invalidate_trade_caches(self) -> None:
        """
        Invalidate all caches related to trade execution.
        """
        # Invalidate all recommendations using prefix invalidation
        # This catches all portfolio-specific keys: recommendations:{hash}
        self._cache.invalidate_prefix("recommendations:")

        logger.debug("Invalidated trade-related caches")

        # Emit event for recommendation updates
        try:
            from app.core.events import SystemEvent, emit

            emit(SystemEvent.RECOMMENDATIONS_INVALIDATED)
        except Exception as e:
            logger.debug(f"Could not emit recommendations invalidated event: {e}")

    def invalidate_recommendation_caches(self) -> None:
        """
        Invalidate recommendation caches.
        """
        # Invalidate all recommendations using prefix invalidation
        # This catches all portfolio-specific keys: recommendations:{hash}
        self._cache.invalidate_prefix("recommendations:")

        logger.debug("Invalidated recommendation caches")

        # Emit event for recommendation updates
        try:
            from app.core.events import SystemEvent, emit

            emit(SystemEvent.RECOMMENDATIONS_INVALIDATED)
        except Exception as e:
            logger.debug(f"Could not emit recommendations invalidated event: {e}")

    def invalidate_portfolio_caches(self) -> None:
        """Invalidate all portfolio-related caches."""
        self._cache.invalidate("stocks_with_scores")
        self._cache.invalidate("sparklines")
        logger.debug("Invalidated portfolio-related caches")

    def invalidate_all_trade_related(self) -> None:
        """Invalidate all trade and recommendation related caches."""
        self.invalidate_trade_caches()
        self.invalidate_portfolio_caches()
        logger.debug("Invalidated all trade-related caches")


def get_cache_invalidation_service(
    cache: SimpleCache | None = None,
) -> CacheInvalidationService:
    """
    Get or create a CacheInvalidationService instance.

    Args:
        cache: Cache instance to use (default: imports from app.core.cache.cache)

    Returns:
        CacheInvalidationService instance
    """
    if cache is None:
        from app.core.cache.cache import cache as default_cache

        cache = default_cache

    return CacheInvalidationService(cache)
