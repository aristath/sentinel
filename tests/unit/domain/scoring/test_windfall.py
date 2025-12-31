"""Tests for windfall detection.

These tests verify the profit-taking detection which is CRITICAL
for identifying when to sell positions with unexpected gains.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.modules.scoring.domain.constants import (
    CONSISTENT_DOUBLE_SELL_PCT,
    WINDFALL_EXCESS_HIGH,
    WINDFALL_EXCESS_MEDIUM,
    WINDFALL_SELL_PCT_HIGH,
    WINDFALL_SELL_PCT_MEDIUM,
)
from app.modules.scoring.domain.windfall import (
    calculate_excess_gain,
    calculate_windfall_score,
    get_windfall_recommendation,
    should_take_profits,
)


class TestCalculateExcessGain:
    """Test excess gain calculation."""

    def test_consistent_grower_no_excess(self):
        """Test that consistent grower shows minimal excess.

        Example: held 3 years, up 61%, historical CAGR = 17%
        expected = (1.17^3) - 1 = 60%
        excess = 61% - 60% = 1%
        """
        excess = calculate_excess_gain(
            current_gain=0.61,  # 61% gain
            years_held=3.0,
            historical_cagr=0.17,  # 17% CAGR
        )

        # Expected gain: (1.17^3) - 1 = 0.601 = 60.1%
        # Excess: 61% - 60.1% = ~1%
        assert excess == pytest.approx(0.01, abs=0.02)

    def test_windfall_spike_high_excess(self):
        """Test that sudden spike shows high excess.

        Example: held 1 year, up 80%, historical CAGR = 10%
        expected = 10%
        excess = 80% - 10% = 70%
        """
        excess = calculate_excess_gain(
            current_gain=0.80,  # 80% gain
            years_held=1.0,
            historical_cagr=0.10,  # 10% CAGR
        )

        # Expected gain: (1.10^1) - 1 = 0.10 = 10%
        # Excess: 80% - 10% = 70%
        assert excess == pytest.approx(0.70, abs=0.01)

    def test_zero_years_held_returns_full_gain(self):
        """Test that zero years held returns full gain as excess."""
        excess = calculate_excess_gain(
            current_gain=0.50,
            years_held=0.0,
            historical_cagr=0.10,
        )

        assert excess == 0.50

    def test_negative_years_held_returns_full_gain(self):
        """Test that negative years held returns full gain as excess."""
        excess = calculate_excess_gain(
            current_gain=0.50,
            years_held=-1.0,
            historical_cagr=0.10,
        )

        assert excess == 0.50

    def test_invalid_cagr_returns_full_gain(self):
        """Test that invalid CAGR (<= -1) returns full gain as excess."""
        excess = calculate_excess_gain(
            current_gain=0.50,
            years_held=2.0,
            historical_cagr=-1.0,  # Would cause math error
        )

        assert excess == 0.50

    def test_negative_cagr_but_valid(self):
        """Test calculation with negative but valid CAGR."""
        excess = calculate_excess_gain(
            current_gain=0.20,  # 20% gain
            years_held=2.0,
            historical_cagr=-0.05,  # -5% CAGR (declining company)
        )

        # Expected: (0.95^2) - 1 = -0.0975 = -9.75%
        # Excess: 20% - (-9.75%) = 29.75%
        assert excess == pytest.approx(0.2975, abs=0.01)

    def test_underperforming_stock_negative_excess(self):
        """Test that underperforming stock shows negative excess."""
        excess = calculate_excess_gain(
            current_gain=0.05,  # 5% gain
            years_held=2.0,
            historical_cagr=0.15,  # 15% CAGR
        )

        # Expected: (1.15^2) - 1 = 0.3225 = 32.25%
        # Excess: 5% - 32.25% = -27.25%
        assert excess < 0
        assert excess == pytest.approx(-0.2725, abs=0.01)

    def test_fractional_years_held(self):
        """Test calculation with fractional years."""
        excess = calculate_excess_gain(
            current_gain=0.15,  # 15% gain
            years_held=0.5,  # 6 months
            historical_cagr=0.10,  # 10% CAGR
        )

        # Expected: (1.10^0.5) - 1 = 0.0488 = ~4.9%
        # Excess: 15% - 4.9% = ~10.1%
        assert excess == pytest.approx(0.101, abs=0.01)


class TestCalculateWindfallScore:
    """Test windfall score calculation."""

    @pytest.mark.asyncio
    async def test_high_excess_returns_score_1(self):
        """Test that high excess (>=50%) returns score of 1.0."""
        with patch("app.repositories.calculations.CalculationsRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_metric.return_value = 0.10  # 10% CAGR
            MockRepo.return_value = mock_repo

            score, details = await calculate_windfall_score(
                symbol="AAPL",
                current_gain=0.70,  # 70% gain
                years_held=1.0,
                historical_cagr=0.10,  # Will give 60% excess
            )

            assert score == 1.0

    @pytest.mark.asyncio
    async def test_medium_excess_returns_mid_score(self):
        """Test that medium excess (25-50%) returns score 0.5-1.0."""
        with patch("app.repositories.calculations.CalculationsRepository") as MockRepo:
            mock_repo = AsyncMock()
            MockRepo.return_value = mock_repo

            score, details = await calculate_windfall_score(
                symbol="AAPL",
                current_gain=0.35,  # 35% gain
                years_held=1.0,
                historical_cagr=0.10,  # Will give 25% excess
            )

            assert 0.5 <= score <= 1.0

    @pytest.mark.asyncio
    async def test_low_excess_returns_low_score(self):
        """Test that low excess (0-25%) returns score 0-0.5."""
        with patch("app.repositories.calculations.CalculationsRepository") as MockRepo:
            mock_repo = AsyncMock()
            MockRepo.return_value = mock_repo

            score, details = await calculate_windfall_score(
                symbol="AAPL",
                current_gain=0.15,  # 15% gain
                years_held=1.0,
                historical_cagr=0.10,  # Will give 5% excess
            )

            assert 0.0 <= score <= 0.5

    @pytest.mark.asyncio
    async def test_no_excess_returns_zero_score(self):
        """Test that no excess or underperforming returns score of 0."""
        with patch("app.repositories.calculations.CalculationsRepository") as MockRepo:
            mock_repo = AsyncMock()
            MockRepo.return_value = mock_repo

            score, details = await calculate_windfall_score(
                symbol="AAPL",
                current_gain=0.05,  # 5% gain
                years_held=1.0,
                historical_cagr=0.15,  # Expected 15%, excess is negative
            )

            assert score == 0.0

    @pytest.mark.asyncio
    async def test_insufficient_data_returns_zero(self):
        """Test that missing data returns zero score."""
        with patch("app.repositories.calculations.CalculationsRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_metric.return_value = 0.10
            MockRepo.return_value = mock_repo

            score, details = await calculate_windfall_score(
                symbol="AAPL",
                current_gain=None,  # Missing data
                years_held=None,
            )

            assert score == 0.0
            assert details["status"] == "insufficient_data"

    @pytest.mark.asyncio
    async def test_fetches_cagr_from_cache_when_not_provided(self):
        """Test that CAGR is fetched from cache when not provided."""
        with patch("app.repositories.calculations.CalculationsRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_metric.return_value = 0.12  # Cached CAGR
            MockRepo.return_value = mock_repo

            score, details = await calculate_windfall_score(
                symbol="AAPL",
                current_gain=0.50,
                years_held=2.0,
                historical_cagr=None,  # Should fetch from cache
            )

            mock_repo.get_metric.assert_called()
            assert details["historical_cagr"] == 0.12

    @pytest.mark.asyncio
    async def test_uses_10y_cagr_as_fallback(self):
        """Test that 10Y CAGR is used when 5Y is not available."""
        with patch("app.repositories.calculations.CalculationsRepository") as MockRepo:
            mock_repo = AsyncMock()

            # First call (CAGR_5Y) returns None, second (CAGR_10Y) returns value
            mock_repo.get_metric.side_effect = [None, 0.08]
            MockRepo.return_value = mock_repo

            score, details = await calculate_windfall_score(
                symbol="AAPL",
                current_gain=0.50,
                years_held=2.0,
            )

            assert details["historical_cagr"] == 0.08

    @pytest.mark.asyncio
    async def test_uses_default_cagr_when_no_data(self):
        """Test that 10% default CAGR is used when no data available."""
        with patch("app.repositories.calculations.CalculationsRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_metric.return_value = None  # No CAGR data
            MockRepo.return_value = mock_repo

            score, details = await calculate_windfall_score(
                symbol="AAPL",
                current_gain=0.50,
                years_held=2.0,
            )

            assert details["historical_cagr"] == 0.10  # Default


class TestShouldTakeProfits:
    """Test profit-taking recommendations."""

    def test_windfall_doubler_recommends_50_percent(self):
        """Test that windfall doubler recommends selling 50%."""
        should_sell, sell_pct, reason = should_take_profits(
            current_gain=1.50,  # 150% gain
            years_held=2.0,
            historical_cagr=0.10,  # Expected ~21%, excess ~129%
        )

        assert should_sell is True
        assert sell_pct == 0.50
        assert "Windfall doubler" in reason

    def test_consistent_doubler_recommends_30_percent(self):
        """Test that consistent doubler recommends selling 30%."""
        should_sell, sell_pct, reason = should_take_profits(
            current_gain=1.00,  # 100% gain (doubled)
            years_held=5.0,
            historical_cagr=0.15,  # Expected ~101%, excess ~-1%
        )

        assert should_sell is True
        assert sell_pct == CONSISTENT_DOUBLE_SELL_PCT
        assert "Consistent doubler" in reason

    def test_high_windfall_recommends_40_percent(self):
        """Test that high windfall (>=50% excess) recommends selling 40%."""
        should_sell, sell_pct, reason = should_take_profits(
            current_gain=0.70,  # 70% gain
            years_held=1.0,
            historical_cagr=0.10,  # Expected 10%, excess 60%
        )

        assert should_sell is True
        assert sell_pct == WINDFALL_SELL_PCT_HIGH
        assert "High windfall" in reason

    def test_medium_windfall_recommends_20_percent(self):
        """Test that medium windfall (25-50% excess) recommends selling 20%."""
        should_sell, sell_pct, reason = should_take_profits(
            current_gain=0.40,  # 40% gain
            years_held=1.0,
            historical_cagr=0.10,  # Expected 10%, excess 30%
        )

        assert should_sell is True
        assert sell_pct == WINDFALL_SELL_PCT_MEDIUM
        assert "Medium windfall" in reason

    def test_low_excess_no_sell(self):
        """Test that low excess (<25%) does not recommend selling."""
        should_sell, sell_pct, reason = should_take_profits(
            current_gain=0.20,  # 20% gain
            years_held=1.0,
            historical_cagr=0.10,  # Expected 10%, excess 10%
        )

        assert should_sell is False
        assert sell_pct == 0.0
        assert "within normal range" in reason

    def test_performing_near_expectations(self):
        """Test stock performing near expectations."""
        should_sell, sell_pct, reason = should_take_profits(
            current_gain=0.10,  # 10% gain
            years_held=1.0,
            historical_cagr=0.10,  # Expected 10%, excess 0%
        )

        assert should_sell is False
        assert sell_pct == 0.0
        assert "near expectations" in reason

    def test_underperforming_stock(self):
        """Test underperforming stock."""
        should_sell, sell_pct, reason = should_take_profits(
            current_gain=0.05,  # 5% gain
            years_held=2.0,
            historical_cagr=0.15,  # Expected ~32%, excess -27%
        )

        assert should_sell is False
        assert sell_pct == 0.0
        assert "Underperforming" in reason


class TestGetWindfallRecommendation:
    """Test complete windfall recommendation."""

    @pytest.mark.asyncio
    async def test_returns_complete_analysis(self):
        """Test that complete analysis is returned."""
        with patch("app.repositories.calculations.CalculationsRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_metric.return_value = 0.10
            MockRepo.return_value = mock_repo

            result = await get_windfall_recommendation(
                symbol="AAPL",
                current_price=150.0,
                avg_price=100.0,  # 50% gain
                first_bought_at="2023-01-01",
            )

            assert "symbol" in result
            assert "current_gain_pct" in result
            assert "years_held" in result
            assert "windfall_score" in result
            assert "excess_gain_pct" in result
            assert "expected_gain_pct" in result
            assert "historical_cagr_pct" in result
            assert "recommendation" in result

    @pytest.mark.asyncio
    async def test_calculates_gain_correctly(self):
        """Test that gain percentage is calculated correctly."""
        with patch("app.repositories.calculations.CalculationsRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_metric.return_value = 0.10
            MockRepo.return_value = mock_repo

            result = await get_windfall_recommendation(
                symbol="AAPL",
                current_price=150.0,
                avg_price=100.0,
            )

            # (150 - 100) / 100 = 0.50 = 50%
            assert result["current_gain_pct"] == 50.0

    @pytest.mark.asyncio
    async def test_handles_invalid_avg_price(self):
        """Test that invalid average price returns error."""
        result = await get_windfall_recommendation(
            symbol="AAPL",
            current_price=150.0,
            avg_price=0.0,  # Invalid
        )

        assert "error" in result
        assert "Invalid average price" in result["error"]

    @pytest.mark.asyncio
    async def test_calculates_years_held_from_date(self):
        """Test that years held is calculated from first_bought_at."""
        with patch("app.repositories.calculations.CalculationsRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_metric.return_value = 0.10
            MockRepo.return_value = mock_repo

            # Bought ~365 days ago
            from datetime import datetime, timedelta

            one_year_ago = (datetime.now() - timedelta(days=365)).isoformat()

            result = await get_windfall_recommendation(
                symbol="AAPL",
                current_price=150.0,
                avg_price=100.0,
                first_bought_at=one_year_ago,
            )

            # Should be approximately 1.0 years
            assert 0.9 <= result["years_held"] <= 1.1

    @pytest.mark.asyncio
    async def test_uses_default_years_when_date_missing(self):
        """Test that default 1.0 years is used when date is missing."""
        with patch("app.repositories.calculations.CalculationsRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_metric.return_value = 0.10
            MockRepo.return_value = mock_repo

            result = await get_windfall_recommendation(
                symbol="AAPL",
                current_price=150.0,
                avg_price=100.0,
                first_bought_at=None,
            )

            assert result["years_held"] == 1.0

    @pytest.mark.asyncio
    async def test_handles_invalid_date_format(self):
        """Test that invalid date format uses default."""
        with patch("app.repositories.calculations.CalculationsRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_metric.return_value = 0.10
            MockRepo.return_value = mock_repo

            result = await get_windfall_recommendation(
                symbol="AAPL",
                current_price=150.0,
                avg_price=100.0,
                first_bought_at="invalid-date",
            )

            assert result["years_held"] == 1.0

    @pytest.mark.asyncio
    async def test_recommendation_includes_sell_info(self):
        """Test that recommendation includes sell information."""
        with patch("app.repositories.calculations.CalculationsRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_metric.return_value = 0.10
            MockRepo.return_value = mock_repo

            result = await get_windfall_recommendation(
                symbol="AAPL",
                current_price=200.0,  # 100% gain
                avg_price=100.0,
                first_bought_at="2020-01-01",  # Held long enough to be consistent
            )

            rec = result["recommendation"]
            assert "take_profits" in rec
            assert "suggested_sell_pct" in rec
            assert "reason" in rec
            assert rec["take_profits"] is True  # Should recommend taking profits


class TestWindfallThresholds:
    """Test that thresholds are correctly applied."""

    def test_threshold_values_are_correct(self):
        """Verify threshold constants are set correctly."""
        assert WINDFALL_EXCESS_HIGH == 0.50
        assert WINDFALL_EXCESS_MEDIUM == 0.25
        assert WINDFALL_SELL_PCT_HIGH == 0.40
        assert WINDFALL_SELL_PCT_MEDIUM == 0.20
        assert CONSISTENT_DOUBLE_SELL_PCT == 0.30

    def test_exactly_at_high_threshold(self):
        """Test behavior at/above high threshold (50%)."""
        should_sell, sell_pct, _ = should_take_profits(
            current_gain=0.61,  # 61% gain - safely above threshold
            years_held=1.0,
            historical_cagr=0.10,  # Excess = 51% (above 50%)
        )

        assert should_sell is True
        assert sell_pct == WINDFALL_SELL_PCT_HIGH

    def test_exactly_at_medium_threshold(self):
        """Test behavior at/above medium threshold (25%)."""
        should_sell, sell_pct, _ = should_take_profits(
            current_gain=0.36,  # 36% gain - safely above threshold
            years_held=1.0,
            historical_cagr=0.10,  # Excess = 26% (above 25%)
        )

        assert should_sell is True
        assert sell_pct == WINDFALL_SELL_PCT_MEDIUM

    def test_just_below_medium_threshold(self):
        """Test behavior just below medium threshold."""
        should_sell, sell_pct, _ = should_take_profits(
            current_gain=0.34,  # 34% gain
            years_held=1.0,
            historical_cagr=0.10,  # Excess 24% (below 25%)
        )

        assert should_sell is False
        assert sell_pct == 0.0
