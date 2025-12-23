"""Tests for scorer module - validates scoring logic catches edge cases.

These tests verify the scoring engine produces CORRECT outputs, not just
that it runs without errors. Each test identifies a specific bug it would catch.
"""

import pytest
from app.services.scorer import (
    score_total_return,
    calculate_dividend_bonus,
    OPTIMAL_CAGR,
    HIGH_DIVIDEND_THRESHOLD,
    MID_DIVIDEND_THRESHOLD,
)


class TestScoreTotalReturn:
    """Tests for the bell curve CAGR scoring function.

    The scoring system is designed for retirement investing:
    - Peak score at 11% CAGR (optimal for 20-year goal)
    - Lower scores for both underperformance AND excessive volatility/risk
    - Asymmetric curve: steeper penalty for low returns than high

    Bug this catches: If the bell curve math is wrong, the system would
    prioritize wrong stocks (either too risky or too conservative).
    """

    def test_optimal_cagr_gets_maximum_score(self):
        """11% CAGR (the target) should get the highest possible score."""
        score = score_total_return(OPTIMAL_CAGR)
        assert score == pytest.approx(1.0, abs=0.01)

    def test_high_cagr_scores_lower_than_optimal(self):
        """30% CAGR should score LOWER than 11% - high growth often means high risk.

        Bug caught: If this fails, the system would chase risky momentum stocks
        instead of steady compounders.
        """
        optimal_score = score_total_return(0.11)
        high_growth_score = score_total_return(0.30)

        assert optimal_score > high_growth_score
        # 30% gets significantly penalized (intentionally) but still above floor
        assert high_growth_score >= 0.15  # At least floor

    def test_low_cagr_scores_lower_than_optimal(self):
        """5% CAGR should score lower than 11% - underperforming target.

        Bug caught: If this fails, the system would accept mediocre returns.
        """
        optimal_score = score_total_return(0.11)
        low_growth_score = score_total_return(0.05)

        assert optimal_score > low_growth_score

    def test_asymmetric_penalty_low_vs_high(self):
        """Low returns should be penalized MORE than high returns.

        Same distance from optimal (11%):
        - 5% = 6 points below optimal
        - 17% = 6 points above optimal

        5% should score LOWER because underperformance is worse than excess growth.

        Bug caught: If symmetric, system would equally avoid growth stocks
        and value stocks, which is wrong for long-term investing.
        """
        low_return_score = score_total_return(0.05)  # 6% below optimal
        high_return_score = score_total_return(0.17)  # 6% above optimal

        assert high_return_score > low_return_score

    def test_negative_cagr_gets_floor_score(self):
        """Negative returns should get minimum score, not zero.

        Bug caught: If returns 0, a negative CAGR stock would be completely
        excluded even if it might recover. Floor allows consideration.
        """
        score = score_total_return(-0.10)  # -10% annual loss

        assert score == pytest.approx(0.15, abs=0.01)  # Floor value
        assert score > 0  # Never completely excluded

    def test_zero_cagr_gets_floor_score(self):
        """Zero returns should get minimum score."""
        score = score_total_return(0.0)

        assert score == pytest.approx(0.15, abs=0.01)

    def test_very_high_cagr_still_reasonable(self):
        """Even 50% CAGR should get some score, not zero.

        Bug caught: If extreme values crash or return zero, outliers
        would break the scoring system.
        """
        score = score_total_return(0.50)

        assert score >= 0.15  # At least floor
        assert score < 1.0    # Less than optimal

    def test_score_range_is_bounded(self):
        """All scores should be between floor (0.15) and max (1.0).

        Bug caught: Mathematical errors could produce scores outside valid range.
        """
        test_values = [-0.50, -0.10, 0.0, 0.05, 0.11, 0.20, 0.50, 1.0]

        for value in test_values:
            score = score_total_return(value)
            assert 0.15 <= score <= 1.0, f"Score {score} for CAGR {value} out of range"


class TestCalculateDividendBonus:
    """Tests for dividend bonus calculation.

    Dividend-paying stocks get a bonus for DRIP (dividend reinvestment) value.
    The system rewards income generation, especially for retirement.

    Bug this catches: Wrong dividend bonus could cause the system to
    over/under-weight dividend stocks in the portfolio.
    """

    def test_high_dividend_gets_maximum_bonus(self):
        """6%+ yield should get the full 0.10 bonus.

        Bug caught: If high dividends don't get proper bonus, income stocks
        would be underweighted.
        """
        bonus = calculate_dividend_bonus(0.06)
        assert bonus == 0.10

        # Even higher should still be max
        bonus_higher = calculate_dividend_bonus(0.12)
        assert bonus_higher == 0.10

    def test_mid_dividend_gets_medium_bonus(self):
        """3-6% yield should get 0.07 bonus."""
        bonus = calculate_dividend_bonus(0.03)
        assert bonus == 0.07

        bonus_mid = calculate_dividend_bonus(0.05)
        assert bonus_mid == 0.07

    def test_low_dividend_gets_small_bonus(self):
        """Any dividend under 3% should get small 0.03 bonus."""
        bonus = calculate_dividend_bonus(0.01)
        assert bonus == 0.03

        bonus_tiny = calculate_dividend_bonus(0.001)
        assert bonus_tiny == 0.03

    def test_zero_dividend_gets_no_bonus(self):
        """Zero dividend should get no bonus."""
        bonus = calculate_dividend_bonus(0.0)
        assert bonus == 0.0

    def test_none_dividend_gets_no_bonus(self):
        """None dividend (data unavailable) should get no bonus.

        Bug caught: If None crashes or returns wrong value, missing data
        would break scoring.
        """
        bonus = calculate_dividend_bonus(None)
        assert bonus == 0.0

    def test_negative_dividend_gets_no_bonus(self):
        """Negative dividend (data error) should get no bonus.

        Bug caught: Invalid data should be handled gracefully.
        """
        bonus = calculate_dividend_bonus(-0.05)
        assert bonus == 0.0

    def test_bonus_thresholds_are_exclusive(self):
        """Test exact threshold boundaries.

        Bug caught: Off-by-one errors at threshold boundaries.
        """
        # Just below 3% threshold
        bonus_below_mid = calculate_dividend_bonus(0.0299)
        assert bonus_below_mid == 0.03

        # Exactly at 3% threshold
        bonus_at_mid = calculate_dividend_bonus(0.03)
        assert bonus_at_mid == 0.07

        # Just below 6% threshold
        bonus_below_high = calculate_dividend_bonus(0.0599)
        assert bonus_below_high == 0.07

        # Exactly at 6% threshold
        bonus_at_high = calculate_dividend_bonus(0.06)
        assert bonus_at_high == 0.10
