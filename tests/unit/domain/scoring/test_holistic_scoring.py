"""Tests for holistic scoring modules - validates end-state and windfall logic.

These tests ensure the holistic planner makes CORRECT decisions about:
- Total return scoring (CAGR + dividends)
- Windfall detection (excess gains vs expected)
- Dividend stability
- End-state portfolio evaluation
"""


import pytest

from app.domain.scoring.constants import (
    CONSISTENT_DOUBLE_SELL_PCT,
    WINDFALL_SELL_PCT_HIGH,
    WINDFALL_SELL_PCT_MEDIUM,
)
from app.domain.scoring.dividend_history import (
    calculate_dividend_growth_rate,
    calculate_dividend_stability_score,
    has_big_dividend_cut,
)
from app.domain.scoring.end_state import (
    score_total_return,
)
from app.domain.scoring.windfall import (
    calculate_excess_gain,
    should_take_profits,
)


class TestScoreTotalReturn:
    """Tests for total return scoring (CAGR + dividend yield).

    The system should:
    - Score highest around 11-13% total return (optimal zone)
    - Penalize very low returns
    - Slightly penalize extremely high returns (sustainability concerns)
    """

    def test_optimal_return_gets_highest_score(self):
        """12% total return (target) should get near-maximum score.

        Bug caught: If optimal returns don't score high, system would
        not prioritize the best stocks.
        """
        score = score_total_return(0.12, target=0.12)
        assert score >= 0.95  # Near maximum

    def test_zero_return_gets_minimum_score(self):
        """0% return should get minimum score.

        Bug caught: Zero return stocks shouldn't be prioritized.
        """
        score = score_total_return(0.0)
        assert score == pytest.approx(0.15, abs=0.05)  # Floor value

    def test_negative_return_gets_minimum_score(self):
        """Negative return should get minimum score.

        Bug caught: Losing stocks should not be scored well.
        """
        score = score_total_return(-0.05)
        assert score == pytest.approx(0.15, abs=0.05)

    def test_moderate_return_gets_good_score(self):
        """8% return should get good (but not max) score.

        Bug caught: Decent performers should still score well.
        """
        score = score_total_return(0.08, target=0.12)
        assert 0.6 < score < 0.95

    def test_high_return_still_scores_well(self):
        """20% return should still score well (but not max).

        Bug caught: High performers should not be penalized too much.
        """
        score = score_total_return(0.20, target=0.12)
        assert score > 0.6

    def test_very_high_return_gets_moderate_score(self):
        """30%+ return gets lower score (sustainability concern).

        Bug caught: Extremely high returns may be unsustainable.
        """
        score_30 = score_total_return(0.30, target=0.12)
        score_12 = score_total_return(0.12, target=0.12)
        assert score_30 < score_12  # 30% scores lower than optimal


class TestCalculateExcessGain:
    """Tests for windfall detection via excess gain calculation.

    Excess gain = actual gain - expected gain (based on historical CAGR).
    The system should correctly identify:
    - Consistent growers (low excess)
    - Windfalls (high excess)
    """

    def test_consistent_grower_has_low_excess(self):
        """Stock growing at its historical rate should have ~0 excess.

        Bug caught: Consistent growers shouldn't be flagged as windfalls.

        Example: Stock with 10% CAGR, held 3 years, up 33%
        Expected: (1.10^3) - 1 = 33.1%
        Excess: 33% - 33.1% = ~0%
        """
        excess = calculate_excess_gain(
            current_gain=0.331,  # 33.1% gain
            years_held=3.0,
            historical_cagr=0.10,  # 10% historical growth
        )
        assert abs(excess) < 0.02  # Near zero excess

    def test_windfall_has_high_excess(self):
        """Stock spiking far above historical growth should have high excess.

        Bug caught: Windfalls should be clearly identified.

        Example: Stock with 10% CAGR, held 1 year, up 80%
        Expected: 10%
        Excess: 80% - 10% = 70%
        """
        excess = calculate_excess_gain(
            current_gain=0.80,  # 80% gain
            years_held=1.0,
            historical_cagr=0.10,  # 10% historical growth
        )
        assert excess == pytest.approx(0.70, abs=0.01)

    def test_underperformer_has_negative_excess(self):
        """Stock growing slower than historical rate has negative excess.

        Bug caught: Underperformers should not trigger profit-taking.
        """
        excess = calculate_excess_gain(
            current_gain=0.05,  # Only 5% gain
            years_held=1.0,
            historical_cagr=0.15,  # Usually grows 15%
        )
        assert excess < 0  # Negative excess

    def test_zero_years_held_returns_full_gain_as_excess(self):
        """With no history, all gain is considered excess.

        Bug caught: Edge case handling for new positions.
        """
        excess = calculate_excess_gain(
            current_gain=0.50,
            years_held=0.0,
            historical_cagr=0.10,
        )
        assert excess == 0.50

    def test_negative_cagr_handled_gracefully(self):
        """Negative historical CAGR should not crash.

        Bug caught: Bad data handling.
        """
        excess = calculate_excess_gain(
            current_gain=0.20,
            years_held=1.0,
            historical_cagr=-0.05,  # Declining stock
        )
        # Should calculate expected = (0.95^1) - 1 = -0.05
        # Excess = 0.20 - (-0.05) = 0.25
        assert excess == pytest.approx(0.25, abs=0.01)


