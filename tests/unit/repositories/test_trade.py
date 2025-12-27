"""Tests for trade repository.

These tests validate trade CRUD operations and position history calculations.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain.models import Trade


class TestTradeRepositoryHelperFunctions:
    """Test helper functions for trade processing."""

    def test_process_pre_start_trades_buy(self):
        """Test processing BUY trades before start date."""
        from app.repositories.trade import _process_pre_start_trades

        trades = [
            {"symbol": "AAPL", "side": "BUY", "quantity": 10},
            {"symbol": "AAPL", "side": "BUY", "quantity": 5},
        ]
        positions = {}

        _process_pre_start_trades(trades, positions)

        assert positions["AAPL"] == 15

    def test_process_pre_start_trades_sell(self):
        """Test processing SELL trades before start date."""
        from app.repositories.trade import _process_pre_start_trades

        trades = [
            {"symbol": "AAPL", "side": "BUY", "quantity": 10},
            {"symbol": "AAPL", "side": "SELL", "quantity": 3},
        ]
        positions = {}

        _process_pre_start_trades(trades, positions)

        assert positions["AAPL"] == 7

    def test_process_pre_start_trades_negative_clipped(self):
        """Test that negative positions are clipped to zero."""
        from app.repositories.trade import _process_pre_start_trades

        trades = [
            {"symbol": "AAPL", "side": "BUY", "quantity": 5},
            {"symbol": "AAPL", "side": "SELL", "quantity": 10},
        ]
        positions = {}

        _process_pre_start_trades(trades, positions)

        assert positions["AAPL"] == 0

    def test_build_initial_positions(self):
        """Test building initial positions at start date."""
        from app.repositories.trade import _build_initial_positions

        positions = {"AAPL": 10, "MSFT": 0, "GOOG": 5}

        result = _build_initial_positions(positions, "2024-01-01")

        # Should only include positive positions
        assert len(result) == 2
        symbols = {r["symbol"] for r in result}
        assert "AAPL" in symbols
        assert "GOOG" in symbols
        assert all(r["date"] == "2024-01-01" for r in result)

    def test_build_positions_by_date(self):
        """Test building positions by date dictionary."""
        from app.repositories.trade import _build_positions_by_date

        trades = [
            {"executed_at": "2024-01-15T10:00:00", "symbol": "AAPL", "side": "BUY", "quantity": 10},
            {"executed_at": "2024-01-15T11:00:00", "symbol": "AAPL", "side": "SELL", "quantity": 3},
            {"executed_at": "2024-01-16T10:00:00", "symbol": "MSFT", "side": "BUY", "quantity": 5},
        ]

        result = _build_positions_by_date(trades)

        assert "2024-01-15" in result
        assert "2024-01-16" in result
        assert result["2024-01-15"]["AAPL"] == 7  # 10 - 3
        assert result["2024-01-16"]["MSFT"] == 5


class TestTradeRepositoryCreate:
    """Test trade creation operations."""

    @pytest.mark.asyncio
    async def test_creates_trade(self):
        """Test creating a trade record."""
        from app.repositories.trade import TradeRepository

        mock_db = AsyncMock()
        mock_db.fetchone = AsyncMock()
        mock_db.fetchall = AsyncMock()

        # Mock transaction context
        mock_db.transaction = MagicMock()
        mock_db.transaction.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.transaction.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = TradeRepository(db=mock_db)

        trade = Trade(
            id=None,
            symbol="AAPL.US",
            side="BUY",
            quantity=10,
            price=150.0,
            executed_at=datetime.now(),
            order_id="ORD123",
            currency="USD",
            currency_rate=0.92,
            value_eur=1380.0,
            source="tradernet",
        )

        await repo.create(trade)

        mock_db.execute.assert_called_once()


class TestTradeRepositoryQueries:
    """Test trade query operations."""

    @pytest.mark.asyncio
    async def test_get_by_order_id_found(self):
        """Test getting trade by order ID when found."""
        from app.repositories.trade import TradeRepository

        mock_row = {
            "id": 1,
            "symbol": "AAPL.US",
            "side": "BUY",
            "quantity": 10,
            "price": 150.0,
            "executed_at": "2024-01-15T10:00:00",
            "order_id": "ORD123",
            "currency": "USD",
            "currency_rate": 0.92,
            "value_eur": 1380.0,
            "source": "tradernet",
        }

        mock_db = AsyncMock()
        mock_db.fetchone = AsyncMock(return_value=mock_row)

        repo = TradeRepository(db=mock_db)

        result = await repo.get_by_order_id("ORD123")

        assert result is not None
        assert result.symbol == "AAPL.US"
        assert result.order_id == "ORD123"

    @pytest.mark.asyncio
    async def test_get_by_order_id_not_found(self):
        """Test getting trade by order ID when not found."""
        from app.repositories.trade import TradeRepository

        mock_db = AsyncMock()
        mock_db.fetchone = AsyncMock(return_value=None)

        repo = TradeRepository(db=mock_db)

        result = await repo.get_by_order_id("NONEXISTENT")

        assert result is None

    @pytest.mark.asyncio
    async def test_exists_true(self):
        """Test checking if trade exists when it does."""
        from app.repositories.trade import TradeRepository

        mock_db = AsyncMock()
        mock_db.fetchone = AsyncMock(return_value=(1,))

        repo = TradeRepository(db=mock_db)

        result = await repo.exists("ORD123")

        assert result is True

    @pytest.mark.asyncio
    async def test_exists_false(self):
        """Test checking if trade exists when it doesn't."""
        from app.repositories.trade import TradeRepository

        mock_db = AsyncMock()
        mock_db.fetchone = AsyncMock(return_value=None)

        repo = TradeRepository(db=mock_db)

        result = await repo.exists("NONEXISTENT")

        assert result is False

    @pytest.mark.asyncio
    async def test_get_history(self):
        """Test getting trade history."""
        from app.repositories.trade import TradeRepository

        mock_rows = [
            {
                "id": 1,
                "symbol": "AAPL.US",
                "side": "BUY",
                "quantity": 10,
                "price": 150.0,
                "executed_at": "2024-01-15T10:00:00",
                "order_id": "ORD123",
                "currency": "USD",
                "currency_rate": 0.92,
                "value_eur": 1380.0,
                "source": "tradernet",
            }
        ]

        mock_db = AsyncMock()
        mock_db.fetchall = AsyncMock(return_value=mock_rows)

        repo = TradeRepository(db=mock_db)

        result = await repo.get_history(limit=50)

        assert len(result) == 1
        assert result[0].symbol == "AAPL.US"

    @pytest.mark.asyncio
    async def test_get_by_symbol(self):
        """Test getting trades by symbol."""
        from app.repositories.trade import TradeRepository

        mock_rows = [
            {
                "id": 1,
                "symbol": "AAPL.US",
                "side": "BUY",
                "quantity": 10,
                "price": 150.0,
                "executed_at": "2024-01-15T10:00:00",
                "order_id": "ORD123",
                "currency": "USD",
                "currency_rate": 0.92,
                "value_eur": 1380.0,
                "source": "tradernet",
            }
        ]

        mock_db = AsyncMock()
        mock_db.fetchall = AsyncMock(return_value=mock_rows)

        repo = TradeRepository(db=mock_db)

        result = await repo.get_by_symbol("AAPL.US")

        assert len(result) == 1
        mock_db.fetchall.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_recently_bought_symbols(self):
        """Test getting recently bought symbols."""
        from app.repositories.trade import TradeRepository

        mock_rows = [{"symbol": "AAPL.US"}, {"symbol": "MSFT.US"}]

        mock_db = AsyncMock()
        mock_db.fetchall = AsyncMock(return_value=mock_rows)

        repo = TradeRepository(db=mock_db)

        result = await repo.get_recently_bought_symbols(days=30)

        assert "AAPL.US" in result
        assert "MSFT.US" in result

    @pytest.mark.asyncio
    async def test_get_recently_sold_symbols(self):
        """Test getting recently sold symbols."""
        from app.repositories.trade import TradeRepository

        mock_rows = [{"symbol": "GOOG.US"}]

        mock_db = AsyncMock()
        mock_db.fetchall = AsyncMock(return_value=mock_rows)

        repo = TradeRepository(db=mock_db)

        result = await repo.get_recently_sold_symbols(days=30)

        assert "GOOG.US" in result

    @pytest.mark.asyncio
    async def test_has_recent_sell_order_true(self):
        """Test checking for recent sell order when exists."""
        from app.repositories.trade import TradeRepository

        mock_db = AsyncMock()
        mock_db.fetchone = AsyncMock(return_value=(1,))

        repo = TradeRepository(db=mock_db)

        result = await repo.has_recent_sell_order("AAPL.US", hours=2)

        assert result is True

    @pytest.mark.asyncio
    async def test_has_recent_sell_order_false(self):
        """Test checking for recent sell order when not exists."""
        from app.repositories.trade import TradeRepository

        mock_db = AsyncMock()
        mock_db.fetchone = AsyncMock(return_value=None)

        repo = TradeRepository(db=mock_db)

        result = await repo.has_recent_sell_order("AAPL.US", hours=2)

        assert result is False

    @pytest.mark.asyncio
    async def test_get_first_buy_date(self):
        """Test getting first buy date for symbol."""
        from app.repositories.trade import TradeRepository

        mock_db = AsyncMock()
        mock_db.fetchone = AsyncMock(return_value={"first_buy": "2023-06-15"})

        repo = TradeRepository(db=mock_db)

        result = await repo.get_first_buy_date("AAPL.US")

        assert result == "2023-06-15"

    @pytest.mark.asyncio
    async def test_get_last_sell_date(self):
        """Test getting last sell date for symbol."""
        from app.repositories.trade import TradeRepository

        mock_db = AsyncMock()
        mock_db.fetchone = AsyncMock(return_value={"last_sell": "2024-01-20"})

        repo = TradeRepository(db=mock_db)

        result = await repo.get_last_sell_date("AAPL.US")

        assert result == "2024-01-20"

    @pytest.mark.asyncio
    async def test_get_trade_dates(self):
        """Test getting trade dates for all symbols."""
        from app.repositories.trade import TradeRepository

        mock_rows = [
            {"symbol": "AAPL.US", "first_buy": "2023-06-15", "last_sell": None},
            {"symbol": "MSFT.US", "first_buy": "2023-01-01", "last_sell": "2024-01-20"},
        ]

        mock_db = AsyncMock()
        mock_db.fetchall = AsyncMock(return_value=mock_rows)

        repo = TradeRepository(db=mock_db)

        result = await repo.get_trade_dates()

        assert "AAPL.US" in result
        assert result["AAPL.US"]["first_bought_at"] == "2023-06-15"
        assert result["MSFT.US"]["last_sold_at"] == "2024-01-20"


