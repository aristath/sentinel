"""Tests for charts API endpoints.

These tests validate security price charting functionality, including
data caching, date range parsing, and data source fallback logic.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.charts import (
    _combine_and_filter_data,
    _fetch_from_tradernet,
    _fetch_from_yahoo,
    _get_cached_security_prices,
    _parse_date_range,
    _should_fetch_data,
    _store_security_prices,
)


class TestParseDateRange:
    """Test the date range parsing function."""

    def test_parse_1m_range(self):
        """Test 1 month range parsing."""
        result = _parse_date_range("1M")
        expected = datetime.now() - timedelta(days=30)

        assert result is not None
        assert abs((result - expected).total_seconds()) < 1

    def test_parse_3m_range(self):
        """Test 3 month range parsing."""
        result = _parse_date_range("3M")
        expected = datetime.now() - timedelta(days=90)

        assert result is not None
        assert abs((result - expected).total_seconds()) < 1

    def test_parse_6m_range(self):
        """Test 6 month range parsing."""
        result = _parse_date_range("6M")
        expected = datetime.now() - timedelta(days=180)

        assert result is not None
        assert abs((result - expected).total_seconds()) < 1

    def test_parse_1y_range(self):
        """Test 1 year range parsing."""
        result = _parse_date_range("1Y")
        expected = datetime.now() - timedelta(days=365)

        assert result is not None
        assert abs((result - expected).total_seconds()) < 1

    def test_parse_5y_range(self):
        """Test 5 year range parsing."""
        result = _parse_date_range("5Y")
        expected = datetime.now() - timedelta(days=365 * 5)

        assert result is not None
        assert abs((result - expected).total_seconds()) < 1

    def test_parse_10y_range(self):
        """Test 10 year range parsing."""
        result = _parse_date_range("10Y")
        expected = datetime.now() - timedelta(days=365 * 10)

        assert result is not None
        assert abs((result - expected).total_seconds()) < 1

    def test_parse_all_range(self):
        """Test 'all' range returns None."""
        result = _parse_date_range("all")
        assert result is None

    def test_parse_invalid_range(self):
        """Test invalid range returns None."""
        result = _parse_date_range("invalid")
        assert result is None

    def test_parse_empty_string(self):
        """Test empty string returns None."""
        result = _parse_date_range("")
        assert result is None


class TestShouldFetchData:
    """Test the data fetch decision logic."""

    @pytest.mark.asyncio
    async def test_should_fetch_when_no_cached_data(self):
        """Test that we fetch when there's no cached data."""
        result = await _should_fetch_data([], datetime.now() - timedelta(days=30))
        assert result is True

    @pytest.mark.asyncio
    async def test_should_not_fetch_when_data_covers_range(self):
        """Test that we don't fetch when cached data covers the range."""
        cached_data = [{"time": "2024-01-01", "value": 100}]
        start_date = datetime(2024, 1, 15)

        result = await _should_fetch_data(cached_data, start_date)
        assert result is False

    @pytest.mark.asyncio
    async def test_should_fetch_when_cached_data_starts_after_range(self):
        """Test that we fetch when cached data doesn't cover start of range."""
        cached_data = [{"time": "2024-02-01", "value": 100}]
        start_date = datetime(2024, 1, 1)  # Earlier than cached data

        result = await _should_fetch_data(cached_data, start_date)
        assert result is True

    @pytest.mark.asyncio
    async def test_should_not_fetch_when_no_start_date_and_has_data(self):
        """Test that we don't fetch when start_date is None and we have data."""
        cached_data = [{"time": "2020-01-01", "value": 100}]

        result = await _should_fetch_data(cached_data, None)
        assert result is False


