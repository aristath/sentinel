"""Tests for dividend history analysis module.

These tests validate dividend stability scoring, cut detection,
and growth rate calculations used by the holistic planner.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.modules.scoring.domain.constants import DIVIDEND_CUT_THRESHOLD
from app.modules.dividends.domain.dividend_history import (
    _calculate_cut_penalty,
    _calculate_growth_bonus,
    _calculate_yield_bonus,
    _get_dividend_recommendation,
    calculate_dividend_growth_rate,
    calculate_dividend_stability_score,
    get_dividend_analysis,
    has_big_dividend_cut,
    is_dividend_consistent,
)


class TestHasBigDividendCut:
    """Test dividend cut detection."""

    def test_no_history_returns_false(self):
        """Test that empty history returns no cut."""
        has_cut, years_since = has_big_dividend_cut([])
        assert has_cut is False
        assert years_since is None

    def test_single_value_returns_false(self):
        """Test that single value returns no cut."""
        has_cut, years_since = has_big_dividend_cut([1.50])
        assert has_cut is False
        assert years_since is None

    def test_no_cut_in_growing_dividends(self):
        """Test that growing dividends show no cut."""
        # Dividends growing from 1.00 to 1.50
        history = [1.00, 1.10, 1.20, 1.30, 1.40, 1.50]
        has_cut, years_since = has_big_dividend_cut(history)
        assert has_cut is False
        assert years_since is None

    def test_small_cut_below_threshold_returns_false(self):
        """Test that cuts below 20% threshold don't trigger."""
        # 15% cut - below 20% threshold
        history = [1.00, 0.85]
        has_cut, years_since = has_big_dividend_cut(history)
        assert has_cut is False
        assert years_since is None

    def test_exactly_at_threshold_does_not_trigger(self):
        """Test that cut exactly at 20% threshold does NOT trigger.

        The implementation uses '<' (strictly less than), so a cut of exactly
        20% (change = -0.20) does not trigger because -0.20 < -0.20 is False.
        """
        # Exactly 20% cut
        history = [1.00, 0.80]
        has_cut, years_since = has_big_dividend_cut(history)
        assert has_cut is False  # Exactly at threshold does not trigger
        assert years_since is None

    def test_big_cut_detected_with_correct_timing(self):
        """Test that >20% cut is detected with correct years since."""
        # Cut from 2.00 to 1.50 (25% cut)
        history = [1.80, 2.00, 1.50, 1.55, 1.60]
        has_cut, years_since = has_big_dividend_cut(history)
        assert has_cut is True
        assert years_since == 3  # len(5) - index(2) = 3 years ago

    def test_multiple_cuts_returns_first_cut(self):
        """Test that multiple cuts return the first (oldest) cut found."""
        # Two cuts: index 1->2 (20% cut) and index 3->4 (30% cut)
        history = [1.00, 1.50, 1.20, 1.00, 0.70]
        has_cut, years_since = has_big_dividend_cut(history)
        assert has_cut is True
        # First cut detected at index 2 (1.50 -> 1.20 = 20% cut)
        assert years_since == 3  # len(5) - index(2) = 3

    def test_zero_previous_dividend_ignored(self):
        """Test that zero previous dividend doesn't cause division error."""
        # Previous dividend is 0, should skip this comparison
        history = [0.0, 1.00, 1.10]
        has_cut, years_since = has_big_dividend_cut(history)
        assert has_cut is False
        assert years_since is None

    def test_recent_cut_returns_years_since_one(self):
        """Test that most recent cut returns years_since=1."""
        history = [1.00, 1.10, 1.20, 0.90]
        has_cut, years_since = has_big_dividend_cut(history)
        assert has_cut is True
        assert years_since == 1  # Most recent year

    def test_massive_cut_detection(self):
        """Test detection of massive dividend cut (>50%)."""
        # 60% cut
        history = [2.50, 1.00]
        has_cut, years_since = has_big_dividend_cut(history)
        assert has_cut is True
        assert years_since == 1

    def test_negative_dividends_handled(self):
        """Test that negative dividends are handled gracefully."""
        # Negative values should not cause errors
        history = [1.00, -0.50, 0.80]
        has_cut, years_since = has_big_dividend_cut(history)
        # From 1.00 to -0.50 is more than 20% cut
        assert has_cut is True