class TestTradeRepositoryPositionHistory:
    """Test position history calculations."""

    @pytest.mark.asyncio
    async def test_get_position_history(self):
        """Test getting position history."""
        from app.repositories.trade import TradeRepository

        mock_rows = [
            {"symbol": "AAPL", "side": "BUY", "quantity": 10, "executed_at": "2024-01-10T10:00:00"},
            {"symbol": "AAPL", "side": "BUY", "quantity": 5, "executed_at": "2024-01-15T10:00:00"},
        ]

        mock_db = AsyncMock()
        mock_db.fetchall = AsyncMock(return_value=mock_rows)

        repo = TradeRepository(db=mock_db)

        result = await repo.get_position_history("2024-01-01", "2024-01-31")

        assert len(result) >= 1


class TestRowToTrade:
    """Test row to trade conversion."""

    def test_converts_valid_row(self):
        """Test converting a valid database row to Trade model."""
        from app.repositories.trade import TradeRepository

        mock_db = AsyncMock()
        repo = TradeRepository(db=mock_db)

        row = {
            "id": 1,
            "symbol": "AAPL.US",
            "side": "BUY",
            "quantity": 10,
            "price": 150.0,
            "executed_at": "2024-01-15T10:00:00",
            "order_id": "ORD123",
            "currency": "USD",
            "currency_rate": 0.92,
            "value_eur": 1380.0,
            "source": "tradernet",
        }

        # Make row behave like sqlite3.Row
        row_mock = MagicMock()
        row_mock.__getitem__ = lambda self, key: row[key]
        row_mock.keys = lambda: row.keys()

        result = repo._row_to_trade(row_mock)

        assert result.symbol == "AAPL.US"
        assert result.side == "BUY"
        assert result.quantity == 10
        assert result.price == 150.0

    def test_handles_invalid_executed_at(self):
        """Test handling invalid executed_at value."""
        from app.repositories.trade import TradeRepository

        mock_db = AsyncMock()
        repo = TradeRepository(db=mock_db)

        row = {
            "id": 1,
            "symbol": "AAPL.US",
            "side": "BUY",
            "quantity": 10,
            "price": 150.0,
            "executed_at": "invalid-date",
            "order_id": "ORD123",
            "currency": "USD",
            "currency_rate": 0.92,
            "value_eur": 1380.0,
            "source": "tradernet",
        }

        row_mock = MagicMock()
        row_mock.__getitem__ = lambda self, key: row[key]
        row_mock.keys = lambda: row.keys()

        result = repo._row_to_trade(row_mock)

        # Should use current datetime as fallback
        assert result.executed_at is not None
