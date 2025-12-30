"""Cash-based rebalance job with drip execution strategy.

Executes ONE trade per cycle (15 minutes) with fresh data before each decision.
Priority: SELL before BUY.
"""

import logging
from typing import TYPE_CHECKING

from app.infrastructure.cache import cache
from app.infrastructure.daily_pnl import get_daily_pnl_tracker
from app.infrastructure.events import SystemEvent, emit
from app.infrastructure.external.tradernet import get_tradernet_client
from app.infrastructure.hardware.display_service import (
    clear_processing,
    set_error,
    set_processing,
)
from app.infrastructure.locking import file_lock
from app.infrastructure.recommendation_cache import get_recommendation_cache
from app.repositories import (
    AllocationRepository,
    PositionRepository,
    RecommendationRepository,
    SettingsRepository,
    StockRepository,
    TradeRepository,
)

if TYPE_CHECKING:
    from app.domain.models import Recommendation

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


async def _check_pnl_guardrails() -> tuple[dict, bool]:
    """Check P&L status and return status dict and whether trading is allowed."""
    pnl_tracker = get_daily_pnl_tracker()
    pnl_status = await pnl_tracker.get_trading_status()
    logger.info(
        f"Daily P&L status: {pnl_status['pnl_display']} ({pnl_status['status']})"
    )

    if pnl_status["status"] == "halted":
        logger.warning(f"Trading halted: {pnl_status['reason']}")
        error_msg = "TRADING HALTED - SEVERE DRAWDOWN"
        emit(SystemEvent.ERROR_OCCURRED, message=error_msg)
        set_error(error_msg)
        emit(SystemEvent.REBALANCE_COMPLETE)
        return pnl_status, False

    return pnl_status, True


async def _validate_next_action(
    next_action,
    pnl_status: dict,
    cash_balance: float,
    min_trade_size: float,
    trade_repo,
    settings_repo,
) -> bool:
    """Validate next action against P&L guardrails, cash, recent orders, and frequency limits."""
    from app.domain.value_objects.trade_side import TradeSide

    # Check trade frequency limits
    if settings_repo:
        from app.application.services.trade_frequency_service import (
            TradeFrequencyService,
        )

        frequency_service = TradeFrequencyService(trade_repo, settings_repo)
        can_trade, reason = await frequency_service.can_execute_trade()
        if not can_trade:
            logger.info(
                f"{next_action.side} {next_action.symbol} blocked by frequency limit: {reason}"
            )
            return False

    if next_action.side == TradeSide.SELL and not pnl_status["can_sell"]:
        logger.info(
            f"SELL {next_action.symbol} blocked by P&L guardrail: {pnl_status['reason']}"
        )
        return False

    if next_action.side == TradeSide.BUY and not pnl_status["can_buy"]:
        logger.info(
            f"BUY {next_action.symbol} blocked by P&L guardrail: {pnl_status['reason']}"
        )
        return False

    if next_action.side == TradeSide.BUY and cash_balance < min_trade_size:
        logger.info(
            f"Cash €{cash_balance:.2f} below threshold €{min_trade_size:.2f}, "
            f"skipping BUY {next_action.symbol}"
        )
        return False

    if next_action.side == TradeSide.SELL:
        has_recent = await trade_repo.has_recent_sell_order(next_action.symbol, hours=2)
        if has_recent:
            logger.warning(
                f"Skipping SELL {next_action.symbol}: recent sell order found "
                f"(within last 2 hours)"
            )
            return False

    return True


