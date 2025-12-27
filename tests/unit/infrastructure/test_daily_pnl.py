"""Tests for daily P&L tracker.

These tests validate the tiered circuit breaker for trading decisions
based on daily portfolio performance.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestDailyPnLTrackerGetStartOfDayValue:
    """Test getting start of day portfolio value."""

    @pytest.mark.asyncio
    async def test_returns_previous_day_value(self):
        """Test returning previous day's snapshot value."""
        from app.infrastructure.daily_pnl import DailyPnLTracker

        mock_row = {"total_value": 50000.0, "date": "2024-01-14"}

        mock_state = AsyncMock()
        mock_state.fetchone = AsyncMock(return_value=mock_row)

        mock_manager = MagicMock()
        mock_manager.state = mock_state

        with patch(
            "app.infrastructure.daily_pnl.get_db_manager",
            return_value=mock_manager,
        ):
            tracker = DailyPnLTracker()
            result = await tracker.get_start_of_day_value()

        assert result == 50000.0

    @pytest.mark.asyncio
    async def test_returns_today_fallback(self):
        """Test returning today's snapshot as fallback."""
        from app.infrastructure.daily_pnl import DailyPnLTracker

        mock_state = AsyncMock()
        # First call returns None (no previous day)
        # Second call returns today's snapshot
        mock_state.fetchone = AsyncMock(side_effect=[None, {"total_value": 45000.0}])

        mock_manager = MagicMock()
        mock_manager.state = mock_state

        with patch(
            "app.infrastructure.daily_pnl.get_db_manager",
            return_value=mock_manager,
        ):
            tracker = DailyPnLTracker()
            result = await tracker.get_start_of_day_value()

        assert result == 45000.0

    @pytest.mark.asyncio
    async def test_returns_none_when_no_snapshots(self):
        """Test returning None when no snapshots exist."""
        from app.infrastructure.daily_pnl import DailyPnLTracker

        mock_state = AsyncMock()
        mock_state.fetchone = AsyncMock(return_value=None)

        mock_manager = MagicMock()
        mock_manager.state = mock_state

        with patch(
            "app.infrastructure.daily_pnl.get_db_manager",
            return_value=mock_manager,
        ):
            tracker = DailyPnLTracker()
            result = await tracker.get_start_of_day_value()

        assert result is None


class TestDailyPnLTrackerGetCurrentValue:
    """Test getting current portfolio value."""

    @pytest.mark.asyncio
    async def test_returns_sum_of_positions(self):
        """Test returning sum of position values."""
        from app.infrastructure.daily_pnl import DailyPnLTracker

        mock_state = AsyncMock()
        mock_state.fetchone = AsyncMock(return_value={"total": 52000.0})

        mock_manager = MagicMock()
        mock_manager.state = mock_state

        with patch(
            "app.infrastructure.daily_pnl.get_db_manager",
            return_value=mock_manager,
        ):
            tracker = DailyPnLTracker()
            result = await tracker.get_current_value()

        assert result == 52000.0

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_positions(self):
        """Test returning zero when no positions exist."""
        from app.infrastructure.daily_pnl import DailyPnLTracker

        mock_state = AsyncMock()
        mock_state.fetchone = AsyncMock(return_value={"total": None})

        mock_manager = MagicMock()
        mock_manager.state = mock_state

        with patch(
            "app.infrastructure.daily_pnl.get_db_manager",
            return_value=mock_manager,
        ):
            tracker = DailyPnLTracker()
            result = await tracker.get_current_value()

        assert result == 0.0


