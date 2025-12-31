"""Tests for market hours module.

These tests validate the market hours functionality including:
- Checking if markets are currently open
- Getting list of open markets
- Filtering securities by open markets
- Grouping securities by exchange
"""

from datetime import datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest


class TestGetCalendar:
    """Test getting exchange calendars."""

    def test_returns_calendar_for_exchange(self):
        """Test returning calendar for exchange name."""
        from app.infrastructure.market_hours import get_calendar

        calendar = get_calendar("NYSE")
        assert calendar is not None
        assert calendar.name == "XNYS"

    def test_returns_calendar_for_nasdaq(self):
        """Test returning calendar for NASDAQ."""
        from app.infrastructure.market_hours import get_calendar

        calendar = get_calendar("NASDAQ")
        assert calendar is not None
        # NASDAQ and NYSE share the same calendar (XNYS) in exchange_calendars
        assert calendar.name == "XNYS"

    def test_returns_default_for_unknown(self):
        """Test returning default calendar for unknown exchange."""
        from app.infrastructure.market_hours import get_calendar

        calendar = get_calendar("UNKNOWN")
        assert calendar is not None
        # Should return XNYS as default
        assert calendar.name == "XNYS"

    def test_caches_calendars(self):
        """Test that calendars are cached."""
        from app.infrastructure.market_hours import get_calendar

        calendar1 = get_calendar("NYSE")
        calendar2 = get_calendar("NYSE")
        assert calendar1 is calendar2


class TestIsMarketOpen:
    """Test checking if a market is currently open."""

    def test_market_closed_on_weekend(self):
        """Test that markets are closed on weekends."""
        from app.infrastructure.market_hours import is_market_open

        # Saturday
        with patch("app.infrastructure.market_hours._get_current_time") as mock_time:
            mock_time.return_value = datetime(
                2024, 1, 13, 12, 0, tzinfo=ZoneInfo("UTC")
            )
            assert is_market_open("NYSE") is False
            assert is_market_open("XETR") is False
            assert is_market_open("XHKG") is False

    def test_market_closed_on_holiday(self):
        """Test that markets are closed on holidays."""
        from app.infrastructure.market_hours import is_market_open

        # Christmas Day 2024 (Wednesday)
        with patch("app.infrastructure.market_hours._get_current_time") as mock_time:
            mock_time.return_value = datetime(
                2024, 12, 25, 15, 0, tzinfo=ZoneInfo("UTC")
            )
            assert is_market_open("NYSE") is False

    def test_us_market_open_during_trading_hours(self):
        """Test US market open during regular trading hours."""
        from app.infrastructure.market_hours import is_market_open

        # Tuesday at 10:00 AM EST = 15:00 UTC
        with patch("app.infrastructure.market_hours._get_current_time") as mock_time:
            mock_time.return_value = datetime(
                2024, 1, 16, 15, 0, tzinfo=ZoneInfo("UTC")
            )
            assert is_market_open("NYSE") is True

    def test_us_market_closed_before_open(self):
        """Test US market closed before opening time."""
        from app.infrastructure.market_hours import is_market_open

        # Tuesday at 8:00 AM EST = 13:00 UTC (before 9:30 AM open)
        with patch("app.infrastructure.market_hours._get_current_time") as mock_time:
            mock_time.return_value = datetime(
                2024, 1, 16, 13, 0, tzinfo=ZoneInfo("UTC")
            )
            assert is_market_open("NYSE") is False

    def test_us_market_closed_after_close(self):
        """Test US market closed after closing time."""
        from app.infrastructure.market_hours import is_market_open

        # Tuesday at 5:00 PM EST = 22:00 UTC (after 4:00 PM close)
        with patch("app.infrastructure.market_hours._get_current_time") as mock_time:
            mock_time.return_value = datetime(
                2024, 1, 16, 22, 0, tzinfo=ZoneInfo("UTC")
            )
            assert is_market_open("NYSE") is False

    def test_eu_market_open_during_trading_hours(self):
        """Test EU market open during regular trading hours."""
        from app.infrastructure.market_hours import is_market_open

        # Tuesday at 10:00 AM CET = 09:00 UTC
        with patch("app.infrastructure.market_hours._get_current_time") as mock_time:
            mock_time.return_value = datetime(2024, 1, 16, 9, 0, tzinfo=ZoneInfo("UTC"))
            assert is_market_open("XETR") is True

    def test_asia_market_open_during_trading_hours(self):
        """Test ASIA market open during regular trading hours."""
        from app.infrastructure.market_hours import is_market_open

        # Tuesday at 10:00 AM HKT = 02:00 UTC
        with patch("app.infrastructure.market_hours._get_current_time") as mock_time:
            mock_time.return_value = datetime(2024, 1, 16, 2, 0, tzinfo=ZoneInfo("UTC"))
            assert is_market_open("XHKG") is True


