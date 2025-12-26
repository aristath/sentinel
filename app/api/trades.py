"""Trade execution API endpoints."""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator
from app.domain.value_objects.trade_side import TradeSide
from app.infrastructure.dependencies import (
    StockRepositoryDep,
    PositionRepositoryDep,
    TradeRepositoryDep,
    RecommendationRepositoryDep,
    SettingsServiceDep,
    TradeSafetyServiceDep,
    TradeExecutionServiceDep,
    PortfolioServiceDep,
    RebalancingServiceDep,
)
from app.infrastructure.cache import cache
from app.infrastructure.cache_invalidation import get_cache_invalidation_service
from app.infrastructure.external.tradernet_connection import ensure_tradernet_connected

logger = logging.getLogger(__name__)
router = APIRouter()


class TradeRequest(BaseModel):
    symbol: str = Field(..., min_length=1, description="Stock symbol")
    side: TradeSide = Field(..., description="Trade side: BUY or SELL")
    quantity: float = Field(..., gt=0, description="Quantity to trade (must be positive)")

    @field_validator('symbol')
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        """Validate and normalize symbol."""
        return v.upper().strip()

    @field_validator('quantity')
    @classmethod
    def validate_quantity(cls, v: float) -> float:
        """Validate quantity is reasonable."""
        if v <= 0:
            raise ValueError("Quantity must be greater than 0")
        if v > 1000000:  # Reasonable upper limit
            raise ValueError("Quantity exceeds maximum allowed (1,000,000)")
        return v


@router.get("")
async def get_trades(trade_repo: TradeRepositoryDep, limit: int = 50):
    """Get trade history."""
    trades = await trade_repo.get_history(limit=limit)
    return [
        {
            "id": t.id,
            "symbol": t.symbol,
            "side": t.side,
            "quantity": t.quantity,
            "price": t.price,
            "executed_at": t.executed_at.isoformat() if t.executed_at else None,
            "order_id": t.order_id,
        }
        for t in trades
    ]


@router.post("/execute")
async def execute_trade(
    trade: TradeRequest,
    stock_repo: StockRepositoryDep,
    trade_repo: TradeRepositoryDep,
    position_repo: PositionRepositoryDep,
    safety_service: TradeSafetyServiceDep,
    trade_execution_service: TradeExecutionServiceDep,
):
    """Execute a manual trade."""
    # Check stock exists
    stock = await stock_repo.get_by_symbol(trade.symbol)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    # Ensure connection
    client = await ensure_tradernet_connected()
    await safety_service.validate_trade(
        symbol=trade.symbol,
        side=trade.side,
        quantity=trade.quantity,
        client=client,
        raise_on_error=True
    )

    result = client.place_order(
        symbol=trade.symbol,
        side=trade.side,
        quantity=trade.quantity,
    )

    if result:
        # Record trade using service
        await trade_execution_service.record_trade(
            symbol=trade.symbol,
            side=trade.side,
            quantity=trade.quantity,
            price=result.price,
            order_id=result.order_id,
        )

        # Invalidate caches
        cache_service = get_cache_invalidation_service()
        cache_service.invalidate_trade_caches()

        return {
            "status": "success",
            "order_id": result.order_id,
            "symbol": trade.symbol,
            "side": trade.side,
            "quantity": trade.quantity,
            "price": result.price,
        }

    raise HTTPException(status_code=500, detail="Trade execution failed")


@router.get("/allocation")
async def get_allocation(portfolio_service: PortfolioServiceDep):
    """Get current portfolio allocation vs targets."""
    summary = await portfolio_service.get_portfolio_summary()

    return {
        "total_value": summary.total_value,
        "cash_balance": summary.cash_balance,
        "geographic": [
            {
                "name": a.name,
                "target_pct": a.target_pct,
                "current_pct": a.current_pct,
                "current_value": a.current_value,
                "deviation": a.deviation,
            }
            for a in summary.geographic_allocations
        ],
        "industry": [
            {
                "name": a.name,
                "target_pct": a.target_pct,
                "current_pct": a.current_pct,
                "current_value": a.current_value,
                "deviation": a.deviation,
            }
            for a in summary.industry_allocations
        ],
    }


@router.get("/recommendations/debug")
async def debug_recommendations(
    rebalancing_service: RebalancingServiceDep,
):
    """
    Debug endpoint to see why recommendations are filtered out.
    """
    debug_info = await rebalancing_service.get_recommendations_debug()
    return debug_info


