"""Tests for daily sync job.

These tests validate the portfolio and price synchronization logic
from Tradernet to local database.
"""

from contextlib import asynccontextmanager
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestExtractQuotesList:
    """Tests for _extract_quotes_list helper."""

    def test_extracts_from_list(self):
        """Test extracting quotes when response is a list."""
        from app.jobs.daily_sync import _extract_quotes_list

        quotes = [{"c": "AAPL.US", "x_curr": "USD"}]
        result = _extract_quotes_list(quotes)

        assert result == quotes

    def test_extracts_from_dict_with_result(self):
        """Test extracting quotes from dict with result.q structure."""
        from app.jobs.daily_sync import _extract_quotes_list

        quotes_data = {"result": {"q": [{"c": "AAPL.US"}]}}
        result = _extract_quotes_list(quotes_data)

        assert result == [{"c": "AAPL.US"}]

    def test_extracts_from_dict_with_q(self):
        """Test extracting quotes from dict with q directly."""
        from app.jobs.daily_sync import _extract_quotes_list

        quotes_data = {"q": [{"c": "MSFT.US"}]}
        result = _extract_quotes_list(quotes_data)

        assert result == [{"c": "MSFT.US"}]

    def test_returns_empty_for_empty_dict(self):
        """Test returns empty list for empty dict."""
        from app.jobs.daily_sync import _extract_quotes_list

        result = _extract_quotes_list({})

        assert result == []

    def test_returns_empty_for_other_types(self):
        """Test returns empty list for non-list/dict types."""
        from app.jobs.daily_sync import _extract_quotes_list

        result = _extract_quotes_list("string")

        assert result == []


class TestCalculateCashBalanceEur:
    """Tests for _calculate_cash_balance_eur helper."""

    def test_calculates_eur_only(self):
        """Test calculating balance with EUR only."""
        from app.jobs.daily_sync import _calculate_cash_balance_eur

        mock_balance = MagicMock()
        mock_balance.currency = "EUR"
        mock_balance.amount = 1000.0

        result = _calculate_cash_balance_eur([mock_balance], {"EUR": 1.0})

        assert result == 1000.0

    def test_converts_usd_to_eur(self):
        """Test converting USD to EUR."""
        from app.jobs.daily_sync import _calculate_cash_balance_eur

        mock_balance = MagicMock()
        mock_balance.currency = "USD"
        mock_balance.amount = 1050.0

        result = _calculate_cash_balance_eur([mock_balance], {"USD": 1.05})

        assert result == 1000.0

    def test_handles_multiple_currencies(self):
        """Test handling multiple currencies."""
        from app.jobs.daily_sync import _calculate_cash_balance_eur

        mock_eur = MagicMock()
        mock_eur.currency = "EUR"
        mock_eur.amount = 500.0

        mock_usd = MagicMock()
        mock_usd.currency = "USD"
        mock_usd.amount = 525.0  # 500 EUR at 1.05 rate

        result = _calculate_cash_balance_eur(
            [mock_eur, mock_usd], {"EUR": 1.0, "USD": 1.05}
        )

        assert result == 1000.0

    def test_skips_zero_or_negative_amounts(self):
        """Test skipping zero or negative non-EUR amounts."""
        from app.jobs.daily_sync import _calculate_cash_balance_eur

        mock_balance = MagicMock()
        mock_balance.currency = "USD"
        mock_balance.amount = 0

        result = _calculate_cash_balance_eur([mock_balance], {"USD": 1.05})

        assert result == 0.0


