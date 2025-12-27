"""Tests for historical data sync job.

These tests validate historical price fetching from Yahoo Finance
and storage in per-symbol databases.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestSyncHistoricalData:
    """Test main sync function with file lock."""

    @pytest.mark.asyncio
    async def test_uses_file_lock(self):
        """Test that file lock is used."""
        from app.jobs.historical_data_sync import sync_historical_data

        with (
            patch("app.jobs.historical_data_sync.file_lock") as mock_lock,
            patch(
                "app.jobs.historical_data_sync._sync_historical_data_internal"
            ) as mock_internal,
        ):
            mock_lock.return_value.__aenter__ = AsyncMock()
            mock_lock.return_value.__aexit__ = AsyncMock()

            await sync_historical_data()

            mock_lock.assert_called_once_with("historical_data_sync", timeout=3600.0)
            mock_internal.assert_called_once()


class TestSyncHistoricalDataInternal:
    """Test internal sync implementation."""

    @pytest.mark.asyncio
    async def test_emits_sync_events(self):
        """Test that sync events are emitted."""
        from app.jobs.historical_data_sync import _sync_historical_data_internal

        with (
            patch(
                "app.jobs.historical_data_sync._sync_stock_price_history"
            ) as mock_sync,
            patch("app.jobs.historical_data_sync.emit") as mock_emit,
            patch("app.jobs.historical_data_sync.clear_processing"),
        ):
            await _sync_historical_data_internal()

            # Should emit SYNC_START and SYNC_COMPLETE
            assert mock_emit.call_count >= 2
            mock_sync.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_sync_error(self):
        """Test error handling during sync."""
        from app.jobs.historical_data_sync import _sync_historical_data_internal

        with (
            patch(
                "app.jobs.historical_data_sync._sync_stock_price_history",
                side_effect=Exception("Sync failed"),
            ),
            patch("app.jobs.historical_data_sync.emit") as mock_emit,
            patch("app.jobs.historical_data_sync.set_error") as mock_set_error,
            patch("app.jobs.historical_data_sync.clear_processing"),
        ):
            with pytest.raises(Exception, match="Sync failed"):
                await _sync_historical_data_internal()

            mock_set_error.assert_called_once()


class TestSyncStockPriceHistory:
    """Test stock price history sync."""

    @pytest.mark.asyncio
    async def test_skips_when_no_active_stocks(self):
        """Test that sync is skipped when no active stocks."""
        from app.jobs.historical_data_sync import _sync_stock_price_history

        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = []

        mock_config = AsyncMock()
        mock_config.execute.return_value = mock_cursor

        mock_db_manager = MagicMock()
        mock_db_manager.config = mock_config

        with (
            patch(
                "app.jobs.historical_data_sync.get_db_manager",
                return_value=mock_db_manager,
            ),
            patch("app.jobs.historical_data_sync.set_processing"),
        ):
            await _sync_stock_price_history()

            # Should only call execute once (to get active stocks)
            mock_config.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_processes_active_stocks(self):
        """Test processing active stocks."""
        from app.jobs.historical_data_sync import _sync_stock_price_history

        # Config cursor returns active stocks
        mock_config_cursor = AsyncMock()
        mock_config_cursor.fetchall.return_value = [
            ("AAPL.US", "AAPL"),
            ("MSFT.US", "MSFT"),
        ]

        mock_config = AsyncMock()
        mock_config.execute.return_value = mock_config_cursor

        # History cursor returns recent date (skip processing)
        mock_history_cursor = AsyncMock()
        mock_history_cursor.fetchone.return_value = (
            (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d"),
        )

        mock_history_db = AsyncMock()
        mock_history_db.execute.return_value = mock_history_cursor

        mock_db_manager = MagicMock()
        mock_db_manager.config = mock_config
        mock_db_manager.history = AsyncMock(return_value=mock_history_db)

        mock_settings = MagicMock()
        mock_settings.external_api_rate_limit_delay = 0.1

        with (
            patch(
                "app.jobs.historical_data_sync.get_db_manager",
                return_value=mock_db_manager,
            ),
            patch("app.jobs.historical_data_sync.settings", mock_settings),
            patch("app.jobs.historical_data_sync.set_processing"),
        ):
            await _sync_stock_price_history()

            # Should call history() for each stock
            assert mock_db_manager.history.call_count == 2

    @pytest.mark.asyncio
    async def test_fetches_prices_when_data_outdated(self):
        """Test that prices are fetched when data is outdated."""
        from app.jobs.historical_data_sync import _sync_stock_price_history

        # Config cursor returns active stocks
        mock_config_cursor = AsyncMock()
        mock_config_cursor.fetchall.return_value = [("AAPL.US", "AAPL")]

        mock_config = AsyncMock()
        mock_config.execute.return_value = mock_config_cursor

        # History cursor returns old date (needs update)
        mock_history_cursor = AsyncMock()
        mock_history_cursor.fetchone.return_value = ("2020-01-01",)

        mock_history_db = AsyncMock()
        mock_history_db.execute.return_value = mock_history_cursor

        mock_db_manager = MagicMock()
        mock_db_manager.config = mock_config
        mock_db_manager.history = AsyncMock(return_value=mock_history_db)

        mock_settings = MagicMock()
        mock_settings.external_api_rate_limit_delay = 0

        with (
            patch(
                "app.jobs.historical_data_sync.get_db_manager",
                return_value=mock_db_manager,
            ),
            patch("app.jobs.historical_data_sync.settings", mock_settings),
            patch("app.jobs.historical_data_sync.set_processing"),
            patch(
                "app.jobs.historical_data_sync._fetch_and_store_prices"
            ) as mock_fetch,
        ):
            await _sync_stock_price_history()

            mock_fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_stock_sync_error(self):
        """Test handling error during individual stock sync."""
        from app.jobs.historical_data_sync import _sync_stock_price_history

        # Config cursor returns active stocks
        mock_config_cursor = AsyncMock()
        mock_config_cursor.fetchall.return_value = [("AAPL.US", "AAPL")]

        mock_config = AsyncMock()
        mock_config.execute.return_value = mock_config_cursor

        mock_db_manager = MagicMock()
        mock_db_manager.config = mock_config
        mock_db_manager.history = AsyncMock(side_effect=Exception("DB error"))

        mock_settings = MagicMock()
        mock_settings.external_api_rate_limit_delay = 0

        with (
            patch(
                "app.jobs.historical_data_sync.get_db_manager",
                return_value=mock_db_manager,
            ),
            patch("app.jobs.historical_data_sync.settings", mock_settings),
            patch("app.jobs.historical_data_sync.set_processing"),
        ):
            # Should not raise - errors are caught and logged
            await _sync_stock_price_history()


class TestFetchAndStorePrices:
    """Test fetching and storing prices."""

    @pytest.mark.asyncio
    async def test_uses_1y_period_when_monthly_exists(self):
        """Test using 1 year period when monthly data exists."""
        from contextlib import asynccontextmanager

        from app.jobs.historical_data_sync import _fetch_and_store_prices

        mock_cursor = AsyncMock()
        mock_cursor.fetchone.return_value = (10,)  # Has monthly data

        @asynccontextmanager
        async def mock_transaction():
            yield

        mock_history_db = AsyncMock()
        mock_history_db.execute.return_value = mock_cursor
        mock_history_db.transaction = mock_transaction

        mock_ohlc = MagicMock()
        mock_ohlc.date = datetime.now()
        mock_ohlc.open = 100.0
        mock_ohlc.high = 105.0
        mock_ohlc.low = 95.0
        mock_ohlc.close = 102.0
        mock_ohlc.volume = 1000000

        with patch(
            "app.jobs.historical_data_sync.yahoo.get_historical_prices",
            return_value=[mock_ohlc],
        ) as mock_yahoo:
            await _fetch_and_store_prices(mock_history_db, "AAPL.US", "AAPL")

            # Should use 1y period when monthly exists
            mock_yahoo.assert_called_once_with("AAPL.US", "AAPL", period="1y")

    @pytest.mark.asyncio
    async def test_uses_10y_period_for_initial_seed(self):
        """Test using 10 year period for initial data seeding."""
        from contextlib import asynccontextmanager

        from app.jobs.historical_data_sync import _fetch_and_store_prices

        mock_cursor = AsyncMock()
        mock_cursor.fetchone.return_value = (0,)  # No monthly data

        @asynccontextmanager
        async def mock_transaction():
            yield

        mock_history_db = AsyncMock()
        mock_history_db.execute.return_value = mock_cursor
        mock_history_db.transaction = mock_transaction

        mock_ohlc = MagicMock()
        mock_ohlc.date = datetime.now()
        mock_ohlc.open = 100.0
        mock_ohlc.high = 105.0
        mock_ohlc.low = 95.0
        mock_ohlc.close = 102.0
        mock_ohlc.volume = 1000000

        with patch(
            "app.jobs.historical_data_sync.yahoo.get_historical_prices",
            return_value=[mock_ohlc],
        ) as mock_yahoo:
            await _fetch_and_store_prices(mock_history_db, "AAPL.US", "AAPL")

            # Should use 10y period for initial seed
            mock_yahoo.assert_called_once_with("AAPL.US", "AAPL", period="10y")

    @pytest.mark.asyncio
    async def test_handles_no_data_from_yahoo(self):
        """Test handling when Yahoo returns no data."""
        from app.jobs.historical_data_sync import _fetch_and_store_prices

        mock_cursor = AsyncMock()
        mock_cursor.fetchone.return_value = (0,)

        mock_history_db = AsyncMock()
        mock_history_db.execute.return_value = mock_cursor

        with patch(
            "app.jobs.historical_data_sync.yahoo.get_historical_prices",
            return_value=None,
        ):
            # Should not raise
            await _fetch_and_store_prices(mock_history_db, "AAPL.US", "AAPL")

    @pytest.mark.asyncio
    async def test_stores_ohlc_data(self):
        """Test that OHLC data is stored correctly."""
        from contextlib import asynccontextmanager

        from app.jobs.historical_data_sync import _fetch_and_store_prices

        mock_cursor = AsyncMock()
        mock_cursor.fetchone.return_value = (5,)  # Has some monthly data

        @asynccontextmanager
        async def mock_transaction():
            yield

        mock_history_db = AsyncMock()
        mock_history_db.execute.return_value = mock_cursor
        mock_history_db.transaction = mock_transaction

        mock_ohlc = MagicMock()
        mock_ohlc.date = datetime(2024, 1, 15)
        mock_ohlc.open = 100.0
        mock_ohlc.high = 105.0
        mock_ohlc.low = 95.0
        mock_ohlc.close = 102.0
        mock_ohlc.volume = 1000000

        with patch(
            "app.jobs.historical_data_sync.yahoo.get_historical_prices",
            return_value=[mock_ohlc],
        ):
            await _fetch_and_store_prices(mock_history_db, "AAPL.US", "AAPL")

            # Should have executed INSERT
            assert mock_history_db.execute.call_count >= 2

    @pytest.mark.asyncio
    async def test_raises_on_fetch_error(self):
        """Test that fetch errors are raised."""
        from app.jobs.historical_data_sync import _fetch_and_store_prices

        mock_cursor = AsyncMock()
        mock_cursor.fetchone.return_value = (0,)

        mock_history_db = AsyncMock()
        mock_history_db.execute.return_value = mock_cursor

        with patch(
            "app.jobs.historical_data_sync.yahoo.get_historical_prices",
            side_effect=Exception("Yahoo API error"),
        ):
            with pytest.raises(Exception, match="Yahoo API error"):
                await _fetch_and_store_prices(mock_history_db, "AAPL.US", "AAPL")


class TestAggregateToMonthly:
    """Test monthly aggregation."""

    @pytest.mark.asyncio
    async def test_executes_aggregation_query(self):
        """Test that aggregation query is executed."""
        from app.jobs.historical_data_sync import _aggregate_to_monthly

        mock_history_db = AsyncMock()

        await _aggregate_to_monthly(mock_history_db)

        mock_history_db.execute.assert_called_once()
        # Verify the query contains expected elements
        call_args = mock_history_db.execute.call_args[0][0]
        assert "INSERT OR REPLACE INTO monthly_prices" in call_args
        assert "AVG(close_price)" in call_args