@router.get("/recommendations")
async def get_recommendations(
    rebalancing_service: RebalancingServiceDep,
    recommendation_repo: RecommendationRepositoryDep,
    limit: int = 3,
):
    """
    Get top N trade recommendations from database (status='pending').

    Returns prioritized list of stocks to buy next, with fixed trade amounts.
    Recommendations are generated and stored when this endpoint is called,
    then filtered to exclude dismissed ones.
    Cached for 5 minutes.
    """
    # Check cache first, but validate it has UUIDs (invalidate if old format)
    cache_key = f"recommendations:{limit}"
    cached = cache.get(cache_key)
    if cached is not None:
        # Validate cached data has UUIDs (new format)
        if cached.get("recommendations") and len(cached.get("recommendations", [])) > 0:
            first_rec = cached["recommendations"][0]
            if "uuid" in first_rec:
                return cached
        # Cache is old format without UUIDs, invalidate it
        cache.invalidate(cache_key)

    try:
        # Generate recommendations (this will store them in the database)
        await rebalancing_service.get_recommendations(limit=limit)

        # Get stored pending BUY recommendations from database
        stored_recs = await recommendation_repo.get_pending_by_side("BUY", limit=limit)

        result = {
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
        }

        # Cache for 5 minutes
        cache.set(cache_key, result, ttl_seconds=300)
        return result
    except Exception as e:
        logger.error(f"Error getting recommendations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recommendations/{uuid}/dismiss")
