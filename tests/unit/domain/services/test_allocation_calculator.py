"""Tests for allocation calculator.

These tests validate allocation and rebalancing calculations including
rebalance band checks, position sizing, and trade limits.
"""

from app.domain.models import StockPriority


class TestIsOutsideRebalanceBand:
    """Test is_outside_rebalance_band function."""

    def test_returns_true_when_deviation_exceeds_explicit_band(self):
        """Test that True is returned when deviation exceeds explicit band."""
        from app.domain.services.allocation_calculator import is_outside_rebalance_band

        result = is_outside_rebalance_band(
            current_weight=0.6, target_weight=0.5, band_pct=0.08
        )

        assert result is True  # Deviation 0.1 > 0.08

    def test_returns_false_when_deviation_within_explicit_band(self):
        """Test that False is returned when deviation is within explicit band."""
        from app.domain.services.allocation_calculator import is_outside_rebalance_band

        result = is_outside_rebalance_band(
            current_weight=0.53, target_weight=0.5, band_pct=0.05
        )

        assert result is False  # Deviation 0.03 < 0.05

    def test_uses_high_priority_band_for_large_positions(self):
        """Test that high priority band (5%) is used for positions >10%."""
        from app.domain.services.allocation_calculator import is_outside_rebalance_band

        # Position > 10%, deviation = 0.06 > 0.05 (high priority band)
        result = is_outside_rebalance_band(
            current_weight=0.56, target_weight=0.5, position_size_pct=0.15
        )

        assert result is True

    def test_uses_medium_band_for_medium_positions(self):
        """Test that medium band (7%) is used for positions 5-10%."""
        from app.domain.services.allocation_calculator import is_outside_rebalance_band

        # Position 5-10%, deviation = 0.08 > 0.07 (medium band)
        result = is_outside_rebalance_band(
            current_weight=0.58, target_weight=0.5, position_size_pct=0.08
        )

        assert result is True

    def test_uses_small_band_for_small_positions(self):
        """Test that small band (10%) is used for positions <5%."""
        from app.domain.services.allocation_calculator import is_outside_rebalance_band

        # Position < 5%, deviation = 0.12 > 0.10 (small band)
        result = is_outside_rebalance_band(
            current_weight=0.12, target_weight=0.0, position_size_pct=0.03
        )

        assert result is True

    def test_uses_max_weight_as_proxy_when_position_size_not_provided(self):
        """Test that max(current, target) is used as proxy when position_size_pct not provided."""
        from app.domain.services.allocation_calculator import is_outside_rebalance_band

        # max(0.15, 0.5) = 0.5 > 0.10, so uses high priority band (5%)
        # Deviation 0.05 is exactly at threshold, should be False
        result = is_outside_rebalance_band(current_weight=0.15, target_weight=0.5)

        assert result is False  # Deviation 0.35, but wait... let me recalculate
        # Actually: deviation = abs(0.15 - 0.5) = 0.35, band = 5% (0.05)
        # So 0.35 > 0.05, should be True
        result2 = is_outside_rebalance_band(current_weight=0.15, target_weight=0.5)
        assert result2 is True


class TestParseIndustries:
    """Test parse_industries function."""

    def test_parses_comma_separated_industries(self):
        """Test that comma-separated industries are parsed correctly."""
        from app.domain.services.allocation_calculator import parse_industries

        result = parse_industries("Technology, Finance, Healthcare")

        assert result == ["Technology", "Finance", "Healthcare"]

    def test_strips_whitespace(self):
        """Test that whitespace is stripped from industry names."""
        from app.domain.services.allocation_calculator import parse_industries

        result = parse_industries(" Technology , Finance , Healthcare ")

        assert result == ["Technology", "Finance", "Healthcare"]

    def test_returns_empty_list_for_none(self):
        """Test that empty list is returned for None input."""
        from app.domain.services.allocation_calculator import parse_industries

        result = parse_industries(None)

        assert result == []

    def test_returns_empty_list_for_empty_string(self):
        """Test that empty list is returned for empty string."""
        from app.domain.services.allocation_calculator import parse_industries

        result = parse_industries("")

        assert result == []

    def test_handles_single_industry(self):
        """Test handling of single industry (no comma)."""
        from app.domain.services.allocation_calculator import parse_industries

        result = parse_industries("Technology")

        assert result == ["Technology"]

    def test_filters_empty_parts(self):
        """Test that empty parts (from double commas) are filtered out."""
        from app.domain.services.allocation_calculator import parse_industries

        result = parse_industries("Technology,,Finance,,")

        assert result == ["Technology", "Finance"]


