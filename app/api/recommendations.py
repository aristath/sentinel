"""Unified recommendations API endpoint.

Handles all recommendations via the holistic planner. The app always executes
the first step from the sequence, then recalculates for the next execution.
"""

import json
import logging
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.infrastructure.cache import cache
from app.infrastructure.dependencies import (
    AllocationRepositoryDep,
    PositionRepositoryDep,
    RebalancingServiceDep,
    SettingsServiceDep,
    StockRepositoryDep,
    TradeExecutionServiceDep,
    TradeRepositoryDep,
    TradernetClientDep,
    TradeSafetyServiceDep,
)

logger = logging.getLogger(__name__)
router = APIRouter()


async def _execute_single_step(
    idx: int,
    step: dict,
    client,
    safety_service,
    trade_execution_service,
) -> dict:
    """Execute a single step in the recommendation sequence."""
    try:
        has_pending = await safety_service.check_pending_orders(
            step["symbol"], step["side"], client
        )

        if has_pending:
            logger.warning(
                f"Step {idx} blocked: pending order exists for {step['symbol']}"
            )
            return {
                "step": idx,
                "status": "blocked",
                "symbol": step["symbol"],
                "error": f"A pending order already exists for {step['symbol']}",
            }

        result = client.place_order(
            symbol=step["symbol"],
            side=step["side"],
            quantity=step["quantity"],
        )

        if result:
            await trade_execution_service.record_trade(
                symbol=step["symbol"],
                side=step["side"],
                quantity=step["quantity"],
                price=result.price,
                order_id=result.order_id,
            )

            return {
                "step": idx,
                "status": "success",
                "order_id": result.order_id,
                "symbol": step["symbol"],
                "side": step["side"],
                "quantity": step["quantity"],
                "price": result.price,
                "estimated_value": step["estimated_value"],
            }
        else:
            return {
                "step": idx,
                "status": "failed",
                "symbol": step["symbol"],
                "error": "Trade execution failed",
            }

    except Exception as e:
        logger.error(f"Error executing step {idx}: {e}", exc_info=True)
        return {
            "step": idx,
            "status": "failed",
            "symbol": step["symbol"],
            "error": str(e),
        }