async def dismiss_recommendation(
    uuid: str,
    recommendation_repo: RecommendationRepositoryDep,
):
    """
    Dismiss a recommendation by UUID.

    Marks the recommendation as dismissed, preventing it from appearing again.
    """
    try:
        
        # Check if recommendation exists
        rec = await recommendation_repo.get_by_uuid(uuid)
        if not rec:
            raise HTTPException(status_code=404, detail=f"Recommendation {uuid} not found")

        # Mark as dismissed
        await recommendation_repo.mark_dismissed(uuid)

        # Invalidate caches
        cache_service = get_cache_invalidation_service()
        cache_service.invalidate_recommendation_caches()

        return {"status": "success", "uuid": uuid, "message": "Recommendation dismissed"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error dismissing recommendation {uuid}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sell-recommendations")
async def get_sell_recommendations(
    rebalancing_service: RebalancingServiceDep,
    recommendation_repo: RecommendationRepositoryDep,
    limit: int = 3,
):
    """
    Get top N sell recommendations from database (status='pending').

    Returns prioritized list of positions to sell, with quantities and reasons.
    Recommendations are generated and stored when this endpoint is called,
    then filtered to exclude dismissed ones.
    Cached for 5 minutes.
    """
    cache_key = f"sell_recommendations:{limit}"
    cached = cache.get(cache_key)
    if cached is not None:
        # Validate cached data has UUIDs (invalidate if old format)
        if cached.get("recommendations") and len(cached.get("recommendations", [])) > 0:
            first_rec = cached["recommendations"][0]
            if "uuid" in first_rec:
                return cached
        # Cache is old format without UUIDs, invalidate it
        cache.invalidate(cache_key)

    try:
        # Generate sell recommendations (this will store them in the database)
        await rebalancing_service.calculate_sell_recommendations(limit=limit)

        # Get stored pending SELL recommendations from database
        stored_recs = await recommendation_repo.get_pending_by_side("SELL", limit=limit)

        result = {
            "recommendations": [
                {
                    "uuid": rec["uuid"],
                    "symbol": rec["symbol"],
                    "name": rec["name"],
                    "side": rec["side"],
                    "quantity": rec.get("quantity"),
                    "estimated_price": rec.get("estimated_price"),
                    "estimated_value": rec.get("estimated_value"),
                    "reason": rec["reason"],
                    "currency": rec.get("currency", "EUR"),
                }
                for rec in stored_recs
            ],
        }

        cache.set(cache_key, result, ttl_seconds=300)
        return result
    except Exception as e:
        logger.error(f"Error getting sell recommendations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sell-recommendations/{uuid}/dismiss")
async def dismiss_sell_recommendation(
    uuid: str,
    recommendation_repo: RecommendationRepositoryDep,
):
    """
    Dismiss a sell recommendation by UUID.

    Marks the recommendation as dismissed, preventing it from appearing again.
    """
    try:
        
        # Check if recommendation exists
        rec = await recommendation_repo.get_by_uuid(uuid)
        if not rec:
            raise HTTPException(status_code=404, detail=f"Recommendation {uuid} not found")

        # Mark as dismissed
        await recommendation_repo.mark_dismissed(uuid)

        # Invalidate caches
        cache_service = get_cache_invalidation_service()
        cache_service.invalidate_recommendation_caches()

        return {"status": "success", "uuid": uuid, "message": "Sell recommendation dismissed"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error dismissing sell recommendation {uuid}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/multi-step-recommendations/strategies")
async def list_recommendation_strategies():
    """
    List available recommendation strategies.

    Returns:
        Dictionary with the holistic planner as the only strategy.
    """
    return {
        "strategies": {
            "holistic": "End-state optimization planner that tests all depths (1-5) automatically"
        }
    }


@router.get("/multi-step-recommendations/all")
async def get_all_strategy_recommendations(
    position_repo: PositionRepositoryDep,
    settings_service: SettingsServiceDep,
    rebalancing_service: RebalancingServiceDep,
):
    """
    Get multi-step recommendations using the holistic planner.

    The holistic planner automatically tests all depths (1-5) and returns
    the sequence with the best end-state score.

    Returns:
        Dictionary with "holistic" as key containing the recommendations.
    """
    from app.domain.portfolio_hash import generate_recommendation_cache_key

    positions = await position_repo.get_all()
    settings = await settings_service.get_settings()
    position_dicts = [{"symbol": p.symbol, "quantity": p.quantity} for p in positions]
    portfolio_cache_key = generate_recommendation_cache_key(position_dicts, settings.to_dict())
    cache_key = f"multi_step_recommendations:all:{portfolio_cache_key}"

    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        steps = await rebalancing_service.get_multi_step_recommendations()

        if not steps:
            result = {
                "holistic": {
                    "steps": [],
                    "depth": 0,
                    "total_score_improvement": 0.0,
                    "final_available_cash": 0.0,
                }
            }
        else:
            total_score_improvement = steps[0].score_change if steps else 0.0
            final_available_cash = steps[-1].available_cash_after if steps else 0.0

            result = {
                "holistic": {
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
            }

        # Cache for 5 minutes
        cache.set(cache_key, result, ttl_seconds=300)

        # Also cache to LED ticker keys for display synchronization
        if result.get("holistic", {}).get("steps"):
            depth = settings.recommendation_depth
            led_cache_key = f"multi_step_recommendations:diversification:{int(depth)}:holistic"
            cache.set(led_cache_key, result["holistic"], ttl_seconds=300)
            cache.set("multi_step_recommendations:diversification:default:holistic", result["holistic"], ttl_seconds=300)
            logger.debug(f"LED ticker cache updated: {led_cache_key}")

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating recommendations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/multi-step-recommendations")
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
    portfolio_cache_key = generate_recommendation_cache_key(position_dicts, settings.to_dict())
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
    portfolio_cache_key = generate_recommendation_cache_key(position_dicts, settings.to_dict())
    cache_key = f"multi_step_recommendations:{portfolio_cache_key}"

    logger.info(f"Cache miss for multi-step recommendations, regenerating...")
    steps_data = await rebalancing_service.get_multi_step_recommendations()

    if not steps_data:
        raise HTTPException(
            status_code=404,
            detail="No multi-step recommendations available. Please check your portfolio and settings."
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


@router.post("/multi-step-recommendations/execute-step/{step_number}")
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

    if step_number < 1:
        raise HTTPException(status_code=400, detail="Step number must be >= 1")
    if step_number > 5:
        raise HTTPException(status_code=400, detail="Step number must be between 1 and 5")

    try:
        # Generate portfolio-aware cache key
        positions = await position_repo.get_all()
        settings = await settings_service.get_settings()
        position_dicts = [{"symbol": p.symbol, "quantity": p.quantity} for p in positions]
        portfolio_cache_key = generate_recommendation_cache_key(position_dicts, settings.to_dict())
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
                detail=f"Step {step_number} not found. Only {len(steps)} steps available."
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
            raise_on_error=True
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
        logger.error(f"Error executing multi-step recommendation step {step_number}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/multi-step-recommendations/execute-all")
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

    try:
        # Generate portfolio-aware cache key
        positions = await position_repo.get_all()
        settings = await settings_service.get_settings()
        position_dicts = [{"symbol": p.symbol, "quantity": p.quantity} for p in positions]
        portfolio_cache_key = generate_recommendation_cache_key(position_dicts, settings.to_dict())
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
                detail="No steps available in multi-step recommendations"
            )

        # Ensure connection
        client = await ensure_tradernet_connected()

        # Check cooldown for all BUY steps
        buy_steps = [s for s in steps if s["side"] == TradeSide.BUY]
        blocked_buys = []
        for step in buy_steps:
            is_cooldown, error = await safety_service.check_cooldown(step["symbol"], step["side"])
            if is_cooldown:
                blocked_buys.append(step)
        
        if blocked_buys:
            symbols = ", ".join([s["symbol"] for s in blocked_buys])
            raise HTTPException(
                status_code=400,
                detail=f"Cannot execute: {symbols} in cooldown period"
            )

        results = []

        # Execute each step sequentially
        for idx, step in enumerate(steps, start=1):
            try:
                # Check for pending orders
                has_pending = await safety_service.check_pending_orders(
                    step["symbol"], step["side"], client
                )
                
                if has_pending:
                    results.append({
                        "step": idx,
                        "status": "blocked",
                        "symbol": step["symbol"],
                        "error": f"A pending order already exists for {step['symbol']}",
                    })
                    logger.warning(f"Step {idx} blocked: pending order exists for {step['symbol']}")
                    continue

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

                    results.append({
                        "step": idx,
                        "status": "success",
                        "order_id": result.order_id,
                        "symbol": step["symbol"],
                        "side": step["side"],
                        "quantity": step["quantity"],
                        "price": result.price,
                        "estimated_value": step["estimated_value"],
                    })
                else:
                    results.append({
                        "step": idx,
                        "status": "failed",
                        "symbol": step["symbol"],
                        "error": "Order placement returned None",
                    })
                    # Continue with remaining steps instead of stopping
                    logger.warning(f"Step {idx} failed, continuing with remaining steps")
                    continue

            except Exception as e:
                logger.error(f"Error executing step {idx}: {e}", exc_info=True)
                results.append({
                    "step": idx,
                    "status": "error",
                    "symbol": step["symbol"],
                    "error": str(e),
                })
                # Continue with remaining steps instead of stopping
                logger.warning(f"Step {idx} errored, continuing with remaining steps")
                continue

        # Invalidate caches after all steps complete
        cache_service = get_cache_invalidation_service()
        cache_service.invalidate_trade_caches()

        return {
            "status": "completed",
            "total_steps": len(steps),
            "executed_steps": len([r for r in results if r["status"] == "success"]),
            "results": results,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing all multi-step recommendations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sell-recommendations/{symbol}/execute")
async def execute_sell_recommendation(
    symbol: str,
    trade_repo: TradeRepositoryDep,
    position_repo: PositionRepositoryDep,
    rebalancing_service: RebalancingServiceDep,
    safety_service: TradeSafetyServiceDep,
    trade_execution_service: TradeExecutionServiceDep,
):
    """
    Execute a sell recommendation for a specific symbol.

    Gets the current sell recommendation and executes it via Tradernet.
    """
    symbol = symbol.upper()

    try:
        recommendations = await rebalancing_service.calculate_sell_recommendations(limit=20)

        # Find the recommendation for the requested symbol
        rec = next((r for r in recommendations if r.symbol == symbol), None)
        if not rec:
            raise HTTPException(
                status_code=404,
                detail=f"No sell recommendation found for {symbol}"
            )

        # Ensure connection
        client = await ensure_tradernet_connected()

        # Safety checks
        await safety_service.validate_trade(
            symbol=rec.symbol,
            side=TradeSide.SELL,
            quantity=rec.quantity,
            client=client,
            raise_on_error=True
        )

        result = client.place_order(
            symbol=rec.symbol,
            side=TradeSide.SELL,
            quantity=rec.quantity,
        )

        if result:
            # Record the trade
            await trade_execution_service.record_trade(
                symbol=symbol,
                side=TradeSide.SELL,
                quantity=rec.quantity,
                price=result.price,
                order_id=result.order_id,
            )

            # Invalidate caches
            cache_service = get_cache_invalidation_service()
            cache_service.invalidate_trade_caches()

            return {
                "status": "success",
                "order_id": result.order_id,
                "symbol": symbol,
                "side": TradeSide.SELL,
                "quantity": rec.quantity,
                "price": result.price,
                "estimated_value": rec.estimated_value,
            }

        raise HTTPException(status_code=500, detail="Trade execution failed")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


