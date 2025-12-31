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

from app.core.events import SystemEvent, emit
from app.domain.models import Recommendation
from app.domain.portfolio_hash import generate_portfolio_hash
from app.domain.value_objects.recommendation_status import RecommendationStatus
from app.domain.value_objects.trade_side import TradeSide
from app.infrastructure.cache_invalidation import get_cache_invalidation_service
from app.infrastructure.locking import file_lock
from app.infrastructure.market_hours import is_market_open, should_check_market_hours
from app.modules.display.services.display_service import set_led4, set_text
from app.modules.planning.database.planner_repository import PlannerRepository
from app.modules.portfolio.database.position_repository import PositionRepository
from app.modules.system.jobs.sync_cycle import (
    _execute_trade_order,
    _step_check_trading_conditions,
    _step_sync_portfolio,
)
from app.shared.domain.value_objects.currency import Currency

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
            await _wait_for_planning_completion()

            # Step 2: Get optimal recommendation
            set_text("GETTING RECOMMENDATION...")
            set_led4(0, 255, 0)  # Green for processing
            recommendation = await _get_optimal_recommendation()

            if not recommendation:
                logger.info("No recommendation available, waiting...")
                await asyncio.sleep(60)  # Wait 1 minute before retrying
                continue

            # Step 3: Check trading conditions (P&L guardrails)
            set_text("CHECKING CONDITIONS...")
            can_trade, pnl_status = await _step_check_trading_conditions()

            if not can_trade:
                logger.warning(f"Trading halted: {pnl_status.get('reason', 'unknown')}")
                await asyncio.sleep(300)  # Wait 5 minutes before retrying
                continue

            # Step 3.5: Check trade frequency limits
            set_text("CHECKING FREQUENCY LIMITS...")
            from app.modules.trading.services.trade_frequency_service import (
                TradeFrequencyService,
            )
            from app.repositories import SettingsRepository, TradeRepository

            trade_repo = TradeRepository()
            settings_repo = SettingsRepository()
            frequency_service = TradeFrequencyService(trade_repo, settings_repo)
            can_execute_frequency, frequency_reason = (
                await frequency_service.can_execute_trade()
            )

            if not can_execute_frequency:
                logger.warning(f"Trade blocked by frequency limit: {frequency_reason}")
                await asyncio.sleep(300)  # Wait 5 minutes before retrying
                continue

            # Step 4: Check if trade can execute (market hours)
            set_text("CHECKING MARKET HOURS...")
            can_execute, reason = await _can_execute_trade(recommendation)

            if not can_execute:
                logger.info(f"Trade cannot execute: {reason}")
                await asyncio.sleep(300)  # Wait 5 minutes before retrying
                continue

            # Step 5: Execute trade
            set_text(f"EXECUTING {recommendation.side} {recommendation.symbol}...")
            result = await _execute_trade_order(recommendation)

            if result.get("status") == "success":
                logger.info(
                    f"Trade executed: {recommendation.side} {recommendation.symbol}"
                )
                # Re-sync portfolio after trade
                set_text("SYNCING PORTFOLIO...")
                await _step_sync_portfolio()

                # Check and rebalance negative balances immediately after trade
                # (trades can affect cash balances)
                from app.modules.rebalancing.jobs.emergency_rebalance import (
                    check_and_rebalance_immediately,
                )

                await check_and_rebalance_immediately()

                # Step 6: Monitor portfolio for changes
                set_text("MONITORING PORTFOLIO...")
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
            error_msg = "MAIN TRADING LOOP CRASHES"
            emit(SystemEvent.ERROR_OCCURRED, message=error_msg)
            set_text(error_msg)
            set_led4(255, 0, 0)  # Red for error
            await asyncio.sleep(60)  # Wait 1 minute before retrying
        finally:
            set_led4(0, 0, 0)  # Clear LED when done


