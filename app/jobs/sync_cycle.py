"""Unified sync cycle job.

This job runs every 15 minutes and performs these steps:
1. Sync trades from Tradernet
2. Sync cash flows from Tradernet
3. Sync portfolio positions
4. Sync prices (market-aware - only for open markets)
5. Check trading conditions (P&L guardrails)
6. Get recommendation (holistic - all markets)
7. Execute trade (market-aware - only if stock's market is open)
8. Update display
"""

import logging
from typing import Any, Optional

from app.infrastructure.events import SystemEvent, emit
from app.infrastructure.external import yahoo_finance as yahoo
from app.infrastructure.hardware.display_service import (
    clear_processing,
    set_error,
    set_next_actions,
    set_processing,
)
from app.infrastructure.locking import file_lock
from app.infrastructure.market_hours import (
    get_open_markets,
    group_stocks_by_exchange,
    is_market_open,
)

logger = logging.getLogger(__name__)


async def run_sync_cycle():
    """
    Run the unified sync cycle.

    This is the main entry point called by the scheduler every 15 minutes.
    """
    async with file_lock("sync_cycle", timeout=600.0):
        await _run_sync_cycle_internal()


async def _run_sync_cycle_internal():
    """Internal sync cycle implementation."""
    logger.info("Starting sync cycle...")

    emit(SystemEvent.SYNC_START)

    try:
        # Step 1: Sync trades
        set_processing("SYNCING TRADES...")
        await _step_sync_trades()

        # Step 2: Sync cash flows
        set_processing("SYNCING CASH FLOWS...")
        await _step_sync_cash_flows()

        # Step 3: Sync portfolio
        set_processing("SYNCING PORTFOLIO...")
        await _step_sync_portfolio()

        # Step 4: Sync prices (market-aware)
        set_processing("SYNCING PRICES...")
        await _step_sync_prices()

        # Step 5: Check trading conditions
        set_processing("CHECKING CONDITIONS...")
        can_trade, pnl_status = await _step_check_trading_conditions()

        if not can_trade:
            logger.warning(f"Trading halted: {pnl_status.get('reason', 'unknown')}")
            await _step_update_display()
            emit(SystemEvent.SYNC_COMPLETE)
            return

        # Step 6: Get recommendation (holistic)
        set_processing("GETTING RECOMMENDATION...")
        recommendation = await _step_get_recommendation()

        # Step 7: Execute trade (market-aware)
        if recommendation:
            set_processing(
                f"EXECUTING {recommendation.side} {recommendation.symbol}..."
            )
            result = await _step_execute_trade(recommendation)
            if result.get("status") == "success":
                logger.info(
                    f"Trade executed: {recommendation.side} {recommendation.symbol}"
                )
                # Re-sync portfolio after trade
                set_processing("SYNCING PORTFOLIO...")
                await _step_sync_portfolio()
            elif result.get("status") == "skipped":
                logger.info(f"Trade skipped: {result.get('reason')}")
        else:
            logger.info("No trades recommended this cycle")

        # Step 8: Update display
        await _step_update_display()

        logger.info("Sync cycle complete")
        emit(SystemEvent.SYNC_COMPLETE)

    except Exception as e:
        logger.error(f"Sync cycle failed: {e}", exc_info=True)
        error_msg = "SYNC CYCLE FAILED"
        emit(SystemEvent.ERROR_OCCURRED, message=error_msg)
        set_error(error_msg)
    finally:
        clear_processing()


async def _step_sync_trades():
    """Step 1: Sync trades from Tradernet."""
    from app.jobs.sync_trades import sync_trades

    try:
        await sync_trades()
    except Exception as e:
        logger.error(f"Trade sync failed: {e}")
        # Continue with other steps


async def _step_sync_cash_flows():
    """Step 2: Sync cash flows from Tradernet."""
    from app.jobs.cash_flow_sync import sync_cash_flows

    try:
        await sync_cash_flows()
    except Exception as e:
        logger.error(f"Cash flow sync failed: {e}")
        # Continue with other steps


async def _step_sync_portfolio():
    """Step 3: Sync portfolio positions from Tradernet."""
    from app.jobs.daily_sync import sync_portfolio

    try:
        await sync_portfolio()
    except Exception as e:
        logger.error(f"Portfolio sync failed: {e}")
        raise  # Portfolio sync is critical


