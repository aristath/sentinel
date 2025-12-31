"""Tests for daily sync job.

These tests validate the portfolio and price synchronization logic
from Tradernet to local database.
"""

from contextlib import asynccontextmanager
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

    @pytest.mark.asyncio
    async def test_calculates_eur_only(self):
        """Test calculating balance with EUR only."""
        from app.jobs.daily_sync import _calculate_cash_balance_eur

        mock_balance = MagicMock()
        mock_balance.currency = "EUR"
        mock_balance.amount = 1000.0

        mock_exchange_service = AsyncMock()
        mock_exchange_service.batch_convert_to_eur.return_value = {"EUR": 1000.0}

        result = await _calculate_cash_balance_eur(
            [mock_balance], mock_exchange_service
        )

        assert result == 1000.0

    @pytest.mark.asyncio
    async def test_converts_usd_to_eur(self):
        """Test converting USD to EUR."""
        from app.jobs.daily_sync import _calculate_cash_balance_eur

        mock_balance = MagicMock()
        mock_balance.currency = "USD"
        mock_balance.amount = 1050.0

        mock_exchange_service = AsyncMock()
        mock_exchange_service.batch_convert_to_eur.return_value = {"USD": 1000.0}

        result = await _calculate_cash_balance_eur(
            [mock_balance], mock_exchange_service
        )

        assert result == 1000.0

    @pytest.mark.asyncio
    async def test_handles_multiple_currencies(self):
        """Test handling multiple currencies."""
        from app.jobs.daily_sync import _calculate_cash_balance_eur

        mock_eur = MagicMock()
        mock_eur.currency = "EUR"
        mock_eur.amount = 500.0

        mock_usd = MagicMock()
        mock_usd.currency = "USD"
        mock_usd.amount = 525.0  # 500 EUR at 1.05 rate

        mock_exchange_service = AsyncMock()
        mock_exchange_service.batch_convert_to_eur.return_value = {
            "EUR": 500.0,
            "USD": 500.0,
        }

        result = await _calculate_cash_balance_eur(
            [mock_eur, mock_usd], mock_exchange_service
        )

        assert result == 1000.0

    @pytest.mark.asyncio
    async def test_skips_zero_or_negative_amounts(self):
        """Test skipping zero or negative non-EUR amounts."""
        from app.jobs.daily_sync import _calculate_cash_balance_eur

        mock_balance = MagicMock()
        mock_balance.currency = "USD"
        mock_balance.amount = 0

        mock_exchange_service = AsyncMock()
        mock_exchange_service.batch_convert_to_eur.return_value = {"USD": 0.0}

        result = await _calculate_cash_balance_eur(
            [mock_balance], mock_exchange_service
        )

        assert result == 0.0


class TestDetermineCountry:
    """Tests for _determine_country helper."""

    @pytest.mark.asyncio
    async def test_returns_country_from_db(self):
        """Test returning country from database."""
        from app.jobs.daily_sync import _determine_country

        mock_cursor = AsyncMock()
        mock_cursor.fetchone.return_value = ("United States",)

        mock_db = MagicMock()
        mock_db.config = AsyncMock()
        mock_db.config.execute.return_value = mock_cursor

        result = await _determine_country("AAPL.US", mock_db)

        assert result == "United States"

    @pytest.mark.asyncio
    async def test_infers_country_from_suffix_legacy(self):
        """Test inferring country from suffix (legacy fallback)."""
        from app.jobs.daily_sync import _determine_country

        mock_cursor = AsyncMock()
        mock_cursor.fetchone.return_value = None

        mock_db = MagicMock()
        mock_db.config = AsyncMock()
        mock_db.config.execute.return_value = mock_cursor

        # Legacy suffixes still return legacy codes for backward compatibility
        for suffix in [".GR", ".DE", ".PA"]:
            result = await _determine_country(f"STOCK{suffix}", mock_db)
            assert result == "EU", f"Failed for {suffix}"

        for suffix in [".AS", ".HK", ".T"]:
            result = await _determine_country(f"STOCK{suffix}", mock_db)
            assert result == "ASIA", f"Failed for {suffix}"

        result = await _determine_country("AAPL.US", mock_db)
        assert result == "US"

    @pytest.mark.asyncio
    async def test_returns_none_for_unknown(self):
        """Test returning None for unknown country."""
        from app.jobs.daily_sync import _determine_country

        mock_cursor = AsyncMock()
        mock_cursor.fetchone.return_value = None

        mock_db = MagicMock()
        mock_db.config = AsyncMock()
        mock_db.config.execute.return_value = mock_cursor

        result = await _determine_country("UNKNOWN", mock_db)

        assert result is None


