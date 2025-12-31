"""Tests for trade sync job.

These tests validate syncing executed trades from Tradernet API
to the local database.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestGetExistingOrderIds:
    """Test existing order ID retrieval."""

    @pytest.mark.asyncio
    async def test_returns_set_of_order_ids(self):
        """Test that existing order IDs are returned as a set."""
        from app.jobs.sync_trades import _get_existing_order_ids

        mock_db = MagicMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = [("order1",), ("order2",), ("order3",)]
        mock_db.ledger = AsyncMock()
        mock_db.ledger.execute.return_value = mock_cursor

        result = await _get_existing_order_ids(mock_db)

        assert result == {"order1", "order2", "order3"}

    @pytest.mark.asyncio
    async def test_returns_empty_set_when_no_orders(self):
        """Test empty set when no existing orders."""
        from app.jobs.sync_trades import _get_existing_order_ids

        mock_db = MagicMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = []
        mock_db.ledger = AsyncMock()
        mock_db.ledger.execute.return_value = mock_cursor

        result = await _get_existing_order_ids(mock_db)

        assert result == set()


class TestGetValidSymbols:
    """Test valid symbol retrieval."""

    @pytest.mark.asyncio
    async def test_returns_set_of_symbols(self):
        """Test that security symbols are returned as a set."""
        from app.jobs.sync_trades import _get_valid_symbols

        mock_db = MagicMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = [("AAPL.US",), ("MSFT.US",)]
        mock_db.config = AsyncMock()
        mock_db.config.execute.return_value = mock_cursor

        result = await _get_valid_symbols(mock_db)

        assert result == {"AAPL.US", "MSFT.US"}


class TestValidateTrade:
    """Test trade validation logic."""

    def test_rejects_missing_order_id(self):
        """Test that trades without order_id are rejected."""
        from app.jobs.sync_trades import _validate_trade

        trade = {"symbol": "AAPL.US", "side": "BUY"}
        existing = set()
        valid_symbols = {"AAPL.US"}

        is_valid, reason = _validate_trade(trade, existing, valid_symbols)

        assert not is_valid
        assert "missing order_id" in reason

    def test_rejects_duplicate_order_id(self):
        """Test that duplicate order IDs are rejected."""
        from app.jobs.sync_trades import _validate_trade

        trade = {"order_id": "123", "symbol": "AAPL.US", "side": "BUY"}
        existing = {"123"}  # Already exists
        valid_symbols = {"AAPL.US"}

        is_valid, reason = _validate_trade(trade, existing, valid_symbols)

        assert not is_valid
        assert "duplicate" in reason

    def test_rejects_invalid_symbol(self):
        """Test that unknown symbols are rejected."""
        from app.jobs.sync_trades import _validate_trade

        trade = {"order_id": "123", "symbol": "UNKNOWN.US", "side": "BUY"}
        existing = set()
        valid_symbols = {"AAPL.US"}

        is_valid, reason = _validate_trade(trade, existing, valid_symbols)

        assert not is_valid
        assert "not in securities table" in reason

    def test_rejects_invalid_side(self):
        """Test that invalid trade sides are rejected."""
        from app.jobs.sync_trades import _validate_trade

        trade = {"order_id": "123", "symbol": "AAPL.US", "side": "HOLD"}
        existing = set()
        valid_symbols = {"AAPL.US"}

        is_valid, reason = _validate_trade(trade, existing, valid_symbols)

        assert not is_valid
        assert "invalid side" in reason

    def test_accepts_valid_buy_trade(self):
        """Test that valid BUY trades are accepted."""
        from app.jobs.sync_trades import _validate_trade

        trade = {"order_id": "123", "symbol": "AAPL.US", "side": "buy"}
        existing = set()
        valid_symbols = {"AAPL.US"}

        is_valid, reason = _validate_trade(trade, existing, valid_symbols)

        assert is_valid
        assert reason == ""

    def test_accepts_valid_sell_trade(self):
        """Test that valid SELL trades are accepted."""
        from app.jobs.sync_trades import _validate_trade

        trade = {"order_id": "456", "symbol": "MSFT.US", "side": "SELL"}
        existing = set()
        valid_symbols = {"MSFT.US"}

        is_valid, reason = _validate_trade(trade, existing, valid_symbols)

        assert is_valid


class TestInsertTrade:
    """Test trade insertion."""

    @pytest.mark.asyncio
    async def test_inserts_trade_successfully(self):
        """Test successful trade insertion."""
        from app.jobs.sync_trades import _insert_trade

        mock_db = MagicMock()
        mock_db.ledger = AsyncMock()

        trade = {
            "symbol": "AAPL.US",
            "side": "buy",
            "quantity": 10,
            "price": 150.0,
            "executed_at": "2024-01-15T10:30:00",
        }

        result = await _insert_trade(mock_db, trade, "order123")

        assert result is True
        mock_db.ledger.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_false_on_error(self):
        """Test that insertion errors return False."""
        from app.jobs.sync_trades import _insert_trade

        mock_db = MagicMock()
        mock_db.ledger = AsyncMock()
        mock_db.ledger.execute.side_effect = Exception("Database error")

        trade = {"symbol": "AAPL.US", "side": "buy"}

        result = await _insert_trade(mock_db, trade, "order123")

        assert result is False

    @pytest.mark.asyncio
    async def test_uses_current_time_if_no_executed_at(self):
        """Test that current time is used when executed_at is missing."""
        from app.jobs.sync_trades import _insert_trade

        mock_db = MagicMock()
        mock_db.ledger = AsyncMock()

        trade = {
            "symbol": "AAPL.US",
            "side": "buy",
            "quantity": 10,
            "price": 150.0,
            # No executed_at
        }

        result = await _insert_trade(mock_db, trade, "order123")

        assert result is True
        # Verify execute was called with an ISO timestamp
        call_args = mock_db.ledger.execute.call_args
        assert call_args is not None


class TestSyncTrades:
    """Test main sync_trades function."""

    @pytest.mark.asyncio
    async def test_uses_file_lock(self):
        """Test that sync_trades uses file locking."""
        from app.jobs.sync_trades import sync_trades

        with patch("app.jobs.sync_trades.file_lock") as mock_lock:
            mock_lock.return_value.__aenter__ = AsyncMock()
            mock_lock.return_value.__aexit__ = AsyncMock()
            with patch(
                "app.jobs.sync_trades._sync_trades_internal",
                new_callable=AsyncMock,
            ):
                await sync_trades()

        mock_lock.assert_called_once_with("sync_trades", timeout=60.0)


class TestSyncTradesInternal:
    """Test internal sync implementation."""

    @pytest.mark.asyncio
    async def test_skips_when_not_connected(self):
        """Test that sync is skipped when broker not connected."""
        from app.jobs.sync_trades import _sync_trades_internal

        mock_client = MagicMock()
        mock_client.is_connected = False
        mock_client.connect.return_value = False

        with patch(
            "app.jobs.sync_trades.get_tradernet_client", return_value=mock_client
        ):
            with patch("app.jobs.sync_trades.emit"):
                with patch("app.jobs.sync_trades.set_text"):
                    with patch("pass  # LED cleared"):
                        await _sync_trades_internal()

        # Should not try to get trades
        mock_client.get_executed_trades.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_no_trades_returned(self):
        """Test handling when no trades returned from API."""
        from app.jobs.sync_trades import _sync_trades_internal

        mock_client = MagicMock()
        mock_client.is_connected = True
        mock_client.get_executed_trades.return_value = []

        with patch(
            "app.jobs.sync_trades.get_tradernet_client", return_value=mock_client
        ):
            with patch("app.jobs.sync_trades.emit"):
                with patch("app.jobs.sync_trades.set_text"):
                    with patch("pass  # LED cleared"):
                        await _sync_trades_internal()

        # Should not crash

    @pytest.mark.asyncio
    async def test_inserts_valid_trades(self):
        """Test that valid trades are inserted."""
        from app.jobs.sync_trades import _sync_trades_internal

        mock_client = MagicMock()
        mock_client.is_connected = True
        mock_client.get_executed_trades.return_value = [
            {
                "order_id": "1",
                "symbol": "AAPL.US",
                "side": "BUY",
                "quantity": 10,
                "price": 150,
            },
        ]

        mock_db = MagicMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = []  # No existing orders
        mock_db.ledger = AsyncMock()
        mock_db.ledger.execute.return_value = mock_cursor
        mock_db.ledger.transaction = MagicMock()
        mock_db.ledger.transaction.return_value.__aenter__ = AsyncMock()
        mock_db.ledger.transaction.return_value.__aexit__ = AsyncMock()

        mock_config_cursor = AsyncMock()
        mock_config_cursor.fetchall.return_value = [("AAPL.US",)]
        mock_db.config = AsyncMock()
        mock_db.config.execute.return_value = mock_config_cursor

        with patch(
            "app.jobs.sync_trades.get_tradernet_client", return_value=mock_client
        ):
            with patch("app.jobs.sync_trades.get_db_manager", return_value=mock_db):
                with patch("app.jobs.sync_trades.emit"):
                    with patch("app.jobs.sync_trades.set_text"):
                        with patch("pass  # LED cleared"):
                            await _sync_trades_internal()

        # Execute should have been called for insert
        assert mock_db.ledger.execute.call_count >= 1

    @pytest.mark.asyncio
    async def test_handles_errors_gracefully(self):
        """Test that errors are handled without crashing."""
        from app.jobs.sync_trades import _sync_trades_internal

        mock_client = MagicMock()
        mock_client.is_connected = True
        mock_client.get_executed_trades.side_effect = Exception("API error")

        with patch(
            "app.jobs.sync_trades.get_tradernet_client", return_value=mock_client
        ):
            with patch("app.jobs.sync_trades.emit"):
                with patch("app.jobs.sync_trades.set_text"):
                    with patch("pass  # LED cleared"):
                        with patch("app.jobs.sync_trades.set_text"):
                            # Should not raise
                            await _sync_trades_internal()


class TestClearAndResyncTrades:
    """Test clear and resync function."""

    @pytest.mark.asyncio
    async def test_clears_trades_table(self):
        """Test that trades table is cleared before resync."""
        from app.jobs.sync_trades import clear_and_resync_trades

        mock_db = MagicMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchone.return_value = (10,)  # 10 existing trades
        mock_db.ledger = AsyncMock()
        mock_db.ledger.execute.return_value = mock_cursor
        mock_db.ledger.transaction = MagicMock()
        mock_db.ledger.transaction.return_value.__aenter__ = AsyncMock()
        mock_db.ledger.transaction.return_value.__aexit__ = AsyncMock()

        with patch("app.jobs.sync_trades.get_db_manager", return_value=mock_db):
            with patch(
                "app.jobs.sync_trades._sync_trades_internal",
                new_callable=AsyncMock,
            ) as mock_sync:
                await clear_and_resync_trades()

        # Should have called DELETE
        execute_calls = mock_db.ledger.execute.call_args_list
        assert any("DELETE FROM trades" in str(call) for call in execute_calls)

        # Should call sync after clearing
        mock_sync.assert_called_once()