async def _execute_trade(
    next_action, client, trade_repo, position_repo, portfolio_hash: str
) -> None:
    """Execute the trade and handle post-execution tasks."""
    from app.application.services.trade_execution_service import TradeExecutionService
    from app.domain.value_objects.trade_side import TradeSide
    from app.jobs.daily_sync import sync_portfolio

    logger.info(
        f"Executing {next_action.side}: {next_action.quantity} {next_action.symbol} "
        f"@ €{next_action.estimated_price:.2f} = €{next_action.estimated_value:.2f} "
        f"({next_action.reason})"
    )

    emit(SystemEvent.SYNC_START)
    from app.infrastructure.database.manager import get_db_manager
    from app.infrastructure.dependencies import (
        get_exchange_rate_service,
        get_tradernet_client,
    )

    # Note: Direct DB access here is a known architecture violation.
    # get_exchange_rate_service() requires db_manager for initialization.
    # A future refactoring could make ExchangeRateService work without requiring db_manager.
    # See README.md Architecture section for details.
    db_manager = get_db_manager()
    tradernet_client = get_tradernet_client()
    exchange_rate_service = get_exchange_rate_service(db_manager)
    from app.infrastructure.dependencies import get_currency_exchange_service_dep

    currency_exchange_service = get_currency_exchange_service_dep(tradernet_client)
    from app.repositories import SettingsRepository, StockRepository

    stock_repo = StockRepository()
    settings_repo = SettingsRepository()
    trade_execution = TradeExecutionService(
        trade_repo,
        position_repo,
        stock_repo,
        tradernet_client,
        currency_exchange_service,
        exchange_rate_service,
        settings_repo=settings_repo,
    )

    currency_balances = None
    if next_action.side == TradeSide.BUY:
        currency_balances = {
            cb.currency: cb.amount for cb in client.get_cash_balances()
        }

        # Check for negative balances and log warnings
        for currency, balance in currency_balances.items():
            if balance < 0:
                logger.warning(
                    f"Negative balance detected in cash rebalance: "
                    f"{balance:.2f} {currency}"
                )
                emit(SystemEvent.ERROR_OCCURRED, message=f"NEGATIVE {currency} BALANCE")

        pending_totals = client.get_pending_order_totals()
        if pending_totals:
            for currency, pending_amount in pending_totals.items():
                if currency in currency_balances:
                    currency_balances[currency] = max(
                        0, currency_balances[currency] - pending_amount
                    )

    if next_action.side == TradeSide.SELL:
        results = await trade_execution.execute_trades([next_action])
    else:
        results = await trade_execution.execute_trades(
            [next_action],
            currency_balances=currency_balances,
            auto_convert_currency=True,
            source_currency="EUR",
        )

    if results and results[0]["status"] == "success":
        logger.info(f"{next_action.side} executed successfully: {next_action.symbol}")
        emit(SystemEvent.TRADE_EXECUTED, is_buy=(next_action.side == TradeSide.BUY))

        rec_cache = get_recommendation_cache()
        await rec_cache.invalidate_portfolio_hash(portfolio_hash)

        recommendation_repo = RecommendationRepository()
        matching_recs = await recommendation_repo.find_matching_for_execution(
            symbol=next_action.symbol,
            side=next_action.side,
            portfolio_hash=portfolio_hash,
        )
        for rec in matching_recs:
            await recommendation_repo.mark_executed(rec["uuid"])
            logger.info(f"Marked recommendation {rec['uuid']} as executed")
    elif results and results[0]["status"] == "skipped":
        reason = results[0].get("error", "unknown")
        logger.info(f"Trade skipped for {next_action.symbol}: {reason}")
    else:
        error = results[0].get("error", "Unknown error") if results else "No result"
        logger.error(f"{next_action.side} failed for {next_action.symbol}: {error}")
        error_msg = f"{next_action.side} ORDER FAILED"
        emit(SystemEvent.ERROR_OCCURRED, message=error_msg)
        set_error(error_msg)

    emit(SystemEvent.SYNC_COMPLETE)
    await sync_portfolio()


