"""Tests for allocator module - validates position sizing logic.

These tests ensure trade sizes are calculated correctly. Wrong position
sizes could lead to over-concentrated positions or wasted cash.
"""

from app.domain.constants import MAX_VOL_WEIGHT, MIN_VOL_WEIGHT
from app.domain.models import SecurityPriority
from app.domain.services.allocation_calculator import (
    calculate_position_size,
    get_max_trades,
    parse_industries,
)


class TestCalculatePositionSize:
    """Tests for position size calculation.

    Position sizing uses risk parity (inverse volatility weighting):
    - Volatility: Low vol securities get larger positions (up to 2x), high vol get smaller (down to 0.5x)
    - Score adjustment: ±10% based on security score

    Bug this catches: Wrong position sizes could cause overexposure
    to risky securities or underinvestment in good opportunities.
    """

    def _make_candidate(
        self,
        score: float = 0.7,
        priority: float = 1.0,
        volatility: float = 0.20,
    ) -> SecurityPriority:
        """Helper to create test candidates."""
        return SecurityPriority(
            symbol="TEST",
            name="Test Security",
            country="United States",
            industry="Consumer Electronics",
            security_score=score,
            volatility=volatility,
            multiplier=1.0,
            min_lot=1,
            combined_priority=priority,
        )

    def test_high_score_gets_larger_position(self):
        """High security score should result in larger position (±20% adjustment).

        Bug caught: If score doesn't affect size, all trades would
        be the same size regardless of conviction.
        """
        base = 1000
        min_size = 100
        vol = 0.20  # Same volatility for fair comparison

        low_score = self._make_candidate(score=0.3, volatility=vol)
        high_score = self._make_candidate(score=0.9, volatility=vol)

        low_size = calculate_position_size(low_score, base, min_size)
        high_size = calculate_position_size(high_score, base, min_size)

        # High score should get larger position (score adjustment ±20%)
        assert high_size > low_size
        # Difference should reflect ~40% range (±20%)
        assert (high_size - low_size) / base < 0.35

    def test_high_volatility_reduces_position(self):
        """High volatility should reduce position size (risk parity).

        Bug caught: If volatility isn't considered, system would
        take same-sized bets on stable and volatile securities.
        """
        base = 1000
        min_size = 100

        low_vol = self._make_candidate(
            volatility=0.10
        )  # 10% annual vol -> larger position
        high_vol = self._make_candidate(
            volatility=0.30
        )  # 30% annual vol -> smaller position

        low_vol_size = calculate_position_size(low_vol, base, min_size)
        high_vol_size = calculate_position_size(high_vol, base, min_size)

        # Low vol should get significantly larger position (risk parity)
        assert low_vol_size > high_vol_size
        # Low vol (10%) should get close to 2x base (15%/10% = 1.5x, capped at 2x)
        assert low_vol_size >= base * 1.4
        # High vol (30%) should get around 0.5x base (15%/30% = 0.5x)
        assert high_vol_size <= base * 0.6

    def test_none_volatility_uses_default(self):
        """None volatility should use default volatility (0.20).

        Bug caught: Missing data shouldn't break calculations.
        """
        base = 1000
        min_size = 100

        no_vol = self._make_candidate(volatility=None)

        size = calculate_position_size(no_vol, base, min_size)

        # Should use default volatility (0.20), so vol_weight = 15%/20% = 0.75x
        assert size >= min_size
        assert size <= base * MAX_VOL_WEIGHT

    def test_never_exceeds_maximum(self):
        """Position should never exceed MAX_VOL_WEIGHT * base * max_score_adj.

        Bug caught: Unbounded position sizes could cause over-concentration.
        """
        base = 1000
        min_size = 100

        # Perfect security: high score, very low vol (gets max vol weight)
        perfect = self._make_candidate(
            score=1.0, volatility=0.05
        )  # 5% vol -> max weight

        size = calculate_position_size(perfect, base, min_size)

        # Max is: vol_weight (2.0x clamped) * score_adj (1.2 for score=1.0)
        max_allowed = base * MAX_VOL_WEIGHT * 1.2  # 2.0x * 1.2 = 2.4x
        assert size <= max_allowed

    def test_never_below_minimum(self):
        """Position should never be below min_size.

        Bug caught: Tiny positions would waste trading fees.
        """
        base = 1000
        min_size = 200

        # Terrible security: low score, very high vol
        terrible = self._make_candidate(
            score=0.1, volatility=0.60
        )  # 60% vol -> min weight

        size = calculate_position_size(terrible, base, min_size)

        assert size >= min_size

    def test_score_adjustment_is_bounded(self):
        """Score adjustment is ±20% on top of volatility weighting.

        Bug caught: Misunderstanding the scoring scale could cause wrong positions.
        """
        base = 1000
        min_size = 100
        vol = 0.20  # Same volatility for fair comparison

        # Score 0.5 = neutral (no adjustment)
        neutral_score = self._make_candidate(score=0.5, volatility=vol)
        # Score 1.0 = +20% adjustment
        high_score = self._make_candidate(score=1.0, volatility=vol)

        neutral_result = calculate_position_size(neutral_score, base, min_size)
        high_result = calculate_position_size(high_score, base, min_size)

        # High score should get larger position
        assert high_result > neutral_result
        # Difference should be ~20% (score adjustment)
        assert (high_result - neutral_result) / neutral_result < 0.25

    def test_extreme_volatility_respects_floor(self):
        """Even extreme volatility should not reduce below MIN_VOL_WEIGHT.

        Bug caught: Extreme volatility causing near-zero positions.
        """
        base = 1000
        min_size = 100

        extreme = self._make_candidate(volatility=1.0)  # 100% annual vol

        size = calculate_position_size(extreme, base, min_size)

        # Should respect both volatility floor (MIN_VOL_WEIGHT = 0.5x) and min_size
        assert size >= min_size
        assert size >= base * MIN_VOL_WEIGHT