class TestCombineAndFilterData:
    """Test the data combination and filtering logic."""

    def test_combines_cached_and_fetched_data(self):
        """Test that cached and fetched data are combined."""
        cached = [{"time": "2024-01-01", "value": 100}]
        fetched = [{"time": "2024-01-02", "value": 110}]

        result = _combine_and_filter_data(cached, fetched, None)

        assert len(result) == 2
        assert result[0]["time"] == "2024-01-01"
        assert result[1]["time"] == "2024-01-02"

    def test_removes_duplicates_keeping_latest(self):
        """Test that duplicates are removed, with fetched data taking priority."""
        cached = [{"time": "2024-01-01", "value": 100}]
        fetched = [{"time": "2024-01-01", "value": 105}]  # Same date, different value

        result = _combine_and_filter_data(cached, fetched, None)

        assert len(result) == 1
        assert result[0]["value"] == 105  # Fetched value takes priority

    def test_sorts_by_date(self):
        """Test that results are sorted by date."""
        cached = [{"time": "2024-01-15", "value": 150}]
        fetched = [
            {"time": "2024-01-01", "value": 100},
            {"time": "2024-01-10", "value": 120},
        ]

        result = _combine_and_filter_data(cached, fetched, None)

        assert len(result) == 3
        assert result[0]["time"] == "2024-01-01"
        assert result[1]["time"] == "2024-01-10"
        assert result[2]["time"] == "2024-01-15"

    def test_filters_by_start_date(self):
        """Test that results are filtered by start date."""
        cached = [
            {"time": "2024-01-01", "value": 100},
            {"time": "2024-01-10", "value": 110},
            {"time": "2024-01-20", "value": 120},
        ]
        fetched = []
        start_date = datetime(2024, 1, 10)

        result = _combine_and_filter_data(cached, fetched, start_date)

        assert len(result) == 2
        assert result[0]["time"] == "2024-01-10"
        assert result[1]["time"] == "2024-01-20"

    def test_handles_empty_inputs(self):
        """Test handling of empty inputs."""
        result = _combine_and_filter_data([], [], None)
        assert result == []

    def test_filters_all_data_outside_range(self):
        """Test when all data is before the start date."""
        cached = [{"time": "2023-01-01", "value": 100}]
        fetched = [{"time": "2023-06-01", "value": 110}]
        start_date = datetime(2024, 1, 1)

        result = _combine_and_filter_data(cached, fetched, start_date)

        assert result == []


class TestGetCachedStockPrices:
    """Test the cached security price retrieval."""

    @pytest.mark.asyncio
    async def test_retrieves_prices_with_date_filter(self):
        """Test retrieval with date filter."""
        mock_db_manager = AsyncMock()
        mock_history_db = AsyncMock()
        mock_db_manager.history.return_value = mock_history_db

        mock_history_db.fetchall.return_value = [
            {"date": "2024-01-01", "close_price": 100.0},
            {"date": "2024-01-02", "close_price": 105.0},
        ]

        start_date = datetime(2024, 1, 1)
        result = await _get_cached_security_prices("AAPL", start_date, mock_db_manager)

        assert len(result) == 2
        assert result[0]["time"] == "2024-01-01"
        assert result[0]["value"] == 100.0

    @pytest.mark.asyncio
    async def test_retrieves_all_prices_when_no_date_filter(self):
        """Test retrieval without date filter."""
        mock_db_manager = AsyncMock()
        mock_history_db = AsyncMock()
        mock_db_manager.history.return_value = mock_history_db

        mock_history_db.fetchall.return_value = [
            {"date": "2020-01-01", "close_price": 50.0},
            {"date": "2024-01-01", "close_price": 200.0},
        ]

        result = await _get_cached_security_prices("AAPL", None, mock_db_manager)

        assert len(result) == 2


