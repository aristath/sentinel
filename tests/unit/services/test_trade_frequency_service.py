"""Tests for trade frequency service.

These tests validate trade frequency limiting to prevent excessive trading,
including minimum time between trades and daily/weekly limits.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from app.modules.trading.services.trade_frequency_service import TradeFrequencyService


class TestTradeFrequencyService:
    """Test TradeFrequencyService class."""

    @pytest.fixture
    def mock_trade_repo(self):
        """Mock TradeRepository."""
        repo = AsyncMock()
        return repo

    @pytest.fixture
    def mock_settings_repo(self):
        """Mock SettingsRepository."""
        repo = AsyncMock()
        repo.get_float = AsyncMock(return_value=1.0)  # Default: enabled
        return repo

    @pytest.fixture
    def service(self, mock_trade_repo, mock_settings_repo):
        """Create TradeFrequencyService with mocked dependencies."""
        return TradeFrequencyService(
            trade_repo=mock_trade_repo,
            settings_repo=mock_settings_repo,
        )

    @pytest.mark.asyncio
    async def test_allows_trade_when_limits_disabled(self, service, mock_settings_repo):
        """Test that trades are allowed when frequency limits are disabled."""
        mock_settings_repo.get_float.return_value = 0.0  # Disabled

        can_trade, reason = await service.can_execute_trade()

        assert can_trade is True
        assert reason is None

    @pytest.mark.asyncio
    async def test_allows_trade_when_no_previous_trades(self, service, mock_trade_repo):
        """Test that trades are allowed when there are no previous trades."""
        mock_trade_repo.get_last_trade_timestamp.return_value = None
        mock_trade_repo.get_trade_count_today.return_value = 0
        mock_trade_repo.get_trade_count_this_week.return_value = 0

        can_trade, reason = await service.can_execute_trade()

        assert can_trade is True
        assert reason is None

    @pytest.mark.asyncio
    async def test_blocks_trade_when_too_soon_after_last(
        self, service, mock_trade_repo, mock_settings_repo
    ):
        """Test that trades are blocked when too soon after last trade."""
        # Last trade was 30 minutes ago
        last_trade_time = datetime.now() - timedelta(minutes=30)
        mock_trade_repo.get_last_trade_timestamp.return_value = last_trade_time
        mock_trade_repo.get_trade_count_today.return_value = 0
        mock_trade_repo.get_trade_count_this_week.return_value = 0

        # Minimum time is 60 minutes
        mock_settings_repo.get_float.side_effect = lambda key, default: {
            "trade_frequency_limits_enabled": 1.0,
            "min_time_between_trades_minutes": 60.0,
            "max_trades_per_day": 4.0,
            "max_trades_per_week": 10.0,
        }.get(key, default)

        can_trade, reason = await service.can_execute_trade()

        assert can_trade is False
        assert (
            "minutes remaining" in reason.lower() or "between trades" in reason.lower()
        )

    @pytest.mark.asyncio
    async def test_allows_trade_after_minimum_time(
        self, service, mock_trade_repo, mock_settings_repo
    ):
        """Test that trades are allowed after minimum time has passed."""
        # Last trade was 2 hours ago
        last_trade_time = datetime.now() - timedelta(hours=2)
        mock_trade_repo.get_last_trade_timestamp.return_value = last_trade_time
        mock_trade_repo.get_trade_count_today.return_value = 0
        mock_trade_repo.get_trade_count_this_week.return_value = 0

        mock_settings_repo.get_float.side_effect = lambda key, default: {
            "trade_frequency_limits_enabled": 1.0,
            "min_time_between_trades_minutes": 60.0,
            "max_trades_per_day": 4.0,
            "max_trades_per_week": 10.0,
        }.get(key, default)

        can_trade, reason = await service.can_execute_trade()

        assert can_trade is True
        assert reason is None

    @pytest.mark.asyncio
    async def test_blocks_trade_when_daily_limit_reached(
        self, service, mock_trade_repo, mock_settings_repo
    ):
        """Test that trades are blocked when daily limit is reached."""
        mock_trade_repo.get_last_trade_timestamp.return_value = None
        mock_trade_repo.get_trade_count_today.return_value = 4  # At limit
        mock_trade_repo.get_trade_count_this_week.return_value = 4

        mock_settings_repo.get_float.side_effect = lambda key, default: {
            "trade_frequency_limits_enabled": 1.0,
            "min_time_between_trades_minutes": 60.0,
            "max_trades_per_day": 4.0,
            "max_trades_per_week": 10.0,
        }.get(key, default)

        can_trade, reason = await service.can_execute_trade()

        assert can_trade is False
        assert "daily" in reason.lower() or "limit reached" in reason.lower()

    @pytest.mark.asyncio
    async def test_allows_trade_below_daily_limit(
        self, service, mock_trade_repo, mock_settings_repo
    ):
        """Test that trades are allowed when below daily limit."""
        mock_trade_repo.get_last_trade_timestamp.return_value = None
        mock_trade_repo.get_trade_count_today.return_value = 2  # Below limit
        mock_trade_repo.get_trade_count_this_week.return_value = 2

        mock_settings_repo.get_float.side_effect = lambda key, default: {
            "trade_frequency_limits_enabled": 1.0,
            "min_time_between_trades_minutes": 60.0,
            "max_trades_per_day": 4.0,
            "max_trades_per_week": 10.0,
        }.get(key, default)

        can_trade, reason = await service.can_execute_trade()

        assert can_trade is True
        assert reason is None

    @pytest.mark.asyncio
    async def test_blocks_trade_when_weekly_limit_reached(
        self, service, mock_trade_repo, mock_settings_repo
    ):
        """Test that trades are blocked when weekly limit is reached."""
        mock_trade_repo.get_last_trade_timestamp.return_value = None
        mock_trade_repo.get_trade_count_today.return_value = 0
        mock_trade_repo.get_trade_count_this_week.return_value = 10  # At limit

        mock_settings_repo.get_float.side_effect = lambda key, default: {
            "trade_frequency_limits_enabled": 1.0,
            "min_time_between_trades_minutes": 60.0,
            "max_trades_per_day": 4.0,
            "max_trades_per_week": 10.0,
        }.get(key, default)

        can_trade, reason = await service.can_execute_trade()

        assert can_trade is False
        assert "weekly" in reason.lower() or "limit reached" in reason.lower()

    @pytest.mark.asyncio
    async def test_allows_trade_below_weekly_limit(
        self, service, mock_trade_repo, mock_settings_repo
    ):
        """Test that trades are allowed when below weekly limit."""
        mock_trade_repo.get_last_trade_timestamp.return_value = None
        mock_trade_repo.get_trade_count_today.return_value = 0
        mock_trade_repo.get_trade_count_this_week.return_value = 5  # Below limit

        mock_settings_repo.get_float.side_effect = lambda key, default: {
            "trade_frequency_limits_enabled": 1.0,
            "min_time_between_trades_minutes": 60.0,
            "max_trades_per_day": 4.0,
            "max_trades_per_week": 10.0,
        }.get(key, default)

        can_trade, reason = await service.can_execute_trade()

        assert can_trade is True
        assert reason is None

    @pytest.mark.asyncio
    async def test_checks_all_limits_in_order(
        self, service, mock_trade_repo, mock_settings_repo
    ):
        """Test that all limits are checked (time, daily, weekly)."""
        # Last trade was recent (should block on time first)
        last_trade_time = datetime.now() - timedelta(minutes=30)
        mock_trade_repo.get_last_trade_timestamp.return_value = last_trade_time
        mock_trade_repo.get_trade_count_today.return_value = 3
        mock_trade_repo.get_trade_count_this_week.return_value = 9

        mock_settings_repo.get_float.side_effect = lambda key, default: {
            "trade_frequency_limits_enabled": 1.0,
            "min_time_between_trades_minutes": 60.0,
            "max_trades_per_day": 4.0,
            "max_trades_per_week": 10.0,
        }.get(key, default)

        can_trade, reason = await service.can_execute_trade()

        # Should block on time limit first
        assert can_trade is False
        assert reason is not None

    @pytest.mark.asyncio
    async def test_handles_exception_gracefully(self, service, mock_trade_repo):
        """Test that exceptions are handled gracefully."""
        mock_trade_repo.get_last_trade_timestamp.side_effect = Exception(
            "Database error"
        )

        # Should not raise, but may return False or handle error
        can_trade, reason = await service.can_execute_trade()

        # Should return a result (either True or False with reason)
        assert isinstance(can_trade, bool)
        assert reason is None or isinstance(reason, str)