class TestParseIndustries:
    """Tests for industry string parsing.

    Stocks can belong to multiple industries (comma-separated).
    Parsing must handle various edge cases.
    """

    def test_single_industry(self):
        """Single industry should return list with one element."""
        result = parse_industries("Consumer Electronics")
        assert result == ["Consumer Electronics"]

    def test_multiple_industries(self):
        """Comma-separated industries should be split and trimmed."""
        result = parse_industries("Industrial, Defense, Aerospace")
        assert result == ["Industrial", "Defense", "Aerospace"]

    def test_extra_whitespace_is_trimmed(self):
        """Whitespace around industry names should be removed.

        Bug caught: Whitespace causing mismatches in lookups.
        """
        result = parse_industries("  Technology  ,  Finance  ")
        assert result == ["Technology", "Finance"]

    def test_empty_string_returns_empty_list(self):
        """Empty string should return empty list.

        Bug caught: Empty string causing errors downstream.
        """
        result = parse_industries("")
        assert result == []

    def test_none_returns_empty_list(self):
        """None should return empty list.

        Bug caught: NoneType has no attribute 'split'.
        """
        result = parse_industries(None)
        assert result == []

    def test_trailing_comma_ignored(self):
        """Trailing comma should not create empty element.

        Bug caught: Empty string in list causing issues.
        """
        result = parse_industries("Tech, Finance,")
        assert result == ["Tech", "Finance"]
        assert "" not in result

    def test_multiple_commas_ignored(self):
        """Multiple commas should not create empty elements."""
        result = parse_industries("Tech,,Finance")
        assert result == ["Tech", "Finance"]
        assert "" not in result


class TestGetMaxTrades:
    """Tests for max trades calculation.

    Limits how many trades can happen based on available cash.
    """

    def test_zero_cash_returns_zero(self):
        """No cash means no trades.

        Bug caught: Trying to trade with no money.
        """
        result = get_max_trades(0)
        assert result == 0

    def test_insufficient_cash_returns_zero(self):
        """Cash below min_trade_size should return zero.

        Bug caught: Attempting trades that are too small.
        """
        # Assuming min_trade_size is typically 100-300
        result = get_max_trades(50)
        assert result == 0

    def test_negative_cash_returns_zero(self):
        """Negative cash (margin?) should return zero.

        Bug caught: Invalid cash values.
        """
        result = get_max_trades(-1000)
        assert result == 0
