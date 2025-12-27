"""Unified recommendations API endpoint.

Handles all recommendations via the holistic planner. The app always executes
the first step from the sequence, then recalculates for the next execution.
"""

import logging

from fastapi import APIRouter, HTTPException

from app.infrastructure.cache import cache
from app.infrastructure.dependencies import (
    PositionRepositoryDep,
    RebalancingServiceDep,
    SettingsServiceDep,
    TradeExecutionServiceDep,
    TradeRepositoryDep,
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
    position_dicts = [{"symbol": p.symbol, "quantity": p.quantity} for p in positions]
    portfolio_cache_key = generate_recommendation_cache_key(
        position_dicts, settings.to_dict()
    )
    cache_key = f"recommendations:{portfolio_cache_key}"

    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        steps = await rebalancing_service.get_recommendations()

        if not steps:
            return {
                "depth": 0,
                "steps": [],
                "total_score_improvement": 0.0,
                "final_available_cash": 0.0,
            }

        # Calculate totals
        total_score_improvement = steps[0].score_change if steps else 0.0
        final_available_cash = steps[-1].available_cash_after

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
        }

        # Cache for 5 minutes
        cache.set(cache_key, result, ttl_seconds=300)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating recommendations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def _regenerate_recommendations_cache(
    position_repo: PositionRepositoryDep,
    settings_service: SettingsServiceDep,
    rebalancing_service: RebalancingServiceDep,
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
    position_dicts = [{"symbol": p.symbol, "quantity": p.quantity} for p in positions]
    portfolio_cache_key = generate_recommendation_cache_key(
        position_dicts, settings.to_dict()
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
    total_score_improvement = steps_data[0].score_change if steps_data else 0.0
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
        position_dicts = [
            {"symbol": p.symbol, "quantity": p.quantity} for p in positions
        ]
        portfolio_cache_key = generate_recommendation_cache_key(
            position_dicts, settings.to_dict()
        )
        cache_key = f"recommendations:{portfolio_cache_key}"

        cached = cache.get(cache_key)

        # If cache miss, regenerate recommendations
        if not cached or not cached.get("steps"):
            cached, cache_key = await _regenerate_recommendations_cache(
                position_repo, settings_service, rebalancing_service
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
