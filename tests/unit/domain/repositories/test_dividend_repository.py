"""Tests for DividendRepository.

These tests verify the dividend tracking which is CRITICAL
for accurate DRIP (Dividend Reinvestment Plan) execution.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.models import DividendRecord
from app.modules.dividends.database.dividend_repository import DividendRepository


def create_mock_dividend(
    id: int = 1,
    symbol: str = "AAPL",
    isin: str | None = None,
    cash_flow_id: int = 100,
    amount: float = 10.0,
    currency: str = "USD",
    amount_eur: float = 9.5,
    payment_date: str = "2024-01-15",
    reinvested: bool = False,
    reinvested_at: str | None = None,
    reinvested_quantity: int | None = None,
    pending_bonus: float = 0.0,
    bonus_cleared: bool = False,
    cleared_at: str | None = None,
    created_at: str = "2024-01-16T10:00:00",
) -> dict:
    """Create a mock dividend database row."""
    return {
        "id": id,
        "symbol": symbol,
        "isin": isin,
        "cash_flow_id": cash_flow_id,
        "amount": amount,
        "currency": currency,
        "amount_eur": amount_eur,
        "payment_date": payment_date,
        "reinvested": 1 if reinvested else 0,
        "reinvested_at": reinvested_at,
        "reinvested_quantity": reinvested_quantity,
        "pending_bonus": pending_bonus,
        "bonus_cleared": 1 if bonus_cleared else 0,
        "cleared_at": cleared_at,
        "created_at": created_at,
    }


class TestDividendRepositoryCreate:
    """Test dividend record creation."""

    @pytest.mark.asyncio
    async def test_create_dividend_record(self):
        """Test creating a new dividend record."""
        with patch("app.repositories.dividend.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = MagicMock()
            mock_db.dividends = mock_ledger
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

            repo = DividendRepository()
            dividend = DividendRecord(
                symbol="AAPL",
                cash_flow_id=100,
                amount=10.0,
                currency="USD",
                amount_eur=9.5,
                payment_date="2024-01-15",
            )

            result = await repo.create(dividend)

            assert result.id == 42
            assert result.created_at is not None
            mock_conn.execute.assert_called_once()


class TestDividendRepositoryQuery:
    """Test dividend query operations."""

    @pytest.mark.asyncio
    async def test_get_by_id(self):
        """Test retrieving dividend by ID."""
        with patch("app.repositories.dividend.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = AsyncMock()
            mock_db.dividends = mock_ledger
            mock_get_db.return_value = mock_db

            mock_row = create_mock_dividend(id=1, symbol="AAPL")
            mock_ledger.fetchone.return_value = mock_row

            repo = DividendRepository()
            result = await repo.get_by_id(1)

            assert result is not None
            assert result.id == 1
            assert result.symbol == "AAPL"

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self):
        """Test retrieving non-existent dividend returns None."""
        with patch("app.repositories.dividend.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = AsyncMock()
            mock_db.dividends = mock_ledger
            mock_get_db.return_value = mock_db

            mock_ledger.fetchone.return_value = None

            repo = DividendRepository()
            result = await repo.get_by_id(999)

            assert result is None

    @pytest.mark.asyncio
    async def test_get_by_cash_flow_id(self):
        """Test retrieving dividend by cash flow ID."""
        with patch("app.repositories.dividend.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = AsyncMock()
            mock_db.dividends = mock_ledger
            mock_get_db.return_value = mock_db

            mock_row = create_mock_dividend(id=1, cash_flow_id=100)
            mock_ledger.fetchone.return_value = mock_row

            repo = DividendRepository()
            result = await repo.get_by_cash_flow_id(100)

            assert result is not None
            assert result.cash_flow_id == 100

    @pytest.mark.asyncio
    async def test_exists_for_cash_flow_true(self):
        """Test checking if dividend exists for cash flow."""
        with patch("app.repositories.dividend.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = AsyncMock()
            mock_db.dividends = mock_ledger
            mock_get_db.return_value = mock_db

            mock_ledger.fetchone.return_value = {"1": 1}  # Row exists

            repo = DividendRepository()
            result = await repo.exists_for_cash_flow(100)

            assert result is True

    @pytest.mark.asyncio
    async def test_exists_for_cash_flow_false(self):
        """Test checking if dividend doesn't exist for cash flow."""
        with patch("app.repositories.dividend.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = AsyncMock()
            mock_db.dividends = mock_ledger
            mock_get_db.return_value = mock_db

            mock_ledger.fetchone.return_value = None

            repo = DividendRepository()
            result = await repo.exists_for_cash_flow(999)

            assert result is False

    @pytest.mark.asyncio
    async def test_get_by_symbol(self):
        """Test retrieving all dividends for a symbol."""
        with patch("app.repositories.dividend.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = AsyncMock()
            mock_db.dividends = mock_ledger
            mock_get_db.return_value = mock_db

            mock_rows = [
                create_mock_dividend(id=1, symbol="AAPL", amount=10.0),
                create_mock_dividend(id=2, symbol="AAPL", amount=12.0),
            ]
            mock_ledger.fetchall.return_value = mock_rows

            repo = DividendRepository()
            result = await repo.get_by_symbol("aapl")  # Test lowercase normalization

            assert len(result) == 2
            assert all(d.symbol == "AAPL" for d in result)

    @pytest.mark.asyncio
    async def test_get_all_with_limit(self):
        """Test retrieving all dividends with limit."""
        with patch("app.repositories.dividend.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = AsyncMock()
            mock_db.dividends = mock_ledger
            mock_get_db.return_value = mock_db

            mock_rows = [create_mock_dividend(id=i) for i in range(5)]
            mock_ledger.fetchall.return_value = mock_rows

            repo = DividendRepository()
            result = await repo.get_all(limit=5)

            assert len(result) == 5
            mock_ledger.fetchall.assert_called()

    @pytest.mark.asyncio
    async def test_get_all_without_limit(self):
        """Test retrieving all dividends without limit."""
        with patch("app.repositories.dividend.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = AsyncMock()
            mock_db.dividends = mock_ledger
            mock_get_db.return_value = mock_db

            mock_rows = [create_mock_dividend(id=i) for i in range(10)]
            mock_ledger.fetchall.return_value = mock_rows

            repo = DividendRepository()
            result = await repo.get_all()

            assert len(result) == 10


class TestDividendRepositoryPendingBonus:
    """Test pending bonus operations."""

    @pytest.mark.asyncio
    async def test_get_pending_bonuses(self):
        """Test retrieving all pending bonuses by symbol."""
        with patch("app.repositories.dividend.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = AsyncMock()
            mock_db.dividends = mock_ledger
            mock_get_db.return_value = mock_db

            mock_rows = [
                {"symbol": "AAPL", "total_bonus": 5.0},
                {"symbol": "GOOGL", "total_bonus": 3.0},
            ]
            mock_ledger.fetchall.return_value = mock_rows

            repo = DividendRepository()
            result = await repo.get_pending_bonuses()

            assert result == {"AAPL": 5.0, "GOOGL": 3.0}

    @pytest.mark.asyncio
    async def test_get_pending_bonus_for_symbol(self):
        """Test retrieving pending bonus for a specific symbol."""
        with patch("app.repositories.dividend.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = AsyncMock()
            mock_db.dividends = mock_ledger
            mock_get_db.return_value = mock_db

            mock_ledger.fetchone.return_value = {"total": 5.0}

            repo = DividendRepository()
            result = await repo.get_pending_bonus("aapl")

            assert result == 5.0

    @pytest.mark.asyncio
    async def test_get_pending_bonus_returns_zero_when_none(self):
        """Test that pending bonus returns 0 when no bonuses exist."""
        with patch("app.repositories.dividend.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = AsyncMock()
            mock_db.dividends = mock_ledger
            mock_get_db.return_value = mock_db

            mock_ledger.fetchone.return_value = {"total": 0}

            repo = DividendRepository()
            result = await repo.get_pending_bonus("NEWSTOCK")

            assert result == 0.0

    @pytest.mark.asyncio
    async def test_set_pending_bonus(self):
        """Test setting pending bonus for a dividend."""
        with patch("app.repositories.dividend.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = AsyncMock()
            mock_db.dividends = mock_ledger
            mock_get_db.return_value = mock_db

            repo = DividendRepository()
            await repo.set_pending_bonus(dividend_id=1, bonus=5.0)

            mock_ledger.execute.assert_called_once()
            mock_ledger.commit.assert_called_once()
            # Verify the bonus value was passed
            call_args = mock_ledger.execute.call_args
            assert 5.0 in call_args[0][1]

    @pytest.mark.asyncio
    async def test_clear_bonus(self):
        """Test clearing pending bonuses for a symbol."""
        with patch("app.repositories.dividend.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = AsyncMock()
            mock_db.dividends = mock_ledger
            mock_get_db.return_value = mock_db

            mock_cursor = MagicMock()
            mock_cursor.rowcount = 2
            mock_ledger.execute.return_value = mock_cursor

            repo = DividendRepository()
            result = await repo.clear_bonus("aapl")

            assert result == 2  # 2 records updated
            mock_ledger.commit.assert_called_once()


class TestDividendRepositoryReinvestment:
    """Test DRIP reinvestment operations."""

    @pytest.mark.asyncio
    async def test_mark_reinvested(self):
        """Test marking a dividend as reinvested."""
        with patch("app.repositories.dividend.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = AsyncMock()
            mock_db.dividends = mock_ledger
            mock_get_db.return_value = mock_db

            repo = DividendRepository()
            await repo.mark_reinvested(dividend_id=1, quantity=5)

            mock_ledger.execute.assert_called_once()
            mock_ledger.commit.assert_called_once()

            # Verify the parameters include quantity and dividend_id
            call_args = mock_ledger.execute.call_args
            params = call_args[0][1]
            assert 5 in params  # quantity
            assert 1 in params  # dividend_id

    @pytest.mark.asyncio
    async def test_get_unreinvested_dividends(self):
        """Test retrieving dividends that haven't been reinvested."""
        with patch("app.repositories.dividend.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = AsyncMock()
            mock_db.dividends = mock_ledger
            mock_get_db.return_value = mock_db

            mock_rows = [
                create_mock_dividend(id=1, reinvested=False, amount_eur=10.0),
                create_mock_dividend(id=2, reinvested=False, amount_eur=15.0),
            ]
            mock_ledger.fetchall.return_value = mock_rows

            repo = DividendRepository()
            result = await repo.get_unreinvested_dividends(min_amount_eur=5.0)

            assert len(result) == 2
            assert all(not d.reinvested for d in result)

    @pytest.mark.asyncio
    async def test_get_total_reinvested(self):
        """Test getting total reinvested amount."""
        with patch("app.repositories.dividend.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = AsyncMock()
            mock_db.dividends = mock_ledger
            mock_get_db.return_value = mock_db

            mock_ledger.fetchone.return_value = {"total": 1500.0}

            repo = DividendRepository()
            result = await repo.get_total_reinvested()

            assert result == 1500.0

    @pytest.mark.asyncio
    async def test_get_total_reinvested_returns_zero_when_none(self):
        """Test that total reinvested returns 0 when no data."""
        with patch("app.repositories.dividend.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = AsyncMock()
            mock_db.dividends = mock_ledger
            mock_get_db.return_value = mock_db

            mock_ledger.fetchone.return_value = None

            repo = DividendRepository()
            result = await repo.get_total_reinvested()

            assert result == 0.0

    @pytest.mark.asyncio
    async def test_get_reinvestment_rate(self):
        """Test calculating reinvestment rate."""
        with patch("app.repositories.dividend.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = AsyncMock()
            mock_db.dividends = mock_ledger
            mock_get_db.return_value = mock_db

            mock_ledger.fetchone.return_value = {"reinvested": 750.0, "total": 1000.0}

            repo = DividendRepository()
            result = await repo.get_reinvestment_rate()

            assert result == 0.75  # 75% reinvestment rate

    @pytest.mark.asyncio
    async def test_get_reinvestment_rate_returns_zero_when_no_dividends(self):
        """Test that reinvestment rate returns 0 when no dividends."""
        with patch("app.repositories.dividend.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = AsyncMock()
            mock_db.dividends = mock_ledger
            mock_get_db.return_value = mock_db

            mock_ledger.fetchone.return_value = {"reinvested": 0, "total": 0}

            repo = DividendRepository()
            result = await repo.get_reinvestment_rate()

            assert result == 0.0


class TestDividendRepositoryStatistics:
    """Test dividend statistics operations."""

    @pytest.mark.asyncio
    async def test_get_total_dividends_by_symbol(self):
        """Test getting total dividends per symbol."""
        with patch("app.repositories.dividend.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_ledger = AsyncMock()
            mock_db.dividends = mock_ledger
            mock_get_db.return_value = mock_db

            mock_rows = [
                {"symbol": "AAPL", "total": 500.0},
                {"symbol": "GOOGL", "total": 300.0},
                {"symbol": "MSFT", "total": 200.0},
            ]
            mock_ledger.fetchall.return_value = mock_rows

            repo = DividendRepository()
            result = await repo.get_total_dividends_by_symbol()

            assert result == {"AAPL": 500.0, "GOOGL": 300.0, "MSFT": 200.0}


class TestDividendRepositoryRowConversion:
    """Test row to model conversion."""

    def test_row_to_dividend_basic(self):
        """Test converting a basic database row to DividendRecord."""
        with patch("app.repositories.dividend.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value = mock_db

            repo = DividendRepository()
            row = create_mock_dividend(
                id=1,
                symbol="AAPL",
                amount=10.0,
                currency="USD",
                amount_eur=9.5,
            )

            result = repo._row_to_dividend(row)

            assert isinstance(result, DividendRecord)
            assert result.id == 1
            assert result.symbol == "AAPL"
            assert result.amount == 10.0
            assert result.currency == "USD"
            assert result.amount_eur == 9.5
            assert result.reinvested is False
            assert result.bonus_cleared is False

    def test_row_to_dividend_reinvested(self):
        """Test converting a reinvested dividend row."""
        with patch("app.repositories.dividend.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value = mock_db

            repo = DividendRepository()
            row = create_mock_dividend(
                id=1,
                reinvested=True,
                reinvested_at="2024-01-20T10:00:00",
                reinvested_quantity=5,
            )

            result = repo._row_to_dividend(row)

            assert result.reinvested is True
            assert result.reinvested_at == "2024-01-20T10:00:00"
            assert result.reinvested_quantity == 5

    def test_row_to_dividend_with_bonus(self):
        """Test converting a dividend row with pending bonus."""
        with patch("app.repositories.dividend.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value = mock_db

            repo = DividendRepository()
            row = create_mock_dividend(
                id=1,
                pending_bonus=5.0,
                bonus_cleared=False,
            )

            result = repo._row_to_dividend(row)

            assert result.pending_bonus == 5.0
            assert result.bonus_cleared is False

    def test_row_to_dividend_cleared_bonus(self):
        """Test converting a dividend row with cleared bonus."""
        with patch("app.repositories.dividend.get_db_manager") as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value = mock_db

            repo = DividendRepository()
            row = create_mock_dividend(
                id=1,
                pending_bonus=0.0,
                bonus_cleared=True,
                cleared_at="2024-01-25T10:00:00",
            )

            result = repo._row_to_dividend(row)

            assert result.pending_bonus == 0.0
            assert result.bonus_cleared is True
            assert result.cleared_at == "2024-01-25T10:00:00"
