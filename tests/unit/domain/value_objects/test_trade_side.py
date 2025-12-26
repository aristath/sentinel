"""Tests for TradeSide enum."""

import pytest

from app.domain.value_objects.trade_side import TradeSide


class TestTradeSide:
    """Test TradeSide enum values and methods."""

    def test_enum_values_exist(self):
        """Test that all expected trade side values exist."""
        assert TradeSide.BUY == "BUY"
        assert TradeSide.SELL == "SELL"

    def test_trade_side_values_are_strings(self):
        """Test that trade side values are strings."""
        assert isinstance(TradeSide.BUY, str)
        assert isinstance(TradeSide.SELL, str)

    def test_trade_side_from_string_valid(self):
        """Test creating trade side from valid string."""
        assert TradeSide.from_string("BUY") == TradeSide.BUY
        assert TradeSide.from_string("SELL") == TradeSide.SELL
        assert TradeSide.from_string("buy") == TradeSide.BUY  # Case insensitive
        assert TradeSide.from_string("sell") == TradeSide.SELL
        assert TradeSide.from_string("Buy") == TradeSide.BUY

    def test_trade_side_from_string_invalid(self):
        """Test creating trade side from invalid string raises error."""
        with pytest.raises(ValueError, match="Invalid trade side"):
            TradeSide.from_string("INVALID")

        with pytest.raises(ValueError, match="Invalid trade side"):
            TradeSide.from_string("")

        with pytest.raises(ValueError, match="Invalid trade side"):
            TradeSide.from_string("PURCHASE")

    def test_trade_side_is_valid(self):
        """Test checking if trade side string is valid."""
        assert TradeSide.is_valid("BUY") is True
        assert TradeSide.is_valid("SELL") is True
        assert TradeSide.is_valid("buy") is True  # Case insensitive
        assert TradeSide.is_valid("INVALID") is False
        assert TradeSide.is_valid("") is False

    def test_trade_side_is_buy(self):
        """Test checking if trade side is BUY."""
        assert TradeSide.BUY.is_buy() is True
        assert TradeSide.SELL.is_buy() is False

    def test_trade_side_is_sell(self):
        """Test checking if trade side is SELL."""
        assert TradeSide.BUY.is_sell() is False
        assert TradeSide.SELL.is_sell() is True
