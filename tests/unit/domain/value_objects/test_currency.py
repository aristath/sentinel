"""Tests for Currency enum."""

import pytest

from app.domain.value_objects.currency import Currency


class TestCurrency:
    """Test Currency enum values and methods."""

    def test_enum_values_exist(self):
        """Test that all expected currency values exist."""
        assert Currency.EUR == "EUR"
        assert Currency.USD == "USD"
        assert Currency.HKD == "HKD"
        assert Currency.GBP == "GBP"

    def test_currency_values_are_strings(self):
        """Test that currency values are strings."""
        assert isinstance(Currency.EUR, str)
        assert isinstance(Currency.USD, str)
        assert isinstance(Currency.HKD, str)
        assert isinstance(Currency.GBP, str)

    def test_all_currencies_listed(self):
        """Test that we can get all currencies."""
        currencies = [Currency.EUR, Currency.USD, Currency.HKD, Currency.GBP]
        assert len(currencies) == 4
        assert Currency.EUR in currencies
        assert Currency.USD in currencies
        assert Currency.HKD in currencies
        assert Currency.GBP in currencies

    def test_currency_from_string_valid(self):
        """Test creating currency from valid string."""
        assert Currency.from_string("EUR") == Currency.EUR
        assert Currency.from_string("USD") == Currency.USD
        assert Currency.from_string("HKD") == Currency.HKD
        assert Currency.from_string("GBP") == Currency.GBP
        assert Currency.from_string("eur") == Currency.EUR  # Case insensitive
        assert Currency.from_string("usd") == Currency.USD

    def test_currency_from_string_invalid(self):
        """Test creating currency from invalid string raises error."""
        with pytest.raises(ValueError, match="Invalid currency"):
            Currency.from_string("INVALID")

        with pytest.raises(ValueError, match="Invalid currency"):
            Currency.from_string("")

        with pytest.raises(ValueError, match="Invalid currency"):
            Currency.from_string("JPY")  # Not supported

    def test_currency_is_valid(self):
        """Test checking if currency string is valid."""
        assert Currency.is_valid("EUR") is True
        assert Currency.is_valid("USD") is True
        assert Currency.is_valid("HKD") is True
        assert Currency.is_valid("GBP") is True
        assert Currency.is_valid("eur") is True  # Case insensitive
        assert Currency.is_valid("INVALID") is False
        assert Currency.is_valid("") is False
        assert Currency.is_valid("JPY") is False

    def test_default_currency(self):
        """Test that EUR is the default currency."""
        assert Currency.default() == Currency.EUR
