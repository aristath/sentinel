"""Cash-based rebalance job with drip execution strategy.

Executes ONE trade per cycle (15 minutes) with fresh data before each decision.
Priority: SELL before BUY.
"""

import logging

import aiosqlite

from app.config import settings
from app.services.tradernet import get_tradernet_client
from app.infrastructure.locking import file_lock
from app.infrastructure.hardware.led_display import get_led_display

logger = logging.getLogger(__name__)


async def check_and_rebalance():
    """
    Check for trade opportunities and execute ONE trade if available.

    Priority: SELL before BUY
    Limit: One trade per 15-minute cycle

    This "drip" strategy ensures:
    - Fresh data before each decision
    - Time for broker to settle orders
    - Recalculated recommendations each cycle
    """
    async with file_lock("rebalance", timeout=600.0):
        await _check_and_rebalance_internal()


async def _check_and_rebalance_internal():
    """Internal rebalance implementation with drip execution."""
    from app.jobs.daily_sync import sync_portfolio
    from app.api.settings import get_min_trade_size
    from app.services.scorer import score_all_stocks
    from app.infrastructure.dependencies import (
        get_stock_repository,
        get_position_repository,
        get_allocation_repository,
        get_portfolio_repository,
        get_trade_repository,
    )
    from app.application.services.rebalancing_service import RebalancingService
    from app.application.services.trade_execution_service import TradeExecutionService

    logger.info("Starting trade cycle check...")

    display = get_led_display()

    try:
        # Step 1: Sync portfolio for fresh data
        logger.info("Step 1: Syncing portfolio for fresh data...")
        await sync_portfolio()

        # Get configurable threshold from database
        min_trade_size = await get_min_trade_size()

        # Connect to broker
        client = get_tradernet_client()
        if not client.is_connected:
            if not client.connect():
                logger.warning("Cannot connect to Tradernet, skipping cycle")
                if display.is_connected:
                    display.show_error("BROKER DOWN")
                return

        cash_balance = client.get_total_cash_eur()
        logger.info(f"Cash balance: €{cash_balance:.2f}, threshold: €{min_trade_size:.2f}")

        async with aiosqlite.connect(settings.database_path) as db:
            db.row_factory = aiosqlite.Row

            # Step 2: Refresh scores
            logger.info("Step 2: Refreshing stock scores...")
            await score_all_stocks(db)

            # Initialize services
            stock_repo = get_stock_repository(db)
            position_repo = get_position_repository(db)
            allocation_repo = get_allocation_repository(db)
            portfolio_repo = get_portfolio_repository(db)
            trade_repo = get_trade_repository(db)

            rebalancing_service = RebalancingService(
                stock_repo, position_repo, allocation_repo, portfolio_repo
            )
            trade_execution = TradeExecutionService(
                trade_repo, db=db, position_repo=position_repo
            )

            # Step 3: Check for SELL recommendation (priority)
            logger.info("Step 3: Checking for SELL recommendations...")
            sell_recommendations = await rebalancing_service.calculate_sell_recommendations(limit=1)

            if sell_recommendations:
                trade = sell_recommendations[0]
                logger.info(
                    f"Executing SELL: {trade.quantity} {trade.symbol} "
                    f"@ €{trade.estimated_price:.2f} = €{trade.estimated_value:.2f} "
                    f"({trade.reason})"
                )

                if display.is_connected:
                    display.show_syncing()

                results = await trade_execution.execute_trades([trade], use_transaction=True)

                if results and results[0]["status"] == "success":
                    logger.info(f"SELL executed successfully: {trade.symbol}")
                    if display.is_connected:
                        display.show_success()
                else:
                    error = results[0].get("error", "Unknown error") if results else "No result"
                    logger.error(f"SELL failed for {trade.symbol}: {error}")
                    if display.is_connected:
                        display.show_error("SELL FAIL")

                # Sync portfolio to update state after trade
                await sync_portfolio()
                return  # Exit - wait for next cycle

            # Step 4: Check for BUY recommendation
            logger.info("Step 4: Checking for BUY recommendations...")

            if cash_balance < min_trade_size:
                logger.info(
                    f"Cash €{cash_balance:.2f} below threshold €{min_trade_size:.2f}, "
                    "no buy possible"
                )
                return

            # Get currency balances for buy validation
            currency_balances = {
                cb.currency: cb.amount
                for cb in client.get_cash_balances()
            }
            logger.info(f"Currency balances: {currency_balances}")

            # Calculate buy recommendations
            buy_recommendations = await rebalancing_service.calculate_rebalance_trades(cash_balance)

            if buy_recommendations:
                trade = buy_recommendations[0]  # Only execute top one
                logger.info(
                    f"Executing BUY: {trade.quantity} {trade.symbol} "
                    f"@ €{trade.estimated_price:.2f} = €{trade.estimated_value:.2f} "
                    f"({trade.reason})"
                )

                if display.is_connected:
                    display.show_syncing()

                results = await trade_execution.execute_trades(
                    [trade],
                    use_transaction=True,
                    currency_balances=currency_balances
                )

                if results and results[0]["status"] == "success":
                    logger.info(f"BUY executed successfully: {trade.symbol}")
                    if display.is_connected:
                        display.show_success()
                else:
                    error = results[0].get("error", "Unknown error") if results else "No result"
                    logger.error(f"BUY failed for {trade.symbol}: {error}")
                    if display.is_connected:
                        display.show_error("BUY FAIL")

                # Sync portfolio to update state after trade
                await sync_portfolio()
                return  # Exit - wait for next cycle

            logger.info("No trades recommended this cycle")

    except Exception as e:
        logger.error(f"Trade cycle error: {e}", exc_info=True)
        if display.is_connected:
            display.show_error("TRADE ERR")
