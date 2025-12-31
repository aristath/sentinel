"""Tests for short-term performance scoring.

These tests validate momentum and drawdown score calculations.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.modules.scoring.domain.groups.short_term import (
    calculate_recent_momentum,
    calculate_short_term_score,
)


class TestCalculateRecentMomentum:
    """Test calculate_recent_momentum function."""

    def test_returns_none_for_insufficient_data(self):
        """Test returning None when less than 30 days of data."""
        prices = [{"close": 100.0}] * 20

        result = calculate_recent_momentum(prices)

        assert result is None

    def test_calculates_positive_momentum(self):
        """Test calculating positive momentum."""
        # Create prices that go from 100 to 110 (10% up)
        prices = [{"close": 100.0}] * 60 + [{"close": 110.0}] * 30

        result = calculate_recent_momentum(prices)

        assert result is not None
        assert result > 0

    def test_calculates_negative_momentum(self):
        """Test calculating negative momentum."""
        # Create prices that go from 100 to 90 (10% down)
        prices = [{"close": 100.0}] * 60 + [{"close": 90.0}] * 30

        result = calculate_recent_momentum(prices)

        assert result is not None
        assert result < 0

    def test_handles_exactly_30_days(self):
        """Test handling exactly 30 days of data."""
        prices = [{"close": 100.0}] * 30

        result = calculate_recent_momentum(prices)

        assert result is not None
        assert result == pytest.approx(0.0)

    def test_handles_zero_price(self):
        """Test handling zero price."""
        prices = [{"close": 0.0}] * 30 + [{"close": 100.0}]

        result = calculate_recent_momentum(prices)

        assert result is not None


class TestCalculateShortTermScore:
    """Test calculate_short_term_score function."""

    @pytest.mark.asyncio
    async def test_calculates_score_with_prices(self):
        """Test calculating score with sufficient price data."""
        prices = [{"close": 100.0 + i * 0.5} for i in range(100)]

        mock_repo = AsyncMock()
        mock_repo.set_metric = AsyncMock()

        with (
            patch(
                "app.repositories.calculations.CalculationsRepository",
                return_value=mock_repo,
            ),
            patch(
                "app.domain.scoring.caching.get_max_drawdown",
                new_callable=AsyncMock,
                return_value=-0.05,
            ),
        ):
            result = await calculate_short_term_score("AAPL.US", prices)

        assert result.score >= 0
        assert result.score <= 1
        assert "momentum" in result.sub_scores
        assert "drawdown" in result.sub_scores

    @pytest.mark.asyncio
    async def test_handles_insufficient_data(self):
        """Test handling insufficient price data."""
        prices = [{"close": 100.0}] * 20

        mock_repo = AsyncMock()
        mock_repo.set_metric = AsyncMock()

        with patch(
            "app.repositories.calculations.CalculationsRepository",
            return_value=mock_repo,
        ):
            result = await calculate_short_term_score("AAPL.US", prices)

        assert result.score >= 0
        assert result.score <= 1

    @pytest.mark.asyncio
    async def test_uses_pyfolio_drawdown_when_provided(self):
        """Test using provided pyfolio drawdown."""
        prices = [{"close": 100.0}] * 100

        mock_repo = AsyncMock()
        mock_repo.set_metric = AsyncMock()

        with patch(
            "app.repositories.calculations.CalculationsRepository",
            return_value=mock_repo,
        ):
            await calculate_short_term_score("AAPL.US", prices, pyfolio_drawdown=-0.15)

        # Should have used the provided drawdown
        mock_repo.set_metric.assert_any_call("AAPL.US", "MAX_DRAWDOWN", -0.15)

    @pytest.mark.asyncio
    async def test_stores_momentum_metrics(self):
        """Test that momentum metrics are stored."""
        prices = [{"close": 100.0}] * 100

        mock_repo = AsyncMock()
        mock_repo.set_metric = AsyncMock()

        with (
            patch(
                "app.repositories.calculations.CalculationsRepository",
                return_value=mock_repo,
            ),
            patch(
                "app.domain.scoring.caching.get_max_drawdown",
                new_callable=AsyncMock,
                return_value=-0.05,
            ),
        ):
            await calculate_short_term_score("AAPL.US", prices)

        # Should have stored 30-day and 90-day momentum
        calls = [str(c) for c in mock_repo.set_metric.call_args_list]
        assert any("MOMENTUM_30D" in c for c in calls)
        assert any("MOMENTUM_90D" in c for c in calls)

    @pytest.mark.asyncio
    async def test_blends_momentum_correctly(self):
        """Test that momentum is blended 60/40."""
        # Create prices with consistent growth
        prices = [{"close": 100.0 + i} for i in range(100)]

        mock_repo = AsyncMock()
        mock_repo.set_metric = AsyncMock()

        with (
            patch(
                "app.repositories.calculations.CalculationsRepository",
                return_value=mock_repo,
            ),
            patch(
                "app.domain.scoring.caching.get_max_drawdown",
                new_callable=AsyncMock,
                return_value=-0.02,
            ),
        ):
            result = await calculate_short_term_score("AAPL.US", prices)

        # With positive momentum and low drawdown, should have decent score
        assert result.score > 0.5
