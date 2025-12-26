"""Multi-step recommendation API endpoints.

Handles holistic multi-step recommendation sequences.
"""

import logging

from fastapi import APIRouter, HTTPException

from app.domain.value_objects.trade_side import TradeSide
from app.infrastructure.cache import cache
from app.infrastructure.dependencies import (
    PositionRepositoryDep,
    RebalancingServiceDep,
    RecommendationRepositoryDep,
    SettingsServiceDep,
    TradeExecutionServiceDep,
    TradeRepositoryDep,
    TradeSafetyServiceDep,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("")
async def get_multi_step_recommendations(
    position_repo: PositionRepositoryDep,
    settings_service: SettingsServiceDep,
    rebalancing_service: RebalancingServiceDep,
):
    """
    Get multi-step recommendation sequence using the holistic planner.

    The holistic planner automatically tests all depths (1-5) and returns
    the sequence with the best end-state score.

    Returns:
        Multi-step recommendation sequence with portfolio state at each step.
    """
    from app.domain.portfolio_hash import generate_recommendation_cache_key

    # Generate portfolio-aware cache key
    positions = await position_repo.get_all()
    settings = await settings_service.get_settings()
    position_dicts = [{"symbol": p.symbol, "quantity": p.quantity} for p in positions]
    portfolio_cache_key = generate_recommendation_cache_key(
        position_dicts, settings.to_dict()
    )
    cache_key = f"multi_step_recommendations:{portfolio_cache_key}"

    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        steps = await rebalancing_service.get_multi_step_recommendations()

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
        logger.error(f"Error generating multi-step recommendations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def _regenerate_multi_step_cache(
    position_repo: PositionRepositoryDep,
    settings_service: SettingsServiceDep,
    rebalancing_service: RebalancingServiceDep,
) -> tuple:
    """
    Regenerate multi-step recommendations cache if missing.

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
    cache_key = f"multi_step_recommendations:{portfolio_cache_key}"

    logger.info("Cache miss for multi-step recommendations, regenerating...")
    steps_data = await rebalancing_service.get_multi_step_recommendations()

    if not steps_data:
        raise HTTPException(
            status_code=404,
            detail="No multi-step recommendations available. Please check your portfolio and settings.",
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


@router.post("/execute-step/{step_number}")
async def execute_multi_step_recommendation_step(
    step_number: int,
    trade_repo: TradeRepositoryDep,
    position_repo: PositionRepositoryDep,
    settings_service: SettingsServiceDep,
    safety_service: TradeSafetyServiceDep,
    trade_execution_service: TradeExecutionServiceDep,
    rebalancing_service: RebalancingServiceDep,
):
    """
    Execute a single step from the multi-step recommendation sequence.

    Args:
        step_number: The step number (1-indexed) to execute

    Returns:
        Execution result for the step
    """
    from app.domain.portfolio_hash import generate_recommendation_cache_key
    from app.infrastructure.cache_invalidation import get_cache_invalidation_service
    from app.infrastructure.external.tradernet_connection import (
        ensure_tradernet_connected,
    )

    if step_number < 1:
        raise HTTPException(status_code=400, detail="Step number must be >= 1")
    if step_number > 5:
        raise HTTPException(
            status_code=400, detail="Step number must be between 1 and 5"
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
        cache_key = f"multi_step_recommendations:{portfolio_cache_key}"

        cached = cache.get(cache_key)

        # If cache miss, regenerate recommendations
        if not cached or not cached.get("steps"):
            cached, cache_key = await _regenerate_multi_step_cache(
                position_repo, settings_service, rebalancing_service
            )

        steps = cached["steps"]
        if step_number > len(steps):
            raise HTTPException(
                status_code=404,
                detail=f"Step {step_number} not found. Only {len(steps)} steps available.",
            )

        step = steps[step_number - 1]  # Convert to 0-indexed

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
                "step": step_number,
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
        logger.error(
            f"Error executing multi-step recommendation step {step_number}: {e}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute-all")
async def execute_all_multi_step_recommendations(
    trade_repo: TradeRepositoryDep,
    position_repo: PositionRepositoryDep,
    settings_service: SettingsServiceDep,
    safety_service: TradeSafetyServiceDep,
    trade_execution_service: TradeExecutionServiceDep,
    rebalancing_service: RebalancingServiceDep,
):
    """
    Execute all steps in the multi-step recommendation sequence in order.

    Executes each step sequentially, continuing with remaining steps if any step fails.

    Returns:
        List of execution results for each step
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
        cache_key = f"multi_step_recommendations:{portfolio_cache_key}"

        cached = cache.get(cache_key)

        # If cache miss, regenerate recommendations
        if not cached or not cached.get("steps"):
            cached, cache_key = await _regenerate_multi_step_cache(
                position_repo, settings_service, rebalancing_service
            )

        steps = cached["steps"]
        if not steps:
            raise HTTPException(
                status_code=404,
                detail="No steps available in multi-step recommendations",
            )

        # Ensure connection
        client = await ensure_tradernet_connected()

        # Check cooldown for all BUY steps
        buy_steps = [s for s in steps if s["side"] == TradeSide.BUY]
        blocked_buys = []
        for step in buy_steps:
            is_cooldown, error = await safety_service.check_cooldown(
                step["symbol"], step["side"]
            )
            if is_cooldown:
                blocked_buys.append(step)

        if blocked_buys:
            symbols = ", ".join([s["symbol"] for s in blocked_buys])
            raise HTTPException(
                status_code=400, detail=f"Cannot execute: {symbols} in cooldown period"
            )

        results = []

        for idx, step in enumerate(steps, start=1):
            result = await _execute_single_step(
                idx, step, client, safety_service, trade_execution_service
            )
            results.append(result)

        # Invalidate caches after execution
        cache_service = get_cache_invalidation_service()
        cache_service.invalidate_trade_caches()

        return {
            "status": "complete",
            "results": results,
            "total_steps": len(steps),
            "successful": len([r for r in results if r["status"] == "success"]),
            "failed": len([r for r in results if r["status"] == "failed"]),
            "blocked": len([r for r in results if r["status"] == "blocked"]),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error executing all multi-step recommendations: {e}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategies")
async def list_recommendation_strategies():
    """
    List available recommendation strategies.

    Returns list of strategy names and descriptions.
    """
    return {
        "strategies": [
            {
                "name": "portfolio-aware",
                "description": "Portfolio-aware recommendations using long-term value scoring with allocation fit",
            },
        ]
    }


@router.get("/all")
async def get_all_strategy_recommendations(
    rebalancing_service: RebalancingServiceDep,
    recommendation_repo: RecommendationRepositoryDep,
):
    """
    Get recommendations from all strategies.

    Currently only supports 'portfolio-aware' strategy.
    """

    # Generate recommendations
    await rebalancing_service.get_recommendations(limit=50)

    # Get all pending BUY recommendations
    stored_recs = await recommendation_repo.get_pending_by_side("BUY", limit=50)

    return {
        "strategies": {
            "portfolio-aware": {
                "recommendations": [
                    {
                        "uuid": rec["uuid"],
                        "symbol": rec["symbol"],
                        "name": rec["name"],
                        "amount": rec["amount"],
                        "priority": rec.get("priority"),
                        "reason": rec["reason"],
                        "geography": rec.get("geography"),
                        "industry": rec.get("industry"),
                        "current_price": rec.get("estimated_price"),
                        "quantity": rec.get("quantity"),
                        "current_portfolio_score": rec.get("current_portfolio_score"),
                        "new_portfolio_score": rec.get("new_portfolio_score"),
                        "score_change": rec.get("score_change"),
                    }
                    for rec in stored_recs
                ],
            },
        }
    }
