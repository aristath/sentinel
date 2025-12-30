"""Tests for TradeSide value object.

These tests validate the TradeSide enum and its conversion/validation functionality.
"""

import pytest

from app.domain.value_objects.trade_side import TradeSide


class TestTradeSide:
    """Test TradeSide enum."""

    def test_trade_side_enum_values(self):
        """Test that TradeSide enum has expected values."""
        assert TradeSide.BUY.value == "BUY"
        assert TradeSide.SELL.value == "SELL"

    def test_from_string_with_valid_side(self):
        """Test from_string with valid trade side strings."""
        assert TradeSide.from_string("BUY") == TradeSide.BUY
        assert TradeSide.from_string("SELL") == TradeSide.SELL

    def test_from_string_case_insensitive(self):
        """Test that from_string is case-insensitive."""
        assert TradeSide.from_string("buy") == TradeSide.BUY
        assert TradeSide.from_string("Buy") == TradeSide.BUY
        assert TradeSide.from_string("BUY") == TradeSide.BUY
        assert TradeSide.from_string("sell") == TradeSide.SELL
        assert TradeSide.from_string("Sell") == TradeSide.SELL

    def test_from_string_with_invalid_side(self):
        """Test that from_string raises ValueError for invalid sides."""
        with pytest.raises(ValueError, match="Invalid trade side"):
            TradeSide.from_string("INVALID")

        with pytest.raises(ValueError):
            TradeSide.from_string("")

        with pytest.raises(ValueError):
            TradeSide.from_string("HOLD")

    def test_from_string_with_none(self):
        """Test that from_string raises ValueError for None."""
        with pytest.raises(ValueError):
            TradeSide.from_string(None)

    def test_is_buy(self):
        """Test is_buy method."""
        assert TradeSide.BUY.is_buy() is True
        assert TradeSide.SELL.is_buy() is False

    def test_is_sell(self):
        """Test is_sell method."""
        assert TradeSide.SELL.is_sell() is True
        assert TradeSide.BUY.is_sell() is False

    def test_trade_side_str_representation(self):
        """Test that TradeSide enum values have correct string representation."""
        assert str(TradeSide.BUY) == "TradeSide.BUY"
        assert str(TradeSide.SELL) == "TradeSide.SELL"

    def test_trade_side_equality(self):
        """Test TradeSide enum equality."""
        assert TradeSide.BUY == TradeSide.BUY
        assert TradeSide.SELL == TradeSide.SELL
        assert TradeSide.BUY != TradeSide.SELL
