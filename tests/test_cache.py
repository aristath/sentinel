"""Tests for in-memory TTL cache.

These tests verify the intended behavior of the Cache class:
1. Basic get/set operations
2. TTL expiration
3. Named singleton pattern
4. Statistics tracking
5. Cache invalidation
"""

import pytest
import time
from unittest.mock import patch

from sentinel.cache import Cache, CacheEntry


class TestCacheBasicOperations:
    """Tests for basic cache operations."""

    def setup_method(self):
        """Clear cache instances before each test."""
        Cache._instances.clear()

    def test_set_and_get(self):
        """Basic set and get operations."""
        cache = Cache('test_basic', ttl_seconds=3600)
        cache.set('key1', 'value1')
        assert cache.get('key1') == 'value1'

    def test_get_nonexistent_returns_none(self):
        """Getting non-existent key returns None."""
        cache = Cache('test_nonexistent', ttl_seconds=3600)
        assert cache.get('nonexistent') is None

    def test_set_overwrites_existing(self):
        """Setting existing key overwrites value."""
        cache = Cache('test_overwrite', ttl_seconds=3600)
        cache.set('key', 'old_value')
        cache.set('key', 'new_value')
        assert cache.get('key') == 'new_value'

    def test_stores_different_types(self):
        """Cache can store different value types."""
        cache = Cache('test_types', ttl_seconds=3600)

        # String
        cache.set('str', 'hello')
        assert cache.get('str') == 'hello'

        # Integer
        cache.set('int', 42)
        assert cache.get('int') == 42

        # Float
        cache.set('float', 3.14)
        assert cache.get('float') == 3.14

        # List
        cache.set('list', [1, 2, 3])
        assert cache.get('list') == [1, 2, 3]

        # Dict
        cache.set('dict', {'a': 1, 'b': 2})
        assert cache.get('dict') == {'a': 1, 'b': 2}

        # None
        cache.set('none', None)
        assert cache.get('none') is None

    def test_stores_complex_objects(self):
        """Cache can store complex nested objects."""
        cache = Cache('test_complex', ttl_seconds=3600)
        complex_obj = {
            'nested': {'a': [1, 2, 3]},
            'tuple_as_list': (1, 2),  # Tuples become lists
            'number': 42.5,
        }
        cache.set('complex', complex_obj)
        assert cache.get('complex') == complex_obj


class TestCacheTTL:
    """Tests for cache TTL expiration."""

    def setup_method(self):
        Cache._instances.clear()

    def test_value_available_before_expiration(self):
        """Value is available before TTL expires."""
        cache = Cache('test_ttl_before', ttl_seconds=3600)
        cache.set('key', 'value')

        # Should be available immediately
        assert cache.get('key') == 'value'

    def test_value_expires_after_ttl(self):
        """Value expires after TTL."""
        cache = Cache('test_ttl_expire', ttl_seconds=1)
        cache.set('key', 'value')

        # Mock time to be after expiration
        with patch('sentinel.cache.time') as mock_time:
            # First call during set
            mock_time.time.return_value = 1000.0
            cache.set('key', 'value')

            # Get before expiration
            mock_time.time.return_value = 1000.5
            assert cache.get('key') == 'value'

            # Get after expiration
            mock_time.time.return_value = 1002.0  # 2 seconds later, TTL=1
            assert cache.get('key') is None

    def test_custom_ttl_per_key(self):
        """Custom TTL can be set per key."""
        cache = Cache('test_custom_ttl', ttl_seconds=3600)  # Default 1 hour

        with patch('sentinel.cache.time') as mock_time:
            mock_time.time.return_value = 1000.0

            # Set with short TTL
            cache.set('short', 'value', ttl_seconds=10)
            # Set with default TTL
            cache.set('default', 'value')

            # After 15 seconds
            mock_time.time.return_value = 1015.0
            assert cache.get('short') is None  # Expired
            assert cache.get('default') == 'value'  # Still valid


class TestCacheNamedSingleton:
    """Tests for named singleton pattern."""

    def setup_method(self):
        Cache._instances.clear()

    def test_same_name_returns_same_instance(self):
        """Same cache name returns same instance."""
        cache1 = Cache('shared', ttl_seconds=100)
        cache2 = Cache('shared', ttl_seconds=200)  # Different TTL ignored

        assert cache1 is cache2

    def test_different_names_return_different_instances(self):
        """Different cache names return different instances."""
        cache1 = Cache('cache_a', ttl_seconds=100)
        cache2 = Cache('cache_b', ttl_seconds=100)

        assert cache1 is not cache2

    def test_data_shared_in_same_instance(self):
        """Data is shared between same-name cache references."""
        cache1 = Cache('shared_data')
        cache2 = Cache('shared_data')

        cache1.set('key', 'value')
        assert cache2.get('key') == 'value'

    def test_data_not_shared_between_instances(self):
        """Data is not shared between different cache instances."""
        cache_a = Cache('isolated_a')
        cache_b = Cache('isolated_b')

        cache_a.set('key', 'value_a')
        cache_b.set('key', 'value_b')

        assert cache_a.get('key') == 'value_a'
        assert cache_b.get('key') == 'value_b'