async def _step_sync_prices():
    """
    Step 4: Sync prices from Yahoo Finance (market-aware).

    Only fetches prices for stocks whose markets are currently open.
    """
    try:
        stocks = await _get_active_stocks()
        if not stocks:
            logger.info("No active stocks to sync prices for")
            return

        open_markets = await get_open_markets()
        if not open_markets:
            logger.info("All markets are closed, skipping price sync")
            return

        logger.info(f"Open markets: {open_markets}")

        grouped = group_stocks_by_exchange(stocks)

        for exchange in open_markets:
            market_stocks = grouped.get(exchange, [])
            if not market_stocks:
                continue

            logger.info(f"Fetching prices for {len(market_stocks)} {exchange} stocks")

            symbol_yahoo_map = {
                s.symbol: s.yahoo_symbol for s in market_stocks if s.yahoo_symbol
            }

            if symbol_yahoo_map:
                quotes = yahoo.get_batch_quotes(symbol_yahoo_map)
                await _update_position_prices(quotes)
                logger.info(f"Updated {len(quotes)} prices for {exchange}")

    except Exception as e:
        logger.error(f"Price sync failed: {e}")
        # Continue with other steps


async def _step_check_trading_conditions() -> tuple[bool, dict[str, Any]]:
    """
    Step 5: Check trading conditions (P&L guardrails).

    Returns:
        Tuple of (can_trade: bool, status: dict)
    """
    from app.infrastructure.daily_pnl import get_daily_pnl_tracker

    try:
        pnl_tracker = get_daily_pnl_tracker()
        pnl_status = await pnl_tracker.get_trading_status()

        logger.info(f"P&L status: {pnl_status['pnl_display']} ({pnl_status['status']})")

        if pnl_status["status"] == "halted":
            return False, pnl_status

        return True, pnl_status

    except Exception as e:
        logger.error(f"P&L check failed: {e}")
        # Allow trading on error to avoid blocking
        return True, {"status": "unknown", "error": str(e)}


async def _step_get_recommendation() -> Optional[Any]:
    """
    Step 6: Get recommendation from holistic planner.

    The planner considers ALL stocks across all markets,
    not just those with open markets.
    """
    try:
        return await _get_holistic_recommendation()
    except Exception as e:
        logger.error(f"Failed to get recommendation: {e}")
        return None


async def _step_execute_trade(recommendation) -> dict[str, Any]:
    """
    Step 7: Execute trade (market-aware).

    Only executes if the stock's market is currently open.

    Args:
        recommendation: The trade recommendation

    Returns:
        Dict with status and details
    """
    try:
        # Get the stock to check its exchange
        stock = await _get_stock_by_symbol(recommendation.symbol)
        if not stock:
            return {"status": "skipped", "reason": "Stock not found"}

        exchange = getattr(stock, "fullExchangeName", None)
        if not exchange:
            logger.warning(f"Stock {recommendation.symbol} has no exchange set")
            # Allow trade anyway - exchange might not be set
        elif not is_market_open(exchange):
            return {
                "status": "skipped",
                "reason": f"Market closed for {exchange}",
                "exchange": exchange,
            }

        # Execute the trade
        return await _execute_trade_order(recommendation)

    except Exception as e:
        logger.error(f"Trade execution failed: {e}")
        return {"status": "error", "reason": str(e)}


async def _step_update_display():
    """Step 8: Update the LED ticker display."""
    try:
        from app.domain.services.ticker_content_service import TickerContentService
        from app.infrastructure.external.tradernet import get_tradernet_client
        from app.repositories import (
            AllocationRepository,
            PortfolioRepository,
            PositionRepository,
            SettingsRepository,
            StockRepository,
        )

        # Instantiate repositories and service
        portfolio_repo = PortfolioRepository()
        position_repo = PositionRepository()
        stock_repo = StockRepository()
        settings_repo = SettingsRepository()
        allocation_repo = AllocationRepository()
        tradernet_client = get_tradernet_client()

        ticker_service = TickerContentService(
            portfolio_repo=portfolio_repo,
            position_repo=position_repo,
            stock_repo=stock_repo,
            settings_repo=settings_repo,
            allocation_repo=allocation_repo,
            tradernet_client=tradernet_client,
        )

        ticker_text = await ticker_service.generate_ticker_text()
        set_next_actions(ticker_text)
        logger.debug(f"Ticker updated: {ticker_text[:50]}...")
    except Exception as e:
        logger.error(f"Display update failed: {e}")