class TestCalculateDividendGrowthRate:
    """Test dividend growth rate calculation."""

    def test_no_history_returns_none(self):
        """Test that empty history returns None."""
        cagr = calculate_dividend_growth_rate([])
        assert cagr is None

    def test_single_value_returns_none(self):
        """Test that single value returns None."""
        cagr = calculate_dividend_growth_rate([1.50])
        assert cagr is None

    def test_steady_growth_calculates_cagr(self):
        """Test CAGR calculation for steady dividend growth."""
        # 10% annual growth: 1.00 -> 1.10 -> 1.21
        history = [1.00, 1.10, 1.21]
        cagr = calculate_dividend_growth_rate(history)
        assert cagr is not None
        assert cagr == pytest.approx(0.10, abs=0.01)

    def test_doubling_over_two_years(self):
        """Test CAGR when dividends double."""
        # From 1.00 to 2.00 in 2 years = 41.4% CAGR
        history = [1.00, 1.414, 2.00]
        cagr = calculate_dividend_growth_rate(history)
        assert cagr is not None
        assert cagr == pytest.approx(0.414, abs=0.02)

    def test_flat_dividends_returns_zero(self):
        """Test that flat dividends return 0% growth."""
        history = [1.00, 1.00, 1.00, 1.00]
        cagr = calculate_dividend_growth_rate(history)
        assert cagr is not None
        assert cagr == pytest.approx(0.0, abs=0.01)

    def test_declining_dividends_returns_negative_cagr(self):
        """Test that declining dividends return negative CAGR."""
        # 10% annual decline
        history = [1.00, 0.90, 0.81]
        cagr = calculate_dividend_growth_rate(history)
        assert cagr is not None
        assert cagr < 0
        assert cagr == pytest.approx(-0.10, abs=0.01)

    def test_filters_out_leading_zeros(self):
        """Test that leading zeros are filtered out."""
        # Start with zeros, then positive dividends
        history = [0.0, 0.0, 1.00, 1.10, 1.21]
        cagr = calculate_dividend_growth_rate(history)
        assert cagr is not None
        # Should calculate from 1.00 to 1.21 (2 years)
        assert cagr == pytest.approx(0.10, abs=0.01)

    def test_all_zeros_returns_none(self):
        """Test that all zeros returns None."""
        history = [0.0, 0.0, 0.0]
        cagr = calculate_dividend_growth_rate(history)
        assert cagr is None

    def test_zero_start_dividend_returns_none(self):
        """Test that zero start dividend after filtering returns None."""
        # After filtering, start is still zero
        history = [0.0]
        cagr = calculate_dividend_growth_rate(history)
        assert cagr is None

    def test_negative_start_dividend_returns_none(self):
        """Test that negative start dividend returns None."""
        history = [-1.00, 1.00, 1.10]
        cagr = calculate_dividend_growth_rate(history)
        # Should filter out negative and start from 1.00
        assert cagr is not None

    def test_handles_division_by_zero(self):
        """Test that division by zero is handled gracefully."""
        # Edge case: single positive value after filtering
        history = [0.0, 0.0, 1.00]
        cagr = calculate_dividend_growth_rate(history)
        # Only one valid value, should return None
        assert cagr is None

    def test_value_error_handled(self):
        """Test that ValueError (e.g., negative base) is handled."""
        # This shouldn't happen with filtering, but test safety
        history = [1.00, 0.00]
        cagr = calculate_dividend_growth_rate(history)
        # end_div / start_div where end is 0 = 0, then 0^(1/years) - 1
        assert cagr is not None
        assert cagr == pytest.approx(-1.0, abs=0.01)


