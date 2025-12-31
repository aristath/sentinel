"""Tests for CashFlowRepository.

These tests verify the cash flow tracking which is CRITICAL
for accurate cash balance calculations and financial reporting.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.models import CashFlow
from app.shared.domain.value_objects.currency import Currency
from app.modules.cash_flows.database.cash_flow_repository import CashFlowRepository


def create_mock_cash_flow(
    id: int = 1,
    transaction_id: str = "TX123",
    type_doc_id: int = 1,
    transaction_type: str = "DEPOSIT",
    date: str = "2024-01-15",
    amount: float = 100.0,
    currency: str = "EUR",
    amount_eur: float = 100.0,
    status: str | None = "completed",
    status_c: int | None = 1,
    description: str | None = "Test deposit",
    params_json: str | None = None,
    created_at: str = "2024-01-16T10:00:00",
) -> dict:
    """Create a mock cash flow database row."""
    return {
        "id": id,
        "transaction_id": transaction_id,
        "type_doc_id": type_doc_id,
        "transaction_type": transaction_type,
        "date": date,
        "amount": amount,
        "currency": currency,
        "amount_eur": amount_eur,
        "status": status,
        "status_c": status_c,
        "description": description,
        "params_json": params_json,
        "created_at": created_at,
    }


class TestCashFlowRepositoryCreate:
    """Test cash flow record creation."""

    @pytest.mark.asyncio
    async def test_create_cash_flow_record(self):
        """Test creating a new cash flow record."""
        with patch("app.repositories.cash_flow.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = MagicMock()
            mock_db.ledger = mock_ledger
            mock_get_db.return_value = mock_db

            # Setup transaction mock as an async context manager
            mock_conn = AsyncMock()
            mock_cursor = MagicMock()
            mock_cursor.lastrowid = 42
            mock_conn.execute.return_value = mock_cursor

            # Create async context manager mock
            mock_transaction_cm = MagicMock()
            mock_transaction_cm.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_transaction_cm.__aexit__ = AsyncMock(return_value=None)
            mock_ledger.transaction.return_value = mock_transaction_cm

            repo = CashFlowRepository()
            cash_flow = CashFlow(
                transaction_id="TX123",
                type_doc_id=1,
                transaction_type="DEPOSIT",
                date="2024-01-15",
                amount=100.0,
                currency=Currency.EUR,
                amount_eur=100.0,
                status="completed",
                status_c=1,
                description="Test deposit",
            )

            result = await repo.create(cash_flow)

            assert result.id == 42
            assert result.created_at is not None
            mock_conn.execute.assert_called_once()

            # Verify INSERT statement parameters
            call_args = mock_conn.execute.call_args
            assert "INSERT INTO cash_flows" in call_args[0][0]
            assert call_args[0][1][0] == "TX123"  # transaction_id
            assert call_args[0][1][3] == "2024-01-15"  # date
            assert call_args[0][1][4] == 100.0  # amount

    @pytest.mark.asyncio
    async def test_create_cash_flow_with_params_json(self):
        """Test creating cash flow with JSON parameters."""
        with patch("app.repositories.cash_flow.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = MagicMock()
            mock_db.ledger = mock_ledger
            mock_get_db.return_value = mock_db

            mock_conn = AsyncMock()
            mock_cursor = MagicMock()
            mock_cursor.lastrowid = 43
            mock_conn.execute.return_value = mock_cursor

            mock_transaction_cm = MagicMock()
            mock_transaction_cm.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_transaction_cm.__aexit__ = AsyncMock(return_value=None)
            mock_ledger.transaction.return_value = mock_transaction_cm

            repo = CashFlowRepository()
            cash_flow = CashFlow(
                transaction_id="TX124",
                type_doc_id=2,
                transaction_type="WITHDRAWAL",
                date="2024-01-16",
                amount=-50.0,
                currency=Currency.EUR,
                amount_eur=-50.0,
                params_json='{"method": "bank_transfer"}',
            )

            result = await repo.create(cash_flow)

            assert result.id == 43
            call_args = mock_conn.execute.call_args
            assert call_args[0][1][10] == '{"method": "bank_transfer"}'  # params_json


class TestCashFlowRepositoryQuery:
    """Test cash flow query operations."""

    @pytest.mark.asyncio
    async def test_get_by_transaction_id(self):
        """Test retrieving cash flow by transaction ID."""
        with patch("app.repositories.cash_flow.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = AsyncMock()
            mock_db.ledger = mock_ledger
            mock_get_db.return_value = mock_db

            mock_row = create_mock_cash_flow(
                id=1, transaction_id="TX123", transaction_type="DEPOSIT"
            )
            mock_ledger.fetchone.return_value = mock_row

            repo = CashFlowRepository()
            result = await repo.get_by_transaction_id("TX123")

            assert result is not None
            assert result.id == 1
            assert result.transaction_id == "TX123"
            assert result.transaction_type == "DEPOSIT"
            mock_ledger.fetchone.assert_called_once_with(
                "SELECT * FROM cash_flows WHERE transaction_id = ?", ("TX123",)
            )

    @pytest.mark.asyncio
    async def test_get_by_transaction_id_not_found(self):
        """Test retrieving non-existent cash flow returns None."""
        with patch("app.repositories.cash_flow.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = AsyncMock()
            mock_db.ledger = mock_ledger
            mock_get_db.return_value = mock_db

            mock_ledger.fetchone.return_value = None

            repo = CashFlowRepository()
            result = await repo.get_by_transaction_id("TX999")

            assert result is None

    @pytest.mark.asyncio
    async def test_exists_true(self):
        """Test checking if cash flow exists returns True."""
        with patch("app.repositories.cash_flow.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = AsyncMock()
            mock_db.ledger = mock_ledger
            mock_get_db.return_value = mock_db

            mock_ledger.fetchone.return_value = {"1": 1}  # Row exists

            repo = CashFlowRepository()
            result = await repo.exists("TX123")

            assert result is True
            mock_ledger.fetchone.assert_called_once_with(
                "SELECT 1 FROM cash_flows WHERE transaction_id = ?", ("TX123",)
            )

    @pytest.mark.asyncio
    async def test_exists_false(self):
        """Test checking if cash flow doesn't exist returns False."""
        with patch("app.repositories.cash_flow.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = AsyncMock()
            mock_db.ledger = mock_ledger
            mock_get_db.return_value = mock_db

            mock_ledger.fetchone.return_value = None

            repo = CashFlowRepository()
            result = await repo.exists("TX999")

            assert result is False

    @pytest.mark.asyncio
    async def test_get_all_with_limit(self):
        """Test retrieving all cash flows with limit."""
        with patch("app.repositories.cash_flow.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = AsyncMock()
            mock_db.ledger = mock_ledger
            mock_get_db.return_value = mock_db

            mock_rows = [
                create_mock_cash_flow(id=1, transaction_id="TX1"),
                create_mock_cash_flow(id=2, transaction_id="TX2"),
                create_mock_cash_flow(id=3, transaction_id="TX3"),
            ]
            mock_ledger.fetchall.return_value = mock_rows

            repo = CashFlowRepository()
            result = await repo.get_all(limit=3)

            assert len(result) == 3
            assert result[0].transaction_id == "TX1"
            mock_ledger.fetchall.assert_called_once_with(
                "SELECT * FROM cash_flows ORDER BY date DESC LIMIT ?", (3,)
            )

    @pytest.mark.asyncio
    async def test_get_all_without_limit(self):
        """Test retrieving all cash flows without limit."""
        with patch("app.repositories.cash_flow.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = AsyncMock()
            mock_db.ledger = mock_ledger
            mock_get_db.return_value = mock_db

            mock_rows = [create_mock_cash_flow(id=i) for i in range(10)]
            mock_ledger.fetchall.return_value = mock_rows

            repo = CashFlowRepository()
            result = await repo.get_all()

            assert len(result) == 10
            mock_ledger.fetchall.assert_called_once_with(
                "SELECT * FROM cash_flows ORDER BY date DESC"
            )

    @pytest.mark.asyncio
    async def test_get_by_date_range(self):
        """Test retrieving cash flows within a date range."""
        with patch("app.repositories.cash_flow.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = AsyncMock()
            mock_db.ledger = mock_ledger
            mock_get_db.return_value = mock_db

            mock_rows = [
                create_mock_cash_flow(id=1, date="2024-01-10"),
                create_mock_cash_flow(id=2, date="2024-01-15"),
                create_mock_cash_flow(id=3, date="2024-01-20"),
            ]
            mock_ledger.fetchall.return_value = mock_rows

            repo = CashFlowRepository()
            result = await repo.get_by_date_range("2024-01-01", "2024-01-31")

            assert len(result) == 3
            call_args = mock_ledger.fetchall.call_args
            assert "WHERE date >= ? AND date <= ?" in call_args[0][0]
            assert call_args[0][1] == ("2024-01-01", "2024-01-31")

    @pytest.mark.asyncio
    async def test_get_by_type(self):
        """Test retrieving cash flows by transaction type."""
        with patch("app.repositories.cash_flow.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = AsyncMock()
            mock_db.ledger = mock_ledger
            mock_get_db.return_value = mock_db

            mock_rows = [
                create_mock_cash_flow(id=1, transaction_type="DEPOSIT"),
                create_mock_cash_flow(id=2, transaction_type="DEPOSIT"),
            ]
            mock_ledger.fetchall.return_value = mock_rows

            repo = CashFlowRepository()
            result = await repo.get_by_type("DEPOSIT")

            assert len(result) == 2
            assert all(cf.transaction_type == "DEPOSIT" for cf in result)
            call_args = mock_ledger.fetchall.call_args
            assert "WHERE transaction_type = ?" in call_args[0][0]
            assert call_args[0][1] == ("DEPOSIT",)


class TestCashFlowRepositorySyncFromAPI:
    """Test syncing cash flows from API."""

    @pytest.mark.asyncio
    async def test_sync_from_api_new_transactions(self):
        """Test syncing new transactions from API."""
        with patch("app.repositories.cash_flow.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = MagicMock()
            mock_db.ledger = mock_ledger
            mock_get_db.return_value = mock_db

            # Mock exists check to return False (new transaction)
            mock_ledger.fetchone = AsyncMock(return_value=None)

            # Mock transaction context manager
            mock_conn = AsyncMock()
            mock_cursor = MagicMock()
            mock_cursor.lastrowid = 100
            mock_conn.execute.return_value = mock_cursor

            mock_transaction_cm = MagicMock()
            mock_transaction_cm.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_transaction_cm.__aexit__ = AsyncMock(return_value=None)
            mock_ledger.transaction.return_value = mock_transaction_cm

            repo = CashFlowRepository()

            api_transactions = [
                {
                    "id": "TX001",
                    "type_doc_id": 1,
                    "type_doc": "DEPOSIT",
                    "dt": "2024-01-15",
                    "sm": 100.0,
                    "curr": "EUR",
                    "sm_eur": 100.0,
                    "status": "completed",
                    "status_c": 1,
                    "description": "Test deposit",
                },
                {
                    "id": "TX002",
                    "type_doc_id": 2,
                    "type_doc": "WITHDRAWAL",
                    "dt": "2024-01-16",
                    "sm": -50.0,
                    "curr": "EUR",
                    "sm_eur": -50.0,
                },
            ]

            result = await repo.sync_from_api(api_transactions)

            assert result == 2  # 2 new transactions synced
            # Should be called twice for exists checks
            assert mock_ledger.fetchone.call_count == 2

    @pytest.mark.asyncio
    async def test_sync_from_api_skip_existing(self):
        """Test that sync skips existing transactions."""
        with patch("app.repositories.cash_flow.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = MagicMock()
            mock_db.ledger = mock_ledger
            mock_get_db.return_value = mock_db

            # Mock exists check to return True (existing transaction)
            mock_ledger.fetchone = AsyncMock(return_value={"1": 1})

            repo = CashFlowRepository()

            api_transactions = [
                {
                    "id": "TX001",
                    "type_doc_id": 1,
                    "type_doc": "DEPOSIT",
                    "dt": "2024-01-15",
                    "sm": 100.0,
                    "curr": "EUR",
                },
            ]

            result = await repo.sync_from_api(api_transactions)

            assert result == 0  # No new transactions

    @pytest.mark.asyncio
    async def test_sync_from_api_with_params(self):
        """Test syncing transactions with JSON params."""
        with patch("app.repositories.cash_flow.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = MagicMock()
            mock_db.ledger = mock_ledger
            mock_get_db.return_value = mock_db

            mock_ledger.fetchone = AsyncMock(return_value=None)

            mock_conn = AsyncMock()
            mock_cursor = MagicMock()
            mock_cursor.lastrowid = 100
            mock_conn.execute.return_value = mock_cursor

            mock_transaction_cm = MagicMock()
            mock_transaction_cm.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_transaction_cm.__aexit__ = AsyncMock(return_value=None)
            mock_ledger.transaction.return_value = mock_transaction_cm

            repo = CashFlowRepository()

            api_transactions = [
                {
                    "id": "TX001",
                    "type_doc_id": 1,
                    "type_doc": "DEPOSIT",
                    "dt": "2024-01-15",
                    "sm": 100.0,
                    "curr": "EUR",
                    "params": {"method": "bank_transfer", "account": "123"},
                }
            ]

            result = await repo.sync_from_api(api_transactions)

            assert result == 1
            # Verify params_json was serialized
            call_args = mock_conn.execute.call_args
            import json

            params_json = call_args[0][1][10]
            assert params_json is not None
            assert json.loads(params_json) == {
                "method": "bank_transfer",
                "account": "123",
            }

    @pytest.mark.asyncio
    async def test_sync_from_api_skip_invalid_transactions(self):
        """Test that sync skips transactions without ID."""
        with patch("app.repositories.cash_flow.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = MagicMock()
            mock_db.ledger = mock_ledger
            mock_get_db.return_value = mock_db

            repo = CashFlowRepository()

            api_transactions = [
                {
                    # Missing ID
                    "type_doc": "DEPOSIT",
                    "dt": "2024-01-15",
                    "sm": 100.0,
                },
                {
                    "id": "",  # Empty ID
                    "type_doc": "DEPOSIT",
                    "dt": "2024-01-15",
                    "sm": 100.0,
                },
            ]

            result = await repo.sync_from_api(api_transactions)

            assert result == 0  # No valid transactions
            mock_ledger.fetchone.assert_not_called()

    @pytest.mark.asyncio
    async def test_sync_from_api_handles_defaults(self):
        """Test that sync handles missing optional fields with defaults."""
        with patch("app.repositories.cash_flow.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = MagicMock()
            mock_db.ledger = mock_ledger
            mock_get_db.return_value = mock_db

            mock_ledger.fetchone = AsyncMock(return_value=None)

            mock_conn = AsyncMock()
            mock_cursor = MagicMock()
            mock_cursor.lastrowid = 100
            mock_conn.execute.return_value = mock_cursor

            mock_transaction_cm = MagicMock()
            mock_transaction_cm.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_transaction_cm.__aexit__ = AsyncMock(return_value=None)
            mock_ledger.transaction.return_value = mock_transaction_cm

            repo = CashFlowRepository()

            # Minimal transaction data
            api_transactions = [
                {
                    "id": "TX001",
                    # Missing most optional fields
                }
            ]

            result = await repo.sync_from_api(api_transactions)

            assert result == 1
            # Verify defaults were used
            call_args = mock_conn.execute.call_args
            params = call_args[0][1]
            assert params[1] == 0  # type_doc_id default
            assert params[4] == 0.0  # amount default
            assert params[5] == "EUR"  # currency default


class TestCashFlowRepositoryTotals:
    """Test total deposits and withdrawals calculations."""

    @pytest.mark.asyncio
    async def test_get_total_deposits(self):
        """Test getting total deposits in EUR."""
        with patch("app.repositories.cash_flow.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = AsyncMock()
            mock_db.ledger = mock_ledger
            mock_get_db.return_value = mock_db

            mock_ledger.fetchone.return_value = {"total": 1500.0}

            repo = CashFlowRepository()
            result = await repo.get_total_deposits()

            assert result == 1500.0
            call_args = mock_ledger.fetchone.call_args
            assert "DEPOSIT" in call_args[0][0]
            assert "SUM(amount_eur)" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_get_total_deposits_returns_zero_when_none(self):
        """Test that total deposits returns 0 when no deposits exist."""
        with patch("app.repositories.cash_flow.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = AsyncMock()
            mock_db.ledger = mock_ledger
            mock_get_db.return_value = mock_db

            mock_ledger.fetchone.return_value = None

            repo = CashFlowRepository()
            result = await repo.get_total_deposits()

            assert result == 0.0

    @pytest.mark.asyncio
    async def test_get_total_deposits_handles_case_variations(self):
        """Test that deposits query handles case variations."""
        with patch("app.repositories.cash_flow.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = AsyncMock()
            mock_db.ledger = mock_ledger
            mock_get_db.return_value = mock_db

            mock_ledger.fetchone.return_value = {"total": 1000.0}

            repo = CashFlowRepository()
            await repo.get_total_deposits()

            call_args = mock_ledger.fetchone.call_args
            sql = call_args[0][0]
            # Should check for DEPOSIT, Deposit, and deposit
            assert "DEPOSIT" in sql
            assert "Deposit" in sql
            assert "deposit" in sql

    @pytest.mark.asyncio
    async def test_get_total_withdrawals(self):
        """Test getting total withdrawals in EUR."""
        with patch("app.repositories.cash_flow.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = AsyncMock()
            mock_db.ledger = mock_ledger
            mock_get_db.return_value = mock_db

            mock_ledger.fetchone.return_value = {"total": 500.0}

            repo = CashFlowRepository()
            result = await repo.get_total_withdrawals()

            assert result == 500.0
            call_args = mock_ledger.fetchone.call_args
            assert "WITHDRAWAL" in call_args[0][0]
            assert "ABS(amount_eur)" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_get_total_withdrawals_returns_zero_when_none(self):
        """Test that total withdrawals returns 0 when no withdrawals exist."""
        with patch("app.repositories.cash_flow.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = AsyncMock()
            mock_db.ledger = mock_ledger
            mock_get_db.return_value = mock_db

            mock_ledger.fetchone.return_value = None

            repo = CashFlowRepository()
            result = await repo.get_total_withdrawals()

            assert result == 0.0


class TestCashFlowRepositoryCashBalanceHistory:
    """Test cash balance history calculations."""

    @pytest.mark.asyncio
    async def test_get_cash_balance_history_with_deposits(self):
        """Test calculating cash balance history with deposits."""
        with patch("app.repositories.cash_flow.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = AsyncMock()
            mock_db.ledger = mock_ledger
            mock_get_db.return_value = mock_db

            mock_rows = [
                {
                    "date": "2024-01-10",
                    "amount_eur": 100.0,
                    "transaction_type": "DEPOSIT",
                },
                {
                    "date": "2024-01-15",
                    "amount_eur": 200.0,
                    "transaction_type": "DEPOSIT",
                },
                {
                    "date": "2024-01-20",
                    "amount_eur": 150.0,
                    "transaction_type": "DEPOSIT",
                },
            ]
            mock_ledger.fetchall.return_value = mock_rows

            repo = CashFlowRepository()
            result = await repo.get_cash_balance_history(
                "2024-01-01", "2024-01-31", initial_cash=0.0
            )

            assert len(result) == 3
            assert result[0] == {"date": "2024-01-10", "cash_balance": 100.0}
            assert result[1] == {"date": "2024-01-15", "cash_balance": 300.0}
            assert result[2] == {"date": "2024-01-20", "cash_balance": 450.0}

    @pytest.mark.asyncio
    async def test_get_cash_balance_history_with_withdrawals(self):
        """Test calculating cash balance history with withdrawals."""
        with patch("app.repositories.cash_flow.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = AsyncMock()
            mock_db.ledger = mock_ledger
            mock_get_db.return_value = mock_db

            mock_rows = [
                {
                    "date": "2024-01-10",
                    "amount_eur": -50.0,
                    "transaction_type": "WITHDRAWAL",
                },
                {
                    "date": "2024-01-15",
                    "amount_eur": -30.0,
                    "transaction_type": "WITHDRAWAL",
                },
            ]
            mock_ledger.fetchall.return_value = mock_rows

            repo = CashFlowRepository()
            result = await repo.get_cash_balance_history(
                "2024-01-01", "2024-01-31", initial_cash=200.0
            )

            assert len(result) == 2
            assert result[0] == {"date": "2024-01-10", "cash_balance": 150.0}
            assert result[1] == {"date": "2024-01-15", "cash_balance": 120.0}

    @pytest.mark.asyncio
    async def test_get_cash_balance_history_with_dividends(self):
        """Test calculating cash balance history including dividends."""
        with patch("app.repositories.cash_flow.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = AsyncMock()
            mock_db.ledger = mock_ledger
            mock_get_db.return_value = mock_db

            mock_rows = [
                {
                    "date": "2024-01-10",
                    "amount_eur": 100.0,
                    "transaction_type": "DEPOSIT",
                },
                {
                    "date": "2024-01-15",
                    "amount_eur": 10.0,
                    "transaction_type": "DIVIDEND",
                },
                {
                    "date": "2024-01-20",
                    "amount_eur": -50.0,
                    "transaction_type": "WITHDRAWAL",
                },
            ]
            mock_ledger.fetchall.return_value = mock_rows

            repo = CashFlowRepository()
            result = await repo.get_cash_balance_history(
                "2024-01-01", "2024-01-31", initial_cash=0.0
            )

            assert len(result) == 3
            assert result[0] == {"date": "2024-01-10", "cash_balance": 100.0}
            assert result[1] == {"date": "2024-01-15", "cash_balance": 110.0}
            assert result[2] == {"date": "2024-01-20", "cash_balance": 60.0}

    @pytest.mark.asyncio
    async def test_get_cash_balance_history_multiple_transactions_same_day(self):
        """Test cash balance history with multiple transactions on the same day."""
        with patch("app.repositories.cash_flow.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = AsyncMock()
            mock_db.ledger = mock_ledger
            mock_get_db.return_value = mock_db

            mock_rows = [
                {
                    "date": "2024-01-10",
                    "amount_eur": 100.0,
                    "transaction_type": "DEPOSIT",
                },
                {
                    "date": "2024-01-10",
                    "amount_eur": 50.0,
                    "transaction_type": "DEPOSIT",
                },
                {
                    "date": "2024-01-10",
                    "amount_eur": -20.0,
                    "transaction_type": "WITHDRAWAL",
                },
            ]
            mock_ledger.fetchall.return_value = mock_rows

            repo = CashFlowRepository()
            result = await repo.get_cash_balance_history(
                "2024-01-01", "2024-01-31", initial_cash=0.0
            )

            # Should have only one entry for the date with net change
            assert len(result) == 1
            assert result[0] == {"date": "2024-01-10", "cash_balance": 130.0}

    @pytest.mark.asyncio
    async def test_get_cash_balance_history_empty_result(self):
        """Test cash balance history with no transactions."""
        with patch("app.repositories.cash_flow.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = AsyncMock()
            mock_db.ledger = mock_ledger
            mock_get_db.return_value = mock_db

            mock_ledger.fetchall.return_value = []

            repo = CashFlowRepository()
            result = await repo.get_cash_balance_history(
                "2024-01-01", "2024-01-31", initial_cash=100.0
            )

            assert result == []

    @pytest.mark.asyncio
    async def test_get_cash_balance_history_with_initial_cash(self):
        """Test cash balance history respects initial cash balance."""
        with patch("app.repositories.cash_flow.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = AsyncMock()
            mock_db.ledger = mock_ledger
            mock_get_db.return_value = mock_db

            mock_rows = [
                {
                    "date": "2024-01-10",
                    "amount_eur": 100.0,
                    "transaction_type": "DEPOSIT",
                },
            ]
            mock_ledger.fetchall.return_value = mock_rows

            repo = CashFlowRepository()
            result = await repo.get_cash_balance_history(
                "2024-01-01", "2024-01-31", initial_cash=500.0
            )

            assert len(result) == 1
            assert result[0] == {"date": "2024-01-10", "cash_balance": 600.0}

    @pytest.mark.asyncio
    async def test_get_cash_balance_history_handles_null_amounts(self):
        """Test cash balance history handles null amount_eur gracefully."""
        with patch("app.repositories.cash_flow.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = AsyncMock()
            mock_db.ledger = mock_ledger
            mock_get_db.return_value = mock_db

            mock_rows = [
                {
                    "date": "2024-01-10",
                    "amount_eur": None,
                    "transaction_type": "DEPOSIT",
                },
                {
                    "date": "2024-01-15",
                    "amount_eur": 100.0,
                    "transaction_type": "DEPOSIT",
                },
            ]
            mock_ledger.fetchall.return_value = mock_rows

            repo = CashFlowRepository()
            result = await repo.get_cash_balance_history(
                "2024-01-01", "2024-01-31", initial_cash=0.0
            )

            # Should handle null as 0
            assert len(result) == 2
            assert result[0] == {"date": "2024-01-10", "cash_balance": 0.0}
            assert result[1] == {"date": "2024-01-15", "cash_balance": 100.0}

    @pytest.mark.asyncio
    async def test_get_cash_balance_history_case_insensitive_types(self):
        """Test cash balance history handles case-insensitive transaction types."""
        with patch("app.repositories.cash_flow.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = AsyncMock()
            mock_db.ledger = mock_ledger
            mock_get_db.return_value = mock_db

            mock_rows = [
                {
                    "date": "2024-01-10",
                    "amount_eur": 100.0,
                    "transaction_type": "deposit",
                },
                {
                    "date": "2024-01-15",
                    "amount_eur": -50.0,
                    "transaction_type": "Withdrawal",
                },
                {
                    "date": "2024-01-20",
                    "amount_eur": 10.0,
                    "transaction_type": "DIVIDEND",
                },
            ]
            mock_ledger.fetchall.return_value = mock_rows

            repo = CashFlowRepository()
            result = await repo.get_cash_balance_history(
                "2024-01-01", "2024-01-31", initial_cash=0.0
            )

            # Should handle all case variations correctly
            assert len(result) == 3
            assert result[0] == {"date": "2024-01-10", "cash_balance": 100.0}
            assert result[1] == {"date": "2024-01-15", "cash_balance": 50.0}
            assert result[2] == {"date": "2024-01-20", "cash_balance": 60.0}


class TestCashFlowRepositoryRowConversion:
    """Test row to model conversion."""

    def test_row_to_cash_flow_basic(self):
        """Test converting a basic database row to CashFlow model."""
        with patch("app.repositories.cash_flow.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value = mock_db

            repo = CashFlowRepository()
            row = create_mock_cash_flow(
                id=1,
                transaction_id="TX123",
                transaction_type="DEPOSIT",
                amount=100.0,
                currency="EUR",
                amount_eur=100.0,
            )

            result = repo._row_to_cash_flow(row)

            assert isinstance(result, CashFlow)
            assert result.id == 1
            assert result.transaction_id == "TX123"
            assert result.transaction_type == "DEPOSIT"
            assert result.amount == 100.0
            assert result.currency == "EUR"
            assert result.amount_eur == 100.0

    def test_row_to_cash_flow_with_all_fields(self):
        """Test converting a complete database row to CashFlow model."""
        with patch("app.repositories.cash_flow.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value = mock_db

            repo = CashFlowRepository()
            row = create_mock_cash_flow(
                id=1,
                transaction_id="TX123",
                type_doc_id=5,
                transaction_type="WITHDRAWAL",
                date="2024-01-15",
                amount=-50.0,
                currency="USD",
                amount_eur=-47.5,
                status="completed",
                status_c=1,
                description="Test withdrawal",
                params_json='{"method": "wire"}',
                created_at="2024-01-16T10:00:00",
            )

            result = repo._row_to_cash_flow(row)

            assert result.id == 1
            assert result.transaction_id == "TX123"
            assert result.type_doc_id == 5
            assert result.transaction_type == "WITHDRAWAL"
            assert result.date == "2024-01-15"
            assert result.amount == -50.0
            assert result.currency == "USD"
            assert result.amount_eur == -47.5
            assert result.status == "completed"
            assert result.status_c == 1
            assert result.description == "Test withdrawal"
            assert result.params_json == '{"method": "wire"}'
            assert result.created_at == "2024-01-16T10:00:00"

    def test_row_to_cash_flow_with_nulls(self):
        """Test converting a database row with null optional fields."""
        with patch("app.repositories.cash_flow.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value = mock_db

            repo = CashFlowRepository()
            row = create_mock_cash_flow(
                id=1,
                transaction_id="TX123",
                status=None,
                status_c=None,
                description=None,
                params_json=None,
            )

            result = repo._row_to_cash_flow(row)

            assert result.status is None
            assert result.status_c is None
            assert result.description is None
            assert result.params_json is None