# Helper functions


async def _get_active_stocks() -> list:
    """Get all active stocks from the database."""
    from app.repositories import StockRepository

    stock_repo = StockRepository()
    return await stock_repo.get_all_active()


async def _get_stock_by_symbol(symbol: str):
    """Get a stock by symbol."""
    from app.repositories import StockRepository

    stock_repo = StockRepository()
    return await stock_repo.get_by_symbol(symbol)


async def _update_position_prices(quotes: dict[str, float]):
    """Update position prices in the database."""
    from datetime import datetime

    from app.infrastructure.database.manager import get_db_manager

    db_manager = get_db_manager()
    now = datetime.now().isoformat()

    async with db_manager.state.transaction():
        for symbol, price in quotes.items():
            await db_manager.state.execute(
                """
                UPDATE positions
                SET current_price = ?,
                    market_value_eur = quantity * ? / currency_rate,
                    last_updated = ?
                WHERE symbol = ?
                """,
                (price, price, now, symbol),
            )


async def _get_holistic_recommendation():
    """Get next recommendation from the holistic planner."""
    from app.application.services.currency_exchange_service import (
        CurrencyExchangeService,
    )
    from app.application.services.rebalancing_service import RebalancingService
    from app.domain.models import Recommendation
    from app.domain.portfolio_hash import generate_recommendation_cache_key
    from app.domain.services.settings_service import SettingsService
    from app.domain.value_objects.currency import Currency
    from app.domain.value_objects.recommendation_status import RecommendationStatus
    from app.domain.value_objects.trade_side import TradeSide
    from app.infrastructure.cache import cache
    from app.infrastructure.database import get_db_manager
    from app.infrastructure.external.tradernet import TradernetClient
    from app.repositories import (
        AllocationRepository,
        PortfolioRepository,
        PositionRepository,
        RecommendationRepository,
        SettingsRepository,
        StockRepository,
        TradeRepository,
    )

    position_repo = PositionRepository()
    settings_repo = SettingsRepository()
    stock_repo = StockRepository()
    allocation_repo = AllocationRepository()
    settings_service = SettingsService(settings_repo)
    tradernet_client = TradernetClient.shared()

    # Check cache first
    positions = await position_repo.get_all()
    stocks = await stock_repo.get_all_active()
    settings = await settings_service.get_settings()
    allocations = await allocation_repo.get_all()
    position_dicts = [{"symbol": p.symbol, "quantity": p.quantity} for p in positions]
    cash_balances = (
        {b.currency: b.amount for b in tradernet_client.get_cash_balances()}
        if tradernet_client.is_connected
        else {}
    )
    portfolio_cache_key = generate_recommendation_cache_key(
        position_dicts, settings.to_dict(), stocks, cash_balances, allocations
    )
    cache_key = f"recommendations:{portfolio_cache_key}"

    # Check if incremental mode is enabled
    incremental_enabled = (
        await settings_repo.get_float("incremental_planner_enabled", 1.0) == 1.0
    )

    # Check planner database first (incremental mode takes priority)
    best_result = None
    if incremental_enabled:
        from app.domain.portfolio_hash import generate_portfolio_hash
        from app.repositories.planner_repository import PlannerRepository

        planner_repo = PlannerRepository()
        portfolio_hash = generate_portfolio_hash(position_dicts, stocks)
        best_result = await planner_repo.get_best_result(portfolio_hash)

    if best_result:
        # We have a result from incremental planner - use it (ignore cache)
        logger.info("Using best result from planner database (incremental mode)")
        best_sequence = await planner_repo.get_best_sequence_from_hash(
            portfolio_hash, best_result["best_sequence_hash"]
        )

        if best_sequence and len(best_sequence) > 0:
            # Use first step from best sequence
            step_action = best_sequence[0]
            logger.info(
                f"Best result from database: {step_action.side} {step_action.symbol}"
            )

            # Update cache with new result
            multi_step_data = {
                "depth": len(best_sequence),
                "steps": [
                    {
                        "step": i + 1,
                        "side": action.side,
                        "symbol": action.symbol,
                        "name": action.name,
                        "quantity": action.quantity,
                        "estimated_price": action.price,
                        "estimated_value": action.value_eur,
                        "currency": action.currency,
                        "reason": action.reason,
                    }
                    for i, action in enumerate(best_sequence)
                ],
            }
            cache.set(cache_key, multi_step_data, ttl_seconds=900)

            # Convert to Recommendation
            currency_val = step_action.currency
            if isinstance(currency_val, str):
                currency = Currency.from_string(currency_val)
            else:
                currency = Currency.from_string("EUR")

            side = TradeSide.BUY if step_action.side == "BUY" else TradeSide.SELL

            return Recommendation(
                symbol=step_action.symbol,
                name=step_action.name,
                side=side,
                quantity=step_action.quantity,
                estimated_price=step_action.price,
                estimated_value=step_action.value_eur,
                reason=step_action.reason,
                country=None,
                currency=currency,
                status=RecommendationStatus.PENDING,
            )

    # No result in database yet - check cache (fallback to old recommendations)
    cached = cache.get(cache_key)
    if cached and cached.get("steps"):
        step = cached["steps"][0]
        logger.info(
            f"Using cached recommendation (no database result yet): {step['side']} {step['symbol']}"
        )

        side = TradeSide.BUY if step["side"] == "BUY" else TradeSide.SELL
        currency_val = step.get("currency", "EUR")
        if isinstance(currency_val, str):
            currency = Currency.from_string(currency_val)
        else:
            currency = currency_val

        return Recommendation(
            symbol=step["symbol"],
            name=step.get("name", step["symbol"]),
            side=side,
            quantity=step["quantity"],
            estimated_price=step["estimated_price"],
            estimated_value=step["estimated_value"],
            reason=step.get("reason", "holistic plan"),
            country=None,
            currency=currency,
            status=RecommendationStatus.PENDING,
        )

    # No cache and no database result - fallback to full planner mode
    logger.info("No cache or database result, falling back to full planner mode...")

    # best_result already checked above, if we get here it's None
    if False:  # This block already handled above
        pass
    else:
        # Get best sequence from database
        best_sequence = await planner_repo.get_best_sequence_from_hash(
            portfolio_hash, best_result["best_sequence_hash"]
        )

        if best_sequence and len(best_sequence) > 0:
            # Use first step from best sequence
            step_action = best_sequence[0]
            logger.info(
                f"Using best result from database: {step_action.side} {step_action.symbol}"
            )

            # Cache the result
            multi_step_data = {
                "depth": len(best_sequence),
                "steps": [
                    {
                        "step": i + 1,
                        "side": action.side,
                        "symbol": action.symbol,
                        "name": action.name,
                        "quantity": action.quantity,
                        "estimated_price": action.price,
                        "estimated_value": action.value_eur,
                        "currency": action.currency,
                        "reason": action.reason,
                    }
                    for i, action in enumerate(best_sequence)
                ],
            }
            cache.set(cache_key, multi_step_data, ttl_seconds=900)

            # Convert to Recommendation
            currency_val = step_action.currency
            if isinstance(currency_val, str):
                currency = Currency.from_string(currency_val)
            else:
                currency = Currency.from_string("EUR")

            side = TradeSide.BUY if step_action.side == "BUY" else TradeSide.SELL

            return Recommendation(
                symbol=step_action.symbol,
                name=step_action.name,
                side=side,
                quantity=step_action.quantity,
                estimated_price=step_action.price,
                estimated_value=step_action.value_eur,
                reason=step_action.reason,
                country=None,
                currency=currency,
                status=RecommendationStatus.PENDING,
            )

    # No result in database yet - call planner (fallback to full mode)
    logger.info("No result in database, calling holistic planner (full mode)...")

    # Instantiate remaining required dependencies (stock_repo and tradernet_client already created)
    allocation_repo = AllocationRepository()
    portfolio_repo = PortfolioRepository()
    trade_repo = TradeRepository()
    recommendation_repo = RecommendationRepository()
    db_manager = get_db_manager()
    exchange_rate_service = CurrencyExchangeService(tradernet_client)

    rebalancing_service = RebalancingService(
        stock_repo=stock_repo,
        position_repo=position_repo,
        allocation_repo=allocation_repo,
        portfolio_repo=portfolio_repo,
        trade_repo=trade_repo,
        settings_repo=settings_repo,
        recommendation_repo=recommendation_repo,
        db_manager=db_manager,
        tradernet_client=tradernet_client,
        exchange_rate_service=exchange_rate_service,
    )
    steps = await rebalancing_service.get_recommendations()

    if not steps:
        return None

    step = steps[0]
    logger.info(f"Fresh recommendation: {step.side} {step.symbol}")

    # Cache the result
    multi_step_data = {
        "depth": len(steps),
        "steps": [
            {
                "step": s.step,
                "side": s.side,
                "symbol": s.symbol,
                "name": s.name,
                "quantity": s.quantity,
                "estimated_price": s.estimated_price,
                "estimated_value": s.estimated_value,
                "currency": s.currency,
                "reason": s.reason,
            }
            for s in steps
        ],
    }
    cache.set(cache_key, multi_step_data, ttl_seconds=900)

    # Convert to Recommendation
    currency_val = step.currency
    if isinstance(currency_val, str):
        currency = Currency.from_string(currency_val)
    else:
        currency = currency_val

    if isinstance(step.side, str):
        trade_side = TradeSide.from_string(step.side)
    else:
        trade_side = step.side

    return Recommendation(
        symbol=step.symbol,
        name=step.name,
        side=trade_side,
        quantity=step.quantity,
        estimated_price=step.estimated_price,
        estimated_value=step.estimated_value,
        reason=step.reason,
        country=None,
        currency=currency,
        status=RecommendationStatus.PENDING,
    )


