"""Tests for singleton patterns.

These tests verify that Settings and Currency classes implement
the singleton pattern correctly. They will fail until the singleton
behavior is added to those classes.
"""

from sentinel.currency import Currency
from sentinel.settings import Settings


class TestSettingsSingleton:
    """Tests for Settings singleton pattern."""

    def test_settings_is_singleton(self):
        """Settings() always returns the same instance."""
        a = Settings()
        b = Settings()
        assert a is b

    def test_settings_singleton_shares_db(self):
        """Both instances share the same _db reference."""
        a = Settings()
        b = Settings()
        assert a._db is b._db


class TestCurrencySingleton:
    """Tests for Currency singleton pattern."""

    def test_currency_is_singleton(self):
        """Currency() always returns the same instance."""
        a = Currency()
        b = Currency()
        assert a is b

    def test_currency_singleton_shares_cache(self):
        """Both instances share the same _rates_cache reference."""
        a = Currency()
        b = Currency()
        assert a._rates_cache is b._rates_cache