@router.get("")
async def get_recommendations(
    position_repo: PositionRepositoryDep,
    settings_service: SettingsServiceDep,
    rebalancing_service: RebalancingServiceDep,
    stock_repo: StockRepositoryDep,
    allocation_repo: AllocationRepositoryDep,
    tradernet_client: TradernetClientDep,
):
    """
    Get recommendation sequence using the holistic planner.

    The holistic planner automatically tests all depths (configurable via
    max_plan_depth setting, default 1-5) and returns the sequence with the
    best end-state score. Only the first step is executed.

    Returns:
        Recommendation sequence with portfolio state at each step.
    """
    from app.domain.portfolio_hash import generate_recommendation_cache_key

    # Generate portfolio-aware cache key
    positions = await position_repo.get_all()
    settings = await settings_service.get_settings()
    stocks = await stock_repo.get_all_active()
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

    # Check if incremental mode is enabled - if so, skip cache and check database first
    from app.repositories import SettingsRepository

    settings_repo = SettingsRepository()
    incremental_enabled = (
        await settings_repo.get_float("incremental_planner_enabled", 1.0) == 1.0
    )

    # If incremental mode is enabled, check database first (don't use stale cache)
    if incremental_enabled:
        from app.domain.portfolio_hash import generate_portfolio_hash
        from app.repositories.planner_repository import PlannerRepository

        planner_repo = PlannerRepository()
        portfolio_hash = generate_portfolio_hash(position_dicts, stocks)
        best_result = await planner_repo.get_best_result(portfolio_hash)

        if best_result:
            # We have a database result - invalidate cache and use database result
            cache.invalidate(cache_key)
            logger.info("Incremental mode: invalidating cache, using database result")
        else:
            # No database result yet for this portfolio hash
            # Don't use stale cache - generate fresh recommendations instead
            logger.info(
                f"Incremental mode: No database result for portfolio hash {portfolio_hash}, "
                "generating fresh recommendations"
            )
            cache.invalidate(cache_key)  # Invalidate any stale cache
    else:
        # Incremental mode disabled - use cache normally
        cached = cache.get(cache_key)
        if cached is not None:
            # Add evaluation count to cached result
            from app.domain.portfolio_hash import generate_portfolio_hash
            from app.repositories.planner_repository import PlannerRepository

            portfolio_hash = generate_portfolio_hash(position_dicts, stocks)
            planner_repo = PlannerRepository()
            evaluated_count = await planner_repo.get_evaluation_count(portfolio_hash)
            cached["evaluated_count"] = evaluated_count
            return cached

    try:
        steps = await rebalancing_service.get_recommendations()

        # Get evaluation count
        from app.domain.portfolio_hash import generate_portfolio_hash
        from app.repositories.planner_repository import PlannerRepository

        portfolio_hash = generate_portfolio_hash(position_dicts, stocks)
        planner_repo = PlannerRepository()
        evaluated_count = await planner_repo.get_evaluation_count(portfolio_hash)

        if not steps:
            # Get evaluation count even if no steps
            from app.domain.portfolio_hash import generate_portfolio_hash
            from app.repositories.planner_repository import PlannerRepository

            portfolio_hash = generate_portfolio_hash(position_dicts, stocks)
            planner_repo = PlannerRepository()
            evaluated_count = await planner_repo.get_evaluation_count(portfolio_hash)

            return {
                "depth": 0,
                "steps": [],
                "total_score_improvement": 0.0,
                "final_available_cash": 0.0,
                "evaluated_count": evaluated_count,
            }

        # Calculate totals
        # Total improvement is the difference between initial and final portfolio scores
        if steps:
            total_score_improvement = (
                steps[-1].portfolio_score_after - steps[0].portfolio_score_before
            )
        else:
            total_score_improvement = 0.0
        final_available_cash = steps[-1].available_cash_after if steps else 0.0

        result = {
            "depth": len(steps),
            "steps": [
                {
                    "step": step.step,
                    "side": step.side,
                    "symbol": step.symbol,
                    "name": step.name,
                    "quantity": step.quantity,
                    "estimated_price": round(step.estimated_price, 2),
                    "estimated_value": round(step.estimated_value, 2),
                    "currency": step.currency,
                    "reason": step.reason,
                    "portfolio_score_before": round(step.portfolio_score_before, 1),
                    "portfolio_score_after": round(step.portfolio_score_after, 1),
                    "score_change": round(step.score_change, 2),
                    "available_cash_before": round(step.available_cash_before, 2),
                    "available_cash_after": round(step.available_cash_after, 2),
                }
                for step in steps
            ],
            "total_score_improvement": round(total_score_improvement, 2),
            "final_available_cash": round(final_available_cash, 2),
            "evaluated_count": evaluated_count,
        }

        # Cache for 5 minutes
        cache.set(cache_key, result, ttl_seconds=300)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating recommendations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stream")
async def stream_recommendation_updates():
    """Stream recommendation update notifications via Server-Sent Events (SSE).

    Real-time streaming of recommendation invalidation events. When recommendations
    are invalidated (due to trades, settings changes, etc.), clients are notified
    to refresh their recommendations.
    """
    from app.infrastructure import recommendation_events

    async def event_generator() -> AsyncIterator[str]:
        """Generate SSE events from recommendation invalidation changes."""
        import asyncio

        logger.info("SSE stream connection established")
        try:
            # Subscribe to recommendation events
            async for (
                invalidation_data
            ) in recommendation_events.subscribe_recommendation_events():
                # Format as SSE event: data: {json}\n\n
                event_data = json.dumps(invalidation_data)
                yield f"data: {event_data}\n\n"

        except asyncio.CancelledError:
            logger.info("SSE stream connection cancelled")
            raise
        except Exception as e:
            logger.error(f"SSE stream error: {e}", exc_info=True)
            # Send error event and close
            error_data = json.dumps({"error": "Stream closed", "message": str(e)})
            yield f"data: {error_data}\n\n"
        finally:
            logger.info("SSE stream connection closed")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _regenerate_recommendations_cache(
    position_repo: PositionRepositoryDep,
    settings_service: SettingsServiceDep,
    rebalancing_service: RebalancingServiceDep,
    stock_repo: StockRepositoryDep,
    allocation_repo: AllocationRepositoryDep,
    tradernet_client: TradernetClientDep,
) -> tuple:
    """
    Regenerate recommendations cache if missing.

    Returns:
        Tuple of (cached_data, cache_key) - the recommendations dict and the portfolio-aware cache key

    Raises:
        HTTPException: If no recommendations are available
    """
    from app.domain.portfolio_hash import generate_recommendation_cache_key

    positions = await position_repo.get_all()
    settings = await settings_service.get_settings()
    stocks = await stock_repo.get_all_active()
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

    logger.info("Cache miss for recommendations, regenerating...")
    steps_data = await rebalancing_service.get_recommendations()

    if not steps_data:
        raise HTTPException(
            status_code=404,
            detail="No recommendations available. Please check your portfolio and settings.",
        )

    # Rebuild cached format
    # Total improvement is the difference between initial and final portfolio scores
    if steps_data:
        total_score_improvement = (
            steps_data[-1].portfolio_score_after - steps_data[0].portfolio_score_before
        )
    else:
        total_score_improvement = 0.0
    final_available_cash = steps_data[-1].available_cash_after if steps_data else 0.0

    cached = {
        "depth": len(steps_data),
        "steps": [
            {
                "step": step.step,
                "side": step.side,
                "symbol": step.symbol,
                "name": step.name,
                "quantity": step.quantity,
                "estimated_price": round(step.estimated_price, 2),
                "estimated_value": round(step.estimated_value, 2),
                "currency": step.currency,
                "reason": step.reason,
                "portfolio_score_before": round(step.portfolio_score_before, 1),
                "portfolio_score_after": round(step.portfolio_score_after, 1),
                "score_change": round(step.score_change, 2),
                "available_cash_before": round(step.available_cash_before, 2),
                "available_cash_after": round(step.available_cash_after, 2),
            }
            for step in steps_data
        ],
        "total_score_improvement": round(total_score_improvement, 2),
        "final_available_cash": round(final_available_cash, 2),
    }
    # Cache the regenerated recommendations
    cache.set(cache_key, cached, ttl_seconds=300)
    return cached, cache_key


