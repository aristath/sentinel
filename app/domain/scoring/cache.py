"""Per-sub-component score caching with database persistence.

Implements tiered caching for scoring sub-components:
- SLOW (7 days): long_term, fundamentals, dividends
- MEDIUM (24 hours): opinion
- FAST (4 hours): opportunity, short_term, technicals
- DYNAMIC (no cache): diversification
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)

# TTL Configuration (seconds)
CACHE_TTL = {
    # SLOW tier - 7 days (604800 seconds)
    "long_term:cagr": 604800,
    "long_term:sortino": 604800,
    "long_term:sharpe": 604800,
    "fundamentals:financial_strength": 604800,
    "fundamentals:consistency": 604800,
    "dividends:yield": 604800,
    "dividends:consistency": 604800,
    # MEDIUM tier - 24 hours (86400 seconds)
    "opinion:recommendation": 86400,
    "opinion:price_target": 86400,
    # FAST tier - 4 hours (14400 seconds)
    "opportunity:below_52w_high": 14400,
    "opportunity:pe_ratio": 14400,
    "short_term:momentum": 14400,
    "short_term:drawdown": 14400,
    "technicals:rsi": 14400,
    "technicals:bollinger": 14400,
    "technicals:ema": 14400,
    # DYNAMIC - no cache
    "diversification:geography": 0,
    "diversification:industry": 0,
    "diversification:averaging": 0,
}

# Sub-component mapping for each group
SUBCOMPONENTS = {
    "long_term": ["cagr", "sortino", "sharpe"],
    "fundamentals": ["financial_strength", "consistency"],
    "dividends": ["yield", "consistency"],
    "opportunity": ["below_52w_high", "pe_ratio"],
    "short_term": ["momentum", "drawdown"],
    "technicals": ["rsi", "bollinger", "ema"],
    "opinion": ["recommendation", "price_target"],
    "diversification": ["geography", "industry", "averaging"],
}


class ScoreCache:
    """Database-backed cache for per-sub-component stock scores.

    Uses a dual-layer caching strategy:
    - Memory cache for hot access during current session
    - Database (cache.db) for persistence across restarts
    """

    def __init__(self, db_manager=None):
        self._db = db_manager
        self._memory_cache: Dict[str, tuple] = {}  # {key: (score, expires_at)}

    def _make_key(self, symbol: str, group: str, subcomponent: str) -> str:
        """Create cache key for a sub-component."""
        return f"score:{symbol}:{group}:{subcomponent}"

    async def get(self, symbol: str, group: str, subcomponent: str) -> Optional[float]:
        """Get cached sub-component score if valid.

        Args:
            symbol: Stock symbol
            group: Scoring group (e.g., 'long_term')
            subcomponent: Sub-component (e.g., 'cagr')

        Returns:
            Cached score or None if not cached/expired
        """
        key = self._make_key(symbol, group, subcomponent)

        # Check memory cache first (fastest)
        if key in self._memory_cache:
            score, expires_at = self._memory_cache[key]
            if datetime.now() < expires_at:
                return score
            # Expired - remove from memory
            del self._memory_cache[key]

        # Check database
        if self._db:
            try:
                cursor = await self._db.cache.execute(
                    "SELECT value, expires_at FROM cache_entries WHERE key = ?",
                    (key,)
                )
                row = await cursor.fetchone()
                if row:
                    value, expires_at_str = row
                    expires_at = datetime.fromisoformat(expires_at_str)
                    if datetime.now() < expires_at:
                        score = float(value)
                        # Promote to memory cache
                        self._memory_cache[key] = (score, expires_at)
                        return score
                    # Expired - clean up
                    await self._db.cache.execute(
                        "DELETE FROM cache_entries WHERE key = ?", (key,)
                    )
            except Exception as e:
                logger.debug(f"Cache get error for {key}: {e}")

        return None

    async def set(self, symbol: str, group: str, subcomponent: str, score: float):
        """Cache a sub-component score with appropriate TTL.

        Args:
            symbol: Stock symbol
            group: Scoring group
            subcomponent: Sub-component name
            score: Score value (0-1)
        """
        ttl_key = f"{group}:{subcomponent}"
        ttl = CACHE_TTL.get(ttl_key, 0)
        if ttl == 0:
            return  # Don't cache dynamic components

        key = self._make_key(symbol, group, subcomponent)
        expires_at = datetime.now() + timedelta(seconds=ttl)

        # Update memory cache
        self._memory_cache[key] = (score, expires_at)

        # Persist to database
        if self._db:
            try:
                await self._db.cache.execute(
                    """INSERT OR REPLACE INTO cache_entries
                       (key, value, expires_at, created_at)
                       VALUES (?, ?, ?, ?)""",
                    (key, str(score), expires_at.isoformat(), datetime.now().isoformat())
                )
                await self._db.cache.commit()
            except Exception as e:
                logger.debug(f"Cache set error for {key}: {e}")

    async def get_group(self, symbol: str, group: str) -> Dict[str, float]:
        """Get all cached sub-components for a group.

        Args:
            symbol: Stock symbol
            group: Scoring group

        Returns:
            Dict of {subcomponent: score} for cached entries
        """
        results = {}
        subcomponents = SUBCOMPONENTS.get(group, [])
        for sub in subcomponents:
            score = await self.get(symbol, group, sub)
            if score is not None:
                results[sub] = score
        return results

    async def set_group(self, symbol: str, group: str, scores: Dict[str, float]):
        """Cache all sub-components for a group.

        Args:
            symbol: Stock symbol
            group: Scoring group
            scores: Dict of {subcomponent: score}
        """
        for subcomponent, score in scores.items():
            await self.set(symbol, group, subcomponent, score)

    async def invalidate(
        self,
        symbol: str,
        group: str = None,
        subcomponent: str = None
    ):
        """Invalidate cache entries.

        Args:
            symbol: Stock symbol
            group: Optional - invalidate specific group
            subcomponent: Optional - invalidate specific subcomponent
        """
        if group and subcomponent:
            # Invalidate single entry
            key = self._make_key(symbol, group, subcomponent)
            self._memory_cache.pop(key, None)
            if self._db:
                await self._db.cache.execute(
                    "DELETE FROM cache_entries WHERE key = ?", (key,)
                )
        elif group:
            # Invalidate all subcomponents in group
            prefix = f"score:{symbol}:{group}:"
            keys_to_remove = [k for k in self._memory_cache if k.startswith(prefix)]
            for k in keys_to_remove:
                del self._memory_cache[k]
            if self._db:
                await self._db.cache.execute(
                    "DELETE FROM cache_entries WHERE key LIKE ?", (f"{prefix}%",)
                )
        else:
            # Invalidate all for symbol
            prefix = f"score:{symbol}:"
            keys_to_remove = [k for k in self._memory_cache if k.startswith(prefix)]
            for k in keys_to_remove:
                del self._memory_cache[k]
            if self._db:
                await self._db.cache.execute(
                    "DELETE FROM cache_entries WHERE key LIKE ?", (f"{prefix}%",)
                )

        if self._db:
            try:
                await self._db.cache.commit()
            except Exception as e:
                logger.debug(f"Cache invalidate commit error: {e}")

    async def invalidate_all(self):
        """Clear entire score cache."""
        self._memory_cache.clear()
        if self._db:
            try:
                await self._db.cache.execute(
                    "DELETE FROM cache_entries WHERE key LIKE 'score:%'"
                )
                await self._db.cache.commit()
                logger.info("Score cache cleared")
            except Exception as e:
                logger.error(f"Failed to clear score cache: {e}")

    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dict with memory and database entry counts
        """
        memory_count = len(self._memory_cache)
        db_count = 0
        if self._db:
            try:
                cursor = await self._db.cache.execute(
                    "SELECT COUNT(*) FROM cache_entries WHERE key LIKE 'score:%'"
                )
                row = await cursor.fetchone()
                db_count = row[0] if row else 0
            except Exception:
                pass

        return {
            "memory_entries": memory_count,
            "database_entries": db_count,
        }


# Global instance (initialized with db_manager in startup)
score_cache: Optional[ScoreCache] = None


def init_score_cache(db_manager):
    """Initialize score cache with database manager.

    Call this during application startup.
    """
    global score_cache
    score_cache = ScoreCache(db_manager)
    logger.info("Score cache initialized")


def get_score_cache() -> Optional[ScoreCache]:
    """Get the global score cache instance."""
    return score_cache
