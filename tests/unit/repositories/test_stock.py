"""Tests for stock repository.

These tests validate stock CRUD operations.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.models import Stock


class TestStockRepositoryInit:
    """Test stock repository initialization."""

    def test_init_with_db(self):
        """Test initialization with provided database."""
        from app.modules.universe.database.stock_repository import StockRepository

        mock_db = AsyncMock()
        mock_db.fetchone = AsyncMock()

        repo = StockRepository(db=mock_db)

        assert repo._db == mock_db

    def test_init_wraps_raw_connection(self):
        """Test that raw connection is wrapped."""
        from app.modules.universe.database.stock_repository import StockRepository

        mock_conn = MagicMock()
        mock_conn.execute = MagicMock()
        # No fetchone attribute

        repo = StockRepository(db=mock_conn)

        # Should be wrapped in DatabaseAdapter
        assert hasattr(repo._db, "fetchone")


class TestStockRepositoryQueries:
    """Test stock query operations."""

    @pytest.mark.asyncio
    async def test_get_by_symbol_found(self):
        """Test getting stock by symbol when found."""
        from app.modules.universe.database.stock_repository import StockRepository

        mock_row = {
            "symbol": "AAPL.US",
            "yahoo_symbol": "AAPL",
            "name": "Apple Inc",
            "industry": "Consumer Electronics",
            "country": "United States",
            "priority_multiplier": 1.0,
            "min_lot": 1,
            "active": 1,
            "allow_buy": 1,
            "allow_sell": 0,
            "currency": "USD",
        }

        mock_db = AsyncMock()
        mock_db.fetchone = AsyncMock(return_value=mock_row)

        repo = StockRepository(db=mock_db)

        result = await repo.get_by_symbol("AAPL.US")

        assert result is not None
        assert result.symbol == "AAPL.US"
        assert result.name == "Apple Inc"

    @pytest.mark.asyncio
    async def test_get_by_symbol_not_found(self):
        """Test getting stock by symbol when not found."""
        from app.modules.universe.database.stock_repository import StockRepository

        mock_db = AsyncMock()
        mock_db.fetchone = AsyncMock(return_value=None)

        repo = StockRepository(db=mock_db)

        result = await repo.get_by_symbol("NONEXISTENT")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_all_active(self):
        """Test getting all active stocks."""
        from app.modules.universe.database.stock_repository import StockRepository

        mock_rows = [
            {
                "symbol": "AAPL.US",
                "yahoo_symbol": "AAPL",
                "name": "Apple Inc",
                "industry": "Consumer Electronics",
                "country": "United States",
                "priority_multiplier": 1.0,
                "min_lot": 1,
                "active": 1,
                "allow_buy": 1,
                "allow_sell": 0,
                "currency": "USD",
            },
            {
                "symbol": "MSFT.US",
                "yahoo_symbol": "MSFT",
                "name": "Microsoft Corp",
                "industry": "Consumer Electronics",
                "country": "United States",
                "priority_multiplier": 1.0,
                "min_lot": 1,
                "active": 1,
                "allow_buy": 1,
                "allow_sell": 0,
                "currency": "USD",
            },
        ]

        mock_db = AsyncMock()
        mock_db.fetchall = AsyncMock(return_value=mock_rows)

        repo = StockRepository(db=mock_db)

        result = await repo.get_all_active()

        assert len(result) == 2
        assert all(isinstance(s, Stock) for s in result)

    @pytest.mark.asyncio
    async def test_get_all(self):
        """Test getting all stocks."""
        from app.modules.universe.database.stock_repository import StockRepository

        mock_rows = [
            {
                "symbol": "AAPL.US",
                "yahoo_symbol": "AAPL",
                "name": "Apple Inc",
                "industry": "Consumer Electronics",
                "country": "United States",
                "priority_multiplier": 1.0,
                "min_lot": 1,
                "active": 1,
                "allow_buy": 1,
                "allow_sell": 0,
                "currency": "USD",
            }
        ]

        mock_db = AsyncMock()
        mock_db.fetchall = AsyncMock(return_value=mock_rows)

        repo = StockRepository(db=mock_db)

        result = await repo.get_all()

        assert len(result) == 1


class TestStockRepositoryCreate:
    """Test stock creation operations."""

    @pytest.mark.asyncio
    async def test_creates_stock(self):
        """Test creating a stock record."""
        from app.modules.universe.database.stock_repository import StockRepository

        mock_db = AsyncMock()
        mock_db.transaction = MagicMock()
        mock_db.transaction.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.transaction.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = StockRepository(db=mock_db)

        stock = Stock(
            symbol="AAPL.US",
            yahoo_symbol="AAPL",
            name="Apple Inc",
            industry="Consumer Electronics",
            country="United States",
            priority_multiplier=1.0,
            min_lot=1,
            active=True,
            allow_buy=True,
            allow_sell=False,
            currency="USD",
        )

        await repo.create(stock)

        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_with_portfolio_targets(self):
        """Test creating a stock with min/max portfolio targets."""
        from app.modules.universe.database.stock_repository import StockRepository

        mock_db = AsyncMock()
        mock_db.transaction = MagicMock()
        mock_db.transaction.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.transaction.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = StockRepository(db=mock_db)

        stock = Stock(
            symbol="AAPL.US",
            name="Apple Inc",
            min_portfolio_target=5.0,
            max_portfolio_target=15.0,
        )

        await repo.create(stock)

        mock_db.execute.assert_called_once()
        # Check that portfolio targets are in the INSERT statement
        call_args = mock_db.execute.call_args[0]
        assert 5.0 in call_args[1]  # min_portfolio_target
        assert 15.0 in call_args[1]  # max_portfolio_target

    @pytest.mark.asyncio
    async def test_create_with_null_portfolio_targets(self):
        """Test creating a stock with NULL portfolio targets."""
        from app.modules.universe.database.stock_repository import StockRepository

        mock_db = AsyncMock()
        mock_db.transaction = MagicMock()
        mock_db.transaction.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.transaction.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = StockRepository(db=mock_db)

        stock = Stock(symbol="AAPL.US", name="Apple Inc")

        await repo.create(stock)

        mock_db.execute.assert_called_once()
        # Check that None values are in the INSERT statement
        call_args = mock_db.execute.call_args[0]
        assert None in call_args[1]  # min_portfolio_target should be None
        # max_portfolio_target should also be None


class TestStockRepositoryUpdate:
    """Test stock update operations."""

    @pytest.mark.asyncio
    async def test_updates_stock(self):
        """Test updating a stock."""
        from app.modules.universe.database.stock_repository import StockRepository

        mock_db = AsyncMock()
        mock_db.transaction = MagicMock()
        mock_db.transaction.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.transaction.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = StockRepository(db=mock_db)

        await repo.update("AAPL.US", name="Apple Inc.", active=True)

        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_no_changes(self):
        """Test update with no changes does nothing."""
        from app.modules.universe.database.stock_repository import StockRepository

        mock_db = AsyncMock()

        repo = StockRepository(db=mock_db)

        await repo.update("AAPL.US")

        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_converts_booleans(self):
        """Test that boolean values are converted to integers."""
        from app.modules.universe.database.stock_repository import StockRepository

        mock_db = AsyncMock()
        mock_db.transaction = MagicMock()
        mock_db.transaction.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.transaction.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = StockRepository(db=mock_db)

        await repo.update("AAPL.US", active=True, allow_buy=False, allow_sell=True)

        mock_db.execute.assert_called_once()
        # Values should be converted to 1/0
        call_args = mock_db.execute.call_args[0][1]
        assert 1 in call_args  # active=True
        assert 0 in call_args  # allow_buy=False

    @pytest.mark.asyncio
    async def test_update_with_portfolio_targets(self):
        """Test updating stock with min/max portfolio targets."""
        from app.modules.universe.database.stock_repository import StockRepository

        mock_db = AsyncMock()
        mock_db.transaction = MagicMock()
        mock_db.transaction.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.transaction.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = StockRepository(db=mock_db)

        await repo.update(
            "AAPL.US", min_portfolio_target=5.0, max_portfolio_target=15.0
        )

        mock_db.execute.assert_called_once()
        call_args = mock_db.execute.call_args[0]
        assert "min_portfolio_target" in call_args[0]
        assert "max_portfolio_target" in call_args[0]

    @pytest.mark.asyncio
    async def test_update_clearing_portfolio_targets(self):
        """Test updating stock to clear portfolio targets (set to None)."""
        from app.modules.universe.database.stock_repository import StockRepository

        mock_db = AsyncMock()
        mock_db.transaction = MagicMock()
        mock_db.transaction.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.transaction.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = StockRepository(db=mock_db)

        await repo.update(
            "AAPL.US", min_portfolio_target=None, max_portfolio_target=None
        )

        mock_db.execute.assert_called_once()
        call_args = mock_db.execute.call_args[0]
        assert "min_portfolio_target" in call_args[0]
        assert "max_portfolio_target" in call_args[0]


class TestStockRepositoryDelete:
    """Test stock delete operations."""

    @pytest.mark.asyncio
    async def test_delete_sets_inactive(self):
        """Test that delete soft-deletes by setting active=False."""
        from app.modules.universe.database.stock_repository import StockRepository

        mock_db = AsyncMock()
        mock_db.transaction = MagicMock()
        mock_db.transaction.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.transaction.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = StockRepository(db=mock_db)

        await repo.delete("AAPL.US")

        # Should call update with active=False
        mock_db.execute.assert_called_once()


class TestStockRepositoryGetWithScores:
    """Test getting stocks with scores."""

    @pytest.mark.asyncio
    async def test_merges_stock_score_position_data(self):
        """Test that stock, score, and position data are merged."""
        from app.modules.universe.database.stock_repository import StockRepository

        mock_stock_row = MagicMock()
        mock_stock_row.__getitem__ = lambda self, key: {
            "symbol": "AAPL.US",
            "yahoo_symbol": "AAPL",
            "name": "Apple Inc",
            "industry": "Consumer Electronics",
            "country": "United States",
            "priority_multiplier": 1.0,
            "min_lot": 1,
            "active": 1,
            "allow_buy": 1,
            "allow_sell": 0,
            "currency": "USD",
            "min_portfolio_target": 5.0,
            "max_portfolio_target": 15.0,
        }[key]
        mock_stock_row.keys = lambda: [
            "symbol",
            "yahoo_symbol",
            "name",
            "industry",
            "country",
            "priority_multiplier",
            "min_portfolio_target",
            "max_portfolio_target",
            "min_lot",
            "active",
            "allow_buy",
            "allow_sell",
            "currency",
        ]

        mock_score_row = MagicMock()
        mock_score_row.__getitem__ = lambda self, key: {
            "symbol": "AAPL.US",
            "total_score": 0.85,
            "quality_score": 0.9,
            "opportunity_score": 0.8,
            "analyst_score": 0.75,
            "allocation_fit_score": 0.7,
            "volatility": 0.2,
            "calculated_at": "2024-01-15",
        }[key]
        mock_score_row.keys = lambda: [
            "symbol",
            "total_score",
            "quality_score",
            "opportunity_score",
            "analyst_score",
            "allocation_fit_score",
            "volatility",
            "calculated_at",
        ]

        mock_position_row = MagicMock()
        mock_position_row.__getitem__ = lambda self, key: {
            "symbol": "AAPL.US",
            "market_value_eur": 5000.0,
            "quantity": 10,
            "avg_price": 145.0,
            "current_price": 150.0,
        }[key]
        mock_position_row.keys = lambda: [
            "symbol",
            "market_value_eur",
            "quantity",
            "avg_price",
            "current_price",
        ]

        mock_db = AsyncMock()
        mock_db.fetchall = AsyncMock(return_value=[mock_stock_row])

        mock_state_db = AsyncMock()
        mock_state_db.fetchall = AsyncMock(return_value=[mock_position_row])

        mock_calculations_db = AsyncMock()
        mock_calculations_db.fetchall = AsyncMock(return_value=[mock_score_row])

        mock_db_manager = MagicMock()
        mock_db_manager.calculations = mock_calculations_db
        mock_db_manager.state = mock_state_db

        repo = StockRepository(db=mock_db)

        with patch(
            "app.modules.universe.database.stock_repository.get_db_manager",
            return_value=mock_db_manager,
        ):
            result = await repo.get_with_scores()

        assert len(result) == 1
        assert result[0]["symbol"] == "AAPL.US"
        assert result[0]["total_score"] == 0.85
        assert result[0]["position_value"] == 5000.0


class TestRowToStock:
    """Test row to stock conversion."""

    def test_converts_valid_row(self):
        """Test converting a valid database row to Stock model."""
        from app.modules.universe.database.stock_repository import StockRepository

        mock_db = AsyncMock()
        repo = StockRepository(db=mock_db)

        row = {
            "symbol": "AAPL.US",
            "yahoo_symbol": "AAPL",
            "name": "Apple Inc",
            "industry": "Consumer Electronics",
            "country": "United States",
            "priority_multiplier": 1.5,
            "min_lot": 1,
            "active": 1,
            "allow_buy": 1,
            "allow_sell": 0,
            "currency": "USD",
        }

        row_mock = MagicMock()
        row_mock.__getitem__ = lambda self, key: row[key]

        result = repo._row_to_stock(row_mock)

        assert result.symbol == "AAPL.US"
        assert result.yahoo_symbol == "AAPL"
        assert result.name == "Apple Inc"
        assert result.active is True
        assert result.allow_buy is True
        assert result.allow_sell is False

    def test_handles_null_priority_multiplier(self):
        """Test handling null priority_multiplier."""
        from app.modules.universe.database.stock_repository import StockRepository

        mock_db = AsyncMock()
        repo = StockRepository(db=mock_db)

        row = {
            "symbol": "AAPL.US",
            "yahoo_symbol": "AAPL",
            "name": "Apple Inc",
            "industry": "Consumer Electronics",
            "country": "United States",
            "priority_multiplier": None,
            "min_lot": None,
            "active": 1,
            "allow_buy": None,
            "allow_sell": None,
            "currency": "USD",
        }

        row_mock = MagicMock()
        row_mock.__getitem__ = lambda self, key: row[key]

        result = repo._row_to_stock(row_mock)

        assert result.priority_multiplier == 1.0
        assert result.min_lot == 1
        assert result.allow_buy is True  # Default
        assert result.allow_sell is False  # Default

    def test_row_to_stock_maps_portfolio_targets(self):
        """Test that _row_to_stock maps portfolio target columns correctly."""
        from app.modules.universe.database.stock_repository import StockRepository

        mock_db = AsyncMock()
        repo = StockRepository(db=mock_db)

        row = {
            "symbol": "AAPL.US",
            "yahoo_symbol": "AAPL",
            "name": "Apple Inc",
            "industry": "Consumer Electronics",
            "country": "United States",
            "priority_multiplier": 1.0,
            "min_lot": 1,
            "active": 1,
            "allow_buy": 1,
            "allow_sell": 0,
            "currency": "USD",
            "min_portfolio_target": 5.0,
            "max_portfolio_target": 15.0,
        }

        row_mock = MagicMock()
        row_mock.__getitem__ = lambda self, key: row[key]
        row_mock.keys = lambda: row.keys()

        result = repo._row_to_stock(row_mock)

        assert result.min_portfolio_target == 5.0
        assert result.max_portfolio_target == 15.0

    def test_row_to_stock_handles_null_portfolio_targets(self):
        """Test that _row_to_stock handles NULL portfolio targets."""
        from app.modules.universe.database.stock_repository import StockRepository

        mock_db = AsyncMock()
        repo = StockRepository(db=mock_db)

        row = {
            "symbol": "AAPL.US",
            "yahoo_symbol": "AAPL",
            "name": "Apple Inc",
            "industry": "Consumer Electronics",
            "country": "United States",
            "priority_multiplier": 1.0,
            "min_lot": 1,
            "active": 1,
            "allow_buy": 1,
            "allow_sell": 0,
            "currency": "USD",
            "min_portfolio_target": None,
            "max_portfolio_target": None,
        }

        row_mock = MagicMock()
        row_mock.__getitem__ = lambda self, key: row[key]
        row_mock.keys = lambda: row.keys()

        result = repo._row_to_stock(row_mock)

        assert result.min_portfolio_target is None
        assert result.max_portfolio_target is None

    def test_row_to_stock_handles_missing_portfolio_target_columns(self):
        """Test that _row_to_stock handles missing portfolio target columns (old schema)."""
        from app.modules.universe.database.stock_repository import StockRepository

        mock_db = AsyncMock()
        repo = StockRepository(db=mock_db)

        row = {
            "symbol": "AAPL.US",
            "yahoo_symbol": "AAPL",
            "name": "Apple Inc",
            "industry": "Consumer Electronics",
            "country": "United States",
            "priority_multiplier": 1.0,
            "min_lot": 1,
            "active": 1,
            "allow_buy": 1,
            "allow_sell": 0,
            "currency": "USD",
        }

        row_mock = MagicMock()
        row_mock.__getitem__ = lambda self, key: row[key]
        row_mock.keys = lambda: row.keys()

        result = repo._row_to_stock(row_mock)

        assert result.min_portfolio_target is None
        assert result.max_portfolio_target is None
