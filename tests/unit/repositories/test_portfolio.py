"""Tests for portfolio repository.

These tests validate portfolio snapshot storage and retrieval.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.models import PortfolioSnapshot
from app.modules.portfolio.database.portfolio_repository import PortfolioRepository


class TestPortfolioRepository:
    """Test PortfolioRepository class."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database."""
        db = AsyncMock()
        db.fetchone = AsyncMock(return_value=None)
        db.fetchall = AsyncMock(return_value=[])
        db.execute = AsyncMock()
        db.commit = AsyncMock()
        return db

    @pytest.fixture
    def repo(self, mock_db):
        """Create repository with mocked database."""
        return PortfolioRepository(db=mock_db)

    @pytest.fixture
    def sample_row(self):
        """Create sample database row."""
        return {
            "date": "2024-01-15",
            "total_value": 100000.0,
            "cash_balance": 5000.0,
            "invested_value": 95000.0,
            "unrealized_pnl": 2500.0,
            "geo_eu_pct": 30.0,
            "geo_asia_pct": 20.0,
            "geo_us_pct": 50.0,
            "position_count": 15,
        }

    @pytest.mark.asyncio
    async def test_get_by_date_returns_snapshot(self, repo, mock_db, sample_row):
        """Test getting snapshot by date."""
        mock_db.fetchone.return_value = sample_row

        result = await repo.get_by_date("2024-01-15")

        assert result is not None
        assert isinstance(result, PortfolioSnapshot)
        assert result.date == "2024-01-15"
        assert result.total_value == 100000.0

    @pytest.mark.asyncio
    async def test_get_by_date_returns_none_when_not_found(self, repo, mock_db):
        """Test getting snapshot for non-existent date."""
        mock_db.fetchone.return_value = None

        result = await repo.get_by_date("2024-01-15")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_latest(self, repo, mock_db, sample_row):
        """Test getting latest snapshot."""
        mock_db.fetchone.return_value = sample_row

        result = await repo.get_latest()

        assert result is not None
        assert result.total_value == 100000.0

    @pytest.mark.asyncio
    async def test_get_latest_returns_none_when_empty(self, repo, mock_db):
        """Test getting latest when no snapshots exist."""
        mock_db.fetchone.return_value = None

        result = await repo.get_latest()

        assert result is None

    @pytest.mark.asyncio
    async def test_get_latest_cash_balance(self, repo, mock_db):
        """Test getting latest cash balance."""
        mock_db.fetchone.return_value = {"cash_balance": 5000.0}

        result = await repo.get_latest_cash_balance()

        assert result == 5000.0

    @pytest.mark.asyncio
    async def test_get_latest_cash_balance_returns_zero_when_empty(self, repo, mock_db):
        """Test getting cash balance when no snapshots exist."""
        mock_db.fetchone.return_value = None

        result = await repo.get_latest_cash_balance()

        assert result == 0.0

    @pytest.mark.asyncio
    async def test_get_history(self, repo, mock_db, sample_row):
        """Test getting snapshot history."""
        mock_db.fetchall.return_value = [sample_row, sample_row]

        result = await repo.get_history(days=30)

        assert len(result) == 2
        assert all(isinstance(s, PortfolioSnapshot) for s in result)

    @pytest.mark.asyncio
    async def test_get_history_empty(self, repo, mock_db):
        """Test getting history when no snapshots exist."""
        mock_db.fetchall.return_value = []

        result = await repo.get_history()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_range(self, repo, mock_db, sample_row):
        """Test getting snapshots within date range."""
        mock_db.fetchall.return_value = [sample_row]

        result = await repo.get_range("2024-01-01", "2024-01-31")

        assert len(result) == 1
        mock_db.fetchall.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_snapshot(self, repo):
        """Test upserting a snapshot."""
        snapshot = PortfolioSnapshot(
            date="2024-01-15",
            total_value=100000.0,
            cash_balance=5000.0,
        )

        with patch(
            "app.modules.portfolio.database.portfolio_repository.transaction_context"
        ) as mock_txn:
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock()

            class MockContext:
                async def __aenter__(self):
                    return mock_conn

                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    return False

            mock_txn.return_value = MockContext()

            await repo.upsert(snapshot)

            mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_before(self, repo, mock_db):
        """Test deleting snapshots before date."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value={"cnt": 5})
        mock_db.execute.return_value = mock_cursor

        with patch(
            "app.modules.portfolio.database.portfolio_repository.transaction_context"
        ) as mock_txn:
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock()

            class MockContext:
                async def __aenter__(self):
                    return mock_conn

                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    return False

            mock_txn.return_value = MockContext()

            result = await repo.delete_before("2024-01-01")

            assert result == 5
            mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_before_none_to_delete(self, repo, mock_db):
        """Test delete_before when no records match."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value={"cnt": 0})
        mock_db.execute.return_value = mock_cursor

        result = await repo.delete_before("2024-01-01")

        assert result == 0

    @pytest.mark.asyncio
    async def test_get_value_change_with_data(self, repo, mock_db, sample_row):
        """Test getting value change over time."""
        old_row = {**sample_row, "total_value": 90000.0}
        new_row = {**sample_row, "total_value": 100000.0}
        mock_db.fetchall.return_value = [new_row, old_row]

        result = await repo.get_value_change(days=30)

        assert result["change"] == 10000.0
        assert result["change_pct"] == pytest.approx(11.11, rel=0.1)
        assert result["days"] == 2

    @pytest.mark.asyncio
    async def test_get_value_change_insufficient_data(self, repo, mock_db, sample_row):
        """Test value change with less than 2 snapshots."""
        mock_db.fetchall.return_value = [sample_row]

        result = await repo.get_value_change()

        assert result == {"change": 0, "change_pct": 0, "days": 0}

    @pytest.mark.asyncio
    async def test_get_value_change_zero_start_value(self, repo, mock_db):
        """Test value change when start value is zero."""
        old_row = {
            "date": "2024-01-01",
            "total_value": 0.0,
            "cash_balance": 0.0,
        }
        new_row = {
            "date": "2024-01-15",
            "total_value": 100000.0,
            "cash_balance": 5000.0,
        }
        mock_db.fetchall.return_value = [new_row, old_row]

        result = await repo.get_value_change()

        assert result["change"] == 100000.0
        assert result["change_pct"] == 0  # Division by zero handled

    def test_row_to_snapshot_with_valid_data(self, repo, sample_row):
        """Test converting row to PortfolioSnapshot."""
        result = repo._row_to_snapshot(sample_row)

        assert isinstance(result, PortfolioSnapshot)
        assert result.date == "2024-01-15"
        assert result.total_value == 100000.0
        assert result.geo_us_pct == 50.0

    def test_row_to_snapshot_with_missing_fields(self, repo):
        """Test converting row with missing optional fields."""
        row = {
            "date": "2024-01-15",
            "total_value": 100000.0,
            "cash_balance": 5000.0,
        }

        class RowProxy:
            def __init__(self, data):
                self._data = data

            def __getitem__(self, key):
                return self._data.get(key)

        result = repo._row_to_snapshot(RowProxy(row))

        assert result.date == "2024-01-15"
        assert result.geo_us_pct is None

    def test_init_with_raw_connection(self):
        """Test initializing with raw aiosqlite connection."""
        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock()
        del mock_conn.fetchone

        repo = PortfolioRepository(db=mock_conn)

        assert hasattr(repo._db, "fetchone")

    def test_init_with_database_instance(self):
        """Test initializing with Database instance."""
        mock_db = AsyncMock()
        mock_db.fetchone = AsyncMock()
        mock_db.fetchall = AsyncMock()

        repo = PortfolioRepository(db=mock_db)

        assert repo._db == mock_db

    def test_init_without_db(self):
        """Test initializing without db uses get_db_manager."""
        with patch(
            "app.modules.portfolio.database.portfolio_repository.get_db_manager"
        ) as mock_manager:
            mock_snapshots = MagicMock()
            mock_db_manager = MagicMock()
            mock_db_manager.snapshots = mock_snapshots
            mock_manager.return_value = mock_db_manager

            repo = PortfolioRepository()

            mock_manager.assert_called_once()
            assert repo._db == mock_snapshots
