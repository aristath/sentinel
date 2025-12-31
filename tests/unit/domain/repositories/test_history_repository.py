"""Tests for HistoryRepository.

These tests verify the per-symbol historical price data operations,
which are critical for technical analysis and performance calculations.
"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.models import DailyPrice, MonthlyPrice
from app.modules.portfolio.database.history_repository import HistoryRepository


def create_mock_transaction(mock_conn: AsyncMock):
    """Create a mock transaction async context manager.

    Since transaction() is an async generator (async context manager),
    we need to properly mock it to work with 'async with'.
    """

    @asynccontextmanager
    async def transaction():
        yield mock_conn

    return transaction


def create_mock_daily_price(
    date: str = "2024-01-15",
    close_price: float = 150.0,
    open_price: float = 148.0,
    high_price: float = 152.0,
    low_price: float = 147.0,
    volume: int = 1000000,
    source: str = "yahoo",
) -> dict:
    """Create a mock daily price database row."""
    return {
        "date": date,
        "close_price": close_price,
        "open_price": open_price,
        "high_price": high_price,
        "low_price": low_price,
        "volume": volume,
        "source": source,
    }


def create_mock_monthly_price(
    year_month: str = "2024-01",
    avg_close: float = 150.0,
    avg_adj_close: float = 149.5,
    min_price: float = 145.0,
    max_price: float = 155.0,
    source: str = "calculated",
) -> dict:
    """Create a mock monthly price database row."""
    return {
        "year_month": year_month,
        "avg_close": avg_close,
        "avg_adj_close": avg_adj_close,
        "min_price": min_price,
        "max_price": max_price,
        "source": source,
    }


class TestHistoryRepositoryInit:
    """Test HistoryRepository initialization."""

    def test_init_normalizes_symbol(self):
        """Test that symbol is normalized to uppercase."""
        with patch("app.modules.portfolio.database.history_repository.get_db_manager"):
            repo = HistoryRepository("aapl")
            assert repo.symbol == "AAPL"

    def test_init_stores_symbol(self):
        """Test that repository stores the symbol."""
        with patch("app.modules.portfolio.database.history_repository.get_db_manager"):
            repo = HistoryRepository("MSFT")
            assert repo.symbol == "MSFT"

    def test_init_db_is_lazy_loaded(self):
        """Test that database is not loaded on init."""
        with patch("app.modules.portfolio.database.history_repository.get_db_manager"):
            repo = HistoryRepository("AAPL")
            assert repo._db is None


class TestHistoryRepositoryGetDb:
    """Test database initialization and lazy loading."""

    @pytest.mark.asyncio
    async def test_get_db_initializes_database(self):
        """Test that _get_db initializes the database on first call."""
        with patch(
            "app.modules.portfolio.database.history_repository.get_db_manager"
        ) as mock_get_db:
            mock_db_manager = MagicMock()
            mock_db = AsyncMock()
            mock_db_manager.history = AsyncMock(return_value=mock_db)
            mock_get_db.return_value = mock_db_manager

            with patch(
                "app.modules.portfolio.database.history_repository.init_history_schema"
            ) as mock_init_schema:
                repo = HistoryRepository("AAPL")
                db = await repo._get_db()

                assert db == mock_db
                mock_db_manager.history.assert_called_once_with("AAPL")
                mock_init_schema.assert_called_once_with(mock_db)

    @pytest.mark.asyncio
    async def test_get_db_caches_database(self):
        """Test that _get_db caches the database after first call."""
        with patch(
            "app.modules.portfolio.database.history_repository.get_db_manager"
        ) as mock_get_db:
            mock_db_manager = MagicMock()
            mock_db = AsyncMock()
            mock_db_manager.history = AsyncMock(return_value=mock_db)
            mock_get_db.return_value = mock_db_manager

            with patch(
                "app.modules.portfolio.database.history_repository.init_history_schema"
            ):
                repo = HistoryRepository("AAPL")

                # First call
                db1 = await repo._get_db()
                # Second call
                db2 = await repo._get_db()

                assert db1 == db2
                # Should only call history() once
                assert mock_db_manager.history.call_count == 1


class TestHistoryRepositoryDailyPrices:
    """Test daily price operations."""

    @pytest.mark.asyncio
    async def test_get_daily_prices_with_default_limit(self):
        """Test retrieving daily prices with default limit."""
        with patch(
            "app.modules.portfolio.database.history_repository.get_db_manager"
        ) as mock_get_db:
            mock_db_manager = MagicMock()
            mock_db = AsyncMock()
            mock_db_manager.history = AsyncMock(return_value=mock_db)
            mock_get_db.return_value = mock_db_manager

            mock_rows = [
                create_mock_daily_price(date="2024-01-15", close_price=150.0),
                create_mock_daily_price(date="2024-01-14", close_price=149.0),
            ]
            mock_db.fetchall.return_value = mock_rows

            with patch(
                "app.modules.portfolio.database.history_repository.init_history_schema"
            ):
                repo = HistoryRepository("AAPL")
                result = await repo.get_daily_prices()

                assert len(result) == 2
                assert all(isinstance(p, DailyPrice) for p in result)
                assert result[0].close_price == 150.0
                assert result[1].close_price == 149.0
                # Verify default limit of 365
                mock_db.fetchall.assert_called_once()
                call_args = mock_db.fetchall.call_args
                assert call_args[0][1] == (365,)

    @pytest.mark.asyncio
    async def test_get_daily_prices_with_custom_limit(self):
        """Test retrieving daily prices with custom limit."""
        with patch(
            "app.modules.portfolio.database.history_repository.get_db_manager"
        ) as mock_get_db:
            mock_db_manager = MagicMock()
            mock_db = AsyncMock()
            mock_db_manager.history = AsyncMock(return_value=mock_db)
            mock_get_db.return_value = mock_db_manager

            mock_db.fetchall.return_value = []

            with patch(
                "app.modules.portfolio.database.history_repository.init_history_schema"
            ):
                repo = HistoryRepository("AAPL")
                await repo.get_daily_prices(limit=100)

                call_args = mock_db.fetchall.call_args
                assert call_args[0][1] == (100,)

    @pytest.mark.asyncio
    async def test_get_daily_prices_empty_result(self):
        """Test retrieving daily prices when no data exists."""
        with patch(
            "app.modules.portfolio.database.history_repository.get_db_manager"
        ) as mock_get_db:
            mock_db_manager = MagicMock()
            mock_db = AsyncMock()
            mock_db_manager.history = AsyncMock(return_value=mock_db)
            mock_get_db.return_value = mock_db_manager

            mock_db.fetchall.return_value = []

            with patch(
                "app.modules.portfolio.database.history_repository.init_history_schema"
            ):
                repo = HistoryRepository("AAPL")
                result = await repo.get_daily_prices()

                assert result == []

    @pytest.mark.asyncio
    async def test_get_daily_range(self):
        """Test retrieving daily prices within a date range."""
        with patch(
            "app.modules.portfolio.database.history_repository.get_db_manager"
        ) as mock_get_db:
            mock_db_manager = MagicMock()
            mock_db = AsyncMock()
            mock_db_manager.history = AsyncMock(return_value=mock_db)
            mock_get_db.return_value = mock_db_manager

            mock_rows = [
                create_mock_daily_price(date="2024-01-10", close_price=145.0),
                create_mock_daily_price(date="2024-01-11", close_price=147.0),
                create_mock_daily_price(date="2024-01-12", close_price=149.0),
            ]
            mock_db.fetchall.return_value = mock_rows

            with patch(
                "app.modules.portfolio.database.history_repository.init_history_schema"
            ):
                repo = HistoryRepository("AAPL")
                result = await repo.get_daily_range("2024-01-10", "2024-01-12")

                assert len(result) == 3
                assert result[0].date == "2024-01-10"
                assert result[2].date == "2024-01-12"
                # Verify parameters
                call_args = mock_db.fetchall.call_args
                assert call_args[0][1] == ("2024-01-10", "2024-01-12")

    @pytest.mark.asyncio
    async def test_get_daily_range_empty(self):
        """Test retrieving daily range with no results."""
        with patch(
            "app.modules.portfolio.database.history_repository.get_db_manager"
        ) as mock_get_db:
            mock_db_manager = MagicMock()
            mock_db = AsyncMock()
            mock_db_manager.history = AsyncMock(return_value=mock_db)
            mock_get_db.return_value = mock_db_manager

            mock_db.fetchall.return_value = []

            with patch(
                "app.modules.portfolio.database.history_repository.init_history_schema"
            ):
                repo = HistoryRepository("AAPL")
                result = await repo.get_daily_range("2024-01-01", "2024-01-05")

                assert result == []

    @pytest.mark.asyncio
    async def test_get_latest_price(self):
        """Test retrieving the most recent daily price."""
        with patch(
            "app.modules.portfolio.database.history_repository.get_db_manager"
        ) as mock_get_db:
            mock_db_manager = MagicMock()
            mock_db = AsyncMock()
            mock_db_manager.history = AsyncMock(return_value=mock_db)
            mock_get_db.return_value = mock_db_manager

            mock_row = create_mock_daily_price(date="2024-01-15", close_price=150.0)
            mock_db.fetchone.return_value = mock_row

            with patch(
                "app.modules.portfolio.database.history_repository.init_history_schema"
            ):
                repo = HistoryRepository("AAPL")
                result = await repo.get_latest_price()

                assert result is not None
                assert isinstance(result, DailyPrice)
                assert result.date == "2024-01-15"
                assert result.close_price == 150.0

    @pytest.mark.asyncio
    async def test_get_latest_price_no_data(self):
        """Test retrieving latest price when no data exists."""
        with patch(
            "app.modules.portfolio.database.history_repository.get_db_manager"
        ) as mock_get_db:
            mock_db_manager = MagicMock()
            mock_db = AsyncMock()
            mock_db_manager.history = AsyncMock(return_value=mock_db)
            mock_get_db.return_value = mock_db_manager

            mock_db.fetchone.return_value = None

            with patch(
                "app.modules.portfolio.database.history_repository.init_history_schema"
            ):
                repo = HistoryRepository("AAPL")
                result = await repo.get_latest_price()

                assert result is None


class TestHistoryRepositoryUpsertDaily:
    """Test daily price insert/update operations."""

    @pytest.mark.asyncio
    async def test_upsert_daily(self):
        """Test upserting a single daily price."""
        with patch(
            "app.modules.portfolio.database.history_repository.get_db_manager"
        ) as mock_get_db:
            mock_db_manager = MagicMock()
            mock_db = AsyncMock()
            mock_db_manager.history = AsyncMock(return_value=mock_db)
            mock_get_db.return_value = mock_db_manager

            # Setup transaction mock
            mock_conn = AsyncMock()
            mock_db.transaction = create_mock_transaction(mock_conn)

            with patch(
                "app.modules.portfolio.database.history_repository.init_history_schema"
            ):
                repo = HistoryRepository("AAPL")
                price = DailyPrice(
                    date="2024-01-15",
                    close_price=150.0,
                    open_price=148.0,
                    high_price=152.0,
                    low_price=147.0,
                    volume=1000000,
                    source="yahoo",
                )

                await repo.upsert_daily(price)

                mock_conn.execute.assert_called_once()
                # Verify the price data was passed
                call_args = mock_conn.execute.call_args
                params = call_args[0][1]
                assert params[0] == "2024-01-15"
                assert params[1] == 148.0
                assert params[2] == 152.0
                assert params[3] == 147.0
                assert params[4] == 150.0
                assert params[5] == 1000000
                assert params[6] == "yahoo"

    @pytest.mark.asyncio
    async def test_upsert_daily_batch_empty(self):
        """Test upserting empty batch returns 0."""
        with patch(
            "app.modules.portfolio.database.history_repository.get_db_manager"
        ) as mock_get_db:
            mock_db_manager = MagicMock()
            mock_db = AsyncMock()
            mock_db_manager.history = AsyncMock(return_value=mock_db)
            mock_get_db.return_value = mock_db_manager

            with patch(
                "app.modules.portfolio.database.history_repository.init_history_schema"
            ):
                repo = HistoryRepository("AAPL")
                result = await repo.upsert_daily_batch([])

                assert result == 0

    @pytest.mark.asyncio
    async def test_upsert_daily_batch_multiple(self):
        """Test upserting multiple daily prices."""
        with patch(
            "app.modules.portfolio.database.history_repository.get_db_manager"
        ) as mock_get_db:
            mock_db_manager = MagicMock()
            mock_db = AsyncMock()
            mock_db_manager.history = AsyncMock(return_value=mock_db)
            mock_get_db.return_value = mock_db_manager

            # Setup transaction mock
            mock_conn = AsyncMock()
            mock_db.transaction = create_mock_transaction(mock_conn)

            with patch(
                "app.modules.portfolio.database.history_repository.init_history_schema"
            ):
                repo = HistoryRepository("AAPL")
                prices = [
                    DailyPrice(
                        date="2024-01-15",
                        close_price=150.0,
                        open_price=148.0,
                        high_price=152.0,
                        low_price=147.0,
                        volume=1000000,
                        source="yahoo",
                    ),
                    DailyPrice(
                        date="2024-01-16",
                        close_price=151.0,
                        open_price=149.0,
                        high_price=153.0,
                        low_price=148.0,
                        volume=1100000,
                        source="yahoo",
                    ),
                ]

                result = await repo.upsert_daily_batch(prices)

                assert result == 2
                assert mock_conn.execute.call_count == 2


class TestHistoryRepositoryMonthlyPrices:
    """Test monthly price operations."""

    @pytest.mark.asyncio
    async def test_get_monthly_prices_with_default_limit(self):
        """Test retrieving monthly prices with default limit."""
        with patch(
            "app.modules.portfolio.database.history_repository.get_db_manager"
        ) as mock_get_db:
            mock_db_manager = MagicMock()
            mock_db = AsyncMock()
            mock_db_manager.history = AsyncMock(return_value=mock_db)
            mock_get_db.return_value = mock_db_manager

            mock_rows = [
                create_mock_monthly_price(year_month="2024-01", avg_close=150.0),
                create_mock_monthly_price(year_month="2023-12", avg_close=145.0),
            ]
            mock_db.fetchall.return_value = mock_rows

            with patch(
                "app.modules.portfolio.database.history_repository.init_history_schema"
            ):
                repo = HistoryRepository("AAPL")
                result = await repo.get_monthly_prices()

                assert len(result) == 2
                assert all(isinstance(p, MonthlyPrice) for p in result)
                assert result[0].avg_close == 150.0
                # Verify default limit of 120
                call_args = mock_db.fetchall.call_args
                assert call_args[0][1] == (120,)

    @pytest.mark.asyncio
    async def test_get_monthly_prices_with_custom_limit(self):
        """Test retrieving monthly prices with custom limit."""
        with patch(
            "app.modules.portfolio.database.history_repository.get_db_manager"
        ) as mock_get_db:
            mock_db_manager = MagicMock()
            mock_db = AsyncMock()
            mock_db_manager.history = AsyncMock(return_value=mock_db)
            mock_get_db.return_value = mock_db_manager

            mock_db.fetchall.return_value = []

            with patch(
                "app.modules.portfolio.database.history_repository.init_history_schema"
            ):
                repo = HistoryRepository("AAPL")
                await repo.get_monthly_prices(limit=60)

                call_args = mock_db.fetchall.call_args
                assert call_args[0][1] == (60,)

    @pytest.mark.asyncio
    async def test_get_monthly_prices_empty(self):
        """Test retrieving monthly prices when no data exists."""
        with patch(
            "app.modules.portfolio.database.history_repository.get_db_manager"
        ) as mock_get_db:
            mock_db_manager = MagicMock()
            mock_db = AsyncMock()
            mock_db_manager.history = AsyncMock(return_value=mock_db)
            mock_get_db.return_value = mock_db_manager

            mock_db.fetchall.return_value = []

            with patch(
                "app.modules.portfolio.database.history_repository.init_history_schema"
            ):
                repo = HistoryRepository("AAPL")
                result = await repo.get_monthly_prices()

                assert result == []

    @pytest.mark.asyncio
    async def test_upsert_monthly(self):
        """Test upserting a monthly price."""
        with patch(
            "app.modules.portfolio.database.history_repository.get_db_manager"
        ) as mock_get_db:
            mock_db_manager = MagicMock()
            mock_db = AsyncMock()
            mock_db_manager.history = AsyncMock(return_value=mock_db)
            mock_get_db.return_value = mock_db_manager

            # Setup transaction mock
            mock_conn = AsyncMock()
            mock_db.transaction = create_mock_transaction(mock_conn)

            with patch(
                "app.modules.portfolio.database.history_repository.init_history_schema"
            ):
                repo = HistoryRepository("AAPL")
                price = MonthlyPrice(
                    year_month="2024-01",
                    avg_close=150.0,
                    avg_adj_close=149.5,
                    min_price=145.0,
                    max_price=155.0,
                    source="calculated",
                )

                await repo.upsert_monthly(price)

                mock_conn.execute.assert_called_once()
                # Verify the price data was passed
                call_args = mock_conn.execute.call_args
                params = call_args[0][1]
                assert params[0] == "2024-01"
                assert params[1] == 150.0
                assert params[2] == 149.5
                assert params[3] == 145.0
                assert params[4] == 155.0
                assert params[5] == "calculated"


class TestHistoryRepositoryAggregation:
    """Test monthly aggregation operations."""

    @pytest.mark.asyncio
    async def test_aggregate_to_monthly(self):
        """Test aggregating daily prices to monthly."""
        with patch(
            "app.modules.portfolio.database.history_repository.get_db_manager"
        ) as mock_get_db:
            mock_db_manager = MagicMock()
            mock_db = AsyncMock()
            mock_db_manager.history = AsyncMock(return_value=mock_db)
            mock_get_db.return_value = mock_db_manager

            # Setup transaction mock
            mock_cursor = MagicMock()
            mock_cursor.rowcount = 12  # 12 months aggregated
            mock_conn = AsyncMock()
            mock_conn.execute.return_value = mock_cursor
            mock_db.transaction = create_mock_transaction(mock_conn)

            with patch(
                "app.modules.portfolio.database.history_repository.init_history_schema"
            ):
                repo = HistoryRepository("AAPL")
                result = await repo.aggregate_to_monthly()

                assert result == 12
                mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_aggregate_to_monthly_no_data(self):
        """Test aggregating when no daily data exists."""
        with patch(
            "app.modules.portfolio.database.history_repository.get_db_manager"
        ) as mock_get_db:
            mock_db_manager = MagicMock()
            mock_db = AsyncMock()
            mock_db_manager.history = AsyncMock(return_value=mock_db)
            mock_get_db.return_value = mock_db_manager

            # Setup transaction mock
            mock_cursor = MagicMock()
            mock_cursor.rowcount = 0
            mock_conn = AsyncMock()
            mock_conn.execute.return_value = mock_cursor
            mock_db.transaction = create_mock_transaction(mock_conn)

            with patch(
                "app.modules.portfolio.database.history_repository.init_history_schema"
            ):
                repo = HistoryRepository("AAPL")
                result = await repo.aggregate_to_monthly()

                assert result == 0


class TestHistoryRepositoryDeletion:
    """Test data deletion operations."""

    @pytest.mark.asyncio
    async def test_delete_before(self):
        """Test deleting daily prices before a date."""
        with patch(
            "app.modules.portfolio.database.history_repository.get_db_manager"
        ) as mock_get_db:
            mock_db_manager = MagicMock()
            mock_db = AsyncMock()
            mock_db_manager.history = AsyncMock(return_value=mock_db)
            mock_get_db.return_value = mock_db_manager

            # Setup count query
            mock_cursor = AsyncMock()
            mock_cursor.fetchone.return_value = {"cnt": 100}
            mock_db.execute.return_value = mock_cursor

            # Setup transaction mock
            mock_conn = AsyncMock()
            mock_db.transaction = create_mock_transaction(mock_conn)

            with patch(
                "app.modules.portfolio.database.history_repository.init_history_schema"
            ):
                repo = HistoryRepository("AAPL")
                result = await repo.delete_before("2023-01-01")

                assert result == 100
                # Verify delete was called
                mock_conn.execute.assert_called_once()
                call_args = mock_conn.execute.call_args
                assert call_args[0][1] == ("2023-01-01",)

    @pytest.mark.asyncio
    async def test_delete_before_no_data(self):
        """Test deleting when no data exists before date."""
        with patch(
            "app.modules.portfolio.database.history_repository.get_db_manager"
        ) as mock_get_db:
            mock_db_manager = MagicMock()
            mock_db = AsyncMock()
            mock_db_manager.history = AsyncMock(return_value=mock_db)
            mock_get_db.return_value = mock_db_manager

            # Setup count query returning 0
            mock_cursor = AsyncMock()
            mock_cursor.fetchone.return_value = {"cnt": 0}
            mock_db.execute.return_value = mock_cursor

            with patch(
                "app.modules.portfolio.database.history_repository.init_history_schema"
            ):
                repo = HistoryRepository("AAPL")
                result = await repo.delete_before("2023-01-01")

                assert result == 0
                # Should not execute delete
                assert not mock_db.transaction.called

    @pytest.mark.asyncio
    async def test_delete_before_null_count(self):
        """Test deleting when count query returns None."""
        with patch(
            "app.modules.portfolio.database.history_repository.get_db_manager"
        ) as mock_get_db:
            mock_db_manager = MagicMock()
            mock_db = AsyncMock()
            mock_db_manager.history = AsyncMock(return_value=mock_db)
            mock_get_db.return_value = mock_db_manager

            # Setup count query returning None
            mock_cursor = AsyncMock()
            mock_cursor.fetchone.return_value = None
            mock_db.execute.return_value = mock_cursor

            with patch(
                "app.modules.portfolio.database.history_repository.init_history_schema"
            ):
                repo = HistoryRepository("AAPL")
                result = await repo.delete_before("2023-01-01")

                assert result == 0


class TestHistoryRepository52Week:
    """Test 52-week high/low operations."""

    @pytest.mark.asyncio
    async def test_get_52_week_high(self):
        """Test retrieving 52-week high price."""
        with patch(
            "app.modules.portfolio.database.history_repository.get_db_manager"
        ) as mock_get_db:
            mock_db_manager = MagicMock()
            mock_db = AsyncMock()
            mock_db_manager.history = AsyncMock(return_value=mock_db)
            mock_get_db.return_value = mock_db_manager

            mock_db.fetchone.return_value = {"high": 160.0}

            with patch(
                "app.modules.portfolio.database.history_repository.init_history_schema"
            ):
                repo = HistoryRepository("AAPL")
                result = await repo.get_52_week_high()

                assert result == 160.0

    @pytest.mark.asyncio
    async def test_get_52_week_high_no_data(self):
        """Test retrieving 52-week high when no data exists."""
        with patch(
            "app.modules.portfolio.database.history_repository.get_db_manager"
        ) as mock_get_db:
            mock_db_manager = MagicMock()
            mock_db = AsyncMock()
            mock_db_manager.history = AsyncMock(return_value=mock_db)
            mock_get_db.return_value = mock_db_manager

            mock_db.fetchone.return_value = None

            with patch(
                "app.modules.portfolio.database.history_repository.init_history_schema"
            ):
                repo = HistoryRepository("AAPL")
                result = await repo.get_52_week_high()

                assert result is None

    @pytest.mark.asyncio
    async def test_get_52_week_low(self):
        """Test retrieving 52-week low price."""
        with patch(
            "app.modules.portfolio.database.history_repository.get_db_manager"
        ) as mock_get_db:
            mock_db_manager = MagicMock()
            mock_db = AsyncMock()
            mock_db_manager.history = AsyncMock(return_value=mock_db)
            mock_get_db.return_value = mock_db_manager

            mock_db.fetchone.return_value = {"low": 140.0}

            with patch(
                "app.modules.portfolio.database.history_repository.init_history_schema"
            ):
                repo = HistoryRepository("AAPL")
                result = await repo.get_52_week_low()

                assert result == 140.0

    @pytest.mark.asyncio
    async def test_get_52_week_low_no_data(self):
        """Test retrieving 52-week low when no data exists."""
        with patch(
            "app.modules.portfolio.database.history_repository.get_db_manager"
        ) as mock_get_db:
            mock_db_manager = MagicMock()
            mock_db = AsyncMock()
            mock_db_manager.history = AsyncMock(return_value=mock_db)
            mock_get_db.return_value = mock_db_manager

            mock_db.fetchone.return_value = None

            with patch(
                "app.modules.portfolio.database.history_repository.init_history_schema"
            ):
                repo = HistoryRepository("AAPL")
                result = await repo.get_52_week_low()

                assert result is None


class TestHistoryRepositoryIntegrity:
    """Test database integrity operations."""

    @pytest.mark.asyncio
    async def test_integrity_check_success(self):
        """Test successful integrity check."""
        with patch(
            "app.modules.portfolio.database.history_repository.get_db_manager"
        ) as mock_get_db:
            mock_db_manager = MagicMock()
            mock_db = AsyncMock()
            mock_db_manager.history = AsyncMock(return_value=mock_db)
            mock_get_db.return_value = mock_db_manager

            mock_db.integrity_check.return_value = "ok"

            with patch(
                "app.modules.portfolio.database.history_repository.init_history_schema"
            ):
                repo = HistoryRepository("AAPL")
                result = await repo.integrity_check()

                assert result == "ok"
                mock_db.integrity_check.assert_called_once()

    @pytest.mark.asyncio
    async def test_integrity_check_failure(self):
        """Test integrity check with errors."""
        with patch(
            "app.modules.portfolio.database.history_repository.get_db_manager"
        ) as mock_get_db:
            mock_db_manager = MagicMock()
            mock_db = AsyncMock()
            mock_db_manager.history = AsyncMock(return_value=mock_db)
            mock_get_db.return_value = mock_db_manager

            mock_db.integrity_check.return_value = "corruption detected"

            with patch(
                "app.modules.portfolio.database.history_repository.init_history_schema"
            ):
                repo = HistoryRepository("AAPL")
                result = await repo.integrity_check()

                assert result == "corruption detected"


class TestHistoryRepositoryRowConversion:
    """Test row to model conversion."""

    def test_row_to_daily_basic(self):
        """Test converting a basic database row to DailyPrice."""
        with patch(
            "app.modules.portfolio.database.history_repository.get_db_manager"
        ) as mock_get_db:
            mock_db_manager = MagicMock()
            mock_get_db.return_value = mock_db_manager

            repo = HistoryRepository("AAPL")
            row = create_mock_daily_price(
                date="2024-01-15",
                close_price=150.0,
                open_price=148.0,
                high_price=152.0,
                low_price=147.0,
                volume=1000000,
                source="yahoo",
            )

            result = repo._row_to_daily(row)

            assert isinstance(result, DailyPrice)
            assert result.date == "2024-01-15"
            assert result.close_price == 150.0
            assert result.open_price == 148.0
            assert result.high_price == 152.0
            assert result.low_price == 147.0
            assert result.volume == 1000000
            assert result.source == "yahoo"

    def test_row_to_daily_with_none_source(self):
        """Test converting a row with None source defaults to 'yahoo'."""
        with patch(
            "app.modules.portfolio.database.history_repository.get_db_manager"
        ) as mock_get_db:
            mock_db_manager = MagicMock()
            mock_get_db.return_value = mock_db_manager

            repo = HistoryRepository("AAPL")
            row = create_mock_daily_price(source=None)
            row["source"] = None

            result = repo._row_to_daily(row)

            assert result.source == "yahoo"

    def test_row_to_monthly_basic(self):
        """Test converting a basic database row to MonthlyPrice."""
        with patch(
            "app.modules.portfolio.database.history_repository.get_db_manager"
        ) as mock_get_db:
            mock_db_manager = MagicMock()
            mock_get_db.return_value = mock_db_manager

            repo = HistoryRepository("AAPL")
            row = create_mock_monthly_price(
                year_month="2024-01",
                avg_close=150.0,
                avg_adj_close=149.5,
                min_price=145.0,
                max_price=155.0,
                source="calculated",
            )

            result = repo._row_to_monthly(row)

            assert isinstance(result, MonthlyPrice)
            assert result.year_month == "2024-01"
            assert result.avg_close == 150.0
            assert result.avg_adj_close == 149.5
            assert result.min_price == 145.0
            assert result.max_price == 155.0
            assert result.source == "calculated"

    def test_row_to_monthly_with_none_source(self):
        """Test converting a row with None source defaults to 'calculated'."""
        with patch(
            "app.modules.portfolio.database.history_repository.get_db_manager"
        ) as mock_get_db:
            mock_db_manager = MagicMock()
            mock_get_db.return_value = mock_db_manager

            repo = HistoryRepository("AAPL")
            row = create_mock_monthly_price(source=None)
            row["source"] = None

            result = repo._row_to_monthly(row)

            assert result.source == "calculated"


class TestHistoryRepositoryEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_get_daily_prices_with_zero_limit(self):
        """Test retrieving daily prices with zero limit."""
        with patch(
            "app.modules.portfolio.database.history_repository.get_db_manager"
        ) as mock_get_db:
            mock_db_manager = MagicMock()
            mock_db = AsyncMock()
            mock_db_manager.history = AsyncMock(return_value=mock_db)
            mock_get_db.return_value = mock_db_manager

            mock_db.fetchall.return_value = []

            with patch(
                "app.modules.portfolio.database.history_repository.init_history_schema"
            ):
                repo = HistoryRepository("AAPL")
                result = await repo.get_daily_prices(limit=0)

                # Should still return empty list
                assert result == []

    @pytest.mark.asyncio
    async def test_upsert_daily_with_minimal_data(self):
        """Test upserting daily price with only required fields."""
        with patch(
            "app.modules.portfolio.database.history_repository.get_db_manager"
        ) as mock_get_db:
            mock_db_manager = MagicMock()
            mock_db = AsyncMock()
            mock_db_manager.history = AsyncMock(return_value=mock_db)
            mock_get_db.return_value = mock_db_manager

            # Setup transaction mock
            mock_conn = AsyncMock()
            mock_db.transaction = create_mock_transaction(mock_conn)

            with patch(
                "app.modules.portfolio.database.history_repository.init_history_schema"
            ):
                repo = HistoryRepository("AAPL")
                price = DailyPrice(
                    date="2024-01-15",
                    close_price=150.0,
                    # Optional fields not provided
                )

                await repo.upsert_daily(price)

                mock_conn.execute.assert_called_once()
                # Verify None values are passed for optional fields
                call_args = mock_conn.execute.call_args
                params = call_args[0][1]
                assert params[0] == "2024-01-15"
                assert params[1] is None  # open_price
                assert params[2] is None  # high_price
                assert params[3] is None  # low_price
                assert params[4] == 150.0  # close_price
                assert params[5] is None  # volume

    @pytest.mark.asyncio
    async def test_symbol_normalization_in_multiple_instances(self):
        """Test that multiple repository instances normalize symbols correctly."""
        with patch(
            "app.modules.portfolio.database.history_repository.get_db_manager"
        ) as mock_get_db:
            mock_db_manager = MagicMock()
            mock_get_db.return_value = mock_db_manager

            repo1 = HistoryRepository("aapl")
            repo2 = HistoryRepository("AAPL")
            repo3 = HistoryRepository("AaPl")

            assert repo1.symbol == "AAPL"
            assert repo2.symbol == "AAPL"
            assert repo3.symbol == "AAPL"

    @pytest.mark.asyncio
    async def test_get_daily_range_same_start_end_date(self):
        """Test retrieving daily range with same start and end date."""
        with patch(
            "app.modules.portfolio.database.history_repository.get_db_manager"
        ) as mock_get_db:
            mock_db_manager = MagicMock()
            mock_db = AsyncMock()
            mock_db_manager.history = AsyncMock(return_value=mock_db)
            mock_get_db.return_value = mock_db_manager

            mock_rows = [create_mock_daily_price(date="2024-01-15")]
            mock_db.fetchall.return_value = mock_rows

            with patch(
                "app.modules.portfolio.database.history_repository.init_history_schema"
            ):
                repo = HistoryRepository("AAPL")
                result = await repo.get_daily_range("2024-01-15", "2024-01-15")

                assert len(result) == 1
                assert result[0].date == "2024-01-15"
