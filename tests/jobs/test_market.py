"""Tests for jobs/market.py - Market checker."""

from unittest.mock import AsyncMock

import pytest

from sentinel.jobs.market import BrokerMarketChecker


class TestBrokerMarketChecker:
    """Tests for BrokerMarketChecker class."""

    @pytest.fixture
    def mock_broker(self):
        """Create a mock broker."""
        broker = AsyncMock()
        broker.get_market_status = AsyncMock(
            return_value={
                "m": [
                    {"n2": "NASDAQ", "s": "OPEN", "i": 1},
                    {"n2": "XETRA", "s": "CLOSED", "i": 2},
                    {"n2": "LSE", "s": "OPEN", "i": 3},
                ]
            }
        )
        return broker

    @pytest.mark.asyncio
    async def test_refresh_loads_market_data(self, mock_broker):
        """Verify refresh loads market data from broker."""
        checker = BrokerMarketChecker(mock_broker)
        await checker.refresh()

        mock_broker.get_market_status.assert_awaited_once_with("*")
        assert len(checker._market_data) == 3

    def test_is_any_market_open_true(self, mock_broker):
        """Verify is_any_market_open returns True when at least one market is open."""
        checker = BrokerMarketChecker(mock_broker)
        checker._market_data = {
            "NASDAQ": {"n2": "NASDAQ", "s": "OPEN"},
            "XETRA": {"n2": "XETRA", "s": "CLOSED"},
        }

        assert checker.is_any_market_open() is True

    def test_is_any_market_open_false(self, mock_broker):
        """Verify is_any_market_open returns False when all markets closed."""
        checker = BrokerMarketChecker(mock_broker)
        checker._market_data = {
            "NASDAQ": {"n2": "NASDAQ", "s": "CLOSED"},
            "XETRA": {"n2": "XETRA", "s": "CLOSED"},
        }

        assert checker.is_any_market_open() is False

    def test_are_all_markets_closed_true(self, mock_broker):
        """Verify are_all_markets_closed returns True when all markets closed."""
        checker = BrokerMarketChecker(mock_broker)
        checker._market_data = {
            "NASDAQ": {"n2": "NASDAQ", "s": "CLOSED"},
            "XETRA": {"n2": "XETRA", "s": "CLOSED"},
        }

        assert checker.are_all_markets_closed() is True

    def test_are_all_markets_closed_false(self, mock_broker):
        """Verify are_all_markets_closed returns False when any market open."""
        checker = BrokerMarketChecker(mock_broker)
        checker._market_data = {
            "NASDAQ": {"n2": "NASDAQ", "s": "OPEN"},
            "XETRA": {"n2": "XETRA", "s": "CLOSED"},
        }

        assert checker.are_all_markets_closed() is False

    def test_are_all_markets_closed_empty(self, mock_broker):
        """Verify are_all_markets_closed returns True when no market data."""
        checker = BrokerMarketChecker(mock_broker)
        checker._market_data = {}

        assert checker.are_all_markets_closed() is True

    def test_is_security_market_open_us(self, mock_broker):
        """Verify is_security_market_open works for US securities."""
        checker = BrokerMarketChecker(mock_broker)
        checker._market_data = {
            "NASDAQ": {"n2": "NASDAQ", "s": "OPEN"},
        }

        assert checker.is_security_market_open("AAPL.US") is True

    def test_is_security_market_open_gr(self, mock_broker):
        """Verify is_security_market_open works for German securities."""
        checker = BrokerMarketChecker(mock_broker)
        checker._market_data = {
            "XETRA": {"n2": "XETRA", "s": "CLOSED"},
        }

        assert checker.is_security_market_open("VOW.GR") is False

    def test_is_security_market_open_no_suffix(self, mock_broker):
        """Verify is_security_market_open returns False for symbol without suffix."""
        checker = BrokerMarketChecker(mock_broker)
        checker._market_data = {
            "NASDAQ": {"n2": "NASDAQ", "s": "OPEN"},
        }

        assert checker.is_security_market_open("AAPL") is False

    @pytest.mark.asyncio
    async def test_ensure_fresh_refreshes_when_stale(self, mock_broker):
        """Verify ensure_fresh calls refresh when data is stale."""
        checker = BrokerMarketChecker(mock_broker)
        # No last_fetch = stale
        assert checker._is_stale() is True

        await checker.ensure_fresh()
        mock_broker.get_market_status.assert_awaited_once()