class TestDetermineGeography:
    """Tests for _determine_geography helper."""

    @pytest.mark.asyncio
    async def test_returns_geography_from_db(self):
        """Test returning geography from database."""
        from app.jobs.daily_sync import _determine_geography

        mock_cursor = AsyncMock()
        mock_cursor.fetchone.return_value = ("US",)

        mock_db = MagicMock()
        mock_db.config = AsyncMock()
        mock_db.config.execute.return_value = mock_cursor

        result = await _determine_geography("AAPL.US", mock_db)

        assert result == "US"

    @pytest.mark.asyncio
    async def test_infers_eu_from_suffix(self):
        """Test inferring EU geography from suffix."""
        from app.jobs.daily_sync import _determine_geography

        mock_cursor = AsyncMock()
        mock_cursor.fetchone.return_value = None

        mock_db = MagicMock()
        mock_db.config = AsyncMock()
        mock_db.config.execute.return_value = mock_cursor

        for suffix in [".GR", ".DE", ".PA"]:
            result = await _determine_geography(f"STOCK{suffix}", mock_db)
            assert result == "EU", f"Failed for {suffix}"

    @pytest.mark.asyncio
    async def test_infers_asia_from_suffix(self):
        """Test inferring ASIA geography from suffix."""
        from app.jobs.daily_sync import _determine_geography

        mock_cursor = AsyncMock()
        mock_cursor.fetchone.return_value = None

        mock_db = MagicMock()
        mock_db.config = AsyncMock()
        mock_db.config.execute.return_value = mock_cursor

        for suffix in [".AS", ".HK", ".T"]:
            result = await _determine_geography(f"STOCK{suffix}", mock_db)
            assert result == "ASIA", f"Failed for {suffix}"

    @pytest.mark.asyncio
    async def test_infers_us_from_suffix(self):
        """Test inferring US geography from suffix."""
        from app.jobs.daily_sync import _determine_geography

        mock_cursor = AsyncMock()
        mock_cursor.fetchone.return_value = None

        mock_db = MagicMock()
        mock_db.config = AsyncMock()
        mock_db.config.execute.return_value = mock_cursor

        result = await _determine_geography("AAPL.US", mock_db)

        assert result == "US"

    @pytest.mark.asyncio
    async def test_returns_none_for_unknown(self):
        """Test returning None for unknown geography."""
        from app.jobs.daily_sync import _determine_geography

        mock_cursor = AsyncMock()
        mock_cursor.fetchone.return_value = None

        mock_db = MagicMock()
        mock_db.config = AsyncMock()
        mock_db.config.execute.return_value = mock_cursor

        result = await _determine_geography("UNKNOWN", mock_db)

        assert result is None


class TestFetchExchangeRates:
    """Tests for _fetch_exchange_rates helper."""

    @pytest.mark.asyncio
    async def test_returns_eur_one_for_empty_set(self):
        """Test returns EUR:1.0 for empty currency set."""
        from app.jobs.daily_sync import _fetch_exchange_rates

        result = await _fetch_exchange_rates(set())

        assert result == {"EUR": 1.0}

    @pytest.mark.asyncio
    async def test_fetches_rates_from_api(self):
        """Test fetching rates from API."""
        from app.jobs.daily_sync import _fetch_exchange_rates

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"rates": {"USD": 1.05, "GBP": 0.85}}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await _fetch_exchange_rates({"USD", "GBP"})

            assert result["EUR"] == 1.0
            assert result["USD"] == 1.05
            assert result["GBP"] == 0.85

    @pytest.mark.asyncio
    async def test_uses_fallback_rates_on_api_error(self):
        """Test using fallback rates when API fails."""
        from app.jobs.daily_sync import _fetch_exchange_rates

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=Exception("API error")
            )

            result = await _fetch_exchange_rates({"USD"})

            assert result["USD"] == 1.05  # fallback rate


