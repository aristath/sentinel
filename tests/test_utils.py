"""Tests for utility modules.

These tests verify the intended behavior of utility functions:
1. Fee calculations
2. Score adjustments for conviction
3. Position value calculations
"""

import pytest
import numpy as np
from unittest.mock import AsyncMock, MagicMock

from sentinel.utils.fees import FeeCalculator
from sentinel.utils.scoring import adjust_score_for_conviction
from sentinel.utils.positions import PositionCalculator


# =============================================================================
# Fee Calculator Tests
# =============================================================================

class TestFeeCalculator:
    """Tests for FeeCalculator."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings with default fees."""
        settings = AsyncMock()
        # Default: €2 fixed + 0.2% variable
        settings.get = AsyncMock(side_effect=lambda key, default: {
            'transaction_fee_fixed': 2.0,
            'transaction_fee_percent': 0.2,
        }.get(key, default))
        return settings

    @pytest.fixture
    def calculator(self, mock_settings):
        return FeeCalculator(settings=mock_settings)

    # -------------------------------------------------------------------------
    # Basic Fee Calculation
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_calculate_small_trade(self, calculator):
        """Small trade: fixed fee dominates."""
        # €100 trade: €2 fixed + €0.20 (0.2%) = €2.20
        fee = await calculator.calculate(100.0)
        assert abs(fee - 2.20) < 0.01

    @pytest.mark.asyncio
    async def test_calculate_medium_trade(self, calculator):
        """Medium trade: both components significant."""
        # €1000 trade: €2 fixed + €2.00 (0.2%) = €4.00
        fee = await calculator.calculate(1000.0)
        assert abs(fee - 4.00) < 0.01

    @pytest.mark.asyncio
    async def test_calculate_large_trade(self, calculator):
        """Large trade: percentage fee dominates."""
        # €10000 trade: €2 fixed + €20.00 (0.2%) = €22.00
        fee = await calculator.calculate(10000.0)
        assert abs(fee - 22.00) < 0.01

    @pytest.mark.asyncio
    async def test_calculate_zero_trade(self, calculator):
        """Zero trade: only fixed fee."""
        fee = await calculator.calculate(0.0)
        assert abs(fee - 2.00) < 0.01

    def test_calculate_with_config_sync(self, calculator):
        """Synchronous calculation with explicit config."""
        # €500 trade with €1.50 fixed + 0.1% variable
        fee = calculator.calculate_with_config(500.0, 1.50, 0.001)
        # €1.50 + €0.50 = €2.00
        assert abs(fee - 2.00) < 0.01

    def test_calculate_with_config_zero_pct(self, calculator):
        """Calculation with zero percentage fee."""
        fee = calculator.calculate_with_config(1000.0, 5.0, 0.0)
        assert fee == 5.0

    def test_calculate_with_config_zero_fixed(self, calculator):
        """Calculation with zero fixed fee."""
        fee = calculator.calculate_with_config(1000.0, 0.0, 0.005)  # 0.5%
        assert abs(fee - 5.0) < 0.01

    # -------------------------------------------------------------------------
    # Batch Fee Calculation
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_calculate_batch_single_buy(self, calculator):
        """Single buy trade."""
        trades = [{'action': 'buy', 'value_eur': 1000.0}]
        result = await calculator.calculate_batch(trades)

        assert result['num_buys'] == 1
        assert result['num_sells'] == 0
        assert result['total_buy_value'] == 1000.0
        assert result['total_sell_value'] == 0.0
        # €2 + €2 = €4
        assert abs(result['buy_fees'] - 4.0) < 0.01
        assert result['sell_fees'] == 0.0
        assert abs(result['total_fees'] - 4.0) < 0.01

    @pytest.mark.asyncio
    async def test_calculate_batch_single_sell(self, calculator):
        """Single sell trade."""
        trades = [{'action': 'sell', 'value_eur': 500.0}]
        result = await calculator.calculate_batch(trades)

        assert result['num_buys'] == 0
        assert result['num_sells'] == 1
        # €2 + €1 = €3
        assert abs(result['sell_fees'] - 3.0) < 0.01

    @pytest.mark.asyncio
    async def test_calculate_batch_multiple_trades(self, calculator):
        """Multiple buys and sells."""
        trades = [
            {'action': 'buy', 'value_eur': 1000.0},
            {'action': 'buy', 'value_eur': 2000.0},
            {'action': 'sell', 'value_eur': 500.0},
        ]
        result = await calculator.calculate_batch(trades)

        assert result['num_buys'] == 2
        assert result['num_sells'] == 1
        assert result['total_buy_value'] == 3000.0
        assert result['total_sell_value'] == 500.0

        # Buy fees: 2 * €2 fixed + €3000 * 0.2% = €4 + €6 = €10
        assert abs(result['buy_fees'] - 10.0) < 0.01
        # Sell fees: 1 * €2 fixed + €500 * 0.2% = €2 + €1 = €3
        assert abs(result['sell_fees'] - 3.0) < 0.01
        # Total: €13
        assert abs(result['total_fees'] - 13.0) < 0.01

    @pytest.mark.asyncio
    async def test_calculate_batch_empty(self, calculator):
        """Empty trade list."""
        result = await calculator.calculate_batch([])

        assert result['num_buys'] == 0
        assert result['num_sells'] == 0
        assert result['total_fees'] == 0.0

    @pytest.mark.asyncio
    async def test_calculate_batch_negative_values_use_abs(self, calculator):
        """Negative values should use absolute value."""
        trades = [{'action': 'buy', 'value_eur': -1000.0}]
        result = await calculator.calculate_batch(trades)

        assert result['total_buy_value'] == 1000.0  # Absolute value

    @pytest.mark.asyncio
    async def test_calculate_batch_unknown_action_ignored(self, calculator):
        """Unknown actions are ignored."""
        trades = [
            {'action': 'hold', 'value_eur': 1000.0},
            {'action': 'buy', 'value_eur': 500.0},
        ]
        result = await calculator.calculate_batch(trades)

        assert result['num_buys'] == 1
        assert result['total_buy_value'] == 500.0