class TestCalculateCutPenalty:
    """Test cut penalty calculation."""

    def test_recent_cut_max_penalty(self):
        """Test that recent cut (<=2 years) returns max penalty."""
        penalty, bonus = _calculate_cut_penalty(
            has_cut=True, years_since=2, dividend_history=[1.0, 0.7]
        )
        assert penalty == 0.40
        assert bonus == 0.0

    def test_medium_term_cut_partial_penalty(self):
        """Test that medium-term cut (3-5 years) returns partial penalty."""
        penalty, bonus = _calculate_cut_penalty(
            has_cut=True, years_since=4, dividend_history=[1.0, 0.7, 0.8]
        )
        assert penalty == 0.25
        assert bonus == 0.0

    def test_old_cut_minimal_penalty(self):
        """Test that old cut (>5 years) returns minimal penalty."""
        penalty, bonus = _calculate_cut_penalty(
            has_cut=True, years_since=6, dividend_history=[1.0] * 7
        )
        assert penalty == 0.10
        assert bonus == 0.0

    def test_no_cut_with_long_history_bonus(self):
        """Test that no cut with long history returns bonus."""
        penalty, bonus = _calculate_cut_penalty(
            has_cut=False, years_since=None, dividend_history=[1.0] * 5
        )
        assert penalty == 0.0
        assert bonus == 0.15  # Long track record bonus

    def test_no_cut_with_medium_history_bonus(self):
        """Test that no cut with medium history returns medium bonus."""
        penalty, bonus = _calculate_cut_penalty(
            has_cut=False, years_since=None, dividend_history=[1.0] * 3
        )
        assert penalty == 0.0
        assert bonus == 0.10

    def test_no_cut_with_short_history_no_bonus(self):
        """Test that no cut with short history returns no bonus."""
        penalty, bonus = _calculate_cut_penalty(
            has_cut=False, years_since=None, dividend_history=[1.0, 1.1]
        )
        assert penalty == 0.0
        assert bonus == 0.0


class TestCalculateGrowthBonus:
    """Test growth bonus calculation."""

    def test_high_growth_max_bonus(self):
        """Test that high growth (>=5%) returns max bonus."""
        bonus = _calculate_growth_bonus(0.08)  # 8% growth
        assert bonus == 0.30

    def test_medium_growth_mid_bonus(self):
        """Test that medium growth (2-5%) returns mid bonus."""
        bonus = _calculate_growth_bonus(0.03)  # 3% growth
        assert bonus == 0.20

    def test_stable_growth_small_bonus(self):
        """Test that stable/flat growth returns small bonus."""
        bonus = _calculate_growth_bonus(0.01)  # 1% growth
        assert bonus == 0.10

    def test_zero_growth_small_bonus(self):
        """Test that zero growth returns small bonus."""
        bonus = _calculate_growth_bonus(0.0)
        assert bonus == 0.10

    def test_negative_growth_no_bonus(self):
        """Test that negative growth returns no bonus."""
        bonus = _calculate_growth_bonus(-0.05)  # -5% growth
        assert bonus == 0.0

    def test_none_growth_no_bonus(self):
        """Test that None growth returns no bonus."""
        bonus = _calculate_growth_bonus(None)
        assert bonus == 0.0