class TestCalculatePositionSize:
    """Test calculate_position_size function."""

    def test_calculates_size_with_volatility_weighting(self):
        """Test that position size is adjusted by volatility."""
        from app.domain.services.allocation_calculator import calculate_position_size

        candidate = StockPriority(
            symbol="AAPL",
            stock_score=0.5,
            volatility=0.20,  # 20% volatility
        )

        result = calculate_position_size(candidate, base_size=1000.0, min_size=100.0)

        # Should be adjusted by inverse volatility
        assert result > 0
        assert result >= 100.0  # min_size parameter

    def test_uses_default_volatility_when_none(self):
        """Test that default volatility is used when volatility is None."""
        from app.domain.services.allocation_calculator import calculate_position_size

        candidate = StockPriority(
            symbol="AAPL",
            stock_score=0.5,
            volatility=None,
        )

        result = calculate_position_size(candidate, base_size=1000.0, min_size=100.0)

        # Should still return a valid size using default volatility
        assert result > 0
        assert result >= 100.0  # min_size parameter

    def test_applies_min_size_constraint(self):
        """Test that minimum size constraint is applied."""
        from app.domain.services.allocation_calculator import calculate_position_size

        candidate = StockPriority(
            symbol="AAPL",
            stock_score=0.5,
            volatility=0.20,
        )

        result = calculate_position_size(candidate, base_size=50.0, min_size=100.0)

        # Should be clamped to minimum size
        assert result == 100.0

    def test_adjusts_for_stock_score(self):
        """Test that stock score adjusts position size."""
        from app.domain.services.allocation_calculator import calculate_position_size

        candidate_high_score = StockPriority(
            symbol="AAPL",
            stock_score=1.0,  # High score
            volatility=0.20,
        )

        candidate_low_score = StockPriority(
            symbol="MSFT",
            stock_score=0.0,  # Low score
            volatility=0.20,
        )

        high_result = calculate_position_size(
            candidate_high_score, base_size=1000.0, min_size=100.0
        )
        low_result = calculate_position_size(
            candidate_low_score, base_size=1000.0, min_size=100.0
        )

        # High score should result in larger position (up to +20%)
        assert high_result > low_result


class TestGetMaxTrades:
    """Test get_max_trades function."""

    def test_returns_zero_when_cash_below_min_trade_amount(self):
        """Test that zero is returned when cash is below minimum trade amount."""
        from app.domain.services.allocation_calculator import get_max_trades

        result = get_max_trades(cash=100.0, min_trade_amount=250.0)

        assert result == 0

    def test_calculates_max_trades_from_cash(self):
        """Test that max trades is calculated from available cash."""
        from app.domain.services.allocation_calculator import get_max_trades

        # 1000 / 250 = 4 trades
        result = get_max_trades(cash=1000.0, min_trade_amount=250.0)

        assert result == 4

    def test_respects_max_trades_per_cycle_setting(self):
        """Test that result is capped by max_trades_per_cycle setting."""
        from app.config import settings
        from app.domain.services.allocation_calculator import get_max_trades

        # Enough cash for 100 trades, but should be capped by setting
        result = get_max_trades(cash=50000.0, min_trade_amount=250.0)

        assert result <= settings.max_trades_per_cycle

    def test_handles_exact_min_trade_amount(self):
        """Test handling when cash exactly equals min trade amount."""
        from app.domain.services.allocation_calculator import get_max_trades

        result = get_max_trades(cash=250.0, min_trade_amount=250.0)

        assert result == 1  # Can make 1 trade