# =============================================================================
# Scoring Utilities Tests
# =============================================================================

class TestAdjustScoreForConviction:
    """Tests for adjust_score_for_conviction function."""

    def test_neutral_conviction_no_change(self):
        """Multiplier 1.0 (neutral) should not change score."""
        base = 0.05  # 5% expected return
        result = adjust_score_for_conviction(base, 1.0)
        assert result == base

    def test_bullish_conviction_boost(self):
        """Multiplier 2.0 (max bullish) adds +0.30."""
        base = 0.05
        result = adjust_score_for_conviction(base, 2.0)
        # 0.05 + (2.0 - 1.0) * 0.3 = 0.05 + 0.30 = 0.35
        assert abs(result - 0.35) < 0.001

    def test_bearish_conviction_penalty(self):
        """Multiplier 0.5 (bearish) subtracts -0.15."""
        base = 0.05
        result = adjust_score_for_conviction(base, 0.5)
        # 0.05 + (0.5 - 1.0) * 0.3 = 0.05 - 0.15 = -0.10
        assert abs(result - (-0.10)) < 0.001

    def test_strong_bearish_conviction(self):
        """Multiplier 0.25 (strong bearish) subtracts -0.225."""
        base = 0.0
        result = adjust_score_for_conviction(base, 0.25)
        # 0.0 + (0.25 - 1.0) * 0.3 = 0.0 - 0.225 = -0.225
        assert abs(result - (-0.225)) < 0.001

    def test_moderate_bullish_conviction(self):
        """Multiplier 1.5 adds +0.15."""
        base = 0.10
        result = adjust_score_for_conviction(base, 1.5)
        # 0.10 + (1.5 - 1.0) * 0.3 = 0.10 + 0.15 = 0.25
        assert abs(result - 0.25) < 0.001

    def test_none_multiplier_treated_as_neutral(self):
        """None multiplier should be treated as 1.0 (neutral)."""
        base = 0.05
        result = adjust_score_for_conviction(base, None)
        assert result == base

    def test_negative_base_score(self):
        """Works correctly with negative base scores."""
        base = -0.10  # -10% expected return
        result = adjust_score_for_conviction(base, 2.0)
        # -0.10 + 0.30 = 0.20
        assert abs(result - 0.20) < 0.001

    def test_conviction_can_flip_sign(self):
        """Strong conviction can flip a negative score to positive."""
        base = -0.05
        result = adjust_score_for_conviction(base, 2.0)
        assert result > 0  # Became positive

    def test_conviction_can_make_negative(self):
        """Bearish conviction can make a positive score negative."""
        base = 0.05
        result = adjust_score_for_conviction(base, 0.25)
        assert result < 0  # Became negative


# =============================================================================
# Position Calculator Tests
# =============================================================================