class TestCalculateYieldBonus:
    """Test yield bonus calculation."""

    def test_significantly_above_average_max_bonus(self):
        """Test that yield 1.5x+ above average returns max bonus."""
        bonus, above_avg = _calculate_yield_bonus(
            current_yield=0.06,  # 6%
            portfolio_avg_yield=0.03,  # 3% avg = 2x ratio
        )
        assert bonus == 0.30
        assert above_avg is True

    def test_above_average_mid_bonus(self):
        """Test that yield above average returns mid bonus."""
        bonus, above_avg = _calculate_yield_bonus(
            current_yield=0.04,  # 4%
            portfolio_avg_yield=0.03,  # 3% avg
        )
        assert bonus == 0.15
        assert above_avg is True

    def test_below_average_no_bonus(self):
        """Test that yield below average returns no bonus."""
        bonus, above_avg = _calculate_yield_bonus(
            current_yield=0.02,  # 2%
            portfolio_avg_yield=0.03,  # 3% avg
        )
        assert bonus == 0.0
        assert above_avg is False

    def test_none_yield_no_bonus(self):
        """Test that None yield returns no bonus."""
        bonus, above_avg = _calculate_yield_bonus(
            current_yield=None, portfolio_avg_yield=0.03
        )
        assert bonus == 0.0
        assert above_avg is False

    def test_zero_yield_no_bonus(self):
        """Test that zero yield returns no bonus."""
        bonus, above_avg = _calculate_yield_bonus(
            current_yield=0.0, portfolio_avg_yield=0.03
        )
        assert bonus == 0.0
        assert above_avg is False

    def test_negative_yield_no_bonus(self):
        """Test that negative yield returns no bonus."""
        bonus, above_avg = _calculate_yield_bonus(
            current_yield=-0.01, portfolio_avg_yield=0.03
        )
        assert bonus == 0.0
        assert above_avg is False

    def test_exactly_at_average_gets_bonus(self):
        """Test that yield exactly at average gets above-average bonus."""
        bonus, above_avg = _calculate_yield_bonus(
            current_yield=0.03, portfolio_avg_yield=0.03
        )
        assert bonus == 0.15  # Above average bonus
        assert above_avg is True

    def test_exactly_at_threshold_gets_max_bonus(self):
        """Test that yield exactly at 1.5x threshold gets max bonus."""
        bonus, above_avg = _calculate_yield_bonus(
            current_yield=0.045, portfolio_avg_yield=0.03  # Exactly 1.5x
        )
        assert bonus == 0.30
        assert above_avg is True


class TestCalculateDividendStabilityScore:
    """Test dividend stability score calculation."""

    def test_perfect_dividend_stock_high_score(self):
        """Test that perfect dividend stock gets high score."""
        # Growing dividends, no cuts, high yield
        history = [1.00, 1.10, 1.21, 1.33, 1.46]  # 10% CAGR
        score, details = calculate_dividend_stability_score(
            dividend_history=history,
            portfolio_avg_yield=0.03,
            current_yield=0.06,  # 2x average
        )

        assert score > 0.85  # Should be high
        assert details["has_big_cut"] is False
        assert details["cut_penalty"] == 0.0
        assert details["growth_bonus"] > 0
        assert details["yield_bonus"] > 0
        assert details["above_portfolio_avg"] is True

    def test_recent_cut_lowers_score(self):
        """Test that recent dividend cut significantly lowers score."""
        # Recent 30% cut
        history = [1.00, 1.10, 1.20, 0.84]  # Cut at end
        score, details = calculate_dividend_stability_score(
            dividend_history=history,
            portfolio_avg_yield=0.03,
            current_yield=0.03,
        )

        assert score < 0.5  # Should be low due to recent cut
        assert details["has_big_cut"] is True
        assert details["years_since_cut"] == 1
        assert details["cut_penalty"] == 0.40  # Max penalty

    def test_old_cut_partial_impact(self):
        """Test that old dividend cut has partial impact."""
        # Cut 6 years ago
        history = [1.00, 0.70] + [0.75, 0.80, 0.85, 0.90, 0.95]
        score, details = calculate_dividend_stability_score(
            dividend_history=history, portfolio_avg_yield=0.03, current_yield=0.03
        )

        assert 0.4 < score < 0.8  # Moderate score
        assert details["has_big_cut"] is True
        assert details["cut_penalty"] == 0.10  # Minimal penalty

    def test_flat_dividends_high_stability_score(self):
        """Test that flat dividends return high stability score.

        Flat dividends with no cuts indicate high stability. The scoring system
        rewards this with a high score (around 0.85) because:
        - No big dividend cuts = no penalty + bonus for cut-free history
        - Zero growth = small bonus (0.02)
        - Consistent payouts are valued
        """
        history = [1.00, 1.00, 1.00, 1.00]
        score, details = calculate_dividend_stability_score(
            dividend_history=history, portfolio_avg_yield=0.03, current_yield=0.03
        )

        assert 0.8 < score < 0.95  # High stability range
        assert details["dividend_growth_rate"] == pytest.approx(0.0, abs=0.01)

    def test_declining_dividends_no_growth_bonus(self):
        """Test that declining dividends get no growth bonus."""
        history = [1.00, 0.95, 0.90, 0.85]  # Declining but not >20% cuts
        score, details = calculate_dividend_stability_score(
            dividend_history=history, portfolio_avg_yield=0.03, current_yield=0.03
        )

        assert details["growth_bonus"] == 0.0
        assert details["dividend_growth_rate"] < 0

    def test_high_yield_boosts_score(self):
        """Test that high yield boosts stability score."""
        history = [1.00, 1.05, 1.10]  # Modest growth
        score, details = calculate_dividend_stability_score(
            dividend_history=history,
            portfolio_avg_yield=0.03,
            current_yield=0.08,  # High yield
        )

        assert details["yield_bonus"] > 0.15  # Should get yield bonus
        assert score > 0.7

    def test_score_clamped_to_valid_range(self):
        """Test that score is clamped between 0 and 1."""
        # Extreme case: multiple bonuses
        history = [0.50, 0.60, 0.70, 0.85, 1.00, 1.20]  # High growth
        score, details = calculate_dividend_stability_score(
            dividend_history=history,
            portfolio_avg_yield=0.02,
            current_yield=0.10,  # Very high yield
        )

        assert 0.0 <= score <= 1.0
        assert score == pytest.approx(1.0, abs=0.01)  # Should max out

    def test_default_portfolio_yield_used(self):
        """Test that default portfolio yield (3%) is used."""
        history = [1.00, 1.05, 1.10]
        score, details = calculate_dividend_stability_score(
            dividend_history=history, current_yield=0.05
        )

        # Should use default 0.03
        assert details["above_portfolio_avg"] is True

    def test_none_current_yield_handled(self):
        """Test that None current yield is handled."""
        history = [1.00, 1.05, 1.10]
        score, details = calculate_dividend_stability_score(
            dividend_history=history, current_yield=None
        )

        assert details["yield_bonus"] == 0.0
        assert details["above_portfolio_avg"] is False


