"""Cash-based rebalance job.

Checks cash balance periodically and executes trades when sufficient funds available.
Replaces the fixed monthly deposit schedule with dynamic cash-triggered rebalancing.
"""

import logging
from datetime import datetime

import aiosqlite

from app.config import settings
from app.services.tradernet import get_tradernet_client
from app.infrastructure.locking import file_lock
from app.infrastructure.hardware.led_display import get_led_display

logger = logging.getLogger(__name__)


async def check_and_rebalance():
    """
    Check cash balance and execute rebalancing if threshold is met.

    This job runs every 15 minutes and:
    1. Gets current cash balance from Tradernet
    2. If cash >= min_cash_threshold (€400), calculates and executes trades
    3. Logs the result

    Trade sizing:
    - Minimum €400 per trade (keeps commission at 0.5%)
    - Maximum 5 trades per cycle
    - Formula: max_trades = min(5, floor(cash / 400))
    """
    logger.info("Checking cash balance for potential rebalance...")

    try:
        # Get cash balance from Tradernet
        client = get_tradernet_client()
        if not client.is_connected:
            if not client.connect():
                logger.warning("Cannot connect to Tradernet, skipping cash check")
                display = get_led_display()
                if display.is_connected:
                    display.show_error("BROKER DOWN")
                return

        cash_balance = client.get_total_cash_eur()
        logger.info(f"Current cash balance: €{cash_balance:.2f}")

        # Fetch per-currency balances for execution-time validation
        currency_balances = {
            cb.currency: cb.amount
            for cb in client.get_cash_balances()
        }
        logger.info(f"Currency balances: {currency_balances}")

        # Check if we have enough cash to trade
        if cash_balance < settings.min_cash_threshold:
            logger.info(
                f"Cash €{cash_balance:.2f} below threshold €{settings.min_cash_threshold:.2f}, "
                "no rebalance needed"
            )
            return

        # We have enough cash - proceed with rebalancing
        logger.info(f"Cash €{cash_balance:.2f} >= threshold, initiating rebalance")

        # Use lock to prevent concurrent rebalancing
        async with file_lock("rebalance", timeout=600.0):
            await _check_and_rebalance_internal(cash_balance, currency_balances)
    except Exception as e:
        logger.error(f"Error during cash rebalance check: {e}", exc_info=True)
        display = get_led_display()
        if display.is_connected:
            display.show_error("REBAL FAIL")


async def _check_and_rebalance_internal(
    cash_balance: float,
    currency_balances: dict[str, float] | None = None
):
    """Internal rebalance implementation."""
    from app.jobs.daily_sync import sync_portfolio
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

    # Step 1: Sync portfolio to get latest positions
    logger.info("Step 1: Syncing portfolio...")
    await sync_portfolio()

    async with aiosqlite.connect(settings.database_path) as db:
        db.row_factory = aiosqlite.Row
        
        # Step 2: Refresh scores
        logger.info("Step 2: Refreshing stock scores...")
        scores = await score_all_stocks(db)
        logger.info(f"Scored {len(scores)} stocks")

        # Step 3: Calculate rebalance trades using application services
        logger.info("Step 3: Calculating rebalance trades...")
        stock_repo = get_stock_repository(db)
        position_repo = get_position_repository(db)
        allocation_repo = get_allocation_repository(db)
        portfolio_repo = get_portfolio_repository(db)

        rebalancing_service = RebalancingService(
            stock_repo, position_repo, allocation_repo, portfolio_repo
        )
        trades = await rebalancing_service.calculate_rebalance_trades(cash_balance)

        if not trades:
            logger.info("No rebalance trades recommended")
            return

        logger.info(f"Generated {len(trades)} trade recommendations:")
        for trade in trades:
            logger.info(
                f"  {trade.side} {trade.quantity} {trade.symbol} "
                f"@ €{trade.estimated_price:.2f} = €{trade.estimated_value:.2f} "
                f"({trade.reason})"
            )

        # Step 4: Execute trades using application service with transaction
        logger.info("Step 4: Executing trades...")
        trade_repo = get_trade_repository(db)
        trade_execution_service = TradeExecutionService(trade_repo, db=db)
        results = await trade_execution_service.execute_trades(
            trades,
            use_transaction=True,
            currency_balances=currency_balances
        )

        successful = sum(1 for r in results if r["status"] == "success")
        failed = sum(1 for r in results if r["status"] != "success")

        logger.info(
            f"Rebalance complete: {successful} successful, {failed} failed"
        )

        # Create snapshot after rebalance
        await sync_portfolio()

        # Log summary
        total_invested = sum(t.estimated_value for t in trades)
        logger.info(
            f"Cash rebalance finished at {datetime.now().isoformat()}: "
            f"invested €{total_invested:.2f} from €{cash_balance:.2f} available"
        )