class TestPositionCalculator:
    """Tests for PositionCalculator."""

    @pytest.fixture
    def mock_converter(self):
        """Create mock currency converter."""
        converter = AsyncMock()
        # EUR is 1:1, USD at 1.10 (1 USD = 0.91 EUR)
        async def to_eur(amount, currency):
            rates = {'EUR': 1.0, 'USD': 0.91, 'GBP': 1.17, 'CHF': 1.02}
            return amount * rates.get(currency, 1.0)
        converter.to_eur = to_eur
        return converter

    @pytest.fixture
    def calculator(self, mock_converter):
        return PositionCalculator(currency_converter=mock_converter)

    # -------------------------------------------------------------------------
    # Value Calculations
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_calculate_value_local(self, calculator):
        """Basic local value calculation."""
        value = await calculator.calculate_value_local(100, 50.0)
        assert value == 5000.0

    @pytest.mark.asyncio
    async def test_calculate_value_local_zero_quantity(self, calculator):
        """Zero quantity produces zero value."""
        value = await calculator.calculate_value_local(0, 100.0)
        assert value == 0.0

    @pytest.mark.asyncio
    async def test_calculate_value_eur_same_currency(self, calculator):
        """EUR position needs no conversion."""
        value = await calculator.calculate_value_eur(100, 50.0, 'EUR')
        assert value == 5000.0

    @pytest.mark.asyncio
    async def test_calculate_value_eur_usd(self, calculator):
        """USD position converts to EUR."""
        # 100 shares at $50 = $5000 USD
        # At 0.91 rate: $5000 * 0.91 = €4550
        value = await calculator.calculate_value_eur(100, 50.0, 'USD')
        assert abs(value - 4550.0) < 0.01

    @pytest.mark.asyncio
    async def test_calculate_value_eur_gbp(self, calculator):
        """GBP position converts to EUR."""
        # 10 shares at £100 = £1000 GBP
        # At 1.17 rate: £1000 * 1.17 = €1170
        value = await calculator.calculate_value_eur(10, 100.0, 'GBP')
        assert abs(value - 1170.0) < 0.01

    # -------------------------------------------------------------------------
    # Allocation Calculations
    # -------------------------------------------------------------------------

    def test_calculate_allocation_normal(self, calculator):
        """Normal allocation percentage."""
        allocation = calculator.calculate_allocation(15000.0, 100000.0)
        assert abs(allocation - 0.15) < 0.001

    def test_calculate_allocation_zero_total(self, calculator):
        """Zero total returns zero allocation."""
        allocation = calculator.calculate_allocation(15000.0, 0.0)
        assert allocation == 0.0

    def test_calculate_allocation_negative_total(self, calculator):
        """Negative total returns zero allocation."""
        allocation = calculator.calculate_allocation(15000.0, -100.0)
        assert allocation == 0.0

    def test_calculate_allocation_full_portfolio(self, calculator):
        """Full portfolio = 100% allocation."""
        allocation = calculator.calculate_allocation(100000.0, 100000.0)
        assert abs(allocation - 1.0) < 0.001

    def test_calculate_allocation_small_position(self, calculator):
        """Small position = small allocation."""
        allocation = calculator.calculate_allocation(100.0, 100000.0)
        assert abs(allocation - 0.001) < 0.0001

    # -------------------------------------------------------------------------
    # Profit Calculations
    # -------------------------------------------------------------------------

    def test_calculate_profit_gain(self, calculator):
        """Profitable position."""
        # 100 shares, bought at €50, now at €60
        pct, value = calculator.calculate_profit(100, 60.0, 50.0)
        assert abs(pct - 20.0) < 0.01  # 20% gain
        assert abs(value - 1000.0) < 0.01  # €1000 profit

    def test_calculate_profit_loss(self, calculator):
        """Losing position."""
        # 100 shares, bought at €50, now at €40
        pct, value = calculator.calculate_profit(100, 40.0, 50.0)
        assert abs(pct - (-20.0)) < 0.01  # 20% loss
        assert abs(value - (-1000.0)) < 0.01  # €1000 loss

    def test_calculate_profit_breakeven(self, calculator):
        """Breakeven position."""
        pct, value = calculator.calculate_profit(100, 50.0, 50.0)
        assert pct == 0.0
        assert value == 0.0

    def test_calculate_profit_zero_cost(self, calculator):
        """Zero cost returns zero (avoid division by zero)."""
        pct, value = calculator.calculate_profit(100, 50.0, 0.0)
        assert pct == 0.0
        assert value == 0.0

    def test_calculate_profit_negative_cost(self, calculator):
        """Negative cost returns zero."""
        pct, value = calculator.calculate_profit(100, 50.0, -10.0)
        assert pct == 0.0
        assert value == 0.0

    # -------------------------------------------------------------------------
    # Portfolio Value Calculations
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_calculate_portfolio_values_single(self, calculator):
        """Single position portfolio."""
        positions = [{
            'symbol': 'TEST',
            'quantity': 100,
            'current_price': 50.0,
            'currency': 'EUR',
        }]
        result = await calculator.calculate_portfolio_values(positions)

        assert abs(result['total_value_eur'] - 5000.0) < 0.01
        assert len(result['positions_with_values']) == 1
        assert result['positions_with_values'][0]['value_eur'] == 5000.0
        assert abs(result['allocations']['TEST'] - 1.0) < 0.001  # 100%

    @pytest.mark.asyncio
    async def test_calculate_portfolio_values_multiple(self, calculator):
        """Multiple position portfolio with different currencies."""
        positions = [
            {'symbol': 'EUR_POS', 'quantity': 100, 'current_price': 50.0, 'currency': 'EUR'},
            {'symbol': 'USD_POS', 'quantity': 100, 'current_price': 50.0, 'currency': 'USD'},
        ]
        result = await calculator.calculate_portfolio_values(positions)

        # EUR: €5000, USD: $5000 * 0.91 = €4550
        expected_total = 5000.0 + 4550.0
        assert abs(result['total_value_eur'] - expected_total) < 0.01

        # Allocations
        eur_alloc = result['allocations']['EUR_POS']
        usd_alloc = result['allocations']['USD_POS']
        assert abs(eur_alloc - (5000.0 / expected_total)) < 0.001
        assert abs(usd_alloc - (4550.0 / expected_total)) < 0.001
        assert abs(eur_alloc + usd_alloc - 1.0) < 0.001  # Sum to 100%

    @pytest.mark.asyncio
    async def test_calculate_portfolio_values_empty(self, calculator):
        """Empty portfolio."""
        result = await calculator.calculate_portfolio_values([])

        assert result['total_value_eur'] == 0.0
        assert len(result['positions_with_values']) == 0
        assert len(result['allocations']) == 0

    @pytest.mark.asyncio
    async def test_calculate_portfolio_values_zero_quantity(self, calculator):
        """Position with zero quantity."""
        positions = [{
            'symbol': 'EMPTY',
            'quantity': 0,
            'current_price': 100.0,
            'currency': 'EUR',
        }]
        result = await calculator.calculate_portfolio_values(positions)

        assert result['total_value_eur'] == 0.0
        assert result['allocations']['EMPTY'] == 0.0

    @pytest.mark.asyncio
    async def test_calculate_portfolio_values_missing_fields(self, calculator):
        """Position with missing fields uses defaults."""
        positions = [{'symbol': 'PARTIAL'}]  # Missing quantity, price, currency
        result = await calculator.calculate_portfolio_values(positions)

        assert result['total_value_eur'] == 0.0


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================

