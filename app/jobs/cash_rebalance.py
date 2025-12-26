"""Cash-based rebalance job with drip execution strategy.

Executes ONE trade per cycle (15 minutes) with fresh data before each decision.
Priority: SELL before BUY.
"""

import logging
from typing import TYPE_CHECKING

from app.config import settings
from app.domain.scoring import PortfolioContext
from app.infrastructure.cache import cache
from app.infrastructure.daily_pnl import get_daily_pnl_tracker
from app.infrastructure.database.manager import get_db_manager
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


async def _check_and_rebalance_internal():
    """Internal rebalance implementation with drip execution."""
    from app.application.services.trade_execution_service import TradeExecutionService
    from app.domain.constants import BUY_COOLDOWN_DAYS
    from app.domain.models import Recommendation
    from app.domain.value_objects.trade_side import TradeSide
    from app.infrastructure.external import yahoo_finance as yahoo
    from app.jobs.daily_sync import sync_portfolio
    from app.jobs.sync_trades import sync_trades

    logger.info("Starting trade cycle check...")

    emit(SystemEvent.REBALANCE_START)
    set_processing("CHECKING TRADE OPPORTUNITIES...")

    try:
        # Step 0: Sync trades from Tradernet for accurate cooldown calculations
        logger.info("Step 0: Syncing trades from Tradernet...")
        await sync_trades()

        # Step 1: Sync portfolio for fresh data
        logger.info("Step 1: Syncing portfolio for fresh data...")
        await sync_portfolio()

        # GUARDRAIL: Check daily P&L circuit breaker
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
            return

        # Get configurable threshold from database
        from app.application.services.rebalancing_service import (
            calculate_min_trade_amount,
        )
        from app.domain.services.settings_service import SettingsService

        settings_service = SettingsService(SettingsRepository())
        settings = await settings_service.get_settings()
        # Calculate minimum worthwhile trade from transaction costs
        min_trade_size = calculate_min_trade_amount(
            settings.transaction_cost_fixed,
            settings.transaction_cost_percent,
        )

        # Connect to broker
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

        # Initialize repositories
        stock_repo = StockRepository()
        position_repo = PositionRepository()
        trade_repo = TradeRepository()
        allocation_repo = AllocationRepository()
        db_manager = get_db_manager()

        # Step 2: Build portfolio context
        logger.info("Step 2: Building portfolio context...")
        set_processing("BUILDING PORTFOLIO CONTEXT...")

        positions = await position_repo.get_all()
        stocks = await stock_repo.get_all_active()
        allocations = await allocation_repo.get_all()
        total_value = await position_repo.get_total_value()

        # Generate portfolio hash for recommendation matching
        from app.domain.portfolio_hash import generate_portfolio_hash

        position_hash_dicts = [
            {"symbol": p.symbol, "quantity": p.quantity} for p in positions
        ]
        portfolio_hash = generate_portfolio_hash(position_hash_dicts)

        # Build portfolio context for scoring
        # get_all() returns Dict[str, float] with keys like "geography:name"
        geo_weights = {}
        industry_weights = {}
        for key, target_pct in allocations.items():
            parts = key.split(":", 1)
            if len(parts) == 2:
                alloc_type, name = parts
                if alloc_type == "geography":
                    geo_weights[name] = target_pct
                elif alloc_type == "industry":
                    industry_weights[name] = target_pct

        position_map = {p.symbol: p.market_value_eur or 0 for p in positions}
        stock_geographies = {s.symbol: s.geography for s in stocks}
        stock_industries = {s.symbol: s.industry for s in stocks if s.industry}
        stock_scores = {}

        # Get existing scores
        score_rows = await db_manager.state.fetchall(
            "SELECT symbol, quality_score FROM scores"
        )
        for row in score_rows:
            if row["quality_score"]:
                stock_scores[row["symbol"]] = row["quality_score"]

        portfolio_context = PortfolioContext(
            geo_weights=geo_weights,
            industry_weights=industry_weights,
            positions=position_map,
            total_value=total_value if total_value > 0 else 1.0,
            stock_geographies=stock_geographies,
            stock_industries=stock_industries,
            stock_scores=stock_scores,
        )

        # Step 3: Get next action from holistic planner
        logger.info("Step 3: Getting recommendation from holistic planner...")
        set_processing("GETTING HOLISTIC RECOMMENDATION...")

        next_action = await _get_next_holistic_action()

        if not next_action:
            logger.info("No trades recommended this cycle")
            emit(SystemEvent.REBALANCE_COMPLETE)
            await _refresh_recommendation_cache()
            clear_processing()
            return

        # Check P&L guardrails for the recommended action
        if next_action.side == TradeSide.SELL and not pnl_status["can_sell"]:
            logger.info(
                f"SELL {next_action.symbol} blocked by P&L guardrail: {pnl_status['reason']}"
            )
            emit(SystemEvent.REBALANCE_COMPLETE)
            await _refresh_recommendation_cache()
            return

        if next_action.side == TradeSide.BUY and not pnl_status["can_buy"]:
            logger.info(
                f"BUY {next_action.symbol} blocked by P&L guardrail: {pnl_status['reason']}"
            )
            emit(SystemEvent.REBALANCE_COMPLETE)
            await _refresh_recommendation_cache()
            return

        # Check cash for BUY actions
        if next_action.side == TradeSide.BUY and cash_balance < min_trade_size:
            logger.info(
                f"Cash €{cash_balance:.2f} below threshold €{min_trade_size:.2f}, "
                f"skipping BUY {next_action.symbol}"
            )
            emit(SystemEvent.REBALANCE_COMPLETE)
            await _refresh_recommendation_cache()
            return

        # Additional safety check for SELL: verify no recent sell order
        if next_action.side == TradeSide.SELL:
            has_recent = await trade_repo.has_recent_sell_order(
                next_action.symbol, hours=2
            )
            if has_recent:
                logger.warning(
                    f"Skipping SELL {next_action.symbol}: recent sell order found "
                    f"(within last 2 hours)"
                )
                emit(SystemEvent.REBALANCE_COMPLETE)
                await _refresh_recommendation_cache()
                return

        # Execute the trade
        logger.info(
            f"Executing {next_action.side}: {next_action.quantity} {next_action.symbol} "
            f"@ €{next_action.estimated_price:.2f} = €{next_action.estimated_value:.2f} "
            f"({next_action.reason})"
        )

        emit(SystemEvent.SYNC_START)
        trade_execution = TradeExecutionService(trade_repo, position_repo)

        # Get currency balances for BUY trades
        currency_balances = None
        if next_action.side == TradeSide.BUY:
            currency_balances = {
                cb.currency: cb.amount for cb in client.get_cash_balances()
            }
            # Deduct pending order amounts
            pending_totals = client.get_pending_order_totals()
            if pending_totals:
                for currency, pending_amount in pending_totals.items():
                    if currency in currency_balances:
                        currency_balances[currency] = max(
                            0, currency_balances[currency] - pending_amount
                        )

        # Execute based on trade type
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
            logger.info(
                f"{next_action.side} executed successfully: {next_action.symbol}"
            )
            emit(SystemEvent.TRADE_EXECUTED, is_buy=(next_action.side == TradeSide.BUY))

            # Invalidate portfolio-hash-based caches (old portfolio is now stale)
            rec_cache = get_recommendation_cache()
            await rec_cache.invalidate_portfolio_hash(portfolio_hash)

            # Mark matching stored recommendations as executed
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
    settings_service = SettingsService(settings_repo)

    # Generate portfolio-aware cache key
    positions = await position_repo.get_all()
    settings = await settings_service.get_settings()
    position_dicts = [{"symbol": p.symbol, "quantity": p.quantity} for p in positions]
    portfolio_cache_key = generate_recommendation_cache_key(
        position_dicts, settings.to_dict()
    )
    cache_key = f"multi_step_recommendations:{portfolio_cache_key}"

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
            geography="",
            currency=currency,
            status=RecommendationStatus.PENDING,
        )

    # Cache miss - call planner directly
    logger.info("Cache miss, calling holistic planner directly...")
    service = RebalancingService()
    steps = await service.get_multi_step_recommendations()

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

    return Recommendation(
        symbol=step.symbol,
        name=step.name,
        side=step.side,
        quantity=step.quantity,
        estimated_price=step.estimated_price,
        estimated_value=step.estimated_value,
        reason=step.reason,
        geography="",
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
        settings_service = SettingsService(settings_repo)
        rebalancing_service = RebalancingService(settings_repo=settings_repo)

        # Generate portfolio-aware cache key
        positions = await position_repo.get_all()
        settings = await settings_service.get_settings()
        position_dicts = [
            {"symbol": p.symbol, "quantity": p.quantity} for p in positions
        ]
        portfolio_cache_key = generate_recommendation_cache_key(
            position_dicts, settings.to_dict()
        )
        cache_key = f"multi_step_recommendations:{portfolio_cache_key}"

        # Get multi-step recommendations (holistic planner auto-tests depths 1-5)
        multi_step_steps = await rebalancing_service.get_multi_step_recommendations()
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
                    multi_step_steps[0].score_change if multi_step_steps else 0.0
                ),
                "final_available_cash": (
                    multi_step_steps[-1].available_cash_after
                    if multi_step_steps
                    else 0.0
                ),
            }
            # Cache to portfolio-hash-based key (for _get_next_holistic_action)
            cache.set(cache_key, multi_step_data, ttl_seconds=900)
            logger.info(
                f"Multi-step recommendation cache refreshed: {len(multi_step_steps)} steps (key: {cache_key})"
            )

            # Also cache to fixed keys for LED ticker display
            # LED ticker looks for: multi_step_recommendations:diversification:{depth}:holistic
            # Use actual depth from holistic planner (it auto-determines optimal depth)
            depth = len(multi_step_steps)
            led_cache_key = (
                f"multi_step_recommendations:diversification:{depth}:holistic"
            )
            cache.set(led_cache_key, multi_step_data, ttl_seconds=900)
            cache.set(
                "multi_step_recommendations:diversification:default:holistic",
                multi_step_data,
                ttl_seconds=900,
            )
            logger.info(f"LED ticker cache refreshed: {led_cache_key}")

        # Always cache single recommendations (for fallback and depth=1)
        buy_recommendations = await rebalancing_service.get_recommendations(limit=3)
        buy_recs = {
            "recommendations": [
                {"symbol": r.symbol, "amount": r.estimated_value}
                for r in buy_recommendations
            ]
        }
        cache.set("recommendations:3", buy_recs, ttl_seconds=900)

        # Get sell recommendations
        sell_recommendations = await rebalancing_service.calculate_sell_recommendations(
            limit=3
        )
        sell_recs = {
            "recommendations": [
                {"symbol": r.symbol, "estimated_value": r.estimated_value}
                for r in sell_recommendations
            ]
        }
        cache.set("sell_recommendations:3", sell_recs, ttl_seconds=900)

        logger.info(
            f"Recommendation cache refreshed: {len(buy_recommendations)} buy, {len(sell_recommendations)} sell"
        )

    except Exception as e:
        logger.warning(f"Failed to refresh recommendation cache: {e}")