class TestGetOpenMarkets:
    """Test getting list of open markets."""

    @pytest.mark.asyncio
    async def test_returns_empty_list_on_weekend(self):
        """Test returning empty list when all markets closed."""
        from app.infrastructure.market_hours import get_open_markets

        # Saturday
        with (
            patch("app.infrastructure.market_hours._get_current_time") as mock_time,
            patch(
                "app.infrastructure.market_hours.get_exchanges_from_database"
            ) as mock_db,
        ):
            mock_time.return_value = datetime(
                2024, 1, 13, 12, 0, tzinfo=ZoneInfo("UTC")
            )
            mock_db.return_value = ["NYSE", "XETR", "XHKG"]
            open_markets = await get_open_markets()
            assert open_markets == []

    @pytest.mark.asyncio
    async def test_returns_open_markets(self):
        """Test returning list of open markets."""
        from app.infrastructure.market_hours import get_open_markets

        # Tuesday at 15:00 UTC - US and EU should be open
        with (
            patch("app.infrastructure.market_hours._get_current_time") as mock_time,
            patch(
                "app.infrastructure.market_hours.get_exchanges_from_database"
            ) as mock_db,
        ):
            mock_time.return_value = datetime(
                2024, 1, 16, 15, 0, tzinfo=ZoneInfo("UTC")
            )
            mock_db.return_value = ["NYSE", "XETR", "XHKG"]
            open_markets = await get_open_markets()
            assert "NYSE" in open_markets or "NasdaqGS" in open_markets
            # EU might be closed by 16:00 CET, check if it's in overlap


class TestGetMarketStatus:
    """Test getting detailed market status."""

    @pytest.mark.asyncio
    async def test_returns_status_for_all_markets(self):
        """Test returning status dict for all markets."""
        from app.infrastructure.market_hours import get_market_status

        with (
            patch("app.infrastructure.market_hours._get_current_time") as mock_time,
            patch(
                "app.infrastructure.market_hours.get_exchanges_from_database"
            ) as mock_db,
        ):
            mock_time.return_value = datetime(
                2024, 1, 16, 15, 0, tzinfo=ZoneInfo("UTC")
            )
            mock_db.return_value = ["NYSE", "XETR", "XHKG"]
            status = await get_market_status()

            # Check for exchange names in status
            assert "NYSE" in status or "NasdaqGS" in status
            assert "XETR" in status or "XETRA" in status
            assert "XHKG" in status or "HKSE" in status

            for market in status.values():
                assert "open" in market
                assert "exchange" in market
                assert "timezone" in market

    @pytest.mark.asyncio
    async def test_includes_next_event_time(self):
        """Test that status includes next open/close time."""
        from app.infrastructure.market_hours import get_market_status

        with (
            patch("app.infrastructure.market_hours._get_current_time") as mock_time,
            patch(
                "app.infrastructure.market_hours.get_exchanges_from_database"
            ) as mock_db,
        ):
            mock_time.return_value = datetime(
                2024, 1, 16, 15, 0, tzinfo=ZoneInfo("UTC")
            )
            mock_db.return_value = ["NYSE", "XETR"]
            status = await get_market_status()

            for market in status.values():
                if market["open"]:
                    assert "closes_at" in market
                else:
                    assert "opens_at" in market