async def _wait_for_planning_completion():
    """
    Wait for planning completion by processing batches until all sequences are evaluated.

    This function calls the planner batch processing until all sequences
    for the current portfolio hash have been evaluated (completed=1).
    """
    from app.core.database.manager import get_db_manager
    from app.domain.services.exchange_rate_service import ExchangeRateService
    from app.infrastructure.external.tradernet import TradernetClient
    from app.modules.planning.domain.holistic_planner import (
        create_holistic_plan_incremental,
    )
    from app.modules.planning.services.portfolio_context_builder import (
        build_portfolio_context,
    )
    from app.repositories import (
        AllocationRepository,
        PositionRepository,
        SecurityRepository,
        SettingsRepository,
    )

    position_repo = PositionRepository()
    security_repo = SecurityRepository()
    settings_repo = SettingsRepository()
    allocation_repo = AllocationRepository()
    tradernet_client = TradernetClient()
    db_manager = get_db_manager()
    exchange_rate_service = ExchangeRateService(db_manager)

    # Get current portfolio state
    positions = await position_repo.get_all()
    stocks = await security_repo.get_all_active()

    # Fetch pending orders
    pending_orders = []
    if tradernet_client.is_connected:
        try:
            pending_orders = tradernet_client.get_pending_orders()
        except Exception as e:
            logger.warning(f"Failed to fetch pending orders: {e}")

    # Generate portfolio hash (with pending orders applied)
    position_dicts = [{"symbol": p.symbol, "quantity": p.quantity} for p in positions]
    cash_balances = (
        {b.currency: b.amount for b in tradernet_client.get_cash_balances()}
        if tradernet_client.is_connected
        else {}
    )
    portfolio_hash = generate_portfolio_hash(
        position_dicts, stocks, cash_balances, pending_orders
    )

    planner_repo = PlannerRepository()

    # Check if sequences exist, if not generate them
    if not await planner_repo.has_sequences(portfolio_hash):
        logger.info("No sequences found, generating initial sequences...")
        # Build portfolio context
        portfolio_context = await build_portfolio_context(
            position_repo=position_repo,
            security_repo=security_repo,
            allocation_repo=allocation_repo,
            db_manager=db_manager,
        )

        # Get available cash (convert all currencies to EUR)
        cash_balances_raw = (
            tradernet_client.get_cash_balances()
            if tradernet_client.is_connected
            else []
        )
        if cash_balances_raw:
            amounts_by_currency = {b.currency: b.amount for b in cash_balances_raw}
            amounts_in_eur = await exchange_rate_service.batch_convert_to_eur(
                amounts_by_currency
            )
            available_cash = sum(amounts_in_eur.values())
        else:
            available_cash = 0.0

        # Apply pending orders to positions and cash
        if pending_orders:
            from app.domain.models import Position
            from app.domain.portfolio_hash import apply_pending_orders_to_portfolio

            # Convert positions to dict format for adjustment
            position_dicts_for_adjustment = [
                {"symbol": p.symbol, "quantity": p.quantity} for p in positions
            ]
            cash_balances_dict = (
                {b.currency: b.amount for b in cash_balances_raw}
                if cash_balances_raw
                else {}
            )

            # Apply pending orders
            adjusted_position_dicts, adjusted_cash_balances = (
                apply_pending_orders_to_portfolio(
                    position_dicts_for_adjustment, cash_balances_dict, pending_orders
                )
            )

            # Convert adjusted position dicts back to Position objects
            position_map = {p.symbol: p for p in positions}
            adjusted_positions = []
            for pos_dict in adjusted_position_dicts:
                symbol = pos_dict["symbol"]
                quantity = pos_dict["quantity"]
                if symbol in position_map:
                    original = position_map[symbol]
                    adjusted_positions.append(
                        Position(
                            symbol=original.symbol,
                            quantity=quantity,
                            avg_price=original.avg_price,
                            isin=original.isin,
                            currency=original.currency,
                            currency_rate=original.currency_rate,
                            current_price=original.current_price,
                            market_value_eur=(
                                original.market_value_eur
                                * (quantity / original.quantity)
                                if original.quantity > 0 and original.market_value_eur
                                else None
                            ),
                            cost_basis_eur=(
                                original.cost_basis_eur * (quantity / original.quantity)
                                if original.quantity > 0 and original.cost_basis_eur
                                else None
                            ),
                            unrealized_pnl=original.unrealized_pnl,
                            unrealized_pnl_pct=original.unrealized_pnl_pct,
                            last_updated=original.last_updated,
                            first_bought_at=original.first_bought_at,
                            last_sold_at=original.last_sold_at,
                        )
                    )
                else:
                    # New position from pending BUY order
                    # Find the order to get the price for avg_price
                    order_price = None
                    order_currency = None
                    for order in pending_orders:
                        if (
                            order.get("symbol", "").upper() == symbol
                            and order.get("side", "").lower() == "buy"
                        ):
                            order_price = float(order.get("price", 0))
                            order_currency = order.get("currency", "EUR")
                            break

                    # Use order price as avg_price (required by Position validation)
                    avg_price = order_price if order_price and order_price > 0 else 0.01

                    from app.shared.domain.value_objects.currency import Currency

                    currency = (
                        Currency.from_string(order_currency)
                        if order_currency
                        else Currency.EUR
                    )

                    adjusted_positions.append(
                        Position(
                            symbol=symbol,
                            quantity=quantity,
                            avg_price=avg_price,
                            currency=currency,
                            currency_rate=1.0,
                        )
                    )

            positions = adjusted_positions

            # Recalculate available_cash from adjusted cash balances
            if adjusted_cash_balances:
                amounts_in_eur = await exchange_rate_service.batch_convert_to_eur(
                    adjusted_cash_balances
                )
                available_cash = sum(amounts_in_eur.values())
                logger.info(
                    f"Adjusted available_cash for pending orders: {available_cash:.2f} EUR"
                )
            else:
                available_cash = 0.0
                logger.info("No cash balances after applying pending orders")

        # Get optimizer target weights if available
        from app.modules.optimization.services.portfolio_optimizer import (
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
        # API-driven mode uses small batches (5) for faster processing
        batch_size = 5
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

    # Trigger first batch via API to start API-driven batch chain
    import httpx

    base_url = "http://localhost:8000"
    url = f"{base_url}/api/status/jobs/planner-batch"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            await client.post(url, json={"portfolio_hash": portfolio_hash, "depth": 1})
        logger.debug("Triggered first planner batch via API")
    except Exception as e:
        logger.warning(
            f"Failed to trigger first batch via API: {e}, falling back to direct call"
        )
        # Fallback: call directly
        from app.modules.planning.jobs.planner_batch import process_planner_batch_job

        await process_planner_batch_job(max_depth=1, portfolio_hash=portfolio_hash)

    # Wait until all sequences are evaluated
    # Reduced wait time since API-driven batches are faster
    max_wait_iterations = 720  # 1 hour max wait (5 second intervals)
    iteration = 0

    while iteration < max_wait_iterations:
        if await planner_repo.are_all_sequences_evaluated(portfolio_hash):
            logger.info("All sequences evaluated, planning complete")
            set_led4(0, 0, 0)  # Clear LED when done
            return

        # Update planning progress display
        total_sequences = await planner_repo.get_total_sequence_count(portfolio_hash)
        evaluated_count = await planner_repo.get_evaluation_count(portfolio_hash)
        is_finished = await planner_repo.are_all_sequences_evaluated(portfolio_hash)

        # Check if planning is active
        is_planning = False
        if total_sequences > 0 and not is_finished:
            try:
                from app.jobs.scheduler import get_scheduler

                scheduler = get_scheduler()
                if scheduler and scheduler.running:
                    jobs = scheduler.get_jobs()
                    planner_job = next(
                        (job for job in jobs if job.id == "planner_batch"), None
                    )
                    if planner_job:
                        is_planning = True
            except Exception:
                # If we can't check scheduler, assume planning is active if there's work to do
                is_planning = total_sequences > 0 and not is_finished

        if is_planning and total_sequences > 0:
            set_text(
                f"PLANNING ({evaluated_count}/{total_sequences} SCENARIOS SIMULATED)"
            )
        else:
            set_led4(0, 0, 0)  # Clear LED when done

        # Check periodically (reduced interval since API-driven batches are faster)
        logger.debug(
            f"Waiting for planning completion (iteration {iteration + 1}/{max_wait_iterations})..."
        )

        iteration += 1
        await asyncio.sleep(
            5
        )  # Reduced from 10 to 5 seconds since API-driven batches are faster

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
    from app.modules.planning.database.planner_repository import PlannerRepository
    from app.modules.universe.database.security_repository import SecurityRepository

    position_repo = PositionRepository()
    security_repo = SecurityRepository()
    planner_repo = PlannerRepository()

    # Get current portfolio state
    positions = await position_repo.get_all()
    stocks = await security_repo.get_all_active()
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
    from app.modules.universe.database.security_repository import SecurityRepository

    security_repo = SecurityRepository()
    stock = await security_repo.get_by_symbol(recommendation.symbol)

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
    # TradeSide is a str enum, use .value to get the actual string value
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
    from app.modules.universe.database.security_repository import SecurityRepository

    position_repo = PositionRepository()
    security_repo = SecurityRepository()
    client = get_tradernet_client()

    # Get initial portfolio hash
    positions = await position_repo.get_all()
    stocks = await security_repo.get_all_active()
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
