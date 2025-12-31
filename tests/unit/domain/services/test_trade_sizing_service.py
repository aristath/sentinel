"""Tests for trade sizing service.

These tests validate trade size calculations including lot size constraints,
currency conversion, and minimum trade size enforcement.
"""

import pytest

from app.modules.trading.services.trade_sizing_service import TradeSizingService


class TestCalculateBuyQuantity:
    """Test calculate_buy_quantity method."""

    def test_calculates_quantity_for_eur_stock(self):
        """Test quantity calculation for EUR stock."""
        result = TradeSizingService.calculate_buy_quantity(
            target_value_eur=1000.0, price=50.0, min_lot=1, exchange_rate=1.0
        )

        assert result.quantity == 20  # 1000 / 50 = 20 shares
        assert result.value_native == 1000.0
        assert result.value_eur == 1000.0
        assert result.num_lots == 20  # 20 / 1 = 20 lots

    def test_respects_min_lot_constraint(self):
        """Test that minimum lot size is respected."""
        # Target 1000 EUR, price 100 EUR = 10 shares, but min_lot = 20
        result = TradeSizingService.calculate_buy_quantity(
            target_value_eur=1000.0, price=100.0, min_lot=20, exchange_rate=1.0
        )

        assert result.quantity == 20  # Rounded up to min_lot
        assert result.num_lots == 1  # 20 / 20 = 1 lot

    def test_handles_currency_conversion(self):
        """Test handling of currency conversion for non-EUR stocks."""
        result = TradeSizingService.calculate_buy_quantity(
            target_value_eur=1000.0, price=100.0, min_lot=1, exchange_rate=1.1
        )

        # 1000 EUR / 1.1 = 909.09 USD value
        # 909.09 / 100 = 9.09 shares, rounded down to 9
        assert result.quantity == 9
        assert result.value_native == pytest.approx(900.0, rel=0.01)  # 9 * 100
        assert result.value_eur == pytest.approx(990.0, rel=0.01)  # 900 * 1.1

    def test_rounds_down_to_whole_shares(self):
        """Test that quantity is rounded down to whole shares."""
        result = TradeSizingService.calculate_buy_quantity(
            target_value_eur=1000.0, price=33.33, min_lot=1, exchange_rate=1.0
        )

        # 1000 / 33.33 = 30.003 shares, should round down to 30
        assert result.quantity == 30
        assert result.value_native == pytest.approx(999.9, rel=0.01)

    def test_handles_fractional_target_that_rounds_to_zero(self):
        """Test handling when target value results in zero shares."""
        result = TradeSizingService.calculate_buy_quantity(
            target_value_eur=10.0, price=1000.0, min_lot=1, exchange_rate=1.0
        )

        # 10 / 1000 = 0.01 shares, rounds down to 0
        # But should respect min_lot, so quantity = 1
        assert result.quantity >= 1  # Should be at least min_lot

    def test_calculates_lots_correctly(self):
        """Test that number of lots is calculated correctly."""
        result = TradeSizingService.calculate_buy_quantity(
            target_value_eur=1000.0, price=50.0, min_lot=10, exchange_rate=1.0
        )

        # 1000 / 50 = 20 shares
        # 20 / 10 = 2 lots
        assert result.quantity == 20
        assert result.num_lots == 2


class TestCalculateSellQuantity:
    """Test calculate_sell_quantity method."""

    def test_rounds_down_to_lot_boundary(self):
        """Test that quantity is rounded down to nearest lot boundary."""
        result = TradeSizingService.calculate_sell_quantity(
            target_quantity=15.7, min_lot=5, current_holdings=100
        )

        # 15.7 / 5 = 3.14, rounds down to 3 lots
        assert result == 15  # 3 * 5 = 15 shares

    def test_respects_min_lot_constraint(self):
        """Test that minimum lot size is respected for sells."""
        result = TradeSizingService.calculate_sell_quantity(
            target_quantity=7, min_lot=5, current_holdings=100
        )

        # 7 / 5 = 1.4, rounds down to 1 lot
        assert result == 5  # 1 * 5 = 5 shares

    def test_caps_at_current_holdings(self):
        """Test that sell quantity is capped at current holdings."""
        result = TradeSizingService.calculate_sell_quantity(
            target_quantity=150, min_lot=1, current_holdings=100
        )

        # Target 150, but only have 100
        assert result == 100

    def test_caps_at_current_holdings_with_lots(self):
        """Test that sell quantity is capped at current holdings when using lots."""
        result = TradeSizingService.calculate_sell_quantity(
            target_quantity=150, min_lot=10, current_holdings=95
        )

        # 150 / 10 = 15 lots = 150 shares, but capped at 95
        # 95 / 10 = 9.5, rounds down to 9 lots = 90 shares
        assert result == 90

    def test_handles_zero_current_holdings(self):
        """Test handling when current holdings is zero."""
        result = TradeSizingService.calculate_sell_quantity(
            target_quantity=100, min_lot=1, current_holdings=0
        )

        # Should round down but not be capped (since holdings=0 means no cap)
        assert result == 100

    def test_handles_min_lot_of_one(self):
        """Test handling when min_lot is 1 (no lot rounding)."""
        result = TradeSizingService.calculate_sell_quantity(
            target_quantity=15.7, min_lot=1, current_holdings=100
        )

        # Should just round down to int
        assert result == 15


