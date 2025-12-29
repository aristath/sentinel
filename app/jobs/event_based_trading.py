"""Event-based trading loop.

This module implements event-based trading that executes trades only after
the holistic planner has finished examining all generated scenarios and
found the optimal recommendation.

Flow:
1. Generate sequences/combinations
2. Process batches until ALL sequences evaluated (completed=1)
3. Get optimal recommendation (best_result)
4. Check if 1st step can execute (market hours restrictions with flexible behavior)
5. Execute trade if allowed (market open or flexible BUY)
6. Start portfolio monitoring (two-phase: 30s for 5min, then 1min for 15min)
7. When portfolio hash changes → invalidate cache → restart loop
"""

import asyncio
import logging
from typing import Optional

from app.domain.models import Recommendation
from app.domain.portfolio_hash import generate_portfolio_hash
from app.domain.value_objects.currency import Currency
from app.domain.value_objects.recommendation_status import RecommendationStatus
from app.domain.value_objects.trade_side import TradeSide
from app.infrastructure.cache_invalidation import get_cache_invalidation_service
from app.infrastructure.events import SystemEvent, emit
from app.infrastructure.hardware.display_service import (
    clear_processing,
    set_error,
    set_processing,
)
from app.infrastructure.locking import file_lock
from app.infrastructure.market_hours import is_market_open, should_check_market_hours
from app.jobs.sync_cycle import (
    _execute_trade_order,
    _step_check_trading_conditions,
    _step_sync_portfolio,
)
from app.repositories import PositionRepository, StockRepository
from app.repositories.planner_repository import PlannerRepository

logger = logging.getLogger(__name__)


async def run_event_based_trading_loop():
    """
    Main entry point for event-based trading loop.

    This function runs continuously, waiting for planning completion,
    executing trades, and monitoring portfolio changes.
    """
    async with file_lock("event_based_trading", timeout=3600.0):
        await _run_event_based_trading_loop_internal()


