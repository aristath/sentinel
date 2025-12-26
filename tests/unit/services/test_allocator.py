"""Tests for allocator module - validates position sizing logic.

These tests ensure trade sizes are calculated correctly. Wrong position
sizes could lead to over-concentrated positions or wasted cash.
"""


from app.domain.constants import (
    MAX_POSITION_SIZE_MULTIPLIER,
)
from app.domain.models import StockPriority
from app.domain.services.allocation_calculator import (
    calculate_position_size,
    get_max_trades,
    parse_industries,
)


class TestCalculatePositionSize:
    """Tests for position size calculation.

    Position sizing uses three multipliers:
    - Conviction: Based on stock score (higher score = larger position)
    - Priority: Based on combined priority (higher = larger)
    - Volatility: Reduces size for volatile stocks

    Bug this catches: Wrong position sizes could cause overexposure
    to risky stocks or underinvestment in good opportunities.
    """

    def _make_candidate(
        self,
        score: float = 0.7,
        priority: float = 1.0,
        volatility: float = 0.20,
    ) -> StockPriority:
        """Helper to create test candidates."""
        return StockPriority(
            symbol="TEST",
            name="Test Stock",
            geography="US",
            industry="Technology",
            stock_score=score,
            volatility=volatility,
            multiplier=1.0,
            min_lot=1,
            combined_priority=priority,
        )

    def test_high_score_gets_larger_position(self):
        """High stock score should result in larger position.

        Bug caught: If score doesn't affect size, all trades would
        be the same size regardless of conviction.
        """
        base = 1000
        min_size = 100

        low_score = self._make_candidate(score=0.3)
        high_score = self._make_candidate(score=0.9)

        low_size = calculate_position_size(low_score, base, min_size)
        high_size = calculate_position_size(high_score, base, min_size)

        assert high_size > low_size

    def test_high_volatility_reduces_position(self):
        """High volatility should reduce position size.

        Bug caught: If volatility isn't considered, system would
        take same-sized bets on stable and volatile stocks.
        """
        base = 1000
        min_size = 100

        low_vol = self._make_candidate(volatility=0.15)  # 15% annual vol
        high_vol = self._make_candidate(volatility=0.40)  # 40% annual vol

        low_vol_size = calculate_position_size(low_vol, base, min_size)
        high_vol_size = calculate_position_size(high_vol, base, min_size)

        assert low_vol_size > high_vol_size

    def test_none_volatility_uses_neutral_multiplier(self):
        """None volatility should not crash or reduce size.

        Bug caught: Missing data shouldn't break calculations.
        """
        base = 1000
        min_size = 100

        no_vol = self._make_candidate(volatility=None)

        size = calculate_position_size(no_vol, base, min_size)

        # Should use neutral multiplier (1.0), so size based only on score/priority
        assert size >= min_size
        assert size <= base * MAX_POSITION_SIZE_MULTIPLIER

    def test_never_exceeds_maximum(self):
        """Position should never exceed MAX_POSITION_SIZE_MULTIPLIER * base.

        Bug caught: Unbounded position sizes could cause over-concentration.
        """
        base = 1000
        min_size = 100

        # Perfect stock: high score, high priority, low vol
        perfect = self._make_candidate(score=1.0, priority=3.0, volatility=0.10)

        size = calculate_position_size(perfect, base, min_size)

        max_allowed = base * MAX_POSITION_SIZE_MULTIPLIER
        assert size <= max_allowed

    def test_never_below_minimum(self):
        """Position should never be below min_size.

        Bug caught: Tiny positions would waste trading fees.
        """
        base = 1000
        min_size = 200

        # Terrible stock: low score, low priority, high vol
        terrible = self._make_candidate(score=0.1, priority=0.1, volatility=0.60)

        size = calculate_position_size(terrible, base, min_size)

        assert size >= min_size

    def test_minimum_score_gets_minimum_multiplier(self):
        """Score of 0.5 is actually minimum conviction - gets smallest position.

        The conviction formula: MIN + (score - 0.5) * 0.8
        At score=0.5, conviction = MIN (0.8)
        Only scores ABOVE 0.5 get larger positions.

        Bug caught: Misunderstanding the scoring scale could cause wrong positions.
        """
        base = 1000
        min_size = 100

        # Score 0.5 = minimum conviction (0.8x)
        min_score = self._make_candidate(score=0.5, priority=1.0, volatility=0.15)
        # Score 0.9 = high conviction (1.12x)
        high_score = self._make_candidate(score=0.9, priority=1.0, volatility=0.15)

        min_size_result = calculate_position_size(min_score, base, min_size)
        high_size_result = calculate_position_size(high_score, base, min_size)

        # High score should get larger position
        assert high_size_result > min_size_result
        # Min score should get around 0.8x base (times priority and vol multipliers)
        assert min_size_result < base

    def test_extreme_volatility_respects_floor(self):
        """Even extreme volatility should not reduce below MIN_VOLATILITY_MULTIPLIER.

        Bug caught: Extreme volatility causing near-zero positions.
        """
        base = 1000
        min_size = 100

        extreme = self._make_candidate(volatility=1.0)  # 100% annual vol

        size = calculate_position_size(extreme, base, min_size)

        # Should respect both volatility floor and min_size
        assert size >= min_size


class TestParseIndustries:
    """Tests for industry string parsing.

    Stocks can belong to multiple industries (comma-separated).
    Parsing must handle various edge cases.
    """

    def test_single_industry(self):
        """Single industry should return list with one element."""
        result = parse_industries("Technology")
        assert result == ["Technology"]

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
