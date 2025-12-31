"""Tests for position repository.

These tests validate position CRUD operations.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain.models import Position


class TestPositionRepositoryInit:
    """Test position repository initialization."""

    def test_init_with_db(self):
        """Test initialization with provided database."""
        from app.modules.portfolio.database.position_repository import (
            PositionRepository,
        )

        mock_db = AsyncMock()
        mock_db.fetchone = AsyncMock()

        repo = PositionRepository(db=mock_db)

        assert repo._db == mock_db

    def test_init_wraps_raw_connection(self):
        """Test that raw connection is wrapped."""
        from app.modules.portfolio.database.position_repository import (
            PositionRepository,
        )

        mock_conn = MagicMock()
        mock_conn.execute = MagicMock()

        repo = PositionRepository(db=mock_conn)

        assert hasattr(repo._db, "fetchone")


class TestPositionRepositoryQueries:
    """Test position query operations."""

    @pytest.mark.asyncio
    async def test_get_by_symbol_found(self):
        """Test getting position by symbol when found."""
        from app.modules.portfolio.database.position_repository import (
            PositionRepository,
        )

        mock_row = {
            "symbol": "AAPL.US",
            "quantity": 10,
            "avg_price": 145.0,
            "current_price": 150.0,
            "currency": "USD",
            "currency_rate": 0.92,
            "market_value_eur": 1380.0,
            "cost_basis_eur": 1334.0,
            "unrealized_pnl": 46.0,
            "unrealized_pnl_pct": 3.45,
            "last_updated": "2024-01-15",
            "first_bought_at": "2023-06-15",
            "last_sold_at": None,
        }

        mock_db = AsyncMock()
        mock_db.fetchone = AsyncMock(return_value=mock_row)

        repo = PositionRepository(db=mock_db)

        result = await repo.get_by_symbol("AAPL.US")

        assert result is not None
        assert result.symbol == "AAPL.US"
        assert result.quantity == 10

    @pytest.mark.asyncio
    async def test_get_by_symbol_not_found(self):
        """Test getting position by symbol when not found."""
        from app.modules.portfolio.database.position_repository import (
            PositionRepository,
        )

        mock_db = AsyncMock()
        mock_db.fetchone = AsyncMock(return_value=None)

        repo = PositionRepository(db=mock_db)

        result = await repo.get_by_symbol("NONEXISTENT")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_all(self):
        """Test getting all positions."""
        from app.modules.portfolio.database.position_repository import (
            PositionRepository,
        )

        mock_rows = [
            {
                "symbol": "AAPL.US",
                "quantity": 10,
                "avg_price": 145.0,
                "current_price": 150.0,
                "currency": "USD",
                "currency_rate": 0.92,
                "market_value_eur": 1380.0,
                "cost_basis_eur": 1334.0,
                "unrealized_pnl": 46.0,
                "unrealized_pnl_pct": 3.45,
                "last_updated": "2024-01-15",
                "first_bought_at": "2023-06-15",
                "last_sold_at": None,
            }
        ]

        mock_db = AsyncMock()
        mock_db.fetchall = AsyncMock(return_value=mock_rows)

        repo = PositionRepository(db=mock_db)

        result = await repo.get_all()

        assert len(result) == 1
        assert all(isinstance(p, Position) for p in result)


class TestPositionRepositoryUpsert:
    """Test position upsert operations."""

    @pytest.mark.asyncio
    async def test_upsert_position(self):
        """Test upserting a position."""
        from app.modules.portfolio.database.position_repository import (
            PositionRepository,
        )

        mock_db = AsyncMock()
        mock_db.transaction = MagicMock()
        mock_db.transaction.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.transaction.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = PositionRepository(db=mock_db)

        position = Position(
            symbol="AAPL.US",
            quantity=10,
            avg_price=145.0,
            current_price=150.0,
            currency="USD",
            currency_rate=0.92,
            market_value_eur=1380.0,
            cost_basis_eur=1334.0,
            unrealized_pnl=46.0,
            unrealized_pnl_pct=3.45,
            last_updated="2024-01-15",
            first_bought_at="2023-06-15",
            last_sold_at=None,
        )

        await repo.upsert(position)

        mock_db.execute.assert_called_once()


class TestPositionRepositoryDelete:
    """Test position delete operations."""

    @pytest.mark.asyncio
    async def test_delete_all(self):
        """Test deleting all positions."""
        from app.modules.portfolio.database.position_repository import (
            PositionRepository,
        )

        mock_db = AsyncMock()
        mock_db.transaction = MagicMock()
        mock_db.transaction.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.transaction.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = PositionRepository(db=mock_db)

        await repo.delete_all()

        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_by_symbol(self):
        """Test deleting a specific position."""
        from app.modules.portfolio.database.position_repository import (
            PositionRepository,
        )

        mock_db = AsyncMock()
        mock_db.transaction = MagicMock()
        mock_db.transaction.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.transaction.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = PositionRepository(db=mock_db)

        await repo.delete("AAPL.US")

        mock_db.execute.assert_called_once()


class TestPositionRepositoryUpdatePrice:
    """Test price update operations."""

    @pytest.mark.asyncio
    async def test_update_price(self):
        """Test updating price for a position."""
        from app.modules.portfolio.database.position_repository import (
            PositionRepository,
        )

        mock_db = AsyncMock()
        mock_db.transaction = MagicMock()
        mock_db.transaction.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.transaction.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = PositionRepository(db=mock_db)

        await repo.update_price("AAPL.US", 155.0, 0.92)

        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_last_sold_at(self):
        """Test updating last sold timestamp."""
        from app.modules.portfolio.database.position_repository import (
            PositionRepository,
        )

        mock_db = AsyncMock()
        mock_db.transaction = MagicMock()
        mock_db.transaction.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.transaction.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = PositionRepository(db=mock_db)

        await repo.update_last_sold_at("AAPL.US")

        mock_db.execute.assert_called_once()


class TestPositionRepositoryGetTotalValue:
    """Test getting total portfolio value."""

    @pytest.mark.asyncio
    async def test_get_total_value(self):
        """Test getting total portfolio value."""
        from app.modules.portfolio.database.position_repository import (
            PositionRepository,
        )

        mock_db = AsyncMock()
        mock_db.fetchone = AsyncMock(return_value={"total": 50000.0})

        repo = PositionRepository(db=mock_db)

        result = await repo.get_total_value()

        assert result == 50000.0

    @pytest.mark.asyncio
    async def test_get_total_value_no_positions(self):
        """Test getting total value when no positions."""
        from app.modules.portfolio.database.position_repository import (
            PositionRepository,
        )

        mock_db = AsyncMock()
        mock_db.fetchone = AsyncMock(return_value=None)

        repo = PositionRepository(db=mock_db)

        result = await repo.get_total_value()

        assert result == 0.0


class TestPositionRepositoryGetWithStockInfo:
    """Test getting positions with security info."""

    @pytest.mark.asyncio
    async def test_get_with_stock_info_empty(self):
        """Test getting positions when empty."""
        from app.modules.portfolio.database.position_repository import (
            PositionRepository,
        )

        mock_db = AsyncMock()
        mock_db.fetchall = AsyncMock(return_value=[])

        repo = PositionRepository(db=mock_db)

        result = await repo.get_with_stock_info()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_with_stock_info_merges_data(self):
        """Test that position and security data are merged."""
        from app.modules.portfolio.database.position_repository import (
            PositionRepository,
        )

        mock_pos_row = MagicMock()
        mock_pos_row.__getitem__ = lambda self, key: {
            "symbol": "AAPL.US",
            "quantity": 10,
            "avg_price": 145.0,
            "current_price": 150.0,
            "currency": "USD",
            "market_value_eur": 1380.0,
        }.get(key)
        mock_pos_row.keys = lambda: [
            "symbol",
            "quantity",
            "avg_price",
            "current_price",
            "currency",
            "market_value_eur",
        ]

        mock_stock_row = MagicMock()
        mock_stock_row.__getitem__ = lambda self, key: {
            "symbol": "AAPL.US",
            "name": "Apple Inc",
            "country": "United States",
            "industry": "Consumer Electronics",
            "min_lot": 1,
            "allow_sell": 1,
            "currency": "USD",
        }.get(key)
        mock_stock_row.keys = lambda: [
            "symbol",
            "name",
            "country",
            "industry",
            "min_lot",
            "allow_sell",
            "currency",
        ]

        mock_db = AsyncMock()
        mock_db.fetchall = AsyncMock(return_value=[mock_pos_row])

        mock_config_db = AsyncMock()
        mock_config_db.fetchall = AsyncMock(return_value=[mock_stock_row])

        mock_manager = MagicMock()
        mock_manager.config = mock_config_db

        repo = PositionRepository(db=mock_db)
        repo._manager = mock_manager

        result = await repo.get_with_stock_info()

        assert len(result) == 1
        assert result[0]["name"] == "Apple Inc"
        assert result[0]["country"] == "United States"


class TestRowToPosition:
    """Test row to position conversion."""

    def test_converts_valid_row(self):
        """Test converting a valid database row to Position model."""
        from app.modules.portfolio.database.position_repository import (
            PositionRepository,
        )

        mock_db = AsyncMock()
        repo = PositionRepository(db=mock_db)

        row = {
            "symbol": "AAPL.US",
            "quantity": 10,
            "avg_price": 145.0,
            "current_price": 150.0,
            "currency": "USD",
            "currency_rate": 0.92,
            "market_value_eur": 1380.0,
            "cost_basis_eur": 1334.0,
            "unrealized_pnl": 46.0,
            "unrealized_pnl_pct": 3.45,
            "last_updated": "2024-01-15",
            "first_bought_at": "2023-06-15",
            "last_sold_at": None,
        }

        row_mock = MagicMock()
        row_mock.__getitem__ = lambda self, key: row[key]
        row_mock.keys = lambda: row.keys()

        result = repo._row_to_position(row_mock)

        assert result.symbol == "AAPL.US"
        assert result.quantity == 10
        assert result.avg_price == 145.0

    def test_handles_null_values(self):
        """Test handling null values in row."""
        from app.modules.portfolio.database.position_repository import (
            PositionRepository,
        )

        mock_db = AsyncMock()
        repo = PositionRepository(db=mock_db)

        row = {
            "symbol": "AAPL.US",
            "quantity": 10,
            "avg_price": 145.0,
            "current_price": 150.0,
            "currency": None,
            "currency_rate": None,
            "market_value_eur": 1380.0,
            "cost_basis_eur": None,
            "unrealized_pnl": None,
            "unrealized_pnl_pct": None,
            "last_updated": "2024-01-15",
            "first_bought_at": None,
            "last_sold_at": None,
        }

        row_mock = MagicMock()
        row_mock.__getitem__ = lambda self, key: row[key]
        row_mock.keys = lambda: row.keys()

        result = repo._row_to_position(row_mock)

        # Should use defaults for nulls
        assert result.currency_rate == 1.0
