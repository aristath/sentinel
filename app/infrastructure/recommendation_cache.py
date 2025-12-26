"""
Recommendation Cache - Caches expensive recommendation calculations.

Uses portfolio hash to cache recommendations and analytics data.
TTL: 48 hours for portfolio-hash-keyed data, 4 hours for symbol-specific data.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.infrastructure.database.manager import get_db_manager

logger = logging.getLogger(__name__)

# TTL constants
RECOMMENDATION_TTL_HOURS = 48
ANALYTICS_TTL_HOURS = 48
SYMBOL_DATA_TTL_HOURS = 4


class RecommendationCache:
    """Cache for expensive recommendation calculations."""

    def __init__(self):
        self._db_manager = None

    async def _get_db(self):
        """Get cache database connection."""
        if self._db_manager is None:
            self._db_manager = get_db_manager()
        return self._db_manager.cache

    async def get_recommendations(
        self, portfolio_hash: str, cache_type: str
    ) -> Optional[List[Dict]]:
        """
        Get cached recommendations for a portfolio hash.

        Args:
            portfolio_hash: MD5 hash of portfolio positions
            cache_type: 'buy', 'sell', 'multi_step', or 'strategic'

        Returns:
            List of recommendation dicts or None if not cached/expired
        """
        db = await self._get_db()
        now = datetime.now().isoformat()

        row = await db.fetchone(
            """SELECT data FROM recommendation_cache
               WHERE portfolio_hash = ? AND cache_type = ? AND expires_at > ?""",
            (portfolio_hash, cache_type, now),
        )

        if row:
            try:
                data = json.loads(row["data"])
                logger.debug(
                    f"Cache HIT: {cache_type} recommendations for hash {portfolio_hash[:8]}..."
                )
                return data
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to parse cached recommendations: {e}")

        logger.debug(
            f"Cache MISS: {cache_type} recommendations for hash {portfolio_hash[:8]}..."
        )
        return None

    async def set_recommendations(
        self,
        portfolio_hash: str,
        cache_type: str,
        data: List[Dict],
        ttl_hours: int = RECOMMENDATION_TTL_HOURS,
    ) -> None:
        """
        Cache recommendations for a portfolio hash.

        Args:
            portfolio_hash: MD5 hash of portfolio positions
            cache_type: 'buy', 'sell', 'multi_step', or 'strategic'
            data: List of recommendation dicts
            ttl_hours: Time to live in hours (default 48)
        """
        db = await self._get_db()
        now = datetime.now()
        expires_at = (now + timedelta(hours=ttl_hours)).isoformat()

        await db.execute(
            """INSERT OR REPLACE INTO recommendation_cache
               (portfolio_hash, cache_type, data, expires_at, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (portfolio_hash, cache_type, json.dumps(data), expires_at, now.isoformat()),
        )
        await db.commit()
        logger.debug(
            f"Cached {len(data)} {cache_type} recommendations for hash {portfolio_hash[:8]}..."
        )

    async def get_analytics(self, cache_key: str) -> Optional[Any]:
        """
        Get cached analytics data.

        Args:
            cache_key: Cache key (e.g., 'perf:weights:{hash}', 'risk:{symbol}')

        Returns:
            Cached data or None if not cached/expired
        """
        db = await self._get_db()
        now = datetime.now().isoformat()

        row = await db.fetchone(
            """SELECT data FROM analytics_cache
               WHERE cache_key = ? AND expires_at > ?""",
            (cache_key, now),
        )

        if row:
            try:
                data = json.loads(row["data"])
                logger.debug(f"Analytics cache HIT: {cache_key}")
                return data
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to parse cached analytics: {e}")

        logger.debug(f"Analytics cache MISS: {cache_key}")
        return None

    async def set_analytics(
        self, cache_key: str, data: Any, ttl_hours: int = ANALYTICS_TTL_HOURS
    ) -> None:
        """
        Cache analytics data.

        Args:
            cache_key: Cache key
            data: Data to cache (must be JSON serializable)
            ttl_hours: Time to live in hours
        """
        db = await self._get_db()
        now = datetime.now()
        expires_at = (now + timedelta(hours=ttl_hours)).isoformat()

        await db.execute(
            """INSERT OR REPLACE INTO analytics_cache
               (cache_key, data, expires_at, created_at)
               VALUES (?, ?, ?, ?)""",
            (cache_key, json.dumps(data), expires_at, now.isoformat()),
        )
        await db.commit()
        logger.debug(f"Cached analytics: {cache_key}")

    async def invalidate_portfolio_hash(self, portfolio_hash: str) -> int:
        """
        Invalidate all cached data for a portfolio hash.

        Called after trades change the portfolio composition.

        Args:
            portfolio_hash: MD5 hash of portfolio positions

        Returns:
            Number of entries invalidated
        """
        db = await self._get_db()

        # Delete recommendation cache entries
        cursor = await db.execute(
            "DELETE FROM recommendation_cache WHERE portfolio_hash = ?",
            (portfolio_hash,),
        )
        rec_count = cursor.rowcount

        # Delete analytics entries keyed by this hash
        cursor = await db.execute(
            "DELETE FROM analytics_cache WHERE cache_key LIKE ?",
            (f"%{portfolio_hash}%",),
        )
        analytics_count = cursor.rowcount

        await db.commit()

        total = rec_count + analytics_count
        if total > 0:
            logger.info(
                f"Invalidated {total} cache entries for portfolio hash {portfolio_hash[:8]}..."
            )
        return total

    async def invalidate_all_recommendations(self) -> int:
        """
        Invalidate all recommendation caches.

        Useful when market conditions change significantly.

        Returns:
            Number of entries invalidated
        """
        db = await self._get_db()

        cursor = await db.execute("DELETE FROM recommendation_cache")
        count = cursor.rowcount

        await db.commit()

        if count > 0:
            logger.info(f"Invalidated {count} recommendation cache entries")
        return count

    async def cleanup_expired(self) -> int:
        """
        Remove expired cache entries.

        Called by maintenance job.

        Returns:
            Number of entries removed
        """
        db = await self._get_db()
        now = datetime.now().isoformat()
        total = 0

        # Clean recommendation cache
        cursor = await db.execute(
            "DELETE FROM recommendation_cache WHERE expires_at < ?", (now,)
        )
        total += cursor.rowcount

        # Clean analytics cache
        cursor = await db.execute(
            "DELETE FROM analytics_cache WHERE expires_at < ?", (now,)
        )
        total += cursor.rowcount

        await db.commit()

        if total > 0:
            logger.info(f"Cleaned up {total} expired cache entries")
        return total

    async def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics for monitoring.

        Returns:
            Dict with cache stats
        """
        db = await self._get_db()
        now = datetime.now().isoformat()

        # Recommendation cache stats
        rec_row = await db.fetchone(
            """SELECT
                COUNT(*) as total,
                SUM(CASE WHEN expires_at > ? THEN 1 ELSE 0 END) as valid
               FROM recommendation_cache""",
            (now,),
        )

        # Analytics cache stats
        analytics_row = await db.fetchone(
            """SELECT
                COUNT(*) as total,
                SUM(CASE WHEN expires_at > ? THEN 1 ELSE 0 END) as valid
               FROM analytics_cache""",
            (now,),
        )

        return {
            "recommendation_cache": {
                "total": rec_row["total"] if rec_row else 0,
                "valid": rec_row["valid"] if rec_row else 0,
            },
            "analytics_cache": {
                "total": analytics_row["total"] if analytics_row else 0,
                "valid": analytics_row["valid"] if analytics_row else 0,
            },
        }


# Singleton instance
_cache_instance: Optional[RecommendationCache] = None


def get_recommendation_cache() -> RecommendationCache:
    """Get the singleton RecommendationCache instance."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = RecommendationCache()
    return _cache_instance