class TestStoreStockPrices:
    """Test security price storage."""

    @pytest.mark.asyncio
    async def test_stores_tradernet_ohlc_data(self):
        """Test storing Tradernet OHLC format data."""
        mock_db_manager = AsyncMock()
        mock_history_db = AsyncMock()
        mock_db_manager.history.return_value = mock_history_db

        # Create mock OHLC data (Tradernet format)
        mock_price = MagicMock()
        mock_price.timestamp = datetime(2024, 1, 15)
        mock_price.close = 150.0
        mock_price.open = 148.0
        mock_price.high = 152.0
        mock_price.low = 147.0
        mock_price.volume = 1000000

        await _store_security_prices("AAPL", [mock_price], "tradernet", mock_db_manager)

        mock_history_db.execute.assert_called_once()
        call_args = mock_history_db.execute.call_args
        assert "INSERT OR REPLACE INTO daily_prices" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_stores_yahoo_historical_data(self):
        """Test storing Yahoo Finance format data."""
        mock_db_manager = AsyncMock()
        mock_history_db = AsyncMock()
        mock_db_manager.history.return_value = mock_history_db

        # Create mock HistoricalPrice (Yahoo format)
        mock_price = MagicMock()
        mock_price.date = datetime(2024, 1, 15)
        mock_price.close = 150.0
        mock_price.open = 148.0
        mock_price.high = 152.0
        mock_price.low = 147.0
        mock_price.volume = 1000000
        # Remove timestamp attribute to simulate Yahoo format
        del mock_price.timestamp

        await _store_security_prices("AAPL", [mock_price], "yahoo", mock_db_manager)

        mock_history_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_invalid_price_data(self):
        """Test that invalid price data is skipped."""
        mock_db_manager = AsyncMock()
        mock_history_db = AsyncMock()
        mock_db_manager.history.return_value = mock_history_db

        # Create mock data without timestamp or date (invalid)
        mock_price = MagicMock(spec=[])  # Empty spec means no attributes

        await _store_security_prices("AAPL", [mock_price], "unknown", mock_db_manager)

        # Should not call execute since data is invalid
        mock_history_db.execute.assert_not_called()