class TestCacheInvalidation:
    """Tests for cache invalidation."""

    def setup_method(self):
        Cache._instances.clear()

    def test_invalidate_existing_key(self):
        """Invalidate removes existing key and returns True."""
        cache = Cache('test_invalidate')
        cache.set('key', 'value')

        result = cache.invalidate('key')

        assert result is True
        assert cache.get('key') is None

    def test_invalidate_nonexistent_key(self):
        """Invalidate on non-existent key returns False."""
        cache = Cache('test_invalidate_missing')
        result = cache.invalidate('nonexistent')
        assert result is False

    def test_clear_removes_all_entries(self):
        """Clear removes all entries and returns count."""
        cache = Cache('test_clear')
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')
        cache.set('key3', 'value3')

        count = cache.clear()

        assert count == 3
        assert cache.get('key1') is None
        assert cache.get('key2') is None
        assert cache.get('key3') is None

    def test_clear_empty_cache(self):
        """Clear on empty cache returns 0."""
        cache = Cache('test_clear_empty')
        count = cache.clear()
        assert count == 0


class TestCacheStatistics:
    """Tests for cache statistics."""

    def setup_method(self):
        Cache._instances.clear()

    def test_stats_tracks_hits(self):
        """Statistics tracks cache hits."""
        cache = Cache('test_stats_hits')
        cache.set('key', 'value')

        cache.get('key')  # Hit
        cache.get('key')  # Hit
        cache.get('key')  # Hit

        stats = cache.stats()
        assert stats['hits'] == 3
        assert stats['misses'] == 0

    def test_stats_tracks_misses(self):
        """Statistics tracks cache misses."""
        cache = Cache('test_stats_misses')

        cache.get('nonexistent1')  # Miss
        cache.get('nonexistent2')  # Miss

        stats = cache.stats()
        assert stats['hits'] == 0
        assert stats['misses'] == 2

    def test_stats_calculates_hit_rate(self):
        """Statistics calculates correct hit rate."""
        cache = Cache('test_hit_rate')
        cache.set('key', 'value')

        cache.get('key')  # Hit
        cache.get('key')  # Hit
        cache.get('missing')  # Miss
        cache.get('missing')  # Miss

        stats = cache.stats()
        assert stats['hit_rate'] == 0.5  # 2 hits, 2 misses = 50%

    def test_stats_hit_rate_zero_requests(self):
        """Hit rate is 0.0 when no requests made."""
        cache = Cache('test_no_requests')
        stats = cache.stats()
        assert stats['hit_rate'] == 0.0

    def test_stats_includes_metadata(self):
        """Stats includes cache metadata."""
        cache = Cache('test_metadata', ttl_seconds=1234)
        stats = cache.stats()

        assert stats['name'] == 'test_metadata'
        assert stats['ttl_seconds'] == 1234

    def test_reset_stats(self):
        """Reset stats clears hit/miss counters."""
        cache = Cache('test_reset_stats')
        cache.set('key', 'value')
        cache.get('key')
        cache.get('missing')

        cache.reset_stats()

        stats = cache.stats()
        assert stats['hits'] == 0
        assert stats['misses'] == 0


class TestCacheClassMethods:
    """Tests for cache class methods."""

    def setup_method(self):
        Cache._instances.clear()

    def test_get_all_stats(self):
        """Get stats for all cache instances."""
        cache1 = Cache('cache_1')
        cache2 = Cache('cache_2')
        cache1.set('a', 1)
        cache2.set('b', 2)

        all_stats = Cache.get_all_stats()

        assert 'cache_1' in all_stats
        assert 'cache_2' in all_stats
        assert all_stats['cache_1']['entries'] == 1
        assert all_stats['cache_2']['entries'] == 1

    def test_clear_all(self):
        """Clear all cache instances."""
        cache1 = Cache('clear_all_1')
        cache2 = Cache('clear_all_2')
        cache1.set('a', 1)
        cache1.set('b', 2)
        cache2.set('c', 3)

        cleared = Cache.clear_all()

        assert cleared['clear_all_1'] == 2
        assert cleared['clear_all_2'] == 1
        assert cache1.get('a') is None
        assert cache2.get('c') is None


class TestCacheEntry:
    """Tests for CacheEntry dataclass."""

    def test_cache_entry_creation(self):
        """CacheEntry stores value and timestamps."""
        entry = CacheEntry(
            value='test_value',
            expires_at=1000.0,
            created_at=900.0
        )
        assert entry.value == 'test_value'
        assert entry.expires_at == 1000.0
        assert entry.created_at == 900.0
