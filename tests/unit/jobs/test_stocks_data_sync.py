"""Tests for the stocks data sync job.

The stocks data sync runs hourly and processes stocks sequentially:
1. Only processes stocks not updated in 24 hours (last_synced)
2. For each stock: sync historical data, calculate metrics, refresh score
3. Updates LED display with "UPDATING {SYMBOL} DATA"
4. Updates last_synced after successful processing
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestStocksDataSync:
    """Test the main daily pipeline orchestration."""

    @pytest.mark.asyncio
    async def test_processes_only_stale_stocks(self):
        """Test that only stocks not synced in 24 hours are processed."""
        from app.jobs.stocks_data_sync import _get_stocks_needing_sync

        now = datetime.now()
        stale_time = (now - timedelta(hours=25)).isoformat()
        fresh_time = (now - timedelta(hours=12)).isoformat()

        mock_stocks = [
            MagicMock(symbol="STALE.DE", last_synced=stale_time),
            MagicMock(symbol="FRESH.US", last_synced=fresh_time),
            MagicMock(symbol="NEVER.HK", last_synced=None),  # Never synced
        ]

        with patch(
            "app.jobs.stocks_data_sync._get_all_active_stocks",
            new_callable=AsyncMock,
            return_value=mock_stocks,
        ):
            stocks_to_sync = await _get_stocks_needing_sync()

        # Only stale and never-synced stocks should be returned
        symbols = [s.symbol for s in stocks_to_sync]
        assert "STALE.DE" in symbols
        assert "NEVER.HK" in symbols
        assert "FRESH.US" not in symbols

    @pytest.mark.asyncio
    async def test_processes_stocks_sequentially(self):
        """Test that stocks are processed one at a time, not in parallel."""
        from app.jobs.stocks_data_sync import run_stocks_data_sync

        processed_order = []

        async def mock_process_stock(symbol):
            processed_order.append(symbol)

        mock_stocks = [
            MagicMock(symbol="AAA.DE", last_synced=None),
            MagicMock(symbol="BBB.US", last_synced=None),
            MagicMock(symbol="CCC.HK", last_synced=None),
        ]

        with (
            patch(
                "app.jobs.stocks_data_sync._get_stocks_needing_sync",
                new_callable=AsyncMock,
                return_value=mock_stocks,
            ),
            patch(
                "app.jobs.stocks_data_sync._process_single_stock",
                new_callable=AsyncMock,
                side_effect=mock_process_stock,
            ),
            patch("app.jobs.stocks_data_sync.file_lock", new_callable=MagicMock),
        ):
            mock_lock = AsyncMock()
            mock_lock.__aenter__ = AsyncMock()
            mock_lock.__aexit__ = AsyncMock()
            with patch("app.jobs.stocks_data_sync.file_lock", return_value=mock_lock):
                await run_stocks_data_sync()

        # All stocks should be processed in order
        assert processed_order == ["AAA.DE", "BBB.US", "CCC.HK"]

    @pytest.mark.asyncio
    async def test_skips_all_when_all_stocks_fresh(self):
        """Test that no processing happens when all stocks are fresh."""
        from app.jobs.stocks_data_sync import run_stocks_data_sync

        process_called = False

        async def mock_process_stock(symbol):
            nonlocal process_called
            process_called = True

        with (
            patch(
                "app.jobs.stocks_data_sync._get_stocks_needing_sync",
                new_callable=AsyncMock,
                return_value=[],  # No stale stocks
            ),
            patch(
                "app.jobs.stocks_data_sync._process_single_stock",
                new_callable=AsyncMock,
                side_effect=mock_process_stock,
            ),
            patch("app.jobs.stocks_data_sync.file_lock", new_callable=MagicMock),
        ):
            mock_lock = AsyncMock()
            mock_lock.__aenter__ = AsyncMock()
            mock_lock.__aexit__ = AsyncMock()
            with patch("app.jobs.stocks_data_sync.file_lock", return_value=mock_lock):
                await run_stocks_data_sync()

        assert process_called is False


class TestProcessSingleStock:
    """Test the per-stock processing pipeline."""

    @pytest.mark.asyncio
    async def test_runs_all_steps_for_stock(self):
        """Test that all three steps run for each stock."""
        from app.jobs.stocks_data_sync import _process_single_stock

        steps_run = []

        async def mock_sync_historical(symbol):
            steps_run.append(("historical", symbol))

        async def mock_calculate_metrics(symbol):
            steps_run.append(("metrics", symbol))
            return 5

        async def mock_refresh_score(symbol):
            steps_run.append(("score", symbol))

        with (
            patch(
                "app.jobs.stocks_data_sync._sync_historical_for_symbol",
                new_callable=AsyncMock,
                side_effect=mock_sync_historical,
            ),
            patch(
                "app.jobs.stocks_data_sync._detect_and_update_country_and_exchange",
                new_callable=AsyncMock,
            ),
            patch(
                "app.jobs.stocks_data_sync._detect_and_update_industry",
                new_callable=AsyncMock,
            ),
            patch(
                "app.jobs.stocks_data_sync._calculate_metrics_for_symbol",
                new_callable=AsyncMock,
                side_effect=mock_calculate_metrics,
            ),
            patch(
                "app.jobs.stocks_data_sync._refresh_score_for_symbol",
                new_callable=AsyncMock,
                side_effect=mock_refresh_score,
            ),
            patch(
                "app.jobs.stocks_data_sync._update_last_synced", new_callable=AsyncMock
            ),
            patch("app.jobs.stocks_data_sync.set_text"),
            patch("pass  # LED cleared"),
        ):
            await _process_single_stock("TEST.DE")

        assert steps_run == [
            ("historical", "TEST.DE"),
            ("metrics", "TEST.DE"),
            ("score", "TEST.DE"),
        ]

    @pytest.mark.asyncio
    async def test_updates_last_synced_on_success(self):
        """Test that last_synced is updated after successful processing."""
        from app.jobs.stocks_data_sync import _process_single_stock

        last_synced_updated = []

        async def mock_update_last_synced(symbol):
            last_synced_updated.append(symbol)

        with (
            patch(
                "app.jobs.stocks_data_sync._sync_historical_for_symbol",
                new_callable=AsyncMock,
            ),
            patch(
                "app.jobs.stocks_data_sync._detect_and_update_country_and_exchange",
                new_callable=AsyncMock,
            ),
            patch(
                "app.jobs.stocks_data_sync._detect_and_update_industry",
                new_callable=AsyncMock,
            ),
            patch(
                "app.jobs.stocks_data_sync._calculate_metrics_for_symbol",
                new_callable=AsyncMock,
                return_value=5,
            ),
            patch(
                "app.jobs.stocks_data_sync._refresh_score_for_symbol",
                new_callable=AsyncMock,
            ),
            patch(
                "app.jobs.stocks_data_sync._update_last_synced",
                new_callable=AsyncMock,
                side_effect=mock_update_last_synced,
            ),
            patch("app.jobs.stocks_data_sync.set_text"),
            patch("pass  # LED cleared"),
        ):
            await _process_single_stock("TEST.DE")

        assert "TEST.DE" in last_synced_updated

    @pytest.mark.asyncio
    async def test_does_not_update_last_synced_on_error(self):
        """Test that last_synced is NOT updated if processing fails."""
        from app.jobs.stocks_data_sync import _process_single_stock

        last_synced_updated = []

        async def mock_update_last_synced(symbol):
            last_synced_updated.append(symbol)

        async def mock_sync_historical_error(symbol):
            raise Exception("Historical sync failed")

        with (
            patch(
                "app.jobs.stocks_data_sync._sync_historical_for_symbol",
                new_callable=AsyncMock,
                side_effect=mock_sync_historical_error,
            ),
            patch(
                "app.jobs.stocks_data_sync._calculate_metrics_for_symbol",
                new_callable=AsyncMock,
            ),
            patch(
                "app.jobs.stocks_data_sync._refresh_score_for_symbol",
                new_callable=AsyncMock,
            ),
            patch(
                "app.jobs.stocks_data_sync._update_last_synced",
                new_callable=AsyncMock,
                side_effect=mock_update_last_synced,
            ),
            patch("app.jobs.stocks_data_sync.set_text"),
            patch("pass  # LED cleared"),
            patch("app.jobs.stocks_data_sync.set_text"),
        ):
            # The function should raise the exception after logging
            with pytest.raises(Exception, match="Historical sync failed"):
                await _process_single_stock("TEST.DE")

        # last_synced should NOT be updated on error
        assert "TEST.DE" not in last_synced_updated


class TestDisplayUpdates:
    """Test LED display updates during processing."""

    @pytest.mark.asyncio
    async def test_shows_updating_message(self):
        """Test that LED shows 'UPDATING {SYMBOL} DATA' during processing."""
        from app.jobs.stocks_data_sync import _process_single_stock

        processing_messages = []

        def mock_set_processing(message):
            processing_messages.append(message)

        with (
            patch(
                "app.jobs.stocks_data_sync._sync_historical_for_symbol",
                new_callable=AsyncMock,
            ),
            patch(
                "app.jobs.stocks_data_sync._detect_and_update_country_and_exchange",
                new_callable=AsyncMock,
            ),
            patch(
                "app.jobs.stocks_data_sync._detect_and_update_industry",
                new_callable=AsyncMock,
            ),
            patch(
                "app.jobs.stocks_data_sync._calculate_metrics_for_symbol",
                new_callable=AsyncMock,
                return_value=5,
            ),
            patch(
                "app.jobs.stocks_data_sync._refresh_score_for_symbol",
                new_callable=AsyncMock,
            ),
            patch(
                "app.jobs.stocks_data_sync._update_last_synced", new_callable=AsyncMock
            ),
            patch(
                "app.jobs.stocks_data_sync.set_text",
                side_effect=mock_set_processing,
            ),
            patch("pass  # LED cleared"),
        ):
            await _process_single_stock("AAPL.US")

        # Should show processing message for the symbol
        assert any("AAPL.US" in msg for msg in processing_messages)
        assert any("PROCESSING" in msg for msg in processing_messages)

    @pytest.mark.asyncio
    async def test_clears_processing_after_completion(self):
        """Test that processing display is cleared after completion."""
        from app.jobs.stocks_data_sync import _process_single_stock

        clear_called = False

        def mock_clear_processing():
            nonlocal clear_called
            clear_called = True

        with (
            patch(
                "app.jobs.stocks_data_sync._sync_historical_for_symbol",
                new_callable=AsyncMock,
            ),
            patch(
                "app.jobs.stocks_data_sync._detect_and_update_country_and_exchange",
                new_callable=AsyncMock,
            ),
            patch(
                "app.jobs.stocks_data_sync._detect_and_update_industry",
                new_callable=AsyncMock,
            ),
            patch(
                "app.jobs.stocks_data_sync._calculate_metrics_for_symbol",
                new_callable=AsyncMock,
                return_value=5,
            ),
            patch(
                "app.jobs.stocks_data_sync._refresh_score_for_symbol",
                new_callable=AsyncMock,
            ),
            patch(
                "app.jobs.stocks_data_sync._update_last_synced", new_callable=AsyncMock
            ),
            patch("app.jobs.stocks_data_sync.set_text"),
            patch(
                "pass  # LED cleared",
                side_effect=mock_clear_processing,
            ),
        ):
            await _process_single_stock("TEST.DE")

        assert clear_called is True


class TestForceRefresh:
    """Test the force refresh functionality for individual stocks."""

    @pytest.mark.asyncio
    async def test_force_refresh_bypasses_last_synced(self):
        """Test that force refresh processes stock regardless of last_synced."""
        from app.jobs.stocks_data_sync import refresh_single_stock

        steps_run = []

        async def mock_sync_historical(symbol):
            steps_run.append(("historical", symbol))

        async def mock_calculate_metrics(symbol):
            steps_run.append(("metrics", symbol))
            return 5

        async def mock_refresh_score(symbol):
            steps_run.append(("score", symbol))

        with (
            patch(
                "app.jobs.stocks_data_sync._sync_historical_for_symbol",
                new_callable=AsyncMock,
                side_effect=mock_sync_historical,
            ),
            patch(
                "app.jobs.stocks_data_sync._detect_and_update_country_and_exchange",
                new_callable=AsyncMock,
            ),
            patch(
                "app.jobs.stocks_data_sync._detect_and_update_industry",
                new_callable=AsyncMock,
            ),
            patch(
                "app.jobs.stocks_data_sync._calculate_metrics_for_symbol",
                new_callable=AsyncMock,
                side_effect=mock_calculate_metrics,
            ),
            patch(
                "app.jobs.stocks_data_sync._refresh_score_for_symbol",
                new_callable=AsyncMock,
                side_effect=mock_refresh_score,
            ),
            patch(
                "app.jobs.stocks_data_sync._update_last_synced", new_callable=AsyncMock
            ),
            patch("app.jobs.stocks_data_sync.set_text"),
            patch("pass  # LED cleared"),
        ):
            result = await refresh_single_stock("FRESH.US")

        # Should process the stock
        assert steps_run == [
            ("historical", "FRESH.US"),
            ("metrics", "FRESH.US"),
            ("score", "FRESH.US"),
        ]
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_force_refresh_returns_error_on_failure(self):
        """Test that force refresh returns error status on failure."""
        from app.jobs.stocks_data_sync import refresh_single_stock

        async def mock_sync_error(symbol):
            raise Exception("Sync failed")

        with (
            patch(
                "app.jobs.stocks_data_sync._sync_historical_for_symbol",
                new_callable=AsyncMock,
                side_effect=mock_sync_error,
            ),
            patch("app.jobs.stocks_data_sync.set_text"),
            patch("pass  # LED cleared"),
            patch("app.jobs.stocks_data_sync.set_text"),
        ):
            result = await refresh_single_stock("ERROR.US")

        assert result["status"] == "error"
        assert "error" in result or "reason" in result
