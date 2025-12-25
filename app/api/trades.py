"""Trade execution API endpoints."""

import logging
from typing import List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator
from app.domain.value_objects.trade_side import TradeSide
from app.domain.value_objects.trade_side import TradeSide
from app.repositories import (
    StockRepository,
    PositionRepository,
    TradeRepository,
    AllocationRepository,
    PortfolioRepository,
    RecommendationRepository,
)
from app.infrastructure.cache import cache
from app.application.services.trade_safety_service import TradeSafetyService
from app.infrastructure.cache_invalidation import get_cache_invalidation_service
from app.services.tradernet_connection import ensure_tradernet_connected
from app.application.services.trade_execution_service import TradeExecutionService

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
async def get_trades(limit: int = 50):
    """Get trade history."""
    trade_repo = TradeRepository()
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
async def execute_trade(trade: TradeRequest):
    """Execute a manual trade."""
    stock_repo = StockRepository()
    trade_repo = TradeRepository()
    position_repo = PositionRepository()

    # Check stock exists
    stock = await stock_repo.get_by_symbol(trade.symbol)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    # Ensure connection
    client = await ensure_tradernet_connected()

    # Safety checks
    safety_service = TradeSafetyService(trade_repo, position_repo)
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
        execution_service = TradeExecutionService(trade_repo, position_repo)
        await execution_service.record_trade(
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
async def get_allocation():
    """Get current portfolio allocation vs targets."""
    from app.application.services.portfolio_service import PortfolioService

    portfolio_repo = PortfolioRepository()
    position_repo = PositionRepository()
    allocation_repo = AllocationRepository()

    portfolio_service = PortfolioService(
        portfolio_repo,
        position_repo,
        allocation_repo,
    )
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
async def debug_recommendations():
    """
    Debug endpoint to see why recommendations are filtered out.
    """
    from app.application.services.rebalancing_service import RebalancingService

    rebalancing_service = RebalancingService()
    debug_info = await rebalancing_service.get_recommendations_debug()
    return debug_info


@router.get("/recommendations")
async def get_recommendations(limit: int = 3):
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

    from app.application.services.rebalancing_service import RebalancingService

    try:
        # Generate recommendations (this will store them in the database)
        rebalancing_service = RebalancingService()
        await rebalancing_service.get_recommendations(limit=limit)

        # Get stored pending BUY recommendations from database
        recommendation_repo = RecommendationRepository()
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
async def dismiss_recommendation(uuid: str):
    """
    Dismiss a recommendation by UUID.

    Marks the recommendation as dismissed, preventing it from appearing again.
    """
    try:
        recommendation_repo = RecommendationRepository()
        
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
async def get_sell_recommendations(limit: int = 3):
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

    from app.application.services.rebalancing_service import RebalancingService

    try:
        # Generate sell recommendations (this will store them in the database)
        rebalancing_service = RebalancingService()
        await rebalancing_service.calculate_sell_recommendations(limit=limit)

        # Get stored pending SELL recommendations from database
        recommendation_repo = RecommendationRepository()
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
async def dismiss_sell_recommendation(uuid: str):
    """
    Dismiss a sell recommendation by UUID.

    Marks the recommendation as dismissed, preventing it from appearing again.
    """
    try:
        recommendation_repo = RecommendationRepository()
        
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
    List all available recommendation strategies.
    
    Returns:
        Dictionary mapping strategy names to descriptions
    """
    try:
        from app.domain.planning.strategies import list_strategies
        strategies = list_strategies()
        return {"strategies": strategies}
    except Exception as e:
        logger.error(f"Error listing strategies: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/multi-step-recommendations/all")
async def get_all_strategy_recommendations(depth: int = None):
    """
    Get multi-step recommendations from ALL strategies.
    
    Runs all available strategies in parallel and returns recommendations from each.
    This allows comparing different strategic approaches side-by-side.
    
    Args:
        depth: Number of steps (1-5). If None, uses setting value (default: 1).
    
    Returns:
        Dictionary with strategy names as keys and their recommendations as values.
        Format: {
            "diversification": {...},
            "sustainability": {...},
            "opportunity": {...}
        }
    """
    # Validate depth parameter
    if depth is not None:
        if depth < 1 or depth > 5:
            raise HTTPException(
                status_code=400,
                detail="Depth must be between 1 and 5"
            )
    
    # Build cache key
    cache_key = f"multi_step_recommendations:all:{depth or 'default'}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    
    from app.application.services.rebalancing_service import RebalancingService
    from app.domain.planning.strategies import list_strategies
    
    try:
        rebalancing_service = RebalancingService()
        available_strategies = list_strategies()
        
        # Run all strategies in parallel
        import asyncio
        
        async def get_strategy_recommendations(strategy_name: str):
            """Get recommendations for a single strategy."""
            try:
                steps = await rebalancing_service.get_multi_step_recommendations(
                    depth=depth,
                    strategy_type=strategy_name
                )
                
                if not steps:
                    return {
                        "strategy": strategy_name,
                        "depth": depth or 1,
                        "steps": [],
                        "total_score_improvement": 0.0,
                        "final_available_cash": 0.0,
                        "error": None,
                    }
                
                total_score_improvement = sum(step.score_change for step in steps)
                final_available_cash = steps[-1].available_cash_after if steps else 0.0
                
                return {
                    "strategy": strategy_name,
                    "depth": depth or len(steps),
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
                    "error": None,
                }
            except Exception as e:
                logger.error(f"Error generating recommendations for strategy {strategy_name}: {e}", exc_info=True)
                return {
                    "strategy": strategy_name,
                    "depth": depth or 1,
                    "steps": [],
                    "total_score_improvement": 0.0,
                    "final_available_cash": 0.0,
                    "error": str(e),
                }
        
        # Run all strategies concurrently
        strategy_names = list(available_strategies.keys())
        results = await asyncio.gather(*[
            get_strategy_recommendations(name) for name in strategy_names
        ])
        
        # Build result dictionary
        result = {
            strategy_result["strategy"]: strategy_result
            for strategy_result in results
        }
        
        # Cache for 5 minutes
        cache.set(cache_key, result, ttl_seconds=300)
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating all-strategy recommendations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/multi-step-recommendations")
async def get_multi_step_recommendations(
    depth: int = None,
    strategy: str = "diversification",
    holistic: bool = True,
):
    """
    Get multi-step recommendation sequence.

    Generates a sequence of buy/sell recommendations that build on each other.
    Each step simulates the portfolio state after the previous transaction.

    Args:
        depth: Number of steps (1-5). If None, uses setting value (default: 1).
        strategy: Strategy to use ("diversification", "sustainability", "opportunity"). Default: "diversification".
        holistic: If True, use holistic planner with end-state optimization,
                  windfall detection, and narrative explanations.

    Returns:
        Multi-step recommendation sequence with portfolio state at each step.
    """
    # Validate depth parameter
    if depth is not None:
        if depth < 1 or depth > 5:
            raise HTTPException(
                status_code=400,
                detail="Depth must be between 1 and 5"
            )
    
    # Validate strategy parameter
    from app.domain.planning.strategies import list_strategies
    available_strategies = list_strategies()
    if strategy not in available_strategies:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid strategy '{strategy}'. Available strategies: {', '.join(available_strategies.keys())}"
        )

    # Build cache key (include strategy and holistic flag in cache key)
    holistic_suffix = ":holistic" if holistic else ""
    cache_key = f"multi_step_recommendations:{strategy}:{depth or 'default'}{holistic_suffix}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    from app.application.services.rebalancing_service import RebalancingService

    try:
        rebalancing_service = RebalancingService()
        steps = await rebalancing_service.get_multi_step_recommendations(
            depth=depth, strategy_type=strategy, use_holistic=holistic
        )

        if not steps:
            return {
                "strategy": strategy,
                "depth": depth or 1,
                "holistic": holistic,
                "steps": [],
                "total_score_improvement": 0.0,
                "final_available_cash": 0.0,
            }

        # Calculate totals
        total_score_improvement = sum(step.score_change for step in steps)
        final_available_cash = steps[-1].available_cash_after

        result = {
            "strategy": strategy,
            "depth": depth or len(steps),
            "holistic": holistic,
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

        # Cache for 5 minutes (same as single recommendations)
        # Cache to both the specific key and :default to ensure execute endpoints can find it
        cache.set(cache_key, result, ttl_seconds=300)
        default_cache_key = f"multi_step_recommendations:{strategy}:default{holistic_suffix}"
        if cache_key != default_cache_key:
            cache.set(default_cache_key, result, ttl_seconds=300)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating multi-step recommendations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def _regenerate_multi_step_cache(cache_key: str = "multi_step_recommendations:diversification:default", strategy: str = "diversification") -> dict:
    """
    Regenerate multi-step recommendations cache if missing.
    
    Args:
        cache_key: Cache key to use (default: "multi_step_recommendations:diversification:default")
        strategy: Strategy to use (default: "diversification")
        
    Returns:
        Cached recommendations dict with steps, depth, totals, etc.
        
    Raises:
        HTTPException: If no recommendations are available
    """
    from app.application.services.rebalancing_service import RebalancingService
    
    logger.info(f"Cache miss for multi-step recommendations, regenerating (key: {cache_key}, strategy: {strategy})...")
    rebalancing_service = RebalancingService()
    steps_data = await rebalancing_service.get_multi_step_recommendations(depth=None, strategy_type=strategy)
    
    if not steps_data:
        raise HTTPException(
            status_code=404,
            detail="No multi-step recommendations available. Please check your portfolio and settings."
        )
    
    # Rebuild cached format
    total_score_improvement = sum(step.score_change for step in steps_data)
    final_available_cash = steps_data[-1].available_cash_after if steps_data and len(steps_data) > 0 else 0.0
    
    cached = {
        "strategy": strategy,
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
    return cached


@router.post("/multi-step-recommendations/execute-step/{step_number}")
async def execute_multi_step_recommendation_step(step_number: int):
    """
    Execute a single step from the multi-step recommendation sequence.

    Args:
        step_number: The step number (1-indexed) to execute

    Returns:
        Execution result for the step
    """
    from app.application.services.rebalancing_service import RebalancingService

    if step_number < 1:
        raise HTTPException(status_code=400, detail="Step number must be >= 1")
    if step_number > 5:
        raise HTTPException(status_code=400, detail="Step number must be between 1 and 5")

    trade_repo = TradeRepository()
    position_repo = PositionRepository()

    try:
        # Get the cached multi-step recommendations (default to diversification strategy)
        strategy = "diversification"
        cache_key = f"multi_step_recommendations:{strategy}:default"
        cached = cache.get(cache_key)
        
        # If cache miss, regenerate recommendations
        if not cached or not cached.get("steps"):
            cached = await _regenerate_multi_step_cache(cache_key, strategy)

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
        safety_service = TradeSafetyService(trade_repo, position_repo)
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
            execution_service = TradeExecutionService(trade_repo, position_repo)
            await execution_service.record_trade(
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
async def execute_all_multi_step_recommendations():
    """
    Execute all steps in the multi-step recommendation sequence in order.

    Executes each step sequentially, continuing with remaining steps if any step fails.

    Returns:
        List of execution results for each step
    """
    from app.application.services.rebalancing_service import RebalancingService

    trade_repo = TradeRepository()
    position_repo = PositionRepository()

    try:
        # Get the cached multi-step recommendations (default to diversification strategy)
        strategy = "diversification"
        cache_key = f"multi_step_recommendations:{strategy}:default"
        cached = cache.get(cache_key)
        
        # If cache miss, regenerate recommendations
        if not cached or not cached.get("steps"):
            cached = await _regenerate_multi_step_cache(cache_key, strategy)

        steps = cached["steps"]
        if not steps:
            raise HTTPException(
                status_code=404,
                detail="No steps available in multi-step recommendations"
            )

        # Ensure connection
        client = await ensure_tradernet_connected()

        # Safety service for validation
        safety_service = TradeSafetyService(trade_repo, position_repo)
        execution_service = TradeExecutionService(trade_repo, position_repo)

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
                    await execution_service.record_trade(
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
async def execute_sell_recommendation(symbol: str):
    """
    Execute a sell recommendation for a specific symbol.

    Gets the current sell recommendation and executes it via Tradernet.
    """
    from app.application.services.rebalancing_service import RebalancingService

    symbol = symbol.upper()
    trade_repo = TradeRepository()
    position_repo = PositionRepository()

    try:
        rebalancing_service = RebalancingService()
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
        safety_service = TradeSafetyService(trade_repo, position_repo)
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
            execution_service = TradeExecutionService(trade_repo, position_repo)
            await execution_service.record_trade(
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


class FundingSellRequest(BaseModel):
    """A single sell in a funding execution request."""
    symbol: str
    quantity: int


class ExecuteFundingRequest(BaseModel):
    """Request to execute a funding plan."""
    strategy: str
    sells: List[FundingSellRequest]


@router.get("/recommendations/{symbol}/funding-options")
async def get_funding_options(symbol: str, exclude_signatures: str = ""):
    """
    Get funding options for a buy recommendation that can't be executed due to insufficient cash.

    Returns 3-4 strategies for raising cash by selling existing positions:
    - score_based: Sell based on underperformance scoring
    - minimal_sells: Minimize number of transactions
    - overweight: Reduce overweight positions first
    - currency_match: Prefer selling same-currency positions
    """
    from app.application.services.funding_service import FundingService
    from app.application.services.rebalancing_service import RebalancingService

    symbol = symbol.upper()

    try:
        # Get current recommendation for this symbol
        rebalancing_service = RebalancingService()
        recommendations = await rebalancing_service.get_recommendations(limit=10)

        rec = next((r for r in recommendations if r.symbol == symbol), None)
        if not rec:
            raise HTTPException(
                status_code=404,
                detail=f"No recommendation found for {symbol}"
            )

        # Get current cash balance
        client = await ensure_tradernet_connected()
        available_cash = client.get_total_cash_eur()

        # Check if funding is needed
        if available_cash >= rec.estimated_value:
            return {
                "buy_symbol": symbol,
                "buy_amount": rec.estimated_value,
                "cash_available": available_cash,
                "cash_needed": 0,
                "options": [],
                "message": "Sufficient cash available, no funding needed"
            }

        # Generate funding options
        funding_service = FundingService()

        # Parse excluded signatures for pagination
        excluded = [s.strip() for s in exclude_signatures.split(",") if s.strip()]

        options = await funding_service.get_funding_options(
            buy_symbol=symbol,
            buy_amount_eur=rec.estimated_value,
            available_cash=available_cash,
            exclude_signatures=excluded,
        )

        return {
            "buy_symbol": symbol,
            "buy_amount": rec.estimated_value,
            "cash_available": round(available_cash, 2),
            "cash_needed": round(rec.estimated_value - available_cash, 2),
            "has_more": len(options) > 0,
            "options": [
                {
                    "strategy": opt.strategy,
                    "description": opt.description,
                    "signature": opt.signature,
                    "sells": [
                        {
                            "symbol": s.symbol,
                            "name": s.name,
                            "quantity": s.quantity,
                            "sell_pct": round(s.sell_pct * 100, 1),
                            "value_eur": s.value_eur,
                            "currency": s.currency,
                            "current_price": s.current_price,
                            "profit_pct": round(s.profit_pct * 100, 1),
                            "warnings": s.warnings,
                        }
                        for s in opt.sells
                    ],
                    "total_sell_value": opt.total_sell_value,
                    "current_score": opt.current_score,
                    "new_score": opt.new_score,
                    "net_score_change": opt.net_score_change,
                    "has_warnings": opt.has_warnings,
                }
                for opt in options
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recommendations/{symbol}/execute-funding")
async def execute_funding(symbol: str, request: ExecuteFundingRequest):
    """
    Execute a funding plan: sell specified positions then buy the target stock.

    Executes all sells first, then executes the buy with the newly available cash.
    """
    symbol = symbol.upper()
    trade_repo = TradeRepository()
    stock_repo = StockRepository()
    position_repo = PositionRepository()

    try:
        # Ensure connection
        client = await ensure_tradernet_connected()

        # Services
        safety_service = TradeSafetyService(trade_repo, position_repo)
        execution_service = TradeExecutionService(trade_repo, position_repo)

        # Check cooldown before executing any trades
        is_cooldown, cooldown_error = await safety_service.check_cooldown(symbol, TradeSide.BUY)
        if is_cooldown:
            raise HTTPException(status_code=400, detail=cooldown_error)

        # Execute all sells
        sell_results = []
        total_sold_value = 0.0

        for sell in request.sells:
            sell_symbol = sell.symbol.upper()

            # Check for pending orders
            has_pending = await safety_service.check_pending_orders(
                sell_symbol, TradeSide.SELL, client
            )
            
            if has_pending:
                sell_results.append({
                    "symbol": sell_symbol,
                    "status": "blocked",
                    "error": f"A pending order already exists for {sell_symbol}",
                })
                continue

            result = client.place_order(
                symbol=sell_symbol,
                side=TradeSide.SELL,
                quantity=sell.quantity,
            )

            if result:
                # Record the trade
                await execution_service.record_trade(
                    symbol=sell_symbol,
                    side=TradeSide.SELL,
                    quantity=sell.quantity,
                    price=result.price,
                    order_id=result.order_id,
                )

                sell_results.append({
                    "symbol": sell_symbol,
                    "status": "success",
                    "quantity": sell.quantity,
                    "price": result.price,
                    "order_id": result.order_id,
                })
                total_sold_value += sell.quantity * result.price
            else:
                sell_results.append({
                    "symbol": sell_symbol,
                    "status": "failed",
                    "error": "Order execution failed",
                })

        # Check how many sells succeeded
        successful_sells = [r for r in sell_results if r["status"] == "success"]
        if not successful_sells:
            raise HTTPException(
                status_code=500,
                detail="All sell orders failed, cannot proceed with buy"
            )

        # Execute the buy
        stock = await stock_repo.get_by_symbol(symbol)
        if not stock:
            raise HTTPException(status_code=404, detail=f"Stock {symbol} not found")

        # Get current price and calculate quantity
        from app.services import yahoo
        price = yahoo.get_current_price(symbol, stock.yahoo_symbol)
        if not price or price <= 0:
            raise HTTPException(
                status_code=500,
                detail=f"Could not get current price for {symbol}"
            )

        # Calculate quantity based on available cash (including new sales)
        available_cash = client.get_total_cash_eur()
        min_lot = stock.min_lot or 1
        quantity = int(available_cash / price / min_lot) * min_lot

        if quantity <= 0:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient cash for minimum lot of {symbol}"
            )

        # Check for pending orders for the buy symbol
        has_pending = await safety_service.check_pending_orders(
            symbol, TradeSide.BUY, client
        )
        
        if has_pending:
            raise HTTPException(
                status_code=409,
                detail=f"A pending order already exists for {symbol}"
            )

        buy_result = client.place_order(
            symbol=symbol,
            side=TradeSide.BUY,
            quantity=quantity,
        )

        if buy_result:
            # Record the buy trade
            await execution_service.record_trade(
                symbol=symbol,
                side=TradeSide.BUY,
                quantity=quantity,
                price=buy_result.price,
                order_id=buy_result.order_id,
            )

            # Invalidate caches
            cache_service = get_cache_invalidation_service()
            cache_service.invalidate_trade_caches()

            return {
                "status": "success",
                "strategy": request.strategy,
                "sells": sell_results,
                "buy": {
                    "symbol": symbol,
                    "status": "success",
                    "quantity": quantity,
                    "price": buy_result.price,
                    "order_id": buy_result.order_id,
                },
                "total_sold": round(total_sold_value, 2),
            }
        else:
            return {
                "status": "partial",
                "message": "Sells succeeded but buy failed",
                "sells": sell_results,
                "buy": {
                    "symbol": symbol,
                    "status": "failed",
                    "error": "Buy order execution failed",
                },
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