class TestFetchFromTradernet:
    """Test Tradernet data fetching."""

    @pytest.mark.asyncio
    async def test_fetches_and_stores_data(self):
        """Test successful fetch from Tradernet."""
        mock_db_manager = AsyncMock()
        mock_history_db = AsyncMock()
        mock_db_manager.history.return_value = mock_history_db

        mock_ohlc = MagicMock()
        mock_ohlc.timestamp = datetime(2024, 1, 15)
        mock_ohlc.close = 150.0
        mock_ohlc.open = 148.0
        mock_ohlc.high = 152.0
        mock_ohlc.low = 147.0
        mock_ohlc.volume = 1000000

        mock_client = MagicMock()
        mock_client.get_historical_prices.return_value = [mock_ohlc]

        with patch(
            "app.api.charts.ensure_tradernet_connected",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            result = await _fetch_from_tradernet(
                "AAPL",
                datetime(2024, 1, 1),
                datetime(2024, 1, 31),
                mock_db_manager,
            )

        assert len(result) == 1
        assert result[0]["time"] == "2024-01-15"
        assert result[0]["value"] == 150.0

    @pytest.mark.asyncio
    async def test_returns_empty_when_not_connected(self):
        """Test that empty list is returned when Tradernet is not connected."""
        mock_db_manager = AsyncMock()

        with patch(
            "app.api.charts.ensure_tradernet_connected",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await _fetch_from_tradernet(
                "AAPL",
                datetime(2024, 1, 1),
                datetime(2024, 1, 31),
                mock_db_manager,
            )

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_on_no_data(self):
        """Test that empty list is returned when no data available."""
        mock_db_manager = AsyncMock()
        mock_client = MagicMock()
        mock_client.get_historical_prices.return_value = []

        with patch(
            "app.api.charts.ensure_tradernet_connected",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            result = await _fetch_from_tradernet(
                "AAPL",
                datetime(2024, 1, 1),
                datetime(2024, 1, 31),
                mock_db_manager,
            )

        assert result == []

    @pytest.mark.asyncio
    async def test_handles_exception(self):
        """Test that exceptions are handled gracefully."""
        mock_db_manager = AsyncMock()
        mock_client = MagicMock()
        mock_client.get_historical_prices.side_effect = Exception("API error")

        with patch(
            "app.api.charts.ensure_tradernet_connected",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            result = await _fetch_from_tradernet(
                "AAPL",
                datetime(2024, 1, 1),
                datetime(2024, 1, 31),
                mock_db_manager,
            )

        assert result == []


class TestFetchFromYahoo:
    """Test Yahoo Finance data fetching."""

    @pytest.mark.asyncio
    async def test_fetches_and_stores_data(self):
        """Test successful fetch from Yahoo Finance."""
        mock_db_manager = AsyncMock()
        mock_history_db = AsyncMock()
        mock_db_manager.history.return_value = mock_history_db

        mock_price = MagicMock()
        mock_price.date = datetime(2024, 1, 15)
        mock_price.close = 150.0
        mock_price.open = 148.0
        mock_price.high = 152.0
        mock_price.low = 147.0
        mock_price.volume = 1000000

        with patch(
            "app.api.charts.yahoo.get_historical_prices", return_value=[mock_price]
        ):
            result = await _fetch_from_yahoo("AAPL", "1Y", mock_db_manager)

        assert len(result) == 1
        assert result[0]["time"] == "2024-01-15"
        assert result[0]["value"] == 150.0

    @pytest.mark.asyncio
    async def test_maps_range_to_yahoo_period(self):
        """Test that range strings are correctly mapped to Yahoo periods."""
        mock_db_manager = AsyncMock()
        mock_history_db = AsyncMock()
        mock_db_manager.history.return_value = mock_history_db

        with patch(
            "app.api.charts.yahoo.get_historical_prices", return_value=[]
        ) as mock_yahoo:
            await _fetch_from_yahoo("AAPL", "5Y", mock_db_manager)
            mock_yahoo.assert_called_once_with("AAPL", period="5y")

    @pytest.mark.asyncio
    async def test_uses_max_for_all_range(self):
        """Test that 'all' range maps to 'max' period."""
        mock_db_manager = AsyncMock()
        mock_history_db = AsyncMock()
        mock_db_manager.history.return_value = mock_history_db

        with patch(
            "app.api.charts.yahoo.get_historical_prices", return_value=[]
        ) as mock_yahoo:
            await _fetch_from_yahoo("AAPL", "all", mock_db_manager)
            mock_yahoo.assert_called_once_with("AAPL", period="max")

    @pytest.mark.asyncio
    async def test_returns_empty_on_no_data(self):
        """Test that empty list is returned when no data available."""
        mock_db_manager = AsyncMock()

        with patch("app.api.charts.yahoo.get_historical_prices", return_value=[]):
            result = await _fetch_from_yahoo("AAPL", "1Y", mock_db_manager)

        assert result == []

    @pytest.mark.asyncio
    async def test_handles_exception(self):
        """Test that exceptions are handled gracefully."""
        mock_db_manager = AsyncMock()

        with patch(
            "app.api.charts.yahoo.get_historical_prices",
            side_effect=Exception("Yahoo API error"),
        ):
            result = await _fetch_from_yahoo("AAPL", "1Y", mock_db_manager)

        assert result == []


class TestSparklines:
    """Test the sparklines endpoint."""

    @pytest.mark.asyncio
    async def test_returns_sparklines_for_active_stocks(self):
        """Test that sparklines are returned for all active securities."""
        from app.api.charts import get_all_stock_sparklines

        mock_db_manager = AsyncMock()
        mock_config_db = MagicMock()
        mock_history_db = AsyncMock()

        mock_db_manager.config = mock_config_db
        mock_config_db.fetchall = AsyncMock(
            return_value=[{"symbol": "AAPL"}, {"symbol": "GOOGL"}]
        )

        mock_db_manager.history.return_value = mock_history_db
        mock_history_db.fetchall.return_value = [
            {"date": "2024-01-01", "close_price": 100.0}
        ]

        with patch("app.api.charts.cache") as mock_cache:
            mock_cache.get.return_value = None  # No cache

            result = await get_all_stock_sparklines(mock_db_manager)

        assert "AAPL" in result
        assert "GOOGL" in result

    @pytest.mark.asyncio
    async def test_uses_cache_when_available(self):
        """Test that cached sparklines are used."""
        from app.api.charts import get_all_stock_sparklines

        mock_db_manager = AsyncMock()
        mock_config_db = MagicMock()
        mock_db_manager.config = mock_config_db
        mock_config_db.fetchall = AsyncMock(return_value=[{"symbol": "AAPL"}])

        cached_data = [{"time": "2024-01-01", "value": 100.0}]

        with patch("app.api.charts.cache") as mock_cache:
            mock_cache.get.return_value = cached_data

            result = await get_all_stock_sparklines(mock_db_manager)

        assert result["AAPL"] == cached_data


class TestStockChart:
    """Test the individual security chart endpoint."""

    @pytest.mark.asyncio
    async def test_returns_chart_data_from_cache(self):
        """Test that chart data is returned from cache."""
        from app.api.charts import get_stock_chart

        mock_db_manager = MagicMock()
        mock_history_db = AsyncMock()
        mock_stock_repo = AsyncMock()

        # db_manager.history() is an async method that returns a db connection
        mock_db_manager.history = AsyncMock(return_value=mock_history_db)

        # Mock security lookup by ISIN
        mock_stock = MagicMock()
        mock_stock.symbol = "AAPL.US"
        mock_stock.isin = "US0378331005"
        mock_stock_repo.get_by_isin.return_value = mock_stock

        # Use recent dates that will pass the date filter for "1M" range
        today = datetime.now()
        yesterday = today - timedelta(days=1)
        day_before = today - timedelta(days=2)

        mock_history_db.fetchall.return_value = [
            {"date": day_before.strftime("%Y-%m-%d"), "close_price": 100.0},
            {"date": yesterday.strftime("%Y-%m-%d"), "close_price": 105.0},
        ]

        with patch("app.api.charts.is_isin", return_value=True):
            result = await get_stock_chart(
                "US0378331005", mock_db_manager, mock_stock_repo, range="1M"
            )

            # Cached data covers the range, so should return it
            assert len(result) == 2
            assert result[0]["value"] == 100.0
            assert result[1]["value"] == 105.0

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_data(self):
        """Test that empty list is returned when no data available."""
        from app.api.charts import get_stock_chart

        mock_db_manager = MagicMock()
        mock_history_db = AsyncMock()
        mock_stock_repo = AsyncMock()
        mock_db_manager.history = AsyncMock(return_value=mock_history_db)

        # Mock security lookup by ISIN
        mock_stock = MagicMock()
        mock_stock.symbol = "AAPL.US"
        mock_stock.isin = "US0378331005"
        mock_stock_repo.get_by_isin.return_value = mock_stock

        # No cached data
        mock_history_db.fetchall.return_value = []

        # Mock tradernet to return None (not connected)
        with patch(
            "app.infrastructure.external.tradernet_connection."
            "ensure_tradernet_connected",
            new_callable=AsyncMock,
            return_value=None,
        ):
            # Mock yahoo to return empty
            with patch(
                "app.api.charts.yahoo.get_historical_prices",
                return_value=[],
            ):
                with patch("app.api.charts.is_isin", return_value=True):
                    result = await get_stock_chart(
                        "US0378331005",
                        mock_db_manager,
                        mock_stock_repo,
                        range="1Y",
                        source="tradernet",
                    )

        assert result == []

    @pytest.mark.asyncio
    async def test_raises_http_exception_on_database_error(self):
        """Test that HTTPException is raised on database errors."""
        from fastapi import HTTPException

        from app.api.charts import get_stock_chart

        mock_db_manager = MagicMock()
        mock_stock_repo = AsyncMock()
        mock_db_manager.history = AsyncMock(side_effect=Exception("Database error"))

        # Mock security lookup by ISIN
        mock_stock = MagicMock()
        mock_stock.symbol = "AAPL.US"
        mock_stock.isin = "US0378331005"
        mock_stock_repo.get_by_isin.return_value = mock_stock

        with patch("app.api.charts.is_isin", return_value=True):
            with pytest.raises(HTTPException) as exc_info:
                await get_stock_chart(
                    "US0378331005", mock_db_manager, mock_stock_repo, range="1Y"
                )

            assert exc_info.value.status_code == 500
            assert "Database error" in str(exc_info.value.detail)