class TestSyncPortfolioInternal:
    """Tests for _sync_portfolio_internal."""

    @pytest.mark.asyncio
    async def test_skips_when_not_connected(self):
        """Test that sync is skipped when Tradernet is not connected."""
        from app.jobs.daily_sync import _sync_portfolio_internal

        with (
            patch("app.jobs.daily_sync.get_tradernet_client") as mock_get_client,
            patch("app.jobs.daily_sync.set_text"),
            patch("app.jobs.daily_sync.set_text") as mock_set_error,
            patch("app.jobs.daily_sync.emit"),
            patch("pass  # LED cleared"),
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

        mock_exchange_service = AsyncMock()
        mock_exchange_service.batch_convert_to_eur.return_value = {"EUR": 1000.0}
        mock_exchange_service.get_rate.return_value = 1.0

        with (
            patch("app.jobs.daily_sync.get_tradernet_client") as mock_get_client,
            patch("app.jobs.daily_sync.get_db_manager") as mock_get_db,
            patch("app.jobs.daily_sync.get_event_bus") as mock_get_bus,
            patch("app.jobs.daily_sync.get_exchange_rate_service") as mock_get_exchange,
            patch("app.jobs.daily_sync.sync_stock_currencies"),
            patch("app.jobs.daily_sync._sync_prices_internal"),
            patch("app.jobs.daily_sync.set_text"),
            patch("pass  # LED cleared"),
            patch("app.jobs.daily_sync.emit"),
            patch("app.repositories.PositionRepository") as mock_position_repo_class,
            patch("app.repositories.SecurityRepository") as mock_stock_repo_class,
        ):
            mock_client = MagicMock()
            mock_client.is_connected = True
            mock_client.get_portfolio.return_value = [mock_position]
            mock_client.get_cash_balances.return_value = [mock_cash]
            mock_get_client.return_value = mock_client
            mock_get_db.return_value = mock_db
            mock_get_bus.return_value = MagicMock()
            mock_get_exchange.return_value = mock_exchange_service

            mock_position_repo = AsyncMock()
            mock_position_repo.get_all = AsyncMock(return_value=[])
            mock_position_repo_class.return_value = mock_position_repo

            mock_stock_repo = AsyncMock()
            mock_stock_repo.get_all_active = AsyncMock(return_value=[])
            mock_stock_repo_class.return_value = mock_stock_repo

            await _sync_portfolio_internal()

            # Should have attempted to insert position
            assert mock_state.execute.call_count >= 1


class TestSyncPricesInternal:
    """Tests for _sync_prices_internal."""

    @pytest.mark.asyncio
    async def test_skips_when_no_stocks(self):
        """Test that sync is skipped when no securities."""
        from app.jobs.daily_sync import _sync_prices_internal

        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_all_active.return_value = []

        with (
            patch("app.jobs.daily_sync.SecurityRepository") as mock_stock_class,
            patch("app.jobs.daily_sync.set_text"),
            patch("app.jobs.daily_sync.emit"),
        ):
            mock_stock_class.return_value = mock_stock_repo

            await _sync_prices_internal()

            # Should have called get_all_active
            mock_stock_repo.get_all_active.assert_called_once()

    @pytest.mark.asyncio
    async def test_syncs_prices_from_yahoo(self):
        """Test syncing prices from Yahoo."""
        from app.jobs.daily_sync import _sync_prices_internal

        @asynccontextmanager
        async def mock_transaction():
            yield

        mock_stock = MagicMock()
        mock_stock.symbol = "AAPL.US"
        mock_stock.yahoo_symbol = "AAPL"

        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_all_active.return_value = [mock_stock]

        mock_cursor = AsyncMock()
        mock_cursor.rowcount = 1

        mock_state = AsyncMock()
        mock_state.execute.return_value = mock_cursor
        mock_state.transaction = mock_transaction

        mock_db = MagicMock()
        mock_db.state = mock_state

        with (
            patch("app.jobs.daily_sync.SecurityRepository") as mock_stock_class,
            patch("app.jobs.daily_sync.get_db_manager") as mock_get_db,
            patch("app.jobs.daily_sync.yahoo.get_batch_quotes") as mock_yahoo,
            patch("app.jobs.daily_sync.set_text"),
            patch("app.jobs.daily_sync.emit"),
        ):
            mock_stock_class.return_value = mock_stock_repo
            mock_get_db.return_value = mock_db
            mock_yahoo.return_value = {"AAPL.US": 175.0}

            await _sync_prices_internal()

            mock_yahoo.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_price_sync_error(self):
        """Test handling price sync error."""
        from app.jobs.daily_sync import _sync_prices_internal

        mock_stock = MagicMock()
        mock_stock.symbol = "AAPL.US"
        mock_stock.yahoo_symbol = "AAPL"

        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_all_active.return_value = [mock_stock]

        with (
            patch("app.jobs.daily_sync.SecurityRepository") as mock_stock_class,
            patch("app.jobs.daily_sync.yahoo.get_batch_quotes") as mock_yahoo,
            patch("app.jobs.daily_sync.set_text"),
            patch("app.jobs.daily_sync.set_text") as mock_set_error,
            patch("app.jobs.daily_sync.emit"),
        ):
            mock_stock_class.return_value = mock_stock_repo
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
            patch("app.jobs.daily_sync.set_text"),
            patch("pass  # LED cleared"),
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
        """Test that sync is skipped when no securities."""
        from app.jobs.daily_sync import sync_stock_currencies

        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_all_active.return_value = []

        with (
            patch("app.jobs.daily_sync.get_tradernet_client") as mock_get_client,
            patch("app.jobs.daily_sync.SecurityRepository") as mock_stock_class,
            patch("app.jobs.daily_sync.set_text"),
        ):
            mock_client = MagicMock()
            mock_client.is_connected = True
            mock_get_client.return_value = mock_client
            mock_stock_class.return_value = mock_stock_repo

            await sync_stock_currencies()

            mock_client.get_quotes_raw.assert_not_called()

    @pytest.mark.asyncio
    async def test_syncs_currencies_from_tradernet(self):
        """Test syncing currencies from Tradernet."""
        from app.jobs.daily_sync import sync_stock_currencies

        @asynccontextmanager
        async def mock_transaction():
            yield

        mock_stock = MagicMock()
        mock_stock.symbol = "AAPL.US"

        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_all_active.return_value = [mock_stock]

        mock_config = AsyncMock()
        mock_config.transaction = mock_transaction

        mock_db = MagicMock()
        mock_db.config = mock_config

        with (
            patch("app.jobs.daily_sync.get_tradernet_client") as mock_get_client,
            patch("app.jobs.daily_sync.SecurityRepository") as mock_stock_class,
            patch("app.jobs.daily_sync.get_db_manager") as mock_get_db,
            patch("app.jobs.daily_sync.set_text"),
        ):
            mock_client = MagicMock()
            mock_client.is_connected = True
            mock_client.get_quotes_raw.return_value = [
                {"c": "AAPL.US", "x_curr": "USD"}
            ]
            mock_get_client.return_value = mock_client
            mock_stock_class.return_value = mock_stock_repo
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
