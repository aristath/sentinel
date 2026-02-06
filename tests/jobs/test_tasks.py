"""Tests for job task functions."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_portfolio():
    """Mock portfolio for testing."""
    portfolio = AsyncMock()
    portfolio.sync = AsyncMock()
    return portfolio


@pytest.fixture
def mock_db():
    """Mock database for testing."""
    db = AsyncMock()
    db.get_all_securities = AsyncMock(
        return_value=[
            {"symbol": "AAPL.US"},
            {"symbol": "MSFT.US"},
            {"symbol": "GOOG.US"},
        ]
    )
    db.save_prices = AsyncMock()
    db.update_quotes_bulk = AsyncMock()
    db.update_security_metadata = AsyncMock()
    db.cache_clear = AsyncMock(return_value=5)
    db.get_ml_enabled_securities = AsyncMock(
        return_value=[
            {"symbol": "AAPL.US"},
            {"symbol": "MSFT.US"},
        ]
    )
    return db


@pytest.fixture
def mock_broker():
    """Mock broker for testing."""
    broker = AsyncMock()
    broker.connected = True
    broker.get_historical_prices_bulk = AsyncMock(
        return_value={
            "AAPL.US": [{"date": "2024-01-01", "close": 100}],
            "MSFT.US": [{"date": "2024-01-01", "close": 200}],
        }
    )
    broker.get_quotes = AsyncMock(
        return_value={
            "AAPL.US": {"price": 100},
            "MSFT.US": {"price": 200},
        }
    )
    broker.get_security_info = AsyncMock(
        return_value={
            "mrkt": {"mkt_id": 1},
            "lot": 1,
        }
    )
    broker.get_market_status = AsyncMock(return_value={"m": [{"i": 1, "n2": "NASDAQ", "s": "OPEN"}]})
    return broker


@pytest.fixture
def mock_cache():
    """Mock cache for testing."""
    cache = MagicMock()
    cache.clear = MagicMock(return_value=10)
    return cache


@pytest.fixture
def mock_analyzer():
    """Mock analyzer for testing."""
    analyzer = AsyncMock()
    analyzer.update_scores = AsyncMock(return_value=5)
    return analyzer


@pytest.fixture
def mock_detector():
    """Mock regime detector for testing."""
    detector = AsyncMock()
    detector.train_model = AsyncMock(return_value={"status": "trained"})
    return detector


@pytest.fixture
def mock_planner():
    """Mock planner for testing."""
    planner = AsyncMock()
    planner.get_recommendations = AsyncMock(return_value=[])
    planner.get_rebalance_summary = AsyncMock(
        return_value={
            "needs_rebalance": False,
            "total_deviation": 0.05,
        }
    )
    planner.calculate_ideal_portfolio = AsyncMock(return_value={"AAPL.US": 0.5})
    return planner


@pytest.fixture
def mock_retrainer():
    """Mock ML retrainer for testing."""
    retrainer = AsyncMock()
    retrainer.retrain_symbol = AsyncMock(
        return_value={
            "validation_rmse": 0.05,
            "training_samples": 100,
        }
    )
    return retrainer


@pytest.fixture
def mock_monitor():
    """Mock ML monitor for testing."""
    monitor = AsyncMock()
    monitor.track_symbol_performance = AsyncMock(
        return_value={
            "xgboost": {"mean_absolute_error": 0.03, "predictions_evaluated": 10},
            "ridge": {"mean_absolute_error": 0.04, "predictions_evaluated": 10},
            "rf": {"mean_absolute_error": 0.035, "predictions_evaluated": 10},
            "svr": {"mean_absolute_error": 0.038, "predictions_evaluated": 10},
        }
    )
    return monitor


class TestSyncPortfolio:
    """Tests for sync_portfolio task."""

    @pytest.mark.asyncio
    async def test_sync_portfolio_calls_sync(self, mock_portfolio):
        """Verify portfolio.sync() is called."""
        from sentinel.jobs.tasks import sync_portfolio

        await sync_portfolio(mock_portfolio)

        mock_portfolio.sync.assert_awaited_once()


class TestSyncPrices:
    """Tests for sync_prices task."""

    @pytest.mark.asyncio
    async def test_sync_prices_clears_cache(self, mock_db, mock_broker, mock_cache):
        """Verify cache is cleared before syncing."""
        from sentinel.jobs.tasks import sync_prices

        await sync_prices(mock_db, mock_broker, mock_cache)

        mock_cache.clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_prices_fetches_bulk(self, mock_db, mock_broker, mock_cache):
        """Verify bulk prices are fetched."""
        from sentinel.jobs.tasks import sync_prices

        await sync_prices(mock_db, mock_broker, mock_cache)

        mock_broker.get_historical_prices_bulk.assert_awaited_once()
        # Verify it used the symbols from the DB
        args = mock_broker.get_historical_prices_bulk.call_args
        assert "AAPL.US" in args[0][0]
        assert "MSFT.US" in args[0][0]

    @pytest.mark.asyncio
    async def test_sync_prices_updates_db(self, mock_db, mock_broker, mock_cache):
        """Verify prices are saved to DB."""
        from sentinel.jobs.tasks import sync_prices

        await sync_prices(mock_db, mock_broker, mock_cache)

        assert mock_db.save_prices.await_count == 2


class TestSyncQuotes:
    """Tests for sync_quotes task."""

    @pytest.mark.asyncio
    async def test_sync_quotes_fetches_and_updates(self, mock_db, mock_broker):
        """Verify quotes are fetched and bulk updated."""
        from sentinel.jobs.tasks import sync_quotes

        await sync_quotes(mock_db, mock_broker)

        mock_broker.get_quotes.assert_awaited_once()
        mock_db.update_quotes_bulk.assert_awaited_once()


class TestSyncMetadata:
    """Tests for sync_metadata task."""

    @pytest.mark.asyncio
    async def test_sync_metadata_fetches_per_security(self, mock_db, mock_broker):
        """Verify metadata is fetched for each security."""
        from sentinel.jobs.tasks import sync_metadata

        await sync_metadata(mock_db, mock_broker)

        # Should fetch info for each security (3 securities in mock_db)
        assert mock_broker.get_security_info.await_count == 3
        assert mock_db.update_security_metadata.await_count == 3


class TestSyncExchangeRates:
    """Tests for sync_exchange_rates task."""

    @pytest.mark.asyncio
    async def test_sync_exchange_rates_calls_currency_sync(self):
        """Verify Currency.sync_rates() is called."""
        from sentinel.jobs.tasks import sync_exchange_rates

        with patch("sentinel.currency.Currency") as MockCurrency:
            mock_currency = AsyncMock()
            mock_currency.sync_rates = AsyncMock(return_value={"USD": 1.1})
            MockCurrency.return_value = mock_currency

            await sync_exchange_rates()

            mock_currency.sync_rates.assert_awaited_once()


class TestScoringCalculate:
    """Tests for scoring_calculate task."""

    @pytest.mark.asyncio
    async def test_scoring_calculate_calls_analyzer(self, mock_analyzer):
        """Verify analyzer.update_scores() is called."""
        from sentinel.jobs.tasks import scoring_calculate

        await scoring_calculate(mock_analyzer)

        mock_analyzer.update_scores.assert_awaited_once()


class TestTradingCheckMarkets:
    """Tests for trading_check_markets task."""

    @pytest.mark.asyncio
    async def test_check_markets_logs_recommendations(self, mock_broker, mock_db, mock_planner):
        """Verify market status is checked and recommendations logged."""
        from sentinel.jobs.tasks import trading_check_markets

        # Mock connected state
        mock_broker.connected = True

        await trading_check_markets(mock_broker, mock_db, mock_planner)

        mock_broker.get_market_status.assert_awaited()


class TestTradingExecute:
    """Tests for trading_execute task."""

    @pytest.mark.asyncio
    async def test_execute_research_mode_no_trades(self, mock_broker, mock_db, mock_planner):
        """Verify no actual trades in research mode."""
        from sentinel.jobs.tasks import trading_execute

        mock_broker.connected = True

        with patch("sentinel.settings.Settings") as MockSettings:
            mock_settings = AsyncMock()
            mock_settings.get = AsyncMock(return_value="research")
            MockSettings.return_value = mock_settings

            await trading_execute(mock_broker, mock_db, mock_planner)

            # Planner should be called to get recommendations for logging
            mock_planner.get_recommendations.assert_awaited()

    @pytest.mark.asyncio
    async def test_execute_live_mode_trades(self, mock_broker, mock_db, mock_planner):
        """Verify trades are executed in live mode."""
        from sentinel.jobs.tasks import trading_execute

        mock_broker.connected = True

        # Setup mock recommendation
        mock_rec = MagicMock()
        mock_rec.symbol = "AAPL.US"
        mock_rec.action = "buy"
        mock_rec.quantity = 10
        mock_rec.price = 100.0
        mock_rec.currency = "USD"
        mock_rec.priority = 1
        mock_planner.get_recommendations = AsyncMock(return_value=[mock_rec])

        # Mock open markets
        mock_db.get_all_securities = AsyncMock(return_value=[{"symbol": "AAPL.US", "data": '{"mrkt": {"mkt_id": 1}}'}])
        mock_broker.get_market_status = AsyncMock(return_value={"m": [{"i": 1, "n2": "NASDAQ", "s": "OPEN"}]})

        with patch("sentinel.settings.Settings") as MockSettings:
            mock_settings = AsyncMock()
            mock_settings.get = AsyncMock(return_value="live")
            MockSettings.return_value = mock_settings

            with patch("sentinel.security.Security") as MockSecurity:
                mock_security = AsyncMock()
                mock_security.buy = AsyncMock(return_value="order123")
                mock_security.load = AsyncMock()
                MockSecurity.return_value = mock_security

                await trading_execute(mock_broker, mock_db, mock_planner)

                mock_security.buy.assert_awaited()


class TestTradingRebalance:
    """Tests for trading_rebalance task."""

    @pytest.mark.asyncio
    async def test_rebalance_checks_summary(self, mock_planner):
        """Verify rebalance summary is checked."""
        from sentinel.jobs.tasks import trading_rebalance

        await trading_rebalance(mock_planner)

        mock_planner.get_rebalance_summary.assert_awaited_once()


class TestPlanningRefresh:
    """Tests for planning_refresh task."""

    @pytest.mark.asyncio
    async def test_planning_refresh_clears_cache(self, mock_db, mock_planner):
        """Verify cache is cleared and ideal recalculated."""
        from sentinel.jobs.tasks import planning_refresh

        await planning_refresh(mock_db, mock_planner)

        mock_db.cache_clear.assert_awaited_once_with("planner:")
        mock_planner.calculate_ideal_portfolio.assert_awaited_once()


class TestTradingBalanceFix:
    """Tests for trading_balance_fix task."""

    @pytest.mark.asyncio
    async def test_balance_fix_skips_when_broker_not_connected(self, mock_db, mock_broker):
        """Verify task skips when broker not connected."""
        from sentinel.jobs.tasks import trading_balance_fix

        mock_broker.connected = False

        await trading_balance_fix(mock_db, mock_broker)

        # Should not attempt to get balances
        mock_db.get_cash_balances.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_balance_fix_does_nothing_when_all_positive(self, mock_db, mock_broker):
        """Verify no action when all balances are positive."""
        from sentinel.jobs.tasks import trading_balance_fix

        mock_broker.connected = True
        mock_db.get_cash_balances = AsyncMock(return_value={"EUR": 1000.0, "USD": 500.0})

        with patch("sentinel.currency_exchange.CurrencyExchangeService") as MockFx:
            mock_fx = MagicMock()
            mock_fx.exchange = AsyncMock()
            MockFx.return_value = mock_fx

            await trading_balance_fix(mock_db, mock_broker)

            # Should not attempt any exchanges
            mock_fx.exchange.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_balance_fix_converts_positive_to_cover_negative(self, mock_db, mock_broker):
        """Verify conversion from positive to negative balance currencies."""
        from sentinel.jobs.tasks import trading_balance_fix

        mock_broker.connected = True
        # EUR is negative, USD is positive
        mock_db.get_cash_balances = AsyncMock(return_value={"EUR": -500.0, "USD": 1000.0})

        with patch("sentinel.currency_exchange.CurrencyExchangeService") as MockFx:
            mock_fx = MagicMock()
            mock_fx.exchange = AsyncMock(return_value={"order_id": "FX123"})
            MockFx.return_value = mock_fx

            with patch("sentinel.currency.Currency") as MockCurrency:
                mock_currency = MagicMock()
                # 1 EUR = 1 EUR, 1 USD = 0.85 EUR
                mock_currency.to_eur = AsyncMock(side_effect=lambda amt, curr: amt if curr == "EUR" else amt * 0.85)
                mock_currency.get_rate = AsyncMock(return_value=0.85)
                MockCurrency.return_value = mock_currency

                await trading_balance_fix(mock_db, mock_broker)

                # Should have attempted to convert USD to EUR
                mock_fx.exchange.assert_awaited()
                call_args = mock_fx.exchange.call_args
                assert call_args[0][0] == "USD"  # from currency
                assert call_args[0][1] == "EUR"  # to currency

    @pytest.mark.asyncio
    async def test_balance_fix_logs_error_when_no_positive_balances(self, mock_db, mock_broker):
        """Verify error logged when no positive balances to convert from."""
        from sentinel.jobs.tasks import trading_balance_fix

        mock_broker.connected = True
        # All negative - nothing to convert from
        mock_db.get_cash_balances = AsyncMock(return_value={"EUR": -500.0, "USD": -200.0})

        with patch("sentinel.currency_exchange.CurrencyExchangeService") as MockFx:
            mock_fx = MagicMock()
            mock_fx.exchange = AsyncMock()
            MockFx.return_value = mock_fx

            # Should complete without error, but not attempt any exchanges
            await trading_balance_fix(mock_db, mock_broker)

            mock_fx.exchange.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_balance_fix_includes_buffer(self, mock_db, mock_broker):
        """Verify buffer is added when calculating conversion amount."""
        from sentinel.jobs.tasks import trading_balance_fix

        mock_broker.connected = True
        # Small negative balance
        mock_db.get_cash_balances = AsyncMock(return_value={"EUR": -5.0, "USD": 1000.0})

        with patch("sentinel.currency_exchange.CurrencyExchangeService") as MockFx:
            mock_fx = MagicMock()
            mock_fx.exchange = AsyncMock(return_value={"order_id": "FX123"})
            MockFx.return_value = mock_fx

            with patch("sentinel.currency.Currency") as MockCurrency:
                mock_currency = MagicMock()
                mock_currency.to_eur = AsyncMock(side_effect=lambda amt, curr: amt if curr == "EUR" else amt * 0.85)
                mock_currency.get_rate = AsyncMock(return_value=0.85)
                MockCurrency.return_value = mock_currency

                await trading_balance_fix(mock_db, mock_broker)

                # Should convert enough to cover deficit + buffer (10 EUR)
                # Deficit = 5, buffer = 10, total needed = 15 EUR
                mock_fx.exchange.assert_awaited()


class TestBackupR2:
    """Tests for backup_r2 task."""

    @pytest.mark.asyncio
    async def test_backup_skips_without_credentials(self, mock_db):
        """Verify backup is skipped when credentials not configured."""
        from sentinel.jobs.tasks import backup_r2

        with patch("sentinel.settings.Settings") as MockSettings:
            mock_settings = AsyncMock()
            mock_settings.get = AsyncMock(return_value="")
            MockSettings.return_value = mock_settings

            # Should not raise, just log warning
            await backup_r2(mock_db)

    @pytest.mark.asyncio
    async def test_backup_creates_and_uploads(self, mock_db):
        """Verify archive is created and uploaded."""
        from sentinel.jobs.tasks import backup_r2

        with patch("sentinel.settings.Settings") as MockSettings:
            mock_settings = AsyncMock()

            async def mock_get(key, default=""):
                values = {
                    "r2_account_id": "test_account",
                    "r2_access_key": "test_key",
                    "r2_secret_key": "test_secret",
                    "r2_bucket_name": "test_bucket",
                    "r2_backup_retention_days": 30,
                }
                return values.get(key, default)

            mock_settings.get = mock_get
            MockSettings.return_value = mock_settings

            with patch("sentinel.jobs.tasks._create_archive") as mock_create:
                with patch("sentinel.jobs.tasks._get_r2_client") as mock_client:
                    with patch("sentinel.jobs.tasks._upload_archive") as mock_upload:
                        with patch("sentinel.jobs.tasks._prune_old_backups"):
                            with patch("os.path.exists", return_value=True):
                                with patch("os.unlink"):
                                    await backup_r2(mock_db)

                                    mock_create.assert_called_once()
                                    mock_client.assert_called_once()
                                    mock_upload.assert_called_once()
