"""Tests for the unified sync cycle job.

The sync cycle runs every 15 minutes and performs these steps:
1. Sync trades from Tradernet
2. Sync cash flows from Tradernet
3. Sync portfolio positions
4. Sync prices (market-aware)
5. Check trading conditions (P&L guardrails)
6. Get recommendation (holistic)
7. Execute trade (market-aware)
8. Update display
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestSyncCycle:
    """Test the main sync cycle orchestration."""

    @pytest.mark.asyncio
    async def test_runs_all_steps_in_order(self):
        """Test that sync cycle runs all steps in correct order."""
        from app.jobs.sync_cycle import run_sync_cycle

        call_order = []

        async def mock_sync_trades():
            call_order.append("sync_trades")

        async def mock_sync_cash_flows():
            call_order.append("sync_cash_flows")

        async def mock_sync_portfolio():
            call_order.append("sync_portfolio")

        async def mock_sync_prices():
            call_order.append("sync_prices")

        async def mock_check_and_rebalance():
            call_order.append("check_and_rebalance")

        async def mock_update_display():
            call_order.append("update_display")

        with (
            patch(
                "app.jobs.sync_cycle._step_sync_trades",
                new_callable=AsyncMock,
                side_effect=mock_sync_trades,
            ),
            patch(
                "app.jobs.sync_cycle._step_sync_cash_flows",
                new_callable=AsyncMock,
                side_effect=mock_sync_cash_flows,
            ),
            patch(
                "app.jobs.sync_cycle._step_sync_portfolio",
                new_callable=AsyncMock,
                side_effect=mock_sync_portfolio,
            ),
            patch(
                "app.jobs.emergency_rebalance.check_and_rebalance_immediately",
                new_callable=AsyncMock,
                side_effect=mock_check_and_rebalance,
            ),
            patch(
                "app.jobs.sync_cycle._step_sync_prices",
                new_callable=AsyncMock,
                side_effect=mock_sync_prices,
            ),
            patch(
                "app.jobs.sync_cycle._step_update_display",
                new_callable=AsyncMock,
                side_effect=mock_update_display,
            ),
        ):
            # Make file_lock work as async context manager
            mock_lock = AsyncMock()
            mock_lock.__aenter__ = AsyncMock()
            mock_lock.__aexit__ = AsyncMock()
            with patch("app.jobs.sync_cycle.file_lock", return_value=mock_lock):
                await run_sync_cycle()

        expected_order = [
            "sync_trades",
            "sync_cash_flows",
            "sync_portfolio",
            "check_and_rebalance",
            "sync_prices",
            "update_display",
        ]
        assert call_order == expected_order

    @pytest.mark.asyncio
    async def test_skips_trade_execution_when_halted(self):
        """Test that trade execution is skipped when P&L halt is triggered."""
        from app.jobs.sync_cycle import run_sync_cycle

        execute_called = False

        async def mock_execute_trade(rec):
            nonlocal execute_called
            execute_called = True

        async def mock_check_conditions():
            return False, {"status": "halted"}  # Trading halted

        with (
            patch("app.jobs.sync_cycle._step_sync_trades", new_callable=AsyncMock),
            patch("app.jobs.sync_cycle._step_sync_cash_flows", new_callable=AsyncMock),
            patch("app.jobs.sync_cycle._step_sync_portfolio", new_callable=AsyncMock),
            patch("app.jobs.sync_cycle._step_sync_prices", new_callable=AsyncMock),
            patch(
                "app.jobs.sync_cycle._step_check_trading_conditions",
                new_callable=AsyncMock,
                side_effect=mock_check_conditions,
            ),
            patch(
                "app.jobs.sync_cycle._step_get_recommendation", new_callable=AsyncMock
            ),
            patch(
                "app.jobs.sync_cycle._step_execute_trade",
                new_callable=AsyncMock,
                side_effect=mock_execute_trade,
            ),
            patch("app.jobs.sync_cycle._step_update_display", new_callable=AsyncMock),
            patch("app.jobs.sync_cycle.file_lock", new_callable=MagicMock),
        ):
            mock_lock = AsyncMock()
            mock_lock.__aenter__ = AsyncMock()
            mock_lock.__aexit__ = AsyncMock()
            with patch("app.jobs.sync_cycle.file_lock", return_value=mock_lock):
                await run_sync_cycle()

        assert execute_called is False


class TestStepSyncPrices:
    """Test the market-aware price sync step."""

    @pytest.mark.asyncio
    async def test_only_fetches_prices_for_open_markets(self):
        """Test that prices are only fetched for stocks with open markets."""
        from app.jobs.sync_cycle import _step_sync_prices

        stock_eu = MagicMock()
        stock_eu.symbol = "SAP.DE"
        stock_eu.yahoo_symbol = "SAP.DE"
        stock_eu.fullExchangeName = "XETR"

        stock_us = MagicMock()
        stock_us.symbol = "AAPL.US"
        stock_us.yahoo_symbol = "AAPL"
        stock_us.fullExchangeName = "NYSE"

        stock_asia = MagicMock()
        stock_asia.symbol = "9988.HK"
        stock_asia.yahoo_symbol = "9988.HK"
        stock_asia.fullExchangeName = "XHKG"

        stocks = [stock_eu, stock_us, stock_asia]
        fetched_symbols = []

        def mock_get_batch_quotes(symbol_map):
            fetched_symbols.extend(symbol_map.keys())
            return {s: 100.0 for s in symbol_map.keys()}

        with (
            patch(
                "app.jobs.sync_cycle.get_open_markets",
                return_value=["XETR"],  # Only XETR open
            ),
            patch(
                "app.jobs.sync_cycle.group_stocks_by_exchange",
                return_value={
                    "XETR": [stock_eu],
                    "NYSE": [stock_us],
                    "XHKG": [stock_asia],
                },
            ),
            patch("app.jobs.sync_cycle._get_active_stocks", return_value=stocks),
            patch(
                "app.jobs.sync_cycle.yahoo.get_batch_quotes",
                side_effect=mock_get_batch_quotes,
            ),
            patch(
                "app.jobs.sync_cycle._update_position_prices", new_callable=AsyncMock
            ),
        ):
            await _step_sync_prices()

        # Only EU stocks should be fetched
        assert "SAP.DE" in fetched_symbols
        assert "AAPL.US" not in fetched_symbols
        assert "9988.HK" not in fetched_symbols

    @pytest.mark.asyncio
    async def test_skips_all_when_no_markets_open(self):
        """Test that no prices are fetched when all markets are closed."""
        from app.jobs.sync_cycle import _step_sync_prices

        fetch_called = False

        def mock_get_batch_quotes(symbol_map):
            nonlocal fetch_called
            fetch_called = True
            return {}

        with (
            patch("app.jobs.sync_cycle.get_open_markets", return_value=[]),
            patch("app.jobs.sync_cycle._get_active_stocks", return_value=[]),
            patch(
                "app.jobs.sync_cycle.yahoo.get_batch_quotes",
                side_effect=mock_get_batch_quotes,
            ),
        ):
            await _step_sync_prices()

        assert fetch_called is False


# NOTE: TestStepExecuteTrade tests are obsolete - trade execution was moved
# to event_based_trading.py. The _step_execute_trade function still exists
# but is not called from the sync cycle anymore.
@pytest.mark.skip(
    reason="Trade execution moved to event_based_trading - these tests are obsolete"
)
class TestStepExecuteTrade:
    """Test the market-aware trade execution step."""

    @pytest.mark.asyncio
    async def test_skips_buy_order_when_strict_market_closed(self):
        """Test that BUY order is skipped when strict market hours exchange is closed."""
        from app.jobs.sync_cycle import _step_execute_trade

        recommendation = MagicMock()
        recommendation.symbol = "9988.HK"
        recommendation.side = "BUY"

        # Mock stock with strict market hours exchange (ASIA)
        mock_stock = MagicMock()
        mock_stock.fullExchangeName = "XHKG"

        execute_called = False

        async def mock_execute():
            nonlocal execute_called
            execute_called = True

        with (
            patch(
                "app.jobs.sync_cycle.should_check_market_hours",
                return_value=True,  # Strict market hours exchange requires check
            ),
            patch(
                "app.jobs.sync_cycle.is_market_open",
                return_value=False,  # Market closed
            ),
            patch(
                "app.jobs.sync_cycle._get_stock_by_symbol",
                new_callable=AsyncMock,
                return_value=mock_stock,
            ),
            patch(
                "app.jobs.sync_cycle._execute_trade_order",
                new_callable=AsyncMock,
                side_effect=mock_execute,
            ),
        ):
            result = await _step_execute_trade(recommendation)

        assert execute_called is False
        assert result["status"] == "skipped"
        assert "market closed" in result["reason"].lower()

    @pytest.mark.asyncio
    async def test_allows_buy_order_when_flexible_market_closed(self):
        """Test that BUY order is allowed when flexible hours market is closed."""
        from app.jobs.sync_cycle import _step_execute_trade

        recommendation = MagicMock()
        recommendation.symbol = "AAPL.US"
        recommendation.side = "BUY"

        # Mock stock with flexible hours exchange (US)
        mock_stock = MagicMock()
        mock_stock.fullExchangeName = "NYSE"

        execute_called = False

        async def mock_execute():
            nonlocal execute_called
            execute_called = True
            return {"status": "success"}

        with (
            patch(
                "app.jobs.sync_cycle.should_check_market_hours",
                return_value=False,  # Flexible hours market doesn't require check for BUY
            ),
            patch(
                "app.jobs.sync_cycle._get_stock_by_symbol",
                new_callable=AsyncMock,
                return_value=mock_stock,
            ),
            patch(
                "app.jobs.sync_cycle._execute_trade_order",
                new_callable=AsyncMock,
                side_effect=mock_execute,
            ),
        ):
            result = await _step_execute_trade(recommendation)

        assert execute_called is True
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_skips_sell_order_when_market_closed(self):
        """Test that SELL order is skipped when market is closed (all markets)."""
        from app.jobs.sync_cycle import _step_execute_trade

        recommendation = MagicMock()
        recommendation.symbol = "AAPL.US"
        recommendation.side = "SELL"

        # Mock stock with flexible hours exchange (US)
        mock_stock = MagicMock()
        mock_stock.fullExchangeName = "NYSE"

        execute_called = False

        async def mock_execute():
            nonlocal execute_called
            execute_called = True

        with (
            patch(
                "app.jobs.sync_cycle.should_check_market_hours",
                return_value=True,  # SELL orders always require check
            ),
            patch(
                "app.jobs.sync_cycle.is_market_open",
                return_value=False,  # Market closed
            ),
            patch(
                "app.jobs.sync_cycle._get_stock_by_symbol",
                new_callable=AsyncMock,
                return_value=mock_stock,
            ),
            patch(
                "app.jobs.sync_cycle._execute_trade_order",
                new_callable=AsyncMock,
                side_effect=mock_execute,
            ),
        ):
            result = await _step_execute_trade(recommendation)

        assert execute_called is False
        assert result["status"] == "skipped"
        assert "market closed" in result["reason"].lower()

    @pytest.mark.asyncio
    async def test_executes_trade_when_market_open(self):
        """Test that trade is executed when stock's market is open."""
        from app.jobs.sync_cycle import _step_execute_trade

        recommendation = MagicMock()
        recommendation.symbol = "AAPL.US"
        recommendation.side = "BUY"
        recommendation.quantity = 10
        recommendation.estimated_price = 150.0

        mock_stock = MagicMock()
        mock_stock.fullExchangeName = "NYSE"

        with (
            patch(
                "app.jobs.sync_cycle.should_check_market_hours",
                return_value=False,  # BUY on flexible hours market doesn't require check
            ),
            patch(
                "app.jobs.sync_cycle._get_stock_by_symbol",
                new_callable=AsyncMock,
                return_value=mock_stock,
            ),
            patch(
                "app.jobs.sync_cycle._execute_trade_order",
                new_callable=AsyncMock,
                return_value={"status": "success"},
            ),
        ):
            result = await _step_execute_trade(recommendation)

        assert result["status"] == "success"