async def _check_and_rebalance_internal():
    """Internal rebalance implementation with drip execution."""
    from app.jobs.daily_sync import sync_portfolio
    from app.jobs.sync_trades import sync_trades

    logger.info("Starting trade cycle check...")

    emit(SystemEvent.REBALANCE_START)
    set_processing("CHECKING TRADE OPPORTUNITIES...")

    try:
        logger.info("Step 0: Syncing trades from Tradernet...")
        await sync_trades()

        logger.info("Step 1: Syncing portfolio for fresh data...")
        await sync_portfolio()

        pnl_status, can_trade = await _check_pnl_guardrails()
        if not can_trade:
            return

        from app.application.services.rebalancing_service import (
            calculate_min_trade_amount,
        )
        from app.domain.services.settings_service import SettingsService

        settings_repo = SettingsRepository()
        settings_service = SettingsService(settings_repo)
        settings = await settings_service.get_settings()
        min_trade_size = calculate_min_trade_amount(
            settings.transaction_cost_fixed,
            settings.transaction_cost_percent,
        )

        client = get_tradernet_client()
        if not client.is_connected:
            if not client.connect():
                logger.warning("Cannot connect to Tradernet, skipping cycle")
                error_msg = "BROKER CONNECTION FAILED"
                emit(SystemEvent.ERROR_OCCURRED, message=error_msg)
                set_error(error_msg)
                return

        cash_balance = client.get_total_cash_eur()
        logger.info(
            f"Cash balance: €{cash_balance:.2f}, threshold: €{min_trade_size:.2f}"
        )

        position_repo = PositionRepository()
        trade_repo = TradeRepository()
        stock_repo = StockRepository()

        logger.info("Step 2: Building portfolio context...")
        set_processing("BUILDING PORTFOLIO CONTEXT...")

        positions = await position_repo.get_all()
        stocks = await stock_repo.get_all_active()

        # Check event-driven rebalancing triggers
        event_driven_enabled = await settings_repo.get_float(
            "event_driven_rebalancing_enabled", 1.0
        )
        if event_driven_enabled == 1.0:
            from app.domain.services.rebalancing_triggers import (
                check_rebalance_triggers,
            )

            # Calculate total portfolio value
            total_position_value = sum(
                p.market_value_eur or 0.0 for p in positions if p.market_value_eur
            )
            total_portfolio_value = total_position_value + cash_balance

            # Get target allocations (empty dict = skip drift check, only check cash)
            target_allocations = {}

            should_rebalance, trigger_reason = await check_rebalance_triggers(
                positions=positions,
                target_allocations=target_allocations,
                total_portfolio_value=total_portfolio_value,
                cash_balance=cash_balance,
                settings_repo=settings_repo,
            )

            if not should_rebalance:
                logger.info(
                    f"Event-driven rebalancing: skipping cycle ({trigger_reason})"
                )
                emit(SystemEvent.REBALANCE_COMPLETE)
                await _refresh_recommendation_cache()
                clear_processing()
                return

            logger.info(
                f"Event-driven rebalancing: triggers met ({trigger_reason}), proceeding"
            )

        from app.domain.portfolio_hash import generate_portfolio_hash

        position_hash_dicts = [
            {"symbol": p.symbol, "quantity": p.quantity} for p in positions
        ]
        cash_balances = {b.currency: b.amount for b in client.get_cash_balances()}
        portfolio_hash = generate_portfolio_hash(
            position_hash_dicts, stocks, cash_balances
        )

        logger.info("Step 3: Getting recommendation from holistic planner...")
        set_processing("GETTING HOLISTIC RECOMMENDATION...")

        next_action = await _get_next_holistic_action()

        if not next_action:
            logger.info("No trades recommended this cycle")
            emit(SystemEvent.REBALANCE_COMPLETE)
            await _refresh_recommendation_cache()
            clear_processing()
            return

        if not await _validate_next_action(
            next_action,
            pnl_status,
            cash_balance,
            min_trade_size,
            trade_repo,
            settings_repo,
        ):
            emit(SystemEvent.REBALANCE_COMPLETE)
            await _refresh_recommendation_cache()
            return

        await _execute_trade(
            next_action, client, trade_repo, position_repo, portfolio_hash
        )
        await _refresh_recommendation_cache()

    except Exception as e:
        logger.error(f"Trade cycle error: {e}", exc_info=True)
        error_msg = "TRADE CYCLE ERROR"
        emit(SystemEvent.ERROR_OCCURRED, message=error_msg)
        set_error(error_msg)
    finally:
        clear_processing()


async def _get_next_holistic_action() -> "Recommendation | None":
    """
    Get the next action from the holistic planner.

    Uses portfolio-aware cache if available, otherwise calls planner directly.

    Returns:
        First step from holistic plan as a Recommendation, or None if no actions.
    """
    from app.application.services.rebalancing_service import RebalancingService
    from app.domain.models import Recommendation
    from app.domain.portfolio_hash import generate_recommendation_cache_key
    from app.domain.services.settings_service import SettingsService
    from app.domain.value_objects.currency import Currency
    from app.domain.value_objects.recommendation_status import RecommendationStatus
    from app.domain.value_objects.trade_side import TradeSide

    position_repo = PositionRepository()
    settings_repo = SettingsRepository()
    stock_repo = StockRepository()
    allocation_repo = AllocationRepository()
    settings_service = SettingsService(settings_repo)
    client = get_tradernet_client()

    # Generate portfolio-aware cache key
    positions = await position_repo.get_all()
    stocks = await stock_repo.get_all_active()
    settings = await settings_service.get_settings()
    allocations = await allocation_repo.get_all()
    position_dicts = [{"symbol": p.symbol, "quantity": p.quantity} for p in positions]
    cash_balances = (
        {b.currency: b.amount for b in client.get_cash_balances()}
        if client.is_connected
        else {}
    )

    # Fetch pending orders for cache key
    pending_orders = []
    if client.is_connected:
        try:
            pending_orders = client.get_pending_orders()
        except Exception as e:
            logger.warning(f"Failed to fetch pending orders: {e}")

    portfolio_cache_key = generate_recommendation_cache_key(
        position_dicts,
        settings.to_dict(),
        stocks,
        cash_balances,
        allocations,
        pending_orders,
    )
    cache_key = f"recommendations:{portfolio_cache_key}"

    # Try cache first
    cached = cache.get(cache_key)
    if cached and cached.get("steps"):
        step = cached["steps"][0]
        logger.info(
            f"Using cached holistic recommendation: {step['side']} {step['symbol']}"
        )

        # Convert cached step dict to Recommendation
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

    # Cache miss - call planner directly
    logger.info("Cache miss, calling holistic planner directly...")
    from app.infrastructure.database.manager import get_db_manager
    from app.infrastructure.dependencies import get_exchange_rate_service
    from app.repositories import PortfolioRepository

    stock_repo = StockRepository()
    position_repo = PositionRepository()
    allocation_repo = AllocationRepository()
    portfolio_repo = PortfolioRepository()
    trade_repo = TradeRepository()
    settings_repo = SettingsRepository()
    recommendation_repo = RecommendationRepository()
    # Note: Direct DB access here is a known architecture violation.
    # get_exchange_rate_service() requires db_manager for initialization.
    # See README.md Architecture section for details.
    db_manager = get_db_manager()
    tradernet_client = get_tradernet_client()
    exchange_rate_service = get_exchange_rate_service(db_manager)

    service = RebalancingService(
        stock_repo=stock_repo,  # type: ignore[arg-type]
        position_repo=position_repo,
        allocation_repo=allocation_repo,
        portfolio_repo=portfolio_repo,
        trade_repo=trade_repo,  # type: ignore[arg-type]
        settings_repo=settings_repo,
        recommendation_repo=recommendation_repo,
        db_manager=db_manager,
        tradernet_client=tradernet_client,
        exchange_rate_service=exchange_rate_service,
    )
    steps = await service.get_recommendations()

    if not steps:
        logger.info("Holistic planner returned no recommendations")
        return None

    step = steps[0]
    logger.info(f"Fresh holistic recommendation: {step.side} {step.symbol}")

    # Convert MultiStepRecommendation to Recommendation
    currency_val = step.currency
    if isinstance(currency_val, str):
        currency = Currency.from_string(currency_val)
    else:
        currency = currency_val

    # Convert side string to TradeSide if needed
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