class TestEdgeCases:
    """Edge case tests for utilities."""

    def test_conviction_with_extreme_multiplier(self):
        """Extreme multipliers are handled gracefully."""
        # Very high multiplier
        result = adjust_score_for_conviction(0.0, 10.0)
        assert abs(result - 2.7) < 0.001  # (10 - 1) * 0.3 = 2.7

        # Very low multiplier
        result = adjust_score_for_conviction(0.0, 0.0)
        assert abs(result - (-0.3)) < 0.001  # (0 - 1) * 0.3 = -0.3

    def test_conviction_with_float_precision(self):
        """Float precision doesn't cause issues."""
        base = 0.123456789
        multiplier = 1.333333333
        result = adjust_score_for_conviction(base, multiplier)
        expected = base + (multiplier - 1.0) * 0.3
        assert abs(result - expected) < 0.0000001

    @pytest.mark.asyncio
    async def test_fee_with_very_large_trade(self):
        """Very large trade values don't overflow."""
        settings = AsyncMock()
        settings.get = AsyncMock(side_effect=lambda k, d: {
            'transaction_fee_fixed': 2.0,
            'transaction_fee_percent': 0.2,
        }.get(k, d))
        calc = FeeCalculator(settings=settings)

        # €1 billion trade
        fee = await calc.calculate(1_000_000_000.0)
        # €2 + €2,000,000 = €2,000,002
        assert abs(fee - 2_000_002.0) < 0.01

    @pytest.mark.asyncio
    async def test_fee_with_fractional_cents(self):
        """Fractional cent values are handled."""
        settings = AsyncMock()
        settings.get = AsyncMock(side_effect=lambda k, d: {
            'transaction_fee_fixed': 1.999,
            'transaction_fee_percent': 0.199,
        }.get(k, d))
        calc = FeeCalculator(settings=settings)

        fee = await calc.calculate(100.0)
        # Should work without errors
        assert fee > 0