async def _execute_trade_order(recommendation) -> dict[str, Any]:
    """Execute a trade order via Tradernet."""
    from app.application.services.trade_execution_service import TradeExecutionService
    from app.domain.value_objects.trade_side import TradeSide
    from app.infrastructure.database.manager import get_db_manager
    from app.infrastructure.dependencies import (
        get_currency_exchange_service_dep,
        get_exchange_rate_service,
        get_tradernet_client,
    )
    from app.repositories import PositionRepository, TradeRepository

    trade_repo = TradeRepository()
    position_repo = PositionRepository()
    db_manager = get_db_manager()
    tradernet_client = get_tradernet_client()
    exchange_rate_service = get_exchange_rate_service(db_manager)
    currency_exchange_service = get_currency_exchange_service_dep(tradernet_client)

    from app.repositories import StockRepository

    stock_repo = StockRepository()
    trade_execution = TradeExecutionService(
        trade_repo,
        position_repo,
        stock_repo,
        tradernet_client,
        currency_exchange_service,
        exchange_rate_service,
    )

    # Get currency balances for buy orders
    currency_balances = None
    if recommendation.side == TradeSide.BUY:
        currency_balances = {
            cb.currency: cb.amount for cb in tradernet_client.get_cash_balances()
        }
        pending_totals = tradernet_client.get_pending_order_totals()
        if pending_totals:
            for currency, pending_amount in pending_totals.items():
                if currency in currency_balances:
                    currency_balances[currency] = max(
                        0, currency_balances[currency] - pending_amount
                    )

    # Execute trade
    if recommendation.side == TradeSide.SELL:
        results = await trade_execution.execute_trades([recommendation])
    else:
        results = await trade_execution.execute_trades(
            [recommendation],
            currency_balances=currency_balances,
            auto_convert_currency=True,
            source_currency="EUR",
        )

    if results and results[0]["status"] == "success":
        emit(
            SystemEvent.TRADE_EXECUTED,
            is_buy=(recommendation.side == TradeSide.BUY),
        )
        return {"status": "success"}
    elif results and results[0]["status"] == "skipped":
        return {"status": "skipped", "reason": results[0].get("error", "unknown")}
    else:
        error = results[0].get("error", "Unknown error") if results else "No result"
        return {"status": "error", "reason": error}