class TestRoundToLots:
    """Test round_to_lots method."""

    def test_rounds_down_to_lot_boundary(self):
        """Test that quantity is rounded down to nearest lot boundary."""
        result = TradeSizingService.round_to_lots(quantity=17, min_lot=5)

        # 17 / 5 = 3.4, rounds down to 3 lots
        assert result == 15  # 3 * 5 = 15 shares

    def test_handles_min_lot_of_one(self):
        """Test handling when min_lot is 1 (no lot rounding)."""
        result = TradeSizingService.round_to_lots(quantity=15.7, min_lot=1)

        # Should just round down to int
        assert result == 15

    def test_handles_exact_lot_multiple(self):
        """Test handling when quantity is exact multiple of min_lot."""
        result = TradeSizingService.round_to_lots(quantity=20, min_lot=5)

        assert result == 20  # 4 * 5 = 20, exact match

    def test_handles_quantity_less_than_lot(self):
        """Test handling when quantity is less than one lot."""
        result = TradeSizingService.round_to_lots(quantity=3, min_lot=5)

        # 3 / 5 = 0.6, rounds down to 0 lots
        assert result == 0


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_handles_zero_price(self):
        """Test handling of zero price (should not crash)."""
        # This would cause division by zero, but method should handle gracefully
        # or raise appropriate error
        with pytest.raises((ZeroDivisionError, ValueError)):
            TradeSizingService.calculate_buy_quantity(
                target_value_eur=1000.0, price=0.0, min_lot=1, exchange_rate=1.0
            )

    def test_handles_zero_target_value(self):
        """Test handling of zero target value."""
        result = TradeSizingService.calculate_buy_quantity(
            target_value_eur=0.0, price=50.0, min_lot=1, exchange_rate=1.0
        )

        assert result.quantity == 0
        assert result.value_native == 0.0
        assert result.value_eur == 0.0

    def test_handles_negative_price(self):
        """Test handling of negative price (should not crash)."""
        # Negative price shouldn't happen in practice, but should handle gracefully
        with pytest.raises(ValueError):
            TradeSizingService.calculate_buy_quantity(
                target_value_eur=1000.0, price=-50.0, min_lot=1, exchange_rate=1.0
            )

    def test_handles_very_small_target_value(self):
        """Test handling of very small target values."""
        result = TradeSizingService.calculate_buy_quantity(
            target_value_eur=1.0, price=100.0, min_lot=1, exchange_rate=1.0
        )

        # 1 / 100 = 0.01 shares, but min_lot costs 100 EUR
        # Since lot_cost_eur (100) > target_value_eur (1), buy exactly min_lot
        assert result.quantity == 1

    def test_handles_very_high_price(self):
        """Test handling of very high stock prices."""
        result = TradeSizingService.calculate_buy_quantity(
            target_value_eur=1000.0, price=10000.0, min_lot=1, exchange_rate=1.0
        )

        # lot_cost_eur = 1 * 10000 / 1 = 10000
        # Since lot_cost_eur (10000) > target_value_eur (1000), buy exactly min_lot
        assert result.quantity == 1

    def test_handles_min_lot_greater_than_calculated_quantity(self):
        """Test when min_lot is greater than calculated quantity."""
        result = TradeSizingService.calculate_buy_quantity(
            target_value_eur=1000.0, price=100.0, min_lot=50, exchange_rate=1.0
        )

        # 1000 / 100 = 10 shares, but min_lot = 50
        # Should round up to 50
        assert result.quantity == 50
        assert result.num_lots == 1
