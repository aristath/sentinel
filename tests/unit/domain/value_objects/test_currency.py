"""Tests for Currency value object.

These tests validate the Currency enum and its from_string conversion functionality.
"""

import pytest

from app.shared.domain.value_objects.currency import Currency


class TestCurrency:
    """Test Currency enum."""

    def test_currency_enum_values(self):
        """Test that Currency enum has expected values."""
        assert Currency.EUR.value == "EUR"
        assert Currency.USD.value == "USD"
        assert Currency.GBP.value == "GBP"
        assert Currency.HKD.value == "HKD"

    def test_from_string_with_valid_currency(self):
        """Test from_string with valid currency strings."""
        assert Currency.from_string("EUR") == Currency.EUR
        assert Currency.from_string("USD") == Currency.USD
        assert Currency.from_string("GBP") == Currency.GBP
        assert Currency.from_string("HKD") == Currency.HKD
        assert Currency.from_string("DKK") == Currency.DKK

    def test_from_string_case_insensitive(self):
        """Test that from_string is case-insensitive."""
        assert Currency.from_string("eur") == Currency.EUR
        assert Currency.from_string("Eur") == Currency.EUR
        assert Currency.from_string("EUR") == Currency.EUR
        assert Currency.from_string("usd") == Currency.USD
        assert Currency.from_string("Usd") == Currency.USD

    def test_from_string_with_invalid_currency(self):
        """Test that from_string raises ValueError for invalid currencies."""
        with pytest.raises(ValueError, match="Unknown currency"):
            Currency.from_string("INVALID")

        with pytest.raises(ValueError):
            Currency.from_string("")

        with pytest.raises(ValueError):
            Currency.from_string("XXX")

    def test_from_string_with_none(self):
        """Test that from_string raises ValueError for None."""
        with pytest.raises(ValueError):
            Currency.from_string(None)

    def test_currency_str_representation(self):
        """Test that Currency enum values have correct string representation."""
        assert str(Currency.EUR) == "Currency.EUR"
        assert str(Currency.USD) == "Currency.USD"

    def test_currency_equality(self):
        """Test Currency enum equality."""
        assert Currency.EUR == Currency.EUR
        assert Currency.USD == Currency.USD
        assert Currency.EUR != Currency.USD

    def test_is_valid_with_valid_currency(self):
        """Test is_valid method with valid currencies."""
        assert Currency.is_valid("EUR") is True
        assert Currency.is_valid("USD") is True
        assert Currency.is_valid("GBP") is True
        assert Currency.is_valid("HKD") is True
        assert Currency.is_valid("eur") is True  # Case insensitive

    def test_is_valid_with_invalid_currency(self):
        """Test is_valid method with invalid currencies."""
        assert Currency.is_valid("INVALID") is False
        assert Currency.is_valid("") is False
        assert Currency.is_valid("XXX") is False

    def test_default_returns_eur(self):
        """Test that default method returns EUR."""
        assert Currency.default() == Currency.EUR