class TestStepGetRecommendation:
    """Test the holistic recommendation step."""

    @pytest.mark.asyncio
    async def test_considers_all_markets(self):
        """Test that recommendations consider all markets, not just open ones."""
        from app.jobs.sync_cycle import _step_get_recommendation

        async def mock_get_recommendations():
            # The planner should receive all stocks (not filtered by market)
            return MagicMock(symbol="SAP.DE", side="BUY")

        with (
            patch(
                "app.jobs.sync_cycle._get_holistic_recommendation",
                new_callable=AsyncMock,
                side_effect=mock_get_recommendations,
            ),
        ):
            result = await _step_get_recommendation()

        # Should return a recommendation
        assert result is not None
        assert result.symbol == "SAP.DE"


class TestStepUpdateDisplay:
    """Test the display update step."""

    @pytest.mark.asyncio
    async def test_updates_ticker_text(self):
        """Test that ticker text is updated."""
        from app.jobs.sync_cycle import _step_update_display

        set_text_called = False

        def mock_set_text(text):
            nonlocal set_text_called
            set_text_called = True

        mock_ticker_service = MagicMock()
        mock_ticker_service.generate_ticker_text = AsyncMock(
            return_value="Portfolio EUR10,000 | BUY AAPL EUR500"
        )

        with (
            patch("app.repositories.PortfolioRepository"),
            patch("app.repositories.PositionRepository"),
            patch("app.repositories.SecurityRepository"),
            patch("app.repositories.SettingsRepository"),
            patch("app.repositories.AllocationRepository"),
            patch("app.infrastructure.external.tradernet.get_tradernet_client"),
            patch(
                "app.domain.services.ticker_content_service.TickerContentService",
                return_value=mock_ticker_service,
            ),
            patch(
                "app.infrastructure.hardware.display_service.set_text",
                side_effect=mock_set_text,
            ),
        ):
            await _step_update_display()

        assert set_text_called is True
