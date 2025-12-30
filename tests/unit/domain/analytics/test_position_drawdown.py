"""Tests for position drawdown calculations.

These tests validate drawdown calculations for individual stock positions,
including maximum drawdown and current drawdown.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.domain.models import DailyPrice


@pytest.fixture
def mock_history_repo():
    """Mock HistoryRepository."""
    repo = AsyncMock()
    repo.get_daily_range.return_value = []
    return repo


class TestGetPositionDrawdown:
    """Test get_position_drawdown function."""

    @pytest.mark.asyncio
    async def test_returns_none_for_insufficient_data(self):
        """Test that None is returned when there's insufficient price data."""
        from app.domain.analytics.position.drawdown import get_position_drawdown

        mock_history_repo = AsyncMock()
        mock_history_repo.get_daily_range.return_value = []  # No price data

        with patch(
            "app.domain.analytics.position.drawdown.HistoryRepository",
            return_value=mock_history_repo,
        ):
            result = await get_position_drawdown("AAPL", "2024-01-01", "2024-01-31")

            assert result["max_drawdown"] is None
            assert result["current_drawdown"] is None

    @pytest.mark.asyncio
    async def test_calculates_max_drawdown_from_peak(self):
        """Test that maximum drawdown is calculated from peak price."""
        from app.domain.analytics.position.drawdown import get_position_drawdown

        # Prices: 100, 110, 105, 90, 95 (peak at 110, lowest at 90)
        prices = [
            DailyPrice(date="2024-01-01", close_price=100.0),
            DailyPrice(date="2024-01-02", close_price=110.0),  # Peak
            DailyPrice(date="2024-01-03", close_price=105.0),
            DailyPrice(date="2024-01-04", close_price=90.0),  # Trough (18.18% down)
            DailyPrice(date="2024-01-05", close_price=95.0),
        ]

        mock_history_repo = AsyncMock()
        mock_history_repo.get_daily_range.return_value = prices

        with patch(
            "app.domain.analytics.position.drawdown.HistoryRepository",
            return_value=mock_history_repo,
        ):
            result = await get_position_drawdown("AAPL", "2024-01-01", "2024-01-31")

            assert result["max_drawdown"] is not None
            # Max drawdown from 110 to 90 = (90 - 110) / 110 = -0.1818... = -18.18%
            assert result["max_drawdown"] == pytest.approx(-0.1818, abs=0.01)

    @pytest.mark.asyncio
    async def test_calculates_current_drawdown_from_latest_peak(self):
        """Test that current drawdown is calculated from latest peak."""
        from app.domain.analytics.position.drawdown import get_position_drawdown

        # Prices: 100, 110, 105, 120, 115
        # Latest peak is 120, current is 115
        prices = [
            DailyPrice(date="2024-01-01", close_price=100.0),
            DailyPrice(date="2024-01-02", close_price=110.0),
            DailyPrice(date="2024-01-03", close_price=105.0),
            DailyPrice(date="2024-01-04", close_price=120.0),  # Latest peak
            DailyPrice(date="2024-01-05", close_price=115.0),  # Current (4.17% down)
        ]

        mock_history_repo = AsyncMock()
        mock_history_repo.get_daily_range.return_value = prices

        with patch(
            "app.domain.analytics.position.drawdown.HistoryRepository",
            return_value=mock_history_repo,
        ):
            result = await get_position_drawdown("AAPL", "2024-01-01", "2024-01-31")

            assert result["current_drawdown"] is not None
            # Current drawdown from 120 to 115 = (115 - 120) / 120 = -0.0417 = -4.17%
            assert result["current_drawdown"] == pytest.approx(-0.0417, abs=0.01)

    @pytest.mark.asyncio
    async def test_returns_zero_drawdown_when_at_peak(self):
        """Test that drawdown is zero when price is at peak."""
        from app.domain.analytics.position.drawdown import get_position_drawdown

        # Prices: 100, 110, 120 (always increasing)
        prices = [
            DailyPrice(date="2024-01-01", close_price=100.0),
            DailyPrice(date="2024-01-02", close_price=110.0),
            DailyPrice(date="2024-01-03", close_price=120.0),  # At peak
        ]

        mock_history_repo = AsyncMock()
        mock_history_repo.get_daily_range.return_value = prices

        with patch(
            "app.domain.analytics.position.drawdown.HistoryRepository",
            return_value=mock_history_repo,
        ):
            result = await get_position_drawdown("AAPL", "2024-01-01", "2024-01-31")

            assert result["current_drawdown"] == 0.0
            assert result["max_drawdown"] == 0.0

    @pytest.mark.asyncio
    async def test_handles_single_price_point(self):
        """Test handling when only one price point is available."""
        from app.domain.analytics.position.drawdown import get_position_drawdown

        prices = [DailyPrice(date="2024-01-01", close_price=100.0)]

        mock_history_repo = AsyncMock()
        mock_history_repo.get_daily_range.return_value = prices

        with patch(
            "app.domain.analytics.position.drawdown.HistoryRepository",
            return_value=mock_history_repo,
        ):
            result = await get_position_drawdown("AAPL", "2024-01-01", "2024-01-31")

            # With only one price, can't calculate drawdown
            assert result["max_drawdown"] is None
            assert result["current_drawdown"] is None

    @pytest.mark.asyncio
    async def test_handles_declining_prices(self):
        """Test handling when prices are continuously declining."""
        from app.domain.analytics.position.drawdown import get_position_drawdown

        # Prices: 120, 110, 100, 90
        prices = [
            DailyPrice(date="2024-01-01", close_price=120.0),  # Peak
            DailyPrice(date="2024-01-02", close_price=110.0),
            DailyPrice(date="2024-01-03", close_price=100.0),
            DailyPrice(date="2024-01-04", close_price=90.0),  # Current (25% down)
        ]

        mock_history_repo = AsyncMock()
        mock_history_repo.get_daily_range.return_value = prices

        with patch(
            "app.domain.analytics.position.drawdown.HistoryRepository",
            return_value=mock_history_repo,
        ):
            result = await get_position_drawdown("AAPL", "2024-01-01", "2024-01-31")

            assert result["max_drawdown"] == pytest.approx(-0.25, abs=0.01)  # -25%
            assert result["current_drawdown"] == pytest.approx(-0.25, abs=0.01)  # Same

    @pytest.mark.asyncio
    async def test_handles_recovery_after_drawdown(self):
        """Test handling when price recovers after drawdown."""
        from app.domain.analytics.position.drawdown import get_position_drawdown

        # Prices: 100, 110, 90, 105
        # Peak at 110, trough at 90 (-18.18%), but recovered to 105
        prices = [
            DailyPrice(date="2024-01-01", close_price=100.0),
            DailyPrice(date="2024-01-02", close_price=110.0),  # Peak
            DailyPrice(date="2024-01-03", close_price=90.0),  # Trough
            DailyPrice(
                date="2024-01-04", close_price=105.0
            ),  # Recovered (but still below peak)
        ]

        mock_history_repo = AsyncMock()
        mock_history_repo.get_daily_range.return_value = prices

        with patch(
            "app.domain.analytics.position.drawdown.HistoryRepository",
            return_value=mock_history_repo,
        ):
            result = await get_position_drawdown("AAPL", "2024-01-01", "2024-01-31")

            # Max drawdown was -18.18% (from 110 to 90)
            assert result["max_drawdown"] == pytest.approx(-0.1818, abs=0.01)
            # Current drawdown from peak 110 to 105 = -4.55%
            assert result["current_drawdown"] == pytest.approx(-0.0455, abs=0.01)
