"""Cache invalidation service - centralizes cache invalidation patterns."""

import logging
from typing import List, Optional

from app.infrastructure.cache import SimpleCache

logger = logging.getLogger(__name__)


class CacheInvalidationService:
    """Service for managing cache invalidation patterns."""

    def __init__(self, cache: SimpleCache):
        self._cache = cache

    def invalidate_trade_caches(self, include_depth: bool = True) -> None:
        """
        Invalidate all caches related to trade execution.

        Args:
            include_depth: If True, invalidate depth-specific recommendation caches
        """
        # Invalidate unified recommendations (portfolio-aware cache keys)
        # Use prefix invalidation to catch all portfolio-specific keys
        self._cache.invalidate_prefix("recommendations:")

        # Invalidate LED ticker caches (legacy format for compatibility)
        self._cache.invalidate("recommendations:3")
        self._cache.invalidate("sell_recommendations:3")

        logger.debug("Invalidated trade-related caches")

    def invalidate_recommendation_caches(
        self, limits: Optional[List[int]] = None, strategies: Optional[List[str]] = None
    ) -> None:
        """
        Invalidate recommendation caches.

        Args:
            limits: List of limit values to invalidate (default: [3])
            strategies: Not used (kept for backward compatibility)
        """
        # Invalidate unified recommendations using prefix
        self._cache.invalidate_prefix("recommendations:")

        # Invalidate LED ticker caches (legacy format for compatibility)
        if limits is None:
            limits = [3]
        for limit in limits:
            self._cache.invalidate(f"recommendations:{limit}")
            self._cache.invalidate(f"sell_recommendations:{limit}")

        logger.debug(f"Invalidated recommendation caches (limits: {limits})")

    def invalidate_portfolio_caches(self) -> None:
        """Invalidate all portfolio-related caches."""
        self._cache.invalidate("stocks_with_scores")
        self._cache.invalidate("sparklines")
        logger.debug("Invalidated portfolio-related caches")

    def invalidate_all_trade_related(self) -> None:
        """Invalidate all trade and recommendation related caches."""
        self.invalidate_trade_caches(include_depth=True)
        self.invalidate_portfolio_caches()
        logger.debug("Invalidated all trade-related caches")


def get_cache_invalidation_service(
    cache: Optional[SimpleCache] = None,
) -> CacheInvalidationService:
    """
    Get or create a CacheInvalidationService instance.

    Args:
        cache: Cache instance to use (default: imports from app.infrastructure.cache)

    Returns:
        CacheInvalidationService instance
    """
    if cache is None:
        from app.infrastructure.cache import cache as default_cache

        cache = default_cache

    return CacheInvalidationService(cache)
