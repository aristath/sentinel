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
    db.invalidate_planner_cache = AsyncMock(return_value=5)
    db.get_planner_state = AsyncMock(return_value=None)
    return db


@pytest.fixture
def mock_broker():
    """Mock broker for testing."""
    broker = AsyncMock()
    broker.connected = True
    broker.has_pending_orders = AsyncMock(return_value=False)
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
    broker.get_security_metadata = AsyncMock(
        return_value={
            "geography": "US",
            "industry": "Computers, Phones & Household Electronics",
            "instr_kind_c": 1,
            "mkt_short_code": "FIX",
            "name": "Mock Inc.",
        }
    )
    broker.get_market_status = AsyncMock(return_value={"m": [{"i": 1, "n2": "NASDAQ", "s": "OPEN"}]})
    broker.get_trades_history = AsyncMock(return_value=[])
    return broker


@pytest.fixture
def mock_cache():
    """Mock cache for testing."""
    cache = MagicMock()
    cache.clear = MagicMock(return_value=10)
    return cache


@pytest.fixture
def mock_planner():
    """Mock planner for testing."""
    planner = AsyncMock()
    planner.get_recommendations = AsyncMock(return_value=[])
    planner.get_rebalance_summary = AsyncMock(
        return_value={
            "needs_rebalance": False,
            "total_deviation": 0.05,
            "status": "aligned",
        }
    )
    planner.calculate_ideal_portfolio = AsyncMock(return_value={"AAPL.US": 0.5})
    return planner


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

    @pytest.fixture(autouse=True)
    def _skip_pacing_sleep(self):
        """Patch the per-iteration sleep so test runs aren't slow.

        The pacing-specific test re-patches it to assert call counts.
        """
        with patch("sentinel.jobs.tasks.asyncio.sleep", new_callable=AsyncMock):
            yield

    @pytest.mark.asyncio
    async def test_sync_metadata_fetches_per_security(self, mock_db, mock_broker):
        """Verify metadata is fetched for each security."""
        from sentinel.jobs.tasks import sync_metadata

        await sync_metadata(mock_db, mock_broker)

        # Should fetch info for each security (3 securities in mock_db)
        assert mock_broker.get_security_info.await_count == 3
        assert mock_broker.get_security_metadata.await_count == 3
        assert mock_db.update_security_metadata.await_count == 3

    @pytest.mark.asyncio
    async def test_sync_metadata_passes_geography_and_industry(self, mock_db, mock_broker):
        """sync_metadata forwards geography/industry from broker to DB."""
        from sentinel.jobs.tasks import sync_metadata

        await sync_metadata(mock_db, mock_broker)

        # Every DB update should include the broker-provided geo/industry
        for call in mock_db.update_security_metadata.await_args_list:
            kwargs = call.kwargs
            assert kwargs["geography"] == "US"
            assert kwargs["industry"] == "Computers, Phones & Household Electronics"

    @pytest.mark.asyncio
    async def test_sync_metadata_persists_instr_kind_c(self, mock_db, mock_broker):
        """instr_kind_c is a first-class column so asset-class grouping works
        in SQL without parsing JSON. The sync job must persist it."""
        from sentinel.jobs.tasks import sync_metadata

        await sync_metadata(mock_db, mock_broker)

        for call in mock_db.update_security_metadata.await_args_list:
            assert call.kwargs["instr_kind_c"] == 1  # from mock_broker

    @pytest.mark.asyncio
    async def test_sync_metadata_blanks_geo_industry_for_etfs(self, mock_db, mock_broker):
        """ETFs (instr_kind_c == 7) get blank geography/industry so they fall out of macro buckets."""
        from sentinel.jobs.tasks import sync_metadata

        mock_broker.get_security_metadata = AsyncMock(
            return_value={
                "geography": "IE",
                "industry": "Equity ETFs",
                "instr_kind_c": 7,
                "mkt_short_code": "EU",
                "name": "Vanguard FTSE All-World UCITS ETF",
            }
        )

        await sync_metadata(mock_db, mock_broker)

        for call in mock_db.update_security_metadata.await_args_list:
            assert call.kwargs["geography"] == ""
            assert call.kwargs["industry"] == ""

    @pytest.mark.asyncio
    async def test_sync_metadata_skips_geo_industry_when_broker_returns_none(self, mock_db, mock_broker):
        """If get_security_metadata returns None (ticker missing at broker), don't touch geo/industry."""
        from sentinel.jobs.tasks import sync_metadata

        mock_broker.get_security_metadata = AsyncMock(return_value=None)

        await sync_metadata(mock_db, mock_broker)

        for call in mock_db.update_security_metadata.await_args_list:
            assert "geography" not in call.kwargs
            assert "industry" not in call.kwargs

    @pytest.mark.asyncio
    async def test_sync_metadata_paces_calls_to_avoid_rate_limit(self, mock_db, mock_broker):
        """`getAllSecurities` is rate-limited — the sync loop must sleep between
        iterations at the configured pace to avoid a 429 mid-sync."""
        from sentinel.jobs import tasks

        # Re-patch sleep here so we can inspect the call args.
        with patch("sentinel.jobs.tasks.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await tasks.sync_metadata(mock_db, mock_broker)

            # One sleep per processed security (3 in the mock), each at the
            # configured pace.
            assert mock_sleep.await_count == 3
            for call in mock_sleep.await_args_list:
                assert call.args[0] == tasks.SYNC_METADATA_PACING_S

    @pytest.mark.asyncio
    async def test_sync_metadata_continues_when_one_ticker_fails(self, mock_db, mock_broker):
        """A single broker error must not abort the whole sync — other tickers still update."""
        from sentinel.jobs.tasks import sync_metadata

        # First ticker raises mid-iteration; second and third succeed normally.
        mock_broker.get_security_info = AsyncMock(
            side_effect=[
                RuntimeError("transient network error"),
                {"mrkt": {"mkt_id": 1}, "lot": 1},
                {"mrkt": {"mkt_id": 1}, "lot": 1},
            ]
        )

        await sync_metadata(mock_db, mock_broker)

        # First ticker raised before update; two remaining updates ran.
        assert mock_db.update_security_metadata.await_count == 2

    @pytest.mark.asyncio
    async def test_blank_geography_from_broker_does_not_overwrite_existing(self, mock_db, mock_broker):
        """If Tradernet ever renames `CntryOfRisk`, all non-ETF rows would return blank.
        We must NOT blank existing DB values in that case — better stale than wiped."""
        from sentinel.jobs.tasks import sync_metadata

        mock_broker.get_security_metadata = AsyncMock(
            return_value={
                "geography": "",  # simulates the API-rename case
                "industry": "Software & IT Services",
                "instr_kind_c": 1,  # NOT an ETF
                "mkt_short_code": "FIX",
                "name": "Some Stock",
            }
        )

        await sync_metadata(mock_db, mock_broker)

        for call in mock_db.update_security_metadata.await_args_list:
            assert "geography" not in call.kwargs  # preserved
            assert call.kwargs["industry"] == "Software & IT Services"  # still written

    @pytest.mark.asyncio
    async def test_blank_industry_from_broker_does_not_overwrite_existing(self, mock_db, mock_broker):
        """Same protection for the `sector_code` field being renamed/missing."""
        from sentinel.jobs.tasks import sync_metadata

        mock_broker.get_security_metadata = AsyncMock(
            return_value={
                "geography": "US",
                "industry": "",  # simulates the API-rename case
                "instr_kind_c": 1,
                "mkt_short_code": "FIX",
                "name": "Some Stock",
            }
        )

        await sync_metadata(mock_db, mock_broker)

        for call in mock_db.update_security_metadata.await_args_list:
            assert call.kwargs["geography"] == "US"
            assert "industry" not in call.kwargs

    @pytest.mark.asyncio
    async def test_etf_blanking_still_overrides_existing_values(self, mock_db, mock_broker):
        """Empty values from Tradernet are preserved, BUT ETFs (positive instr_kind_c==7
        signal) are still explicitly blanked — that signal is the authority."""
        from sentinel.jobs.tasks import sync_metadata

        mock_broker.get_security_metadata = AsyncMock(
            return_value={
                "geography": "IE",
                "industry": "Equity ETFs",
                "instr_kind_c": 7,
                "mkt_short_code": "EU",
                "name": "Vanguard FTSE All-World UCITS ETF",
            }
        )

        await sync_metadata(mock_db, mock_broker)

        for call in mock_db.update_security_metadata.await_args_list:
            assert call.kwargs["geography"] == ""
            assert call.kwargs["industry"] == ""


class TestDecayUserMultipliers:
    """The scheduled job that fades stored user_multipliers toward neutral.

    Replaces the read-time fade machinery — once a row's slider is older than
    `decay_interval_days`, one decay step is applied to the stored value and
    the timestamp moves forward.
    """

    @pytest.fixture
    def db_with_rows(self, mock_db):
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        old_iso = (now - timedelta(days=10)).isoformat()
        fresh_iso = (now - timedelta(days=3)).isoformat()
        # Simulate a small mixed roster: one due for decay, one too fresh,
        # one already at neutral, one off-the-charts old.
        rows = [
            {"symbol": "OLD.US", "user_multiplier": 0.7, "user_multiplier_updated_at": old_iso},
            {"symbol": "FRESH.US", "user_multiplier": 0.9, "user_multiplier_updated_at": fresh_iso},
            {"symbol": "NEUTRAL.US", "user_multiplier": 0.5, "user_multiplier_updated_at": old_iso},
            {"symbol": "NULL_TS.US", "user_multiplier": 0.8, "user_multiplier_updated_at": None},
        ]
        mock_db.get_all_securities = AsyncMock(return_value=rows)
        mock_db.set_user_multiplier = AsyncMock()
        return mock_db

    @pytest.fixture
    def mock_settings(self, mock_settings_factory=None):
        settings = AsyncMock()
        defaults = {
            "user_multiplier_decay_factor": 0.9,
            "user_multiplier_decay_interval_days": 7,
        }
        settings.get = AsyncMock(side_effect=lambda key, default=None: defaults.get(key, default))
        return settings

    @pytest.mark.asyncio
    async def test_old_rows_get_one_decay_step(self, db_with_rows, mock_settings):
        from sentinel.jobs.tasks import decay_user_multipliers

        await decay_user_multipliers(db_with_rows, mock_settings)

        # OLD.US (0.7, 10 days old) -> 0.5 + 0.2 * 0.9 = 0.68
        called_for = {c.args[0]: c.args[1] for c in db_with_rows.set_user_multiplier.await_args_list}
        assert "OLD.US" in called_for
        assert abs(called_for["OLD.US"] - 0.68) < 1e-9

    @pytest.mark.asyncio
    async def test_fresh_rows_are_skipped(self, db_with_rows, mock_settings):
        from sentinel.jobs.tasks import decay_user_multipliers

        await decay_user_multipliers(db_with_rows, mock_settings)

        called_symbols = {c.args[0] for c in db_with_rows.set_user_multiplier.await_args_list}
        assert "FRESH.US" not in called_symbols

    @pytest.mark.asyncio
    async def test_neutral_rows_are_skipped(self, db_with_rows, mock_settings):
        """A value already at 0.5 has nothing left to fade — no write needed."""
        from sentinel.jobs.tasks import decay_user_multipliers

        await decay_user_multipliers(db_with_rows, mock_settings)

        called_symbols = {c.args[0] for c in db_with_rows.set_user_multiplier.await_args_list}
        assert "NEUTRAL.US" not in called_symbols

    @pytest.mark.asyncio
    async def test_rows_with_no_timestamp_are_skipped(self, db_with_rows, mock_settings):
        """If we can't tell how long ago the value was set, leave it alone —
        better than randomly decaying a value the user set 30 seconds ago."""
        from sentinel.jobs.tasks import decay_user_multipliers

        await decay_user_multipliers(db_with_rows, mock_settings)

        called_symbols = {c.args[0] for c in db_with_rows.set_user_multiplier.await_args_list}
        assert "NULL_TS.US" not in called_symbols

    @pytest.mark.asyncio
    async def test_logs_count_of_decayed_rows(self, db_with_rows, mock_settings, caplog):
        import logging

        from sentinel.jobs.tasks import decay_user_multipliers

        caplog.set_level(logging.INFO)
        await decay_user_multipliers(db_with_rows, mock_settings)

        assert any("decayed" in r.message.lower() for r in caplog.records)


class TestSyncBenchmarks:
    """Verify `sync:benchmarks` refreshes the index roster from Tradernet
    AND syncs daily prices. Both must happen in one job — benchmarks are
    useless without prices."""

    @pytest.fixture(autouse=True)
    def _skip_pacing_sleep(self):
        with patch("sentinel.jobs.tasks.asyncio.sleep", new_callable=AsyncMock):
            yield

    @pytest.fixture
    def mock_broker_indices(self, mock_broker):
        mock_broker.get_all_indices = AsyncMock(
            return_value=[
                {
                    "symbol": "SP500.IDX",
                    "name": "S&P 500",
                    "mkt_short_code": "FIX",
                    "instr_kind_c": 1,
                    "currency": "USD",
                },
                {"symbol": "DAX.IDX", "name": "DAX", "mkt_short_code": "EU", "instr_kind_c": 1, "currency": "EUR"},
            ]
        )
        mock_broker.get_historical_prices_bulk = AsyncMock(
            return_value={
                "SP500.IDX": [{"date": "2025-01-02", "close": 4720.0}],
                "DAX.IDX": [{"date": "2025-01-02", "close": 19800.0}],
            }
        )
        return mock_broker

    @pytest.fixture
    def mock_db_benchmarks(self, mock_db):
        mock_db.upsert_benchmark = AsyncMock()
        mock_db.save_benchmark_prices = AsyncMock()
        mock_db.get_benchmarks = AsyncMock(
            return_value=[
                {"symbol": "SP500.IDX"},
                {"symbol": "DAX.IDX"},
            ]
        )
        return mock_db

    @pytest.mark.asyncio
    async def test_upserts_each_index_returned_from_broker(self, mock_db_benchmarks, mock_broker_indices):
        from sentinel.jobs.tasks import sync_benchmarks

        await sync_benchmarks(mock_db_benchmarks, mock_broker_indices)

        assert mock_db_benchmarks.upsert_benchmark.await_count == 2
        symbols = {call.args[0] for call in mock_db_benchmarks.upsert_benchmark.await_args_list}
        assert symbols == {"SP500.IDX", "DAX.IDX"}

    @pytest.mark.asyncio
    async def test_saves_prices_for_each_benchmark(self, mock_db_benchmarks, mock_broker_indices):
        from sentinel.jobs.tasks import sync_benchmarks

        await sync_benchmarks(mock_db_benchmarks, mock_broker_indices)

        assert mock_db_benchmarks.save_benchmark_prices.await_count == 2
        saved_symbols = {call.args[0] for call in mock_db_benchmarks.save_benchmark_prices.await_args_list}
        assert saved_symbols == {"SP500.IDX", "DAX.IDX"}

    @pytest.mark.asyncio
    async def test_broker_offline_skips_metadata_refresh_but_syncs_known_prices(
        self, mock_db_benchmarks, mock_broker_indices
    ):
        """If the roster fetch fails, fall back to syncing prices for whatever
        benchmarks we already have in the DB — partial progress is still useful."""
        from sentinel.jobs.tasks import sync_benchmarks

        mock_broker_indices.get_all_indices = AsyncMock(return_value=None)

        await sync_benchmarks(mock_db_benchmarks, mock_broker_indices)

        mock_db_benchmarks.upsert_benchmark.assert_not_awaited()
        # Existing roster (2 entries) still gets price-synced.
        assert mock_db_benchmarks.save_benchmark_prices.await_count == 2

    @pytest.mark.asyncio
    async def test_no_benchmarks_at_all_is_a_no_op(self, mock_db, mock_broker):
        from sentinel.jobs.tasks import sync_benchmarks

        mock_broker.get_all_indices = AsyncMock(return_value=[])
        mock_db.get_benchmarks = AsyncMock(return_value=[])
        mock_db.upsert_benchmark = AsyncMock()
        mock_db.save_benchmark_prices = AsyncMock()
        mock_broker.get_historical_prices_bulk = AsyncMock(return_value={})

        await sync_benchmarks(mock_db, mock_broker)

        mock_db.upsert_benchmark.assert_not_awaited()
        mock_db.save_benchmark_prices.assert_not_awaited()


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
    async def test_execute_research_mode_no_trades(self, mock_broker, mock_db, mock_planner, mock_portfolio):
        """Verify no actual trades in research mode."""
        from sentinel.jobs.tasks import trading_execute

        mock_broker.connected = True

        with patch("sentinel.settings.Settings") as MockSettings:
            mock_settings = AsyncMock()
            mock_settings.get = AsyncMock(return_value="research")
            MockSettings.return_value = mock_settings
            mock_db.get_all_securities = AsyncMock(
                return_value=[{"symbol": "AAPL.US", "data": '{"mrkt": {"mkt_id": 1}}'}]
            )

            await trading_execute(mock_broker, mock_db, mock_planner, mock_portfolio)

            # Planner should be called to get recommendations for logging
            mock_planner.get_recommendations.assert_awaited()
            # Pending-orders check is a live-mode concern; in research mode
            # we short-circuit before reaching it.
            mock_broker.has_pending_orders.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_execute_live_mode_trades(self, mock_broker, mock_db, mock_planner, mock_portfolio):
        """Verify trades are executed in live mode."""
        from sentinel.jobs.tasks import trading_execute

        mock_broker.connected = True

        from sentinel.planner.models import TradeRecommendation

        mock_rec = TradeRecommendation(
            symbol="AAPL.US",
            action="buy",
            current_allocation=0.0,
            target_allocation=0.1,
            allocation_delta=0.1,
            current_value_eur=0.0,
            target_value_eur=1000.0,
            value_delta_eur=1000.0,
            quantity=10,
            price=100.0,
            currency="USD",
            lot_size=1,
            contrarian_score=0.8,
            priority=1.0,
            reason="test",
            execution_rank=1,
        )
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

                await trading_execute(mock_broker, mock_db, mock_planner, mock_portfolio)

                mock_security.buy.assert_awaited()
                mock_portfolio.sync.assert_awaited_once()
                mock_db.cache_clear.assert_awaited_with("quotes:")
                mock_db.invalidate_planner_cache.assert_awaited()
                mock_db.set_planner_state.assert_awaited_once()
                mock_planner.get_recommendations.assert_awaited_once_with(
                    eligible_symbols={"AAPL.US"},
                    track_fallback_state=True,
                )

    @pytest.mark.asyncio
    async def test_execute_submits_only_first_ranked_trade(self, mock_broker, mock_db, mock_planner, mock_portfolio):
        from sentinel.jobs.tasks import trading_execute
        from sentinel.planner.models import TradeRecommendation

        def recommendation(symbol, action, rank):
            return TradeRecommendation(
                symbol=symbol,
                action=action,
                current_allocation=0.1,
                target_allocation=0.2,
                allocation_delta=0.1,
                current_value_eur=1000.0,
                target_value_eur=2000.0,
                value_delta_eur=1000.0 if action == "buy" else -1000.0,
                quantity=10,
                price=100.0,
                currency="USD",
                lot_size=1,
                contrarian_score=0.8,
                priority=1.0,
                reason="test",
                execution_rank=rank,
            )

        first = recommendation("SELL.US", "sell", 1)
        second = recommendation("BUY.US", "buy", 2)
        mock_planner.get_recommendations = AsyncMock(return_value=[second, first])
        mock_db.get_all_securities = AsyncMock(
            return_value=[
                {"symbol": "SELL.US", "data": '{"mrkt": {"mkt_id": 1}}'},
                {"symbol": "BUY.US", "data": '{"mrkt": {"mkt_id": 1}}'},
            ]
        )

        with patch("sentinel.settings.Settings") as MockSettings:
            MockSettings.return_value.get = AsyncMock(return_value="live")
            with patch("sentinel.security.Security") as MockSecurity:
                security = AsyncMock()
                security.sell = AsyncMock(return_value="sell-order")
                security.buy = AsyncMock(return_value="buy-order")
                MockSecurity.return_value = security

                await trading_execute(mock_broker, mock_db, mock_planner, mock_portfolio)

        security.sell.assert_awaited_once_with(10)
        security.buy.assert_not_awaited()
        assert mock_db.set_planner_state.await_args.args[1]["order_id"] == "sell-order"

    @pytest.mark.asyncio
    async def test_execute_skips_when_orders_pending(self, mock_broker, mock_db, mock_planner, mock_portfolio):
        """No new orders are submitted while previous orders are still outstanding."""
        from sentinel.jobs.tasks import trading_execute

        mock_broker.connected = True
        mock_broker.has_pending_orders = AsyncMock(return_value=True)

        mock_rec = MagicMock()
        mock_rec.symbol = "AAPL.US"
        mock_rec.action = "buy"
        mock_rec.quantity = 10
        mock_rec.price = 100.0
        mock_rec.currency = "USD"
        mock_rec.priority = 1
        mock_planner.get_recommendations = AsyncMock(return_value=[mock_rec])

        with patch("sentinel.settings.Settings") as MockSettings:
            mock_settings = AsyncMock()
            mock_settings.get = AsyncMock(return_value="live")
            MockSettings.return_value = mock_settings

            with patch("sentinel.security.Security") as MockSecurity:
                mock_security = AsyncMock()
                mock_security.buy = AsyncMock(return_value="order123")
                mock_security.load = AsyncMock()
                MockSecurity.return_value = mock_security

                await trading_execute(mock_broker, mock_db, mock_planner, mock_portfolio)

                mock_broker.has_pending_orders.assert_awaited_once()
                mock_security.buy.assert_not_awaited()
                # Recommendations shouldn't even be fetched when we're skipping.
                mock_planner.get_recommendations.assert_not_awaited()
                # Each cycle still refreshes broker-backed state before deciding
                # whether another transaction can be submitted.
                mock_portfolio.sync.assert_awaited_once()


class TestTradingRebalance:
    """Tests for trading_rebalance task."""

    @pytest.mark.asyncio
    async def test_rebalance_checks_summary(self, mock_planner):
        """Verify rebalance summary is checked."""
        from sentinel.jobs.tasks import trading_rebalance

        await trading_rebalance(mock_planner)

        mock_planner.get_rebalance_summary.assert_awaited_once()
        mock_planner.get_recommendations.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rebalance_accepts_planner_status_shape(self, mock_planner):
        """Planner summary status is enough to trigger recommendation logging."""
        from sentinel.jobs.tasks import trading_rebalance

        mock_planner.get_rebalance_summary.return_value = {
            "total_deviation": 0.12,
            "max_deviation": 0.08,
            "status": "needs_rebalance",
        }

        await trading_rebalance(mock_planner)

        mock_planner.get_recommendations.assert_awaited_once()


class TestPlanningRefresh:
    """Tests for planning_refresh task."""

    @pytest.mark.asyncio
    async def test_planning_refresh_syncs_trades_then_refreshes(self, mock_db, mock_planner, mock_broker):
        """Verify trades are synced before planner cache refresh."""
        from sentinel.jobs.tasks import planning_refresh

        reconcile_result = MagicMock()
        reconcile_result.changed = False
        with (
            patch("sentinel.jobs.tasks.sync_trades", new=AsyncMock()) as mock_sync_trades,
            patch(
                "sentinel.universe.reconcile_universe_from_freedom24_default_list",
                new=AsyncMock(return_value=reconcile_result),
            ) as mock_reconcile,
        ):
            await planning_refresh(mock_db, mock_planner, mock_broker)

        mock_sync_trades.assert_awaited_once_with(mock_db, mock_broker)
        mock_reconcile.assert_awaited_once_with(mock_db, mock_broker)
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


class TestParseBrokerTimestamp:
    """Tests for _parse_broker_timestamp covering the broker date formats."""

    def test_iso_with_t_and_milliseconds_preserves_time(self):
        """The current Tradernet/Freedom24 ISO form keeps its intraday time."""
        from datetime import datetime

        from sentinel.jobs.tasks import _parse_broker_timestamp

        ts = _parse_broker_timestamp("2026-06-03T11:46:14.640")
        # Round-trips back to the same wall-clock instant (not midnight).
        assert datetime.fromtimestamp(ts) == datetime(2026, 6, 3, 11, 46, 14)

    def test_space_separated_form(self):
        from datetime import datetime

        from sentinel.jobs.tasks import _parse_broker_timestamp

        ts = _parse_broker_timestamp("2026-06-03 11:46:14")
        assert datetime.fromtimestamp(ts) == datetime(2026, 6, 3, 11, 46, 14)

    def test_date_only_form(self):
        from datetime import datetime

        from sentinel.jobs.tasks import _parse_broker_timestamp

        ts = _parse_broker_timestamp("2026-06-03")
        assert datetime.fromtimestamp(ts) == datetime(2026, 6, 3, 0, 0, 0)

    def test_iso_with_trailing_z_is_utc(self):
        from datetime import datetime, timezone

        from sentinel.jobs.tasks import _parse_broker_timestamp

        ts = _parse_broker_timestamp("2026-06-03T11:46:14.640Z")
        assert datetime.fromtimestamp(ts, tz=timezone.utc).replace(microsecond=0) == datetime(
            2026, 6, 3, 11, 46, 14, tzinfo=timezone.utc
        )

    def test_garbage_with_valid_date_prefix_falls_back_to_date(self):
        from datetime import datetime

        from sentinel.jobs.tasks import _parse_broker_timestamp

        ts = _parse_broker_timestamp("2026-06-03 not-a-time")
        assert datetime.fromtimestamp(ts) == datetime(2026, 6, 3, 0, 0, 0)

    def test_empty_or_invalid_returns_zero(self):
        from sentinel.jobs.tasks import _parse_broker_timestamp

        assert _parse_broker_timestamp("") == 0
        assert _parse_broker_timestamp("   ") == 0
        assert _parse_broker_timestamp("nonsense") == 0
        assert _parse_broker_timestamp(None) == 0  # type: ignore[arg-type]