class TestSyncPortfolioInternal:
    """Tests for _sync_portfolio_internal."""

    @pytest.mark.asyncio
    async def test_skips_when_not_connected(self):
        """Test that sync is skipped when Tradernet is not connected."""
        from app.jobs.daily_sync import _sync_portfolio_internal

        with (
            patch("app.jobs.daily_sync.get_tradernet_client") as mock_get_client,
            patch("app.jobs.daily_sync.set_processing"),
            patch("app.jobs.daily_sync.set_error") as mock_set_error,
            patch("app.jobs.daily_sync.emit"),
            patch("app.jobs.daily_sync.clear_processing"),
        ):
            mock_client = MagicMock()
            mock_client.is_connected = False
            mock_client.connect.return_value = False
            mock_get_client.return_value = mock_client

            await _sync_portfolio_internal()

            mock_set_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_syncs_positions_successfully(self):
        """Test successful position sync."""
        from app.jobs.daily_sync import _sync_portfolio_internal

        mock_position = MagicMock()
        mock_position.symbol = "AAPL.US"
        mock_position.quantity = 10
        mock_position.avg_price = 150.0
        mock_position.currency = None

        mock_cash = MagicMock()
        mock_cash.currency = "EUR"
        mock_cash.amount = 1000.0

        @asynccontextmanager
        async def mock_transaction():
            yield

        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = ("US",)

        mock_state = AsyncMock()
        mock_state.execute.return_value = mock_cursor
        mock_state.transaction = mock_transaction

        mock_ledger = AsyncMock()
        mock_ledger.execute.return_value = mock_cursor

        mock_db = MagicMock()
        mock_db.state = mock_state
        mock_db.ledger = mock_ledger
        mock_db.config = AsyncMock()
        mock_db.config.execute.return_value = mock_cursor

        with (
            patch("app.jobs.daily_sync.get_tradernet_client") as mock_get_client,
            patch("app.jobs.daily_sync.get_db_manager") as mock_get_db,
            patch("app.jobs.daily_sync.get_event_bus") as mock_get_bus,
            patch("app.jobs.daily_sync._fetch_exchange_rates") as mock_rates,
            patch("app.jobs.daily_sync.sync_stock_currencies"),
            patch("app.jobs.daily_sync._sync_prices_internal"),
            patch("app.jobs.daily_sync.set_processing"),
            patch("app.jobs.daily_sync.clear_processing"),
            patch("app.jobs.daily_sync.emit"),
        ):
            mock_client = MagicMock()
            mock_client.is_connected = True
            mock_client.get_portfolio.return_value = [mock_position]
            mock_client.get_cash_balances.return_value = [mock_cash]
            mock_get_client.return_value = mock_client
            mock_get_db.return_value = mock_db
            mock_get_bus.return_value = MagicMock()
            mock_rates.return_value = {"EUR": 1.0}

            await _sync_portfolio_internal()

            # Should have attempted to insert position
            assert mock_state.execute.call_count >= 1


class TestSyncPricesInternal:
    """Tests for _sync_prices_internal."""

    @pytest.mark.asyncio
    async def test_skips_when_no_stocks(self):
        """Test that sync is skipped when no stocks."""
        from app.jobs.daily_sync import _sync_prices_internal

        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = []

        mock_config = AsyncMock()
        mock_config.execute.return_value = mock_cursor

        mock_db = MagicMock()
        mock_db.config = mock_config

        with (
            patch("app.jobs.daily_sync.get_db_manager") as mock_get_db,
            patch("app.jobs.daily_sync.set_processing"),
            patch("app.jobs.daily_sync.emit"),
        ):
            mock_get_db.return_value = mock_db

            await _sync_prices_internal()

            # Should not have called yahoo
            mock_db.state.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_syncs_prices_from_yahoo(self):
        """Test syncing prices from Yahoo."""
        from app.jobs.daily_sync import _sync_prices_internal

        @asynccontextmanager
        async def mock_transaction():
            yield

        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = [("AAPL.US", "AAPL")]
        mock_cursor.rowcount = 1

        mock_config = AsyncMock()
        mock_config.execute.return_value = mock_cursor

        mock_state = AsyncMock()
        mock_state.execute.return_value = mock_cursor
        mock_state.transaction = mock_transaction

        mock_db = MagicMock()
        mock_db.config = mock_config
        mock_db.state = mock_state

        with (
            patch("app.jobs.daily_sync.get_db_manager") as mock_get_db,
            patch(
                "app.jobs.daily_sync.yahoo.get_batch_quotes"
            ) as mock_yahoo,
            patch("app.jobs.daily_sync.set_processing"),
            patch("app.jobs.daily_sync.emit"),
        ):
            mock_get_db.return_value = mock_db
            mock_yahoo.return_value = {"AAPL.US": 175.0}

            await _sync_prices_internal()

            mock_yahoo.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_price_sync_error(self):
        """Test handling price sync error."""
        from app.jobs.daily_sync import _sync_prices_internal

        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = [("AAPL.US", "AAPL")]

        mock_config = AsyncMock()
        mock_config.execute.return_value = mock_cursor

        mock_db = MagicMock()
        mock_db.config = mock_config

        with (
            patch("app.jobs.daily_sync.get_db_manager") as mock_get_db,
            patch(
                "app.jobs.daily_sync.yahoo.get_batch_quotes"
            ) as mock_yahoo,
            patch("app.jobs.daily_sync.set_processing"),
            patch("app.jobs.daily_sync.set_error") as mock_set_error,
            patch("app.jobs.daily_sync.emit"),
        ):
            mock_get_db.return_value = mock_db
            mock_yahoo.side_effect = Exception("Yahoo error")

            with pytest.raises(Exception, match="Yahoo error"):
                await _sync_prices_internal()

            mock_set_error.assert_called_once()