class TestShouldTakeProfits:
    """Tests for profit-taking decision logic.

    The system should:
    - Take profits on windfalls
    - Partially trim consistent doublers
    - NOT sell consistent growers at ATH
    """

    def test_windfall_doubler_sells_50_percent(self):
        """Doubled money with windfall component should sell 50%.

        Bug caught: Large windfalls should be harvested aggressively.
        """
        should_sell, pct, reason = should_take_profits(
            current_gain=1.20,  # 120% gain (more than doubled)
            years_held=1.0,
            historical_cagr=0.10,  # Expected only 10%
        )
        assert should_sell is True
        assert pct == 0.50
        assert "windfall" in reason.lower()

    def test_consistent_doubler_sells_30_percent(self):
        """Doubled money via consistent growth should sell only 30%.

        Bug caught: Don't over-trim consistent growers.

        Example: 25% CAGR over 3 years = (1.25^3) - 1 = 95% expected
        If actual is 100%, excess is only 5% - consistent doubler
        """
        should_sell, pct, reason = should_take_profits(
            current_gain=1.00,  # Exactly doubled (100% gain)
            years_held=3.0,
            historical_cagr=0.25,  # Expected ~95%
        )
        assert should_sell is True
        assert pct == CONSISTENT_DOUBLE_SELL_PCT  # 30%
        assert "consistent" in reason.lower()

    def test_high_windfall_sells_40_percent(self):
        """50%+ excess gain (not doubled) should sell 40%.

        Bug caught: Large excess should trigger profit-taking.
        """
        should_sell, pct, reason = should_take_profits(
            current_gain=0.70,  # 70% gain
            years_held=1.0,
            historical_cagr=0.10,  # Expected 10%, excess = 60%
        )
        assert should_sell is True
        assert pct == WINDFALL_SELL_PCT_HIGH  # 40%

    def test_medium_windfall_sells_20_percent(self):
        """25-50% excess gain should sell 20%.

        Bug caught: Moderate excess should trigger moderate profit-taking.
        """
        should_sell, pct, reason = should_take_profits(
            current_gain=0.45,  # 45% gain
            years_held=1.0,
            historical_cagr=0.10,  # Expected 10%, excess = 35%
        )
        assert should_sell is True
        assert pct == WINDFALL_SELL_PCT_MEDIUM  # 20%

    def test_consistent_grower_at_ath_does_not_sell(self):
        """Consistent grower at ATH should NOT trigger profit-taking.

        Bug caught: System should not sell consistent performers just
        because they're at all-time high. If a stock grows 10%/year
        consistently, every year will be its highest year!
        """
        should_sell, pct, reason = should_take_profits(
            current_gain=0.33,  # 33% gain over 3 years
            years_held=3.0,
            historical_cagr=0.10,  # Expected ~33% - right on track
        )
        assert should_sell is False
        assert pct == 0.0

    def test_underperformer_does_not_trigger_profit_taking(self):
        """Stocks below expected growth should not trigger profit-taking.

        Bug caught: Don't sell underperformers via windfall logic.
        """
        should_sell, pct, reason = should_take_profits(
            current_gain=0.05,  # Only 5% gain
            years_held=1.0,
            historical_cagr=0.15,  # Expected 15%
        )
        assert should_sell is False
        assert "underperforming" in reason.lower() or "expectations" in reason.lower()


