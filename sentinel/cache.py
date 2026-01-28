"""
Cache - Simple in-memory TTL cache for expensive computations.

Usage:
    from sentinel.cache import Cache

    cache = Cache('motion', ttl_seconds=86400)
    cache.set('AAPL.US', motion_object)
    cached = cache.get('AAPL.US')  # Returns None if expired
    cache.invalidate('AAPL.US')    # Remove single entry
    cache.clear()                   # Remove all entries
"""

import time
from typing import TypeVar, Generic, Optional
from dataclasses import dataclass

T = TypeVar('T')


@dataclass
class CacheEntry(Generic[T]):
    """A cached value with expiration timestamp."""
    value: T
    expires_at: float
    created_at: float


class Cache(Generic[T]):
    """
    Simple in-memory TTL cache with named singleton instances.

    Each cache name gets a single shared instance, so Cache('motion')
    returns the same cache object throughout the application.
    """

    _instances: dict[str, 'Cache'] = {}

    def __new__(cls, name: str, ttl_seconds: int = 86400):
        """Named singleton pattern - one cache instance per name."""
        if name not in cls._instances:
            instance = super().__new__(cls)
            instance._initialized = False
            cls._instances[name] = instance
        return cls._instances[name]

    def __init__(self, name: str, ttl_seconds: int = 86400):
        if self._initialized:
            return
        self._initialized = True
        self._name = name
        self._ttl = ttl_seconds
        self._data: dict[str, CacheEntry[T]] = {}
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[T]:
        """
        Get a cached value by key.

        Returns None if key doesn't exist or has expired.
        """
        if key not in self._data:
            self._misses += 1
            return None

        entry = self._data[key]
        if time.time() > entry.expires_at:
            del self._data[key]
            self._misses += 1
            return None

        self._hits += 1
        return entry.value

    def set(self, key: str, value: T, ttl_seconds: Optional[int] = None) -> None:
        """
        Store a value in the cache.

        Args:
            key: Cache key
            value: Value to store
            ttl_seconds: Optional override for TTL (uses default if not specified)
        """
        ttl = ttl_seconds if ttl_seconds is not None else self._ttl
        now = time.time()
        self._data[key] = CacheEntry(
            value=value,
            expires_at=now + ttl,
            created_at=now,
        )

    def invalidate(self, key: str) -> bool:
        """
        Remove a single entry from the cache.

        Returns True if the key existed, False otherwise.
        """
        if key in self._data:
            del self._data[key]
            return True
        return False

    def clear(self) -> int:
        """
        Remove all entries from the cache.

        Returns the number of entries removed.
        """
        count = len(self._data)
        self._data.clear()
        return count

    def stats(self) -> dict:
        """
        Get cache statistics.

        Returns dict with entries, hits, misses, and hit rate.
        """
        now = time.time()
        valid_entries = sum(1 for e in self._data.values() if e.expires_at > now)
        total_requests = self._hits + self._misses

        return {
            'name': self._name,
            'entries': valid_entries,
            'ttl_seconds': self._ttl,
            'hits': self._hits,
            'misses': self._misses,
            'hit_rate': self._hits / total_requests if total_requests > 0 else 0.0,
        }

    def reset_stats(self) -> None:
        """Reset hit/miss counters."""
        self._hits = 0
        self._misses = 0

    @classmethod
    def get_all_stats(cls) -> dict[str, dict]:
        """Get statistics for all cache instances."""
        return {name: cache.stats() for name, cache in cls._instances.items()}

    @classmethod
    def clear_all(cls) -> dict[str, int]:
        """Clear all cache instances. Returns count of cleared entries per cache."""
        return {name: cache.clear() for name, cache in cls._instances.items()}