class TestDailyPnLTrackerGetDailyPnL:
    """Test calculating daily P&L."""

    @pytest.mark.asyncio
    async def test_calculates_positive_pnl(self):
        """Test calculating positive P&L."""
        from app.infrastructure.daily_pnl import DailyPnLTracker

        mock_state = AsyncMock()
        # get_start_of_day_value returns 50000
        # get_current_value returns 52000
        mock_state.fetchone = AsyncMock(
            side_effect=[
                {"total_value": 50000.0, "date": "2024-01-14"},
                {"total": 52000.0},
            ]
        )

        mock_manager = MagicMock()
        mock_manager.state = mock_state

        with patch(
            "app.infrastructure.daily_pnl.get_db_manager",
            return_value=mock_manager,
        ):
            tracker = DailyPnLTracker()
            result = await tracker.get_daily_pnl()

        # (52000 - 50000) / 50000 = 0.04 = 4%
        assert result == pytest.approx(0.04, rel=0.01)

    @pytest.mark.asyncio
    async def test_calculates_negative_pnl(self):
        """Test calculating negative P&L."""
        from app.infrastructure.daily_pnl import DailyPnLTracker

        mock_state = AsyncMock()
        mock_state.fetchone = AsyncMock(
            side_effect=[
                {"total_value": 50000.0, "date": "2024-01-14"},
                {"total": 48000.0},
            ]
        )

        mock_manager = MagicMock()
        mock_manager.state = mock_state

        with patch(
            "app.infrastructure.daily_pnl.get_db_manager",
            return_value=mock_manager,
        ):
            tracker = DailyPnLTracker()
            result = await tracker.get_daily_pnl()

        # (48000 - 50000) / 50000 = -0.04 = -4%
        assert result == pytest.approx(-0.04, rel=0.01)

    @pytest.mark.asyncio
    async def test_returns_cached_value(self):
        """Test returning cached P&L value."""
        from app.infrastructure.daily_pnl import DailyPnLTracker

        mock_state = AsyncMock()
        mock_state.fetchone = AsyncMock(
            side_effect=[
                {"total_value": 50000.0, "date": "2024-01-14"},
                {"total": 52000.0},
            ]
        )

        mock_manager = MagicMock()
        mock_manager.state = mock_state

        with patch(
            "app.infrastructure.daily_pnl.get_db_manager",
            return_value=mock_manager,
        ):
            tracker = DailyPnLTracker()
            result1 = await tracker.get_daily_pnl()
            # Second call should use cache
            result2 = await tracker.get_daily_pnl()

        assert result1 == result2
        # Should only query database twice (for first call)
        assert mock_state.fetchone.call_count == 2

    @pytest.mark.asyncio
    async def test_returns_none_when_no_start_value(self):
        """Test returning None when start value unavailable."""
        from app.infrastructure.daily_pnl import DailyPnLTracker

        mock_state = AsyncMock()
        mock_state.fetchone = AsyncMock(return_value=None)

        mock_manager = MagicMock()
        mock_manager.state = mock_state

        with patch(
            "app.infrastructure.daily_pnl.get_db_manager",
            return_value=mock_manager,
        ):
            tracker = DailyPnLTracker()
            result = await tracker.get_daily_pnl()

        assert result is None


class TestDailyPnLTrackerCanBuy:
    """Test buy permission based on P&L."""

    @pytest.mark.asyncio
    async def test_allows_buy_in_normal_trading(self):
        """Test allowing buys during normal trading."""
        from app.infrastructure.daily_pnl import DailyPnLTracker

        mock_state = AsyncMock()
        mock_state.fetchone = AsyncMock(
            side_effect=[
                {"total_value": 50000.0, "date": "2024-01-14"},
                {"total": 51000.0},  # +2%
            ]
        )

        mock_manager = MagicMock()
        mock_manager.state = mock_state

        with patch(
            "app.infrastructure.daily_pnl.get_db_manager",
            return_value=mock_manager,
        ):
            tracker = DailyPnLTracker()
            allowed, reason = await tracker.can_buy()

        assert allowed is True
        assert "Normal" in reason

    @pytest.mark.asyncio
    async def test_allows_buy_during_moderate_drawdown(self):
        """Test allowing buys during moderate drawdown (buy the dip)."""
        from app.infrastructure.daily_pnl import DailyPnLTracker

        mock_state = AsyncMock()
        mock_state.fetchone = AsyncMock(
            side_effect=[
                {"total_value": 50000.0, "date": "2024-01-14"},
                {"total": 48000.0},  # -4% (moderate drawdown)
            ]
        )

        mock_manager = MagicMock()
        mock_manager.state = mock_state

        with patch(
            "app.infrastructure.daily_pnl.get_db_manager",
            return_value=mock_manager,
        ):
            tracker = DailyPnLTracker()
            allowed, reason = await tracker.can_buy()

        assert allowed is True
        assert "dip" in reason.lower()

    @pytest.mark.asyncio
    async def test_blocks_buy_during_severe_crash(self):
        """Test blocking buys during severe crash (>5% loss)."""
        from app.infrastructure.daily_pnl import DailyPnLTracker

        mock_state = AsyncMock()
        mock_state.fetchone = AsyncMock(
            side_effect=[
                {"total_value": 50000.0, "date": "2024-01-14"},
                {"total": 47000.0},  # -6% (severe)
            ]
        )

        mock_manager = MagicMock()
        mock_manager.state = mock_state

        with patch(
            "app.infrastructure.daily_pnl.get_db_manager",
            return_value=mock_manager,
        ):
            tracker = DailyPnLTracker()
            allowed, reason = await tracker.can_buy()

        assert allowed is False
        assert "halt" in reason.lower()