class TestHasBigDividendCut:
    """Tests for dividend cut detection.

    The system should:
    - Detect >20% year-over-year cuts
    - Track how long ago the cut happened
    - Handle edge cases gracefully
    """

    def test_detects_big_cut(self):
        """25% dividend cut should be flagged.

        Bug caught: Big cuts indicate trouble and should be tracked.
        """
        history = [1.00, 1.00, 0.70]  # Cut from 1.00 to 0.70 (30% cut)
        has_cut, years_since = has_big_dividend_cut(history)

        assert has_cut is True
        assert years_since == 1  # Cut detected in most recent period

    def test_ignores_small_cut(self):
        """15% cut should not be flagged (below 20% threshold).

        Bug caught: Small fluctuations shouldn't penalize a stock.
        """
        history = [1.00, 0.90, 0.85]  # 10% cut, then 5.5% cut
        has_cut, years_since = has_big_dividend_cut(history)

        assert has_cut is False

    def test_tracks_years_since_cut(self):
        """Old cuts should have higher years_since value.

        Bug caught: Recent cuts are worse than old cuts.
        """
        history = [1.00, 0.70, 0.70, 0.70]  # Cut 3 years ago
        has_cut, years_since = has_big_dividend_cut(history)

        assert has_cut is True
        assert years_since == 3

    def test_handles_short_history(self):
        """Single-year history should return False.

        Bug caught: Can't detect cuts with no comparison.
        """
        has_cut, years_since = has_big_dividend_cut([1.00])
        assert has_cut is False
        assert years_since is None

    def test_handles_empty_history(self):
        """Empty history should not crash.

        Bug caught: Edge case handling.
        """
        has_cut, years_since = has_big_dividend_cut([])
        assert has_cut is False

    def test_handles_zero_dividend(self):
        """Zero previous dividend should not cause division error.

        Bug caught: Division by zero.
        """
        history = [0.0, 0.50, 0.50]  # Started paying dividends
        has_cut, years_since = has_big_dividend_cut(history)
        # First year had 0, so no "cut" from it
        assert has_cut is False


class TestCalculateDividendGrowthRate:
    """Tests for dividend growth rate calculation."""

    def test_calculates_positive_growth(self):
        """Growing dividends should return positive CAGR.

        Bug caught: Growth rate calculation errors.
        """
        history = [1.00, 1.10, 1.21]  # 10% growth per year
        cagr = calculate_dividend_growth_rate(history)

        assert cagr == pytest.approx(0.10, abs=0.01)

    def test_calculates_negative_growth(self):
        """Declining dividends should return negative CAGR.

        Bug caught: Must handle declining dividends.
        """
        history = [1.00, 0.90, 0.81]  # -10% per year
        cagr = calculate_dividend_growth_rate(history)

        assert cagr == pytest.approx(-0.10, abs=0.01)

    def test_returns_none_for_short_history(self):
        """Single value should return None.

        Bug caught: Can't calculate rate with one data point.
        """
        cagr = calculate_dividend_growth_rate([1.00])
        assert cagr is None

    def test_skips_leading_zeros(self):
        """Should skip years with zero dividends at start.

        Bug caught: New dividend payers shouldn't break calculation.
        """
        history = [0.0, 0.0, 1.00, 1.10]  # Started paying 2 years ago
        cagr = calculate_dividend_growth_rate(history)

        assert cagr == pytest.approx(0.10, abs=0.01)


class TestCalculateDividendStabilityScore:
    """Tests for overall dividend stability scoring."""

    def test_no_cuts_and_growth_gets_high_score(self):
        """Stable, growing dividends should score high.

        Bug caught: Good dividend stocks should be recognized.
        """
        history = [1.00, 1.05, 1.10, 1.15, 1.20]  # 5% growth, no cuts
        score, details = calculate_dividend_stability_score(
            dividend_history=history,
            portfolio_avg_yield=0.03,
            current_yield=0.05,  # Above average
        )

        assert score >= 0.7
        assert details["has_big_cut"] is False
        assert details["above_portfolio_avg"] is True

    def test_recent_cut_gets_low_score(self):
        """Recent dividend cut should significantly lower score.

        Bug caught: Recent cuts indicate trouble.
        """
        history = [1.00, 1.00, 0.70]  # 30% cut in most recent year
        score, details = calculate_dividend_stability_score(
            dividend_history=history,
            portfolio_avg_yield=0.03,
            current_yield=0.02,
        )

        assert score < 0.5
        assert details["has_big_cut"] is True

    def test_old_cut_has_less_penalty(self):
        """Old dividend cut should have smaller penalty.

        Bug caught: Recovery from old cuts should be recognized.
        """
        # Cut 5 years ago, stable since
        history = [1.00, 0.70, 0.70, 0.70, 0.70, 0.70]
        score_old, _ = calculate_dividend_stability_score(
            dividend_history=history,
            portfolio_avg_yield=0.03,
        )

        # Cut in most recent year
        history_recent = [1.00, 1.00, 0.70]
        score_recent, _ = calculate_dividend_stability_score(
            dividend_history=history_recent,
            portfolio_avg_yield=0.03,
        )

        assert score_old > score_recent

    def test_above_average_yield_gets_bonus(self):
        """Yield above portfolio average should boost score.

        Bug caught: High yielders should be valued for income.
        """
        history = [1.00, 1.00, 1.00]  # Stable

        score_above, details_above = calculate_dividend_stability_score(
            dividend_history=history,
            portfolio_avg_yield=0.03,
            current_yield=0.06,  # 2x average
        )

        score_below, details_below = calculate_dividend_stability_score(
            dividend_history=history,
            portfolio_avg_yield=0.03,
            current_yield=0.02,  # Below average
        )

        assert score_above > score_below
        assert details_above["above_portfolio_avg"] is True
        assert details_below["above_portfolio_avg"] is False