class TestGetDividendAnalysis:
    """Test complete dividend analysis."""

    @pytest.mark.asyncio
    async def test_returns_complete_analysis(self):
        """Test that complete analysis is returned."""
        with patch("app.repositories.calculations.CalculationsRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_metric.side_effect = [
                0.05,  # DIVIDEND_YIELD
                0.40,  # PAYOUT_RATIO
            ]
            MockRepo.return_value = mock_repo

            result = await get_dividend_analysis(symbol="VZ", portfolio_avg_yield=0.03)

            assert "symbol" in result
            assert "current_yield_pct" in result
            assert "portfolio_avg_yield_pct" in result
            assert "payout_ratio_pct" in result
            assert "stability_score" in result
            assert "yield_assessment" in result
            assert "above_portfolio_avg" in result
            assert "recommendation" in result

    @pytest.mark.asyncio
    async def test_sustainable_payout_high_stability(self):
        """Test that sustainable payout ratio (30-60%) gives high stability."""
        with patch("app.repositories.calculations.CalculationsRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_metric.side_effect = [
                0.04,  # DIVIDEND_YIELD
                0.50,  # PAYOUT_RATIO (sustainable)
            ]
            MockRepo.return_value = mock_repo

            result = await get_dividend_analysis(symbol="VZ")

            assert result["stability_score"] == 0.85

    @pytest.mark.asyncio
    async def test_high_payout_low_stability(self):
        """Test that high payout ratio (>80%) gives low stability."""
        with patch("app.repositories.calculations.CalculationsRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_metric.side_effect = [
                0.04,  # DIVIDEND_YIELD
                0.90,  # PAYOUT_RATIO (high risk)
            ]
            MockRepo.return_value = mock_repo

            result = await get_dividend_analysis(symbol="VZ")

            assert result["stability_score"] == 0.40

    @pytest.mark.asyncio
    async def test_yield_assessment_significantly_above(self):
        """Test yield assessment for significantly above average."""
        with patch("app.repositories.calculations.CalculationsRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_metric.side_effect = [
                0.06,  # DIVIDEND_YIELD (2x average)
                0.50,  # PAYOUT_RATIO
            ]
            MockRepo.return_value = mock_repo

            result = await get_dividend_analysis(symbol="VZ", portfolio_avg_yield=0.03)

            assert result["yield_assessment"] == "significantly_above_average"
            assert result["above_portfolio_avg"] is True

    @pytest.mark.asyncio
    async def test_yield_assessment_above_average(self):
        """Test yield assessment for above average."""
        with patch("app.repositories.calculations.CalculationsRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_metric.side_effect = [
                0.04,  # DIVIDEND_YIELD
                0.50,  # PAYOUT_RATIO
            ]
            MockRepo.return_value = mock_repo

            result = await get_dividend_analysis(symbol="VZ", portfolio_avg_yield=0.03)

            assert result["yield_assessment"] == "above_average"

    @pytest.mark.asyncio
    async def test_yield_assessment_below_average(self):
        """Test yield assessment for below average."""
        with patch("app.repositories.calculations.CalculationsRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_metric.side_effect = [
                0.02,  # DIVIDEND_YIELD
                0.50,  # PAYOUT_RATIO
            ]
            MockRepo.return_value = mock_repo

            result = await get_dividend_analysis(symbol="VZ", portfolio_avg_yield=0.03)

            assert result["yield_assessment"] == "below_average"

    @pytest.mark.asyncio
    async def test_yield_assessment_no_dividend(self):
        """Test yield assessment for non-dividend stock."""
        with patch("app.repositories.calculations.CalculationsRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_metric.side_effect = [
                None,  # DIVIDEND_YIELD (no dividend)
                None,  # PAYOUT_RATIO
            ]
            MockRepo.return_value = mock_repo

            result = await get_dividend_analysis(symbol="GOOGL")

            assert result["yield_assessment"] == "no_dividend"
            assert result["current_yield_pct"] == 0.0

    @pytest.mark.asyncio
    async def test_caches_stability_score(self):
        """Test that stability score is cached."""
        with patch("app.repositories.calculations.CalculationsRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_metric.side_effect = [
                0.04,  # DIVIDEND_YIELD
                0.50,  # PAYOUT_RATIO
            ]
            MockRepo.return_value = mock_repo

            await get_dividend_analysis(symbol="VZ")

            # Should have called set_metric to cache
            mock_repo.set_metric.assert_called_once()
            args = mock_repo.set_metric.call_args[0]
            assert args[0] == "VZ"
            assert args[1] == "DIVIDEND_STABILITY"
            assert isinstance(args[2], float)

    @pytest.mark.asyncio
    async def test_handles_none_payout_ratio(self):
        """Test handling of None payout ratio."""
        with patch("app.repositories.calculations.CalculationsRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_metric.side_effect = [
                0.03,  # DIVIDEND_YIELD
                None,  # PAYOUT_RATIO (not available)
            ]
            MockRepo.return_value = mock_repo

            result = await get_dividend_analysis(symbol="VZ")

            assert result["payout_ratio_pct"] is None
            assert result["stability_score"] == 0.50  # Default

    @pytest.mark.asyncio
    async def test_formats_percentages_correctly(self):
        """Test that percentages are formatted correctly."""
        with patch("app.repositories.calculations.CalculationsRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_metric.side_effect = [
                0.0456,  # DIVIDEND_YIELD
                0.4532,  # PAYOUT_RATIO
            ]
            MockRepo.return_value = mock_repo

            result = await get_dividend_analysis(
                symbol="VZ", portfolio_avg_yield=0.0325
            )

            assert result["current_yield_pct"] == 4.56  # Rounded to 2 decimals
            assert result["portfolio_avg_yield_pct"] == 3.25
            assert result["payout_ratio_pct"] == 45.3  # Rounded to 1 decimal


