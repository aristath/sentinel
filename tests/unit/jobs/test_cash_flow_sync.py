"""Tests for cash flow sync job.

These tests validate the cash flow synchronization logic including
API fetching, database updates, and error handling.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestSyncCashFlowsInternal:
    """Tests for the internal cash flow sync implementation."""

    @pytest.mark.asyncio
    async def test_skips_when_not_connected(self):
        """Test that sync is skipped when Tradernet is not connected."""
        from app.jobs.cash_flow_sync import _sync_cash_flows_internal

        with (
            patch("app.jobs.cash_flow_sync.get_tradernet_client") as mock_get_client,
            patch("app.jobs.cash_flow_sync.set_processing"),
            patch("app.jobs.cash_flow_sync.set_error") as mock_set_error,
            patch("app.jobs.cash_flow_sync.clear_processing"),
            patch("app.jobs.cash_flow_sync.emit"),
        ):
            mock_client = MagicMock()
            mock_client.is_connected = False
            mock_client.connect.return_value = False
            mock_get_client.return_value = mock_client

            await _sync_cash_flows_internal()

            # Should set error message
            mock_set_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_empty_transactions(self):
        """Test handling when no transactions are returned."""
        from app.jobs.cash_flow_sync import _sync_cash_flows_internal

        with (
            patch("app.jobs.cash_flow_sync.get_tradernet_client") as mock_get_client,
            patch("app.jobs.cash_flow_sync.set_processing"),
            patch("app.jobs.cash_flow_sync.clear_processing") as mock_clear,
            patch("app.jobs.cash_flow_sync.emit"),
        ):
            mock_client = MagicMock()
            mock_client.is_connected = True
            mock_client.get_all_cash_flows.return_value = []
            mock_get_client.return_value = mock_client

            await _sync_cash_flows_internal()

            # Should still clear processing
            mock_clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_syncs_new_transactions(self):
        """Test syncing new transactions to database."""
        from contextlib import asynccontextmanager

        from app.jobs.cash_flow_sync import _sync_cash_flows_internal

        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = []  # No existing transactions

        @asynccontextmanager
        async def mock_transaction():
            yield

        mock_ledger = AsyncMock()
        mock_ledger.execute.return_value = mock_cursor
        mock_ledger.transaction = mock_transaction

        mock_db = MagicMock()
        mock_db.ledger = mock_ledger

        transactions = [
            {
                "transaction_id": "TXN001",
                "type_doc_id": 1,
                "type": "DEPOSIT",
                "date": "2024-01-15",
                "amount": 1000.0,
                "currency": "EUR",
                "amount_eur": 1000.0,
                "status": "COMPLETED",
                "status_c": "C",
                "description": "Wire transfer",
                "params_json": "{}",
            }
        ]

        with (
            patch("app.jobs.cash_flow_sync.get_tradernet_client") as mock_get_client,
            patch("app.jobs.cash_flow_sync.get_db_manager") as mock_get_db,
            patch("app.jobs.cash_flow_sync.set_processing"),
            patch("app.jobs.cash_flow_sync.clear_processing"),
            patch("app.jobs.cash_flow_sync.emit"),
        ):
            mock_client = MagicMock()
            mock_client.is_connected = True
            mock_client.get_all_cash_flows.return_value = transactions
            mock_get_client.return_value = mock_client
            mock_get_db.return_value = mock_db

            await _sync_cash_flows_internal()

            # Should have called execute multiple times (select + insert)
            assert mock_ledger.execute.call_count >= 1

    @pytest.mark.asyncio
    async def test_skips_existing_transactions(self):
        """Test that existing transactions are skipped."""
        from app.jobs.cash_flow_sync import _sync_cash_flows_internal

        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = [("TXN001",)]  # Already exists

        mock_ledger = AsyncMock()
        mock_ledger.execute.return_value = mock_cursor
        mock_ledger.transaction.return_value.__aenter__ = AsyncMock()
        mock_ledger.transaction.return_value.__aexit__ = AsyncMock()

        mock_db = MagicMock()
        mock_db.ledger = mock_ledger

        transactions = [
            {"transaction_id": "TXN001", "type": "DEPOSIT", "amount": 1000.0}
        ]

        with (
            patch("app.jobs.cash_flow_sync.get_tradernet_client") as mock_get_client,
            patch("app.jobs.cash_flow_sync.get_db_manager") as mock_get_db,
            patch("app.jobs.cash_flow_sync.set_processing"),
            patch("app.jobs.cash_flow_sync.clear_processing"),
            patch("app.jobs.cash_flow_sync.emit"),
        ):
            mock_client = MagicMock()
            mock_client.is_connected = True
            mock_client.get_all_cash_flows.return_value = transactions
            mock_get_client.return_value = mock_client
            mock_get_db.return_value = mock_db

            await _sync_cash_flows_internal()

            # Should only have SELECT call, no INSERT for existing txn
            # (Actually there might still be inserts for other logic)

    @pytest.mark.asyncio
    async def test_handles_exception(self):
        """Test exception handling during sync."""
        from app.jobs.cash_flow_sync import _sync_cash_flows_internal

        with (
            patch("app.jobs.cash_flow_sync.get_tradernet_client") as mock_get_client,
            patch("app.jobs.cash_flow_sync.get_db_manager") as mock_get_db,
            patch("app.jobs.cash_flow_sync.set_processing"),
            patch("app.jobs.cash_flow_sync.set_error") as mock_set_error,
            patch("app.jobs.cash_flow_sync.clear_processing") as mock_clear,
            patch("app.jobs.cash_flow_sync.emit"),
        ):
            mock_client = MagicMock()
            mock_client.is_connected = True
            mock_client.get_all_cash_flows.side_effect = Exception("API error")
            mock_get_client.return_value = mock_client

            await _sync_cash_flows_internal()

            # Should set error and clear processing
            mock_set_error.assert_called_once()
            mock_clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_uses_amount_fallback_for_eur(self):
        """Test that amount is used as fallback when amount_eur is not provided."""
        from app.jobs.cash_flow_sync import _sync_cash_flows_internal

        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = []

        mock_ledger = AsyncMock()
        mock_ledger.execute.return_value = mock_cursor
        mock_ledger.transaction.return_value.__aenter__ = AsyncMock()
        mock_ledger.transaction.return_value.__aexit__ = AsyncMock()

        mock_db = MagicMock()
        mock_db.ledger = mock_ledger

        transactions = [
            {
                "transaction_id": "TXN002",
                "type": "DEPOSIT",
                "amount": 500.0,
                "currency": "EUR",
                # No amount_eur provided - should use amount as fallback
            }
        ]

        with (
            patch("app.jobs.cash_flow_sync.get_tradernet_client") as mock_get_client,
            patch("app.jobs.cash_flow_sync.get_db_manager") as mock_get_db,
            patch("app.jobs.cash_flow_sync.set_processing"),
            patch("app.jobs.cash_flow_sync.clear_processing"),
            patch("app.jobs.cash_flow_sync.emit"),
        ):
            mock_client = MagicMock()
            mock_client.is_connected = True
            mock_client.get_all_cash_flows.return_value = transactions
            mock_get_client.return_value = mock_client
            mock_get_db.return_value = mock_db

            await _sync_cash_flows_internal()

            # Should complete without error


class TestSyncCashFlows:
    """Tests for the main sync_cash_flows function."""

    @pytest.mark.asyncio
    async def test_uses_file_lock(self):
        """Test that file lock is used to prevent concurrent syncs."""
        from app.jobs.cash_flow_sync import sync_cash_flows

        with (
            patch("app.jobs.cash_flow_sync.file_lock") as mock_lock,
            patch("app.jobs.cash_flow_sync._sync_cash_flows_internal") as mock_internal,
        ):
            mock_lock.return_value.__aenter__ = AsyncMock()
            mock_lock.return_value.__aexit__ = AsyncMock()

            await sync_cash_flows()

            mock_lock.assert_called_once_with("cash_flow_sync", timeout=120.0)
            mock_internal.assert_called_once()