async def _refresh_recommendation_cache():
    """Refresh the recommendation cache for the LED ticker display."""
    from app.application.services.rebalancing_service import RebalancingService
    from app.domain.portfolio_hash import generate_recommendation_cache_key
    from app.domain.services.settings_service import SettingsService

    try:
        # Create repos once and reuse
        settings_repo = SettingsRepository()
        position_repo = PositionRepository()
        stock_repo = StockRepository()
        allocation_repo = AllocationRepository()
        settings_service = SettingsService(settings_repo)
        rebalancing_service = RebalancingService(settings_repo=settings_repo)
        client = get_tradernet_client()

        # Generate portfolio-aware cache key
        positions = await position_repo.get_all()
        stocks = await stock_repo.get_all_active()
        settings = await settings_service.get_settings()
        allocations = await allocation_repo.get_all()
        position_dicts = [
            {"symbol": p.symbol, "quantity": p.quantity} for p in positions
        ]
        cash_balances = (
            {b.currency: b.amount for b in client.get_cash_balances()}
            if client.is_connected
            else {}
        )

        # Fetch pending orders for cache key
        pending_orders = []
        if client.is_connected:
            try:
                pending_orders = client.get_pending_orders()
            except Exception as e:
                logger.warning(f"Failed to fetch pending orders: {e}")

        portfolio_cache_key = generate_recommendation_cache_key(
            position_dicts,
            settings.to_dict(),
            stocks,
            cash_balances,
            allocations,
            pending_orders,
        )
        cache_key = f"recommendations:{portfolio_cache_key}"

        # Get multi-step recommendations (holistic planner auto-tests depths per max_plan_depth setting)
        multi_step_steps = await rebalancing_service.get_recommendations()
        if multi_step_steps:
            multi_step_data = {
                "depth": len(multi_step_steps),
                "steps": [
                    {
                        "step": step.step,
                        "side": step.side,
                        "symbol": step.symbol,
                        "name": step.name,
                        "quantity": step.quantity,
                        "estimated_price": step.estimated_price,
                        "estimated_value": step.estimated_value,
                        "currency": step.currency,
                        "reason": step.reason,
                        "portfolio_score_before": step.portfolio_score_before,
                        "portfolio_score_after": step.portfolio_score_after,
                        "score_change": step.score_change,
                        "available_cash_before": step.available_cash_before,
                        "available_cash_after": step.available_cash_after,
                    }
                    for step in multi_step_steps
                ],
                "total_score_improvement": (
                    (
                        multi_step_steps[-1].portfolio_score_after
                        - multi_step_steps[0].portfolio_score_before
                    )
                    if multi_step_steps
                    else 0.0
                ),
                "final_available_cash": (
                    multi_step_steps[-1].available_cash_after
                    if multi_step_steps
                    else 0.0
                ),
            }
            # Cache to portfolio-hash-based key (single source of truth)
            cache.set(cache_key, multi_step_data, ttl_seconds=900)
            logger.info(
                f"Recommendation cache refreshed: {len(multi_step_steps)} steps (key: {cache_key})"
            )

    except Exception as e:
        logger.warning(f"Failed to refresh recommendation cache: {e}")