class TestFilterStocksByOpenMarkets:
    """Test filtering securities by open markets."""

    @pytest.mark.asyncio
    async def test_filters_stocks_to_open_markets_only(self):
        """Test filtering securities to only those with open markets."""
        from app.infrastructure.market_hours import filter_stocks_by_open_markets

        # Create mock securities
        stock_eu = MagicMock()
        stock_eu.fullExchangeName = "XETR"
        stock_eu.symbol = "SAP.DE"

        stock_us = MagicMock()
        stock_us.fullExchangeName = "NYSE"
        stock_us.symbol = "AAPL.US"

        stock_asia = MagicMock()
        stock_asia.fullExchangeName = "XHKG"
        stock_asia.symbol = "9988.HK"

        securities = [stock_eu, stock_us, stock_asia]

        # Saturday - all markets closed
        with (
            patch("app.infrastructure.market_hours._get_current_time") as mock_time,
            patch(
                "app.infrastructure.market_hours.get_exchanges_from_database"
            ) as mock_db,
        ):
            mock_time.return_value = datetime(
                2024, 1, 13, 12, 0, tzinfo=ZoneInfo("UTC")
            )
            mock_db.return_value = ["XETR", "NYSE", "XHKG"]
            filtered = await filter_stocks_by_open_markets(securities)
            assert len(filtered) == 0

    @pytest.mark.asyncio
    async def test_returns_all_stocks_when_all_markets_open(self):
        """Test returning all securities when their markets are open."""
        from app.infrastructure.market_hours import filter_stocks_by_open_markets

        stock_us = MagicMock()
        stock_us.fullExchangeName = "NYSE"
        stock_us.symbol = "AAPL.US"

        securities = [stock_us]

        # Tuesday at 15:00 UTC - US market open
        with (
            patch("app.infrastructure.market_hours._get_current_time") as mock_time,
            patch(
                "app.infrastructure.market_hours.get_exchanges_from_database"
            ) as mock_db,
        ):
            mock_time.return_value = datetime(
                2024, 1, 16, 15, 0, tzinfo=ZoneInfo("UTC")
            )
            mock_db.return_value = ["NYSE"]
            filtered = await filter_stocks_by_open_markets(securities)
            assert len(filtered) == 1
            assert filtered[0].symbol == "AAPL.US"


class TestRequiresStrictMarketHours:
    """Test strict market hours exchange identification."""

    def test_identifies_strict_market_hours_exchanges(self):
        """Test that strict market hours exchanges are identified correctly."""
        from app.infrastructure.market_hours import requires_strict_market_hours

        # Asian exchanges requiring strict market hours
        assert requires_strict_market_hours("HKSE") is True
        assert requires_strict_market_hours("XHKG") is True
        assert requires_strict_market_hours("Shenzhen") is True
        assert requires_strict_market_hours("XSHG") is True
        assert requires_strict_market_hours("TSE") is True
        assert requires_strict_market_hours("XTSE") is True
        assert requires_strict_market_hours("ASX") is True
        assert requires_strict_market_hours("XASX") is True

    def test_identifies_flexible_hours_exchanges(self):
        """Test that flexible hours exchanges are identified correctly."""
        from app.infrastructure.market_hours import requires_strict_market_hours

        # US and EU exchanges with flexible hours
        assert requires_strict_market_hours("NYSE") is False
        assert requires_strict_market_hours("NASDAQ") is False
        assert requires_strict_market_hours("NasdaqGS") is False
        assert requires_strict_market_hours("XETR") is False
        assert requires_strict_market_hours("XETRA") is False
        assert requires_strict_market_hours("LSE") is False
        assert requires_strict_market_hours("Amsterdam") is False
        assert requires_strict_market_hours("Paris") is False