class TestSyncStockCurrencies:
    """Tests for sync_stock_currencies."""

    @pytest.mark.asyncio
    async def test_skips_when_not_connected(self):
        """Test that sync is skipped when Tradernet is not connected."""
        from app.jobs.daily_sync import sync_stock_currencies

        with (
            patch("app.jobs.daily_sync.get_tradernet_client") as mock_get_client,
            patch("app.jobs.daily_sync.set_processing"),
            patch("app.jobs.daily_sync.clear_processing"),
        ):
            mock_client = MagicMock()
            mock_client.is_connected = False
            mock_client.connect.return_value = False
            mock_get_client.return_value = mock_client

            await sync_stock_currencies()

            # Should have returned early
            mock_client.get_quotes_raw.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_no_stocks(self):
        """Test that sync is skipped when no stocks."""
        from app.jobs.daily_sync import sync_stock_currencies

        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = []

        mock_config = AsyncMock()
        mock_config.execute.return_value = mock_cursor

        mock_db = MagicMock()
        mock_db.config = mock_config

        with (
            patch("app.jobs.daily_sync.get_tradernet_client") as mock_get_client,
            patch("app.jobs.daily_sync.get_db_manager") as mock_get_db,
            patch("app.jobs.daily_sync.set_processing"),
        ):
            mock_client = MagicMock()
            mock_client.is_connected = True
            mock_get_client.return_value = mock_client
            mock_get_db.return_value = mock_db

            await sync_stock_currencies()

            mock_client.get_quotes_raw.assert_not_called()

    @pytest.mark.asyncio
    async def test_syncs_currencies_from_tradernet(self):
        """Test syncing currencies from Tradernet."""
        from app.jobs.daily_sync import sync_stock_currencies

        @asynccontextmanager
        async def mock_transaction():
            yield

        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = [("AAPL.US",)]

        mock_config = AsyncMock()
        mock_config.execute.return_value = mock_cursor
        mock_config.transaction = mock_transaction

        mock_db = MagicMock()
        mock_db.config = mock_config

        with (
            patch("app.jobs.daily_sync.get_tradernet_client") as mock_get_client,
            patch("app.jobs.daily_sync.get_db_manager") as mock_get_db,
            patch("app.jobs.daily_sync.set_processing"),
        ):
            mock_client = MagicMock()
            mock_client.is_connected = True
            mock_client.get_quotes_raw.return_value = [
                {"c": "AAPL.US", "x_curr": "USD"}
            ]
            mock_get_client.return_value = mock_client
            mock_get_db.return_value = mock_db

            await sync_stock_currencies()

            mock_client.get_quotes_raw.assert_called_once_with(["AAPL.US"])


class TestSyncPortfolio:
    """Tests for sync_portfolio main function."""

    @pytest.mark.asyncio
    async def test_uses_file_lock(self):
        """Test that file lock is used."""
        from app.jobs.daily_sync import sync_portfolio

        with (
            patch("app.jobs.daily_sync.file_lock") as mock_lock,
            patch("app.jobs.daily_sync._sync_portfolio_internal") as mock_internal,
        ):
            mock_lock.return_value.__aenter__ = AsyncMock()
            mock_lock.return_value.__aexit__ = AsyncMock()

            await sync_portfolio()

            mock_lock.assert_called_once_with("portfolio_sync", timeout=60.0)
            mock_internal.assert_called_once()


class TestSyncPrices:
    """Tests for sync_prices main function."""

    @pytest.mark.asyncio
    async def test_uses_file_lock(self):
        """Test that file lock is used."""
        from app.jobs.daily_sync import sync_prices

        with (
            patch("app.jobs.daily_sync.file_lock") as mock_lock,
            patch("app.jobs.daily_sync._sync_prices_internal") as mock_internal,
        ):
            mock_lock.return_value.__aenter__ = AsyncMock()
            mock_lock.return_value.__aexit__ = AsyncMock()

            await sync_prices()

            mock_lock.assert_called_once_with("price_sync", timeout=120.0)
            mock_internal.assert_called_once()