class TestDailyPnLTrackerCanSell:
    """Test sell permission based on P&L."""

    @pytest.mark.asyncio
    async def test_allows_sell_in_normal_trading(self):
        """Test allowing sells during normal trading."""
        from app.infrastructure.daily_pnl import DailyPnLTracker

        mock_state = AsyncMock()
        mock_state.fetchone = AsyncMock(
            side_effect=[
                {"total_value": 50000.0, "date": "2024-01-14"},
                {"total": 50500.0},  # +1%
            ]
        )

        mock_manager = MagicMock()
        mock_manager.state = mock_state

        with patch(
            "app.infrastructure.daily_pnl.get_db_manager",
            return_value=mock_manager,
        ):
            tracker = DailyPnLTracker()
            allowed, reason = await tracker.can_sell()

        assert allowed is True
        assert "Normal" in reason

    @pytest.mark.asyncio
    async def test_blocks_sell_during_moderate_drawdown(self):
        """Test blocking sells during moderate drawdown (>2% loss)."""
        from app.infrastructure.daily_pnl import DailyPnLTracker

        mock_state = AsyncMock()
        mock_state.fetchone = AsyncMock(
            side_effect=[
                {"total_value": 50000.0, "date": "2024-01-14"},
                {"total": 48500.0},  # -3% (moderate drawdown)
            ]
        )

        mock_manager = MagicMock()
        mock_manager.state = mock_state

        with patch(
            "app.infrastructure.daily_pnl.get_db_manager",
            return_value=mock_manager,
        ):
            tracker = DailyPnLTracker()
            allowed, reason = await tracker.can_sell()

        assert allowed is False
        assert "blocked" in reason.lower()


class TestDailyPnLTrackerGetTradingStatus:
    """Test comprehensive trading status."""

    @pytest.mark.asyncio
    async def test_normal_status(self):
        """Test normal trading status."""
        from app.infrastructure.daily_pnl import DailyPnLTracker

        mock_state = AsyncMock()
        mock_state.fetchone = AsyncMock(
            side_effect=[
                {"total_value": 50000.0, "date": "2024-01-14"},
                {"total": 51000.0},  # +2%
                # Additional calls for can_buy/can_sell
                {"total_value": 50000.0, "date": "2024-01-14"},
                {"total": 51000.0},
                {"total_value": 50000.0, "date": "2024-01-14"},
                {"total": 51000.0},
            ]
        )

        mock_manager = MagicMock()
        mock_manager.state = mock_state

        with patch(
            "app.infrastructure.daily_pnl.get_db_manager",
            return_value=mock_manager,
        ):
            tracker = DailyPnLTracker()
            status = await tracker.get_trading_status()

        assert status["status"] == "normal"
        assert status["can_buy"] is True
        assert status["can_sell"] is True
        assert status["pnl"] > 0

    @pytest.mark.asyncio
    async def test_unknown_status(self):
        """Test unknown status when P&L unavailable."""
        from app.infrastructure.daily_pnl import DailyPnLTracker

        mock_state = AsyncMock()
        mock_state.fetchone = AsyncMock(return_value=None)

        mock_manager = MagicMock()
        mock_manager.state = mock_state

        with patch(
            "app.infrastructure.daily_pnl.get_db_manager",
            return_value=mock_manager,
        ):
            tracker = DailyPnLTracker()
            status = await tracker.get_trading_status()

        assert status["status"] == "unknown"
        assert status["pnl"] is None
        assert status["can_buy"] is True
        assert status["can_sell"] is True


class TestGetDailyPnLTracker:
    """Test singleton getter."""

    def test_returns_same_instance(self):
        """Test that same instance is returned."""
        # Reset the singleton
        import app.infrastructure.daily_pnl
        from app.infrastructure.daily_pnl import (
            _tracker,
            get_daily_pnl_tracker,
        )

        app.infrastructure.daily_pnl._tracker = None

        with patch(
            "app.infrastructure.daily_pnl.get_db_manager",
            return_value=MagicMock(),
        ):
            tracker1 = get_daily_pnl_tracker()
            tracker2 = get_daily_pnl_tracker()

        assert tracker1 is tracker2