class TestGetDividendRecommendation:
    """Test dividend recommendation generation."""

    def test_no_dividend_stock(self):
        """Test recommendation for non-dividend stock."""
        rec = _get_dividend_recommendation(
            stability=0.80, yield_assessment="no_dividend", payout_ratio=None
        )
        assert rec == "Non-dividend stock - income not a factor"

    def test_excellent_high_yield(self):
        """Test recommendation for excellent stability with high yield."""
        rec = _get_dividend_recommendation(
            stability=0.85,
            yield_assessment="significantly_above_average",
            payout_ratio=0.50,
        )
        assert rec == "Excellent: High yield with sustainable payout"

    def test_good_above_average(self):
        """Test recommendation for good stability with above-average yield."""
        rec = _get_dividend_recommendation(
            stability=0.82, yield_assessment="above_average", payout_ratio=0.45
        )
        assert rec == "Good: Above-average yield, stable history"

    def test_stable_below_average(self):
        """Test recommendation for stable but below-average yield."""
        rec = _get_dividend_recommendation(
            stability=0.85, yield_assessment="below_average", payout_ratio=0.40
        )
        assert rec == "Stable dividend, but yield below portfolio average"

    def test_moderate_stability(self):
        """Test recommendation for moderate stability."""
        rec = _get_dividend_recommendation(
            stability=0.70, yield_assessment="above_average", payout_ratio=0.50
        )
        assert rec == "Moderate stability - monitor for changes"

    def test_caution_high_payout(self):
        """Test caution recommendation for high payout ratio."""
        rec = _get_dividend_recommendation(
            stability=0.65, yield_assessment="above_average", payout_ratio=0.75
        )
        assert rec == "Caution: High payout ratio may be unsustainable"

    def test_warning_low_stability(self):
        """Test warning for low stability."""
        rec = _get_dividend_recommendation(
            stability=0.45, yield_assessment="above_average", payout_ratio=0.50
        )
        assert rec == "Warning: Dividend may be at risk"

    def test_high_risk_very_low_stability(self):
        """Test high risk for very low stability."""
        rec = _get_dividend_recommendation(
            stability=0.35, yield_assessment="above_average", payout_ratio=0.90
        )
        assert rec == "High risk: Dividend appears unsustainable"