@router.post("/execute")
async def execute_recommendation(
    trade_repo: TradeRepositoryDep,
    position_repo: PositionRepositoryDep,
    settings_service: SettingsServiceDep,
    safety_service: TradeSafetyServiceDep,
    trade_execution_service: TradeExecutionServiceDep,
    rebalancing_service: RebalancingServiceDep,
    stock_repo: StockRepositoryDep,
    allocation_repo: AllocationRepositoryDep,
    tradernet_client: TradernetClientDep,
):
    """
    Execute the first step from the recommendation sequence.

    The app always executes the first step, then recalculates the sequence
    for the next execution. No step_number parameter needed.

    Returns:
        Execution result for the first step
    """
    from app.domain.portfolio_hash import generate_recommendation_cache_key
    from app.infrastructure.cache_invalidation import get_cache_invalidation_service
    from app.infrastructure.external.tradernet_connection import (
        ensure_tradernet_connected,
    )

    try:
        # Generate portfolio-aware cache key
        positions = await position_repo.get_all()
        settings = await settings_service.get_settings()
        stocks = await stock_repo.get_all_active()
        allocations = await allocation_repo.get_all()
        position_dicts = [
            {"symbol": p.symbol, "quantity": p.quantity} for p in positions
        ]
        cash_balances = (
            {b.currency: b.amount for b in tradernet_client.get_cash_balances()}
            if tradernet_client.is_connected
            else {}
        )
        portfolio_cache_key = generate_recommendation_cache_key(
            position_dicts, settings.to_dict(), stocks, cash_balances, allocations
        )
        cache_key = f"recommendations:{portfolio_cache_key}"

        cached = cache.get(cache_key)

        # If cache miss, regenerate recommendations
        if not cached or not cached.get("steps"):
            cached, cache_key = await _regenerate_recommendations_cache(
                position_repo,
                settings_service,
                rebalancing_service,
                stock_repo,
                allocation_repo,
                tradernet_client,
            )

        steps = cached["steps"]
        if not steps:
            raise HTTPException(
                status_code=404,
                detail="No steps available in recommendations.",
            )

        # Always execute first step (step 1)
        step = steps[0]

        # Ensure connection
        client = await ensure_tradernet_connected()

        # Safety checks
        await safety_service.validate_trade(
            symbol=step["symbol"],
            side=step["side"],
            quantity=step["quantity"],
            client=client,
            raise_on_error=True,
        )

        # Execute the trade
        result = client.place_order(
            symbol=step["symbol"],
            side=step["side"],
            quantity=step["quantity"],
        )

        if result:
            # Record the trade
            await trade_execution_service.record_trade(
                symbol=step["symbol"],
                side=step["side"],
                quantity=step["quantity"],
                price=result.price,
                order_id=result.order_id,
            )

            # Invalidate caches
            cache_service = get_cache_invalidation_service()
            cache_service.invalidate_trade_caches()

            return {
                "status": "success",
                "step": 1,  # Always step 1
                "order_id": result.order_id,
                "symbol": step["symbol"],
                "side": step["side"],
                "quantity": step["quantity"],
                "price": result.price,
                "estimated_value": step["estimated_value"],
            }

        raise HTTPException(status_code=500, detail="Trade execution failed")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing recommendation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