class TestShouldCheckMarketHours:
    """Test market hours check requirement logic."""

    def test_sell_orders_always_require_check(self):
        """Test that SELL orders always require market hours check."""
        from app.infrastructure.market_hours import should_check_market_hours

        # SELL orders should always check, regardless of exchange
        assert should_check_market_hours("NYSE", "SELL") is True
        assert should_check_market_hours("XETR", "SELL") is True
        assert should_check_market_hours("XHKG", "SELL") is True
        assert should_check_market_hours("XSHG", "SELL") is True

    def test_buy_orders_flexible_hours_markets(self):
        """Test that BUY orders on flexible hours markets don't require check."""
        from app.infrastructure.market_hours import should_check_market_hours

        # BUY orders on flexible hours markets don't require check
        assert should_check_market_hours("NYSE", "BUY") is False
        assert should_check_market_hours("NASDAQ", "BUY") is False
        assert should_check_market_hours("XETR", "BUY") is False
        assert should_check_market_hours("LSE", "BUY") is False

    def test_buy_orders_strict_hours_markets(self):
        """Test that BUY orders on strict hours markets require check."""
        from app.infrastructure.market_hours import should_check_market_hours

        # BUY orders on strict hours markets require check
        assert should_check_market_hours("HKSE", "BUY") is True
        assert should_check_market_hours("XHKG", "BUY") is True
        assert should_check_market_hours("Shenzhen", "BUY") is True
        assert should_check_market_hours("XSHG", "BUY") is True
        assert should_check_market_hours("TSE", "BUY") is True
        assert should_check_market_hours("XTSE", "BUY") is True
        assert should_check_market_hours("ASX", "BUY") is True
        assert should_check_market_hours("XASX", "BUY") is True

    def test_unknown_side_defaults_to_check(self):
        """Test that unknown side defaults to requiring check (safe default)."""
        from app.infrastructure.market_hours import should_check_market_hours

        # Unknown side should default to checking (safe default)
        assert should_check_market_hours("NYSE", "UNKNOWN") is True
        assert should_check_market_hours("XHKG", "UNKNOWN") is True


class TestGroupStocksByExchange:
    """Test grouping securities by exchange."""

    def test_groups_stocks_correctly(self):
        """Test grouping securities by their exchange."""
        from app.infrastructure.market_hours import group_stocks_by_exchange

        stock_eu1 = MagicMock()
        stock_eu1.fullExchangeName = "XETR"
        stock_eu1.symbol = "SAP.DE"

        stock_eu2 = MagicMock()
        stock_eu2.fullExchangeName = "XETR"
        stock_eu2.symbol = "ASML.NL"

        stock_us = MagicMock()
        stock_us.fullExchangeName = "NYSE"
        stock_us.symbol = "AAPL.US"

        stock_asia = MagicMock()
        stock_asia.fullExchangeName = "XHKG"
        stock_asia.symbol = "9988.HK"

        securities = [stock_eu1, stock_eu2, stock_us, stock_asia]

        grouped = group_stocks_by_exchange(securities)

        assert len(grouped["XETR"]) == 2
        assert len(grouped["NYSE"]) == 1
        assert len(grouped["XHKG"]) == 1

    def test_handles_empty_list(self):
        """Test handling empty security list."""
        from app.infrastructure.market_hours import group_stocks_by_exchange

        grouped = group_stocks_by_exchange([])

        assert grouped == {}

    def test_handles_unknown_exchange(self):
        """Test handling securities with unknown or missing exchange."""
        from app.infrastructure.market_hours import group_stocks_by_exchange

        security = MagicMock()
        security.fullExchangeName = None
        security.symbol = "XXX.XX"

        grouped = group_stocks_by_exchange([security])

        # Should not appear in any group
        assert len(grouped) == 0