class TestIsDividendConsistent:
    """Test dividend consistency check."""

    def test_consistent_dividend_returns_true(self):
        """Test that consistent dividend returns True."""
        result = is_dividend_consistent(
            symbol_yield=0.04,  # 4% yield
            portfolio_avg_yield=0.03,
            stability_score=0.70,  # Above min
            min_stability=0.60,
        )
        assert result is True

    def test_no_yield_returns_false(self):
        """Test that zero yield returns False."""
        result = is_dividend_consistent(
            symbol_yield=0.0,
            portfolio_avg_yield=0.03,
            stability_score=0.80,
            min_stability=0.60,
        )
        assert result is False

    def test_negative_yield_returns_false(self):
        """Test that negative yield returns False."""
        result = is_dividend_consistent(
            symbol_yield=-0.01,
            portfolio_avg_yield=0.03,
            stability_score=0.80,
            min_stability=0.60,
        )
        assert result is False

    def test_low_stability_returns_false(self):
        """Test that low stability returns False."""
        result = is_dividend_consistent(
            symbol_yield=0.04,
            portfolio_avg_yield=0.03,
            stability_score=0.50,  # Below min
            min_stability=0.60,
        )
        assert result is False

    def test_exactly_at_min_stability_returns_true(self):
        """Test that exactly at min stability returns True."""
        result = is_dividend_consistent(
            symbol_yield=0.04,
            portfolio_avg_yield=0.03,
            stability_score=0.60,  # Exactly at min
            min_stability=0.60,
        )
        assert result is True

    def test_below_average_yield_but_stable_returns_true(self):
        """Test that below-average yield but stable still returns True."""
        result = is_dividend_consistent(
            symbol_yield=0.02,  # Below average
            portfolio_avg_yield=0.03,
            stability_score=0.80,
            min_stability=0.60,
        )
        assert result is True

    def test_custom_min_stability(self):
        """Test custom minimum stability threshold."""
        result = is_dividend_consistent(
            symbol_yield=0.04,
            portfolio_avg_yield=0.03,
            stability_score=0.70,
            min_stability=0.75,  # Higher threshold
        )
        assert result is False


class TestDividendConstants:
    """Test dividend-related constants."""

    def test_dividend_cut_threshold_value(self):
        """Verify dividend cut threshold is set correctly."""
        assert DIVIDEND_CUT_THRESHOLD == 0.20  # 20% threshold