async def _run_event_based_trading_loop_internal():
    """Internal event-based trading loop implementation."""
    logger.info("Starting event-based trading loop...")

    while True:
        try:
            # Step 1: Wait for planning completion
            set_processing("WAITING FOR PLANNING...")
            await _wait_for_planning_completion()

            # Step 2: Get optimal recommendation
            set_processing("GETTING RECOMMENDATION...")
            recommendation = await _get_optimal_recommendation()

            if not recommendation:
                logger.info("No recommendation available, waiting...")
                await asyncio.sleep(60)  # Wait 1 minute before retrying
                continue

            # Step 3: Check trading conditions (P&L guardrails)
            set_processing("CHECKING CONDITIONS...")
            can_trade, pnl_status = await _step_check_trading_conditions()

            if not can_trade:
                logger.warning(f"Trading halted: {pnl_status.get('reason', 'unknown')}")
                await asyncio.sleep(300)  # Wait 5 minutes before retrying
                continue

            # Step 4: Check if trade can execute (market hours)
            set_processing("CHECKING MARKET HOURS...")
            can_execute, reason = await _can_execute_trade(recommendation)

            if not can_execute:
                logger.info(f"Trade cannot execute: {reason}")
                await asyncio.sleep(300)  # Wait 5 minutes before retrying
                continue

            # Step 5: Execute trade
            set_processing(
                f"EXECUTING {recommendation.side} {recommendation.symbol}..."
            )
            result = await _execute_trade_order(recommendation)

            if result.get("status") == "success":
                logger.info(
                    f"Trade executed: {recommendation.side} {recommendation.symbol}"
                )
                # Re-sync portfolio after trade
                set_processing("SYNCING PORTFOLIO...")
                await _step_sync_portfolio()

                # Step 6: Monitor portfolio for changes
                set_processing("MONITORING PORTFOLIO...")
                portfolio_changed = await _monitor_portfolio_for_changes()

                if portfolio_changed:
                    logger.info("Portfolio hash changed, restarting planning cycle")
                    # Loop will restart and wait for new planning completion
                    continue
                else:
                    logger.info(
                        "Portfolio monitoring completed, starting new planning cycle"
                    )
                    # Continue to next iteration to start new planning
                    continue
            elif result.get("status") == "skipped":
                logger.info(f"Trade skipped: {result.get('reason')}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying
                continue
            else:
                logger.error(f"Trade execution failed: {result.get('reason')}")
                await asyncio.sleep(300)  # Wait 5 minutes before retrying
                continue

        except Exception as e:
            logger.error(f"Event-based trading loop failed: {e}", exc_info=True)
            error_msg = "TRADING LOOP FAILED"
            emit(SystemEvent.ERROR_OCCURRED, message=error_msg)
            set_error(error_msg)
            await asyncio.sleep(60)  # Wait 1 minute before retrying
        finally:
            clear_processing()


async def _wait_for_planning_completion():
    """
    Wait for planning completion by processing batches until all sequences are evaluated.

    This function calls the planner batch processing until all sequences
    for the current portfolio hash have been evaluated (completed=1).
    """
    from app.application.services.recommendation.portfolio_context_builder import (
        build_portfolio_context,
    )
    from app.domain.planning.holistic_planner import create_holistic_plan_incremental
    from app.domain.services.exchange_rate_service import ExchangeRateService
    from app.infrastructure.database.manager import get_db_manager
    from app.infrastructure.external.tradernet import TradernetClient
    from app.repositories import (
        AllocationRepository,
        PositionRepository,
        SettingsRepository,
        StockRepository,
    )

    position_repo = PositionRepository()
    stock_repo = StockRepository()
    settings_repo = SettingsRepository()
    allocation_repo = AllocationRepository()
    tradernet_client = TradernetClient()
    db_manager = get_db_manager()
    exchange_rate_service = ExchangeRateService(db_manager)

    # Get current portfolio state
    positions = await position_repo.get_all()
    stocks = await stock_repo.get_all_active()

    # Generate portfolio hash
    position_dicts = [{"symbol": p.symbol, "quantity": p.quantity} for p in positions]
    portfolio_hash = generate_portfolio_hash(position_dicts, stocks)

    planner_repo = PlannerRepository()

    # Check if sequences exist, if not generate them
    if not await planner_repo.has_sequences(portfolio_hash):
        logger.info("No sequences found, generating initial sequences...")
        # Build portfolio context
        portfolio_context = await build_portfolio_context(
            position_repo=position_repo,
            stock_repo=stock_repo,
            allocation_repo=allocation_repo,
            db_manager=db_manager,
        )

        # Get available cash
        cash_balances = (
            tradernet_client.get_cash_balances()
            if tradernet_client.is_connected
            else []
        )
        available_cash = sum(b.amount for b in cash_balances if b.currency == "EUR")

        # Get optimizer target weights if available
        from app.application.services.optimization.portfolio_optimizer import (
            PortfolioOptimizer,
        )
        from app.repositories import GroupingRepository

        grouping_repo = GroupingRepository()
        optimizer = PortfolioOptimizer(grouping_repo=grouping_repo)

        target_weights: Optional[dict] = None
        current_prices: Optional[dict] = None

        try:
            optimization_result = await optimizer.optimize()
            if optimization_result and optimization_result.target_weights:
                target_weights = optimization_result.target_weights
                # Get current prices for target weights
                from app.infrastructure.external import yahoo_finance as yahoo

                symbols = list(target_weights.keys())
                quotes = await yahoo.get_quotes(symbols)
                current_prices = {
                    symbol: quote["price"] for symbol, quote in quotes.items()
                }
        except Exception as e:
            logger.debug(f"Could not get optimizer weights: {e}")

        # Get planner settings
        batch_size = int(await settings_repo.get_float("planner_batch_size", 100.0))
        max_plan_depth = int(await settings_repo.get_float("max_plan_depth", 5.0))
        max_opportunities_per_category = int(
            await settings_repo.get_float("max_opportunities_per_category", 5.0)
        )
        enable_combinatorial = (
            await settings_repo.get_float("enable_combinatorial_generation", 1.0) == 1.0
        )
        priority_threshold = await settings_repo.get_float(
            "priority_threshold_for_combinations", 0.3
        )
        combinatorial_max_combinations_per_depth = int(
            await settings_repo.get_float(
                "combinatorial_max_combinations_per_depth", 50.0
            )
        )
        combinatorial_max_sells = int(
            await settings_repo.get_float("combinatorial_max_sells", 4.0)
        )
        combinatorial_max_buys = int(
            await settings_repo.get_float("combinatorial_max_buys", 4.0)
        )
        combinatorial_max_candidates = int(
            await settings_repo.get_float("combinatorial_max_candidates", 12.0)
        )

        # Generate sequences by calling incremental planner
        await create_holistic_plan_incremental(
            portfolio_context=portfolio_context,
            available_cash=available_cash,
            stocks=stocks,
            positions=positions,
            exchange_rate_service=exchange_rate_service,
            target_weights=target_weights,
            current_prices=current_prices,
            transaction_cost_fixed=await settings_repo.get_float(
                "transaction_cost_fixed", 2.0
            ),
            transaction_cost_percent=await settings_repo.get_float(
                "transaction_cost_percent", 0.002
            ),
            max_plan_depth=max_plan_depth,
            max_opportunities_per_category=max_opportunities_per_category,
            enable_combinatorial=enable_combinatorial,
            priority_threshold=priority_threshold,
            combinatorial_max_combinations_per_depth=combinatorial_max_combinations_per_depth,
            combinatorial_max_sells=combinatorial_max_sells,
            combinatorial_max_buys=combinatorial_max_buys,
            combinatorial_max_candidates=combinatorial_max_candidates,
            batch_size=batch_size,
        )

    # Wait until all sequences are evaluated
    max_wait_iterations = 360  # 1 hour max wait (10 second intervals)
    iteration = 0

    while iteration < max_wait_iterations:
        if await planner_repo.are_all_sequences_evaluated(portfolio_hash):
            logger.info("All sequences evaluated, planning complete")
            return

        # Process next batch
        logger.debug(
            f"Waiting for planning completion (iteration {iteration + 1}/{max_wait_iterations})..."
        )

        # Call planner batch processing
        from app.jobs.planner_batch import process_planner_batch_job

        await process_planner_batch_job()

        iteration += 1
        await asyncio.sleep(10)  # Wait 10 seconds between checks

    logger.warning(
        "Planning completion timeout reached, proceeding with best result so far"
    )


async def _get_optimal_recommendation() -> Optional[Recommendation]:
    """
    Get the optimal recommendation (first step from best sequence).

    Returns:
        Recommendation object for the first step, or None if no recommendation available
    """
    from app.domain.portfolio_hash import generate_portfolio_hash
    from app.repositories.planner_repository import PlannerRepository

    position_repo = PositionRepository()
    stock_repo = StockRepository()
    planner_repo = PlannerRepository()

    # Get current portfolio state
    positions = await position_repo.get_all()
    stocks = await stock_repo.get_all_active()
    position_dicts = [{"symbol": p.symbol, "quantity": p.quantity} for p in positions]
    portfolio_hash = generate_portfolio_hash(position_dicts, stocks)

    # Get best result
    best_result = await planner_repo.get_best_result(portfolio_hash)
    if not best_result:
        logger.debug("No best result found in planner database")
        return None

    # Get best sequence
    best_sequence = await planner_repo.get_best_sequence_from_hash(
        portfolio_hash, best_result["best_sequence_hash"]
    )

    if not best_sequence or len(best_sequence) == 0:
        logger.debug("Best sequence is empty")
        return None

    # Extract first step
    step_action = best_sequence[0]
    logger.info(f"Best result from database: {step_action.side} {step_action.symbol}")

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


async def _can_execute_trade(
    recommendation: Recommendation,
) -> tuple[bool, Optional[str]]:
    """
    Check if trade can be executed based on market hours rules.

    Rules:
    - SELL orders: Always require market hours check → must execute when market is open
    - BUY orders on flexible markets (NYSE, NASDAQ, XETR, LSE, etc.):
      No check required, can execute anytime
    - BUY orders on strict markets (XHKG, XSHG, XTSE, XASX):
      Require market hours check → must execute when market is open

    Args:
        recommendation: The trade recommendation

    Returns:
        Tuple of (can_execute: bool, reason: Optional[str])
    """
    stock_repo = StockRepository()
    stock = await stock_repo.get_by_symbol(recommendation.symbol)

    if not stock:
        logger.warning(
            f"Stock {recommendation.symbol} not found, cannot check market hours. Allowing trade."
        )
        return True, None

    exchange = getattr(stock, "fullExchangeName", None)
    if not exchange:
        logger.warning(
            f"Stock {recommendation.symbol} has no exchange set. Allowing trade."
        )
        return True, None

    # Check if market hours validation is required for this trade
    if not should_check_market_hours(exchange, recommendation.side.value):
        # Market hours check not required (e.g., BUY on flexible hours market)
        # Can execute anytime
        return True, None

    # Market hours check IS required (SELL orders or BUY on strict markets)
    if not is_market_open(exchange):
        return False, f"Market closed for {exchange}"

    return True, None


async def _monitor_portfolio_for_changes() -> bool:
    """
    Monitor portfolio for changes with two-phase approach.

    Phase 1: Every 30 seconds for 5 minutes (10 iterations)
    Phase 2: Every 1 minute for 15 minutes (15 iterations)

    Returns:
        True if portfolio hash changed (trigger restart), False if timeout
    """
    from app.infrastructure.external.tradernet import get_tradernet_client

    position_repo = PositionRepository()
    stock_repo = StockRepository()
    client = get_tradernet_client()

    # Get initial portfolio hash
    positions = await position_repo.get_all()
    stocks = await stock_repo.get_all_active()
    cash_balances = (
        {b.currency: b.amount for b in client.get_cash_balances()}
        if client.is_connected
        else {}
    )
    position_dicts = [{"symbol": p.symbol, "quantity": p.quantity} for p in positions]
    initial_hash = generate_portfolio_hash(position_dicts, stocks, cash_balances)

    # Phase 1: Every 30 seconds for 5 minutes (10 iterations)
    for i in range(10):
        await asyncio.sleep(30)
        await _step_sync_portfolio()

        # Check if hash changed
        positions_after = await position_repo.get_all()
        cash_balances_after = (
            {b.currency: b.amount for b in client.get_cash_balances()}
            if client.is_connected
            else {}
        )
        position_dicts_after = [
            {"symbol": p.symbol, "quantity": p.quantity} for p in positions_after
        ]
        current_hash = generate_portfolio_hash(
            position_dicts_after, stocks, cash_balances_after
        )

        if current_hash != initial_hash:
            logger.info(f"Portfolio hash changed during phase 1 (iteration {i+1})")
            cache_service = get_cache_invalidation_service()
            cache_service.invalidate_recommendation_caches()
            return True

    # Phase 2: Every 1 minute for 15 minutes (15 iterations)
    for i in range(15):
        await asyncio.sleep(60)
        await _step_sync_portfolio()

        # Check if hash changed
        positions_after = await position_repo.get_all()
        cash_balances_after = (
            {b.currency: b.amount for b in client.get_cash_balances()}
            if client.is_connected
            else {}
        )
        position_dicts_after = [
            {"symbol": p.symbol, "quantity": p.quantity} for p in positions_after
        ]
        current_hash = generate_portfolio_hash(
            position_dicts_after, stocks, cash_balances_after
        )

        if current_hash != initial_hash:
            logger.info(f"Portfolio hash changed during phase 2 (iteration {i+1})")
            cache_service = get_cache_invalidation_service()
            cache_service.invalidate_recommendation_caches()
            return True

    logger.info("Portfolio monitoring completed (20 minutes) without hash change")
    return False
