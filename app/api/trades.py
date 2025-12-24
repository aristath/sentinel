"""Trade execution API endpoints."""

import logging
from datetime import datetime
from typing import List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator
from enum import Enum
from app.domain.constants import TRADE_SIDE_BUY, TRADE_SIDE_SELL
from app.domain.models import Trade
from app.repositories import (
    StockRepository,
    PositionRepository,
    TradeRepository,
    AllocationRepository,
    PortfolioRepository,
)
from app.infrastructure.cache import cache

logger = logging.getLogger(__name__)
router = APIRouter()


class TradeSide(str, Enum):
    """Trade side enumeration."""
    BUY = TRADE_SIDE_BUY
    SELL = TRADE_SIDE_SELL


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

    # Check stock exists
    stock = await stock_repo.get_by_symbol(trade.symbol)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    from app.services.tradernet import get_tradernet_client

    client = get_tradernet_client()
    if not client.is_connected:
        raise HTTPException(status_code=503, detail="Tradernet not connected")

    result = client.place_order(
        symbol=trade.symbol,
        side=trade.side,
        quantity=trade.quantity,
    )

    if result:
        # Record trade using repository
        trade_record = Trade(
            symbol=trade.symbol,
            side=trade.side,
            quantity=trade.quantity,
            price=result.price,
            executed_at=datetime.now(),
            order_id=result.order_id,
        )
        await trade_repo.create(trade_record)

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


@router.get("/recommendations")
async def get_recommendations(limit: int = 3):
    """
    Get top N trade recommendations based on current portfolio state.

    Returns prioritized list of stocks to buy next, with fixed trade amounts.
    Independent of current cash balance - shows what to buy when cash is available.
    Cached for 5 minutes.
    """
    # Check cache first
    cache_key = f"recommendations:{limit}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    from app.application.services.rebalancing_service import RebalancingService

    try:
        rebalancing_service = RebalancingService()
        recommendations = await rebalancing_service.get_recommendations(limit=limit)

        result = {
            "recommendations": [
                {
                    "symbol": r.symbol,
                    "name": r.name,
                    "amount": r.amount,
                    "priority": r.priority,
                    "reason": r.reason,
                    "geography": r.geography,
                    "industry": r.industry,
                    "current_price": r.current_price,
                    "quantity": r.quantity,
                    "current_portfolio_score": r.current_portfolio_score,
                    "new_portfolio_score": r.new_portfolio_score,
                    "score_change": r.score_change,
                }
                for r in recommendations
            ],
        }

        # Cache for 5 minutes
        cache.set(cache_key, result, ttl_seconds=300)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recommendations/{symbol}/execute")
async def execute_recommendation(symbol: str):
    """
    Execute a single recommendation by symbol.

    Gets the current recommendation for the symbol and executes it.
    """
    from app.application.services.rebalancing_service import RebalancingService
    from app.services.tradernet import get_tradernet_client

    symbol = symbol.upper()
    trade_repo = TradeRepository()

    try:
        # Get recommendations to find this symbol
        rebalancing_service = RebalancingService()
        recommendations = await rebalancing_service.get_recommendations(limit=10)

        # Find the recommendation for this symbol
        rec = next((r for r in recommendations if r.symbol == symbol), None)
        if not rec:
            raise HTTPException(status_code=404, detail=f"No recommendation found for {symbol}")

        if not rec.quantity or not rec.current_price:
            raise HTTPException(status_code=400, detail=f"Cannot execute: no valid price/quantity for {symbol}")

        # Execute the trade
        client = get_tradernet_client()
        if not client.is_connected:
            raise HTTPException(status_code=503, detail="Tradernet not connected")

        result = client.place_order(
            symbol=symbol,
            side=TRADE_SIDE_BUY,
            quantity=rec.quantity,
        )

        if result:
            # Record trade
            trade_record = Trade(
                symbol=symbol,
                side=TRADE_SIDE_BUY,
                quantity=rec.quantity,
                price=result.price,
                executed_at=datetime.now(),
                order_id=result.order_id,
            )
            await trade_repo.create(trade_record)

            # Invalidate caches (including limit-specific keys)
            cache.invalidate("recommendations")
            cache.invalidate("recommendations:3")
            cache.invalidate("recommendations:10")
            cache.invalidate("sell_recommendations")
            cache.invalidate("sell_recommendations:3")
            cache.invalidate("sell_recommendations:20")
            cache.invalidate("multi_step_recommendations:default")
            # Invalidate all depth-specific caches
            for depth in range(1, 6):
                cache.invalidate(f"multi_step_recommendations:{depth}")

            return {
                "status": "success",
                "order_id": result.order_id,
                "symbol": symbol,
                "side": TRADE_SIDE_BUY,
                "quantity": rec.quantity,
                "price": result.price,
                "estimated_value": rec.amount,
            }

        raise HTTPException(status_code=500, detail="Trade execution failed")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sell-recommendations")
async def get_sell_recommendations(limit: int = 3):
    """
    Get top N sell recommendations based on sell scoring system.

    Returns prioritized list of positions to sell, with quantities and reasons.
    Cached for 5 minutes.
    """
    cache_key = f"sell_recommendations:{limit}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    from app.application.services.rebalancing_service import RebalancingService

    try:
        rebalancing_service = RebalancingService()
        recommendations = await rebalancing_service.calculate_sell_recommendations(limit=limit)

        result = {
            "recommendations": [
                {
                    "symbol": r.symbol,
                    "name": r.name,
                    "side": r.side,
                    "quantity": r.quantity,
                    "estimated_price": r.estimated_price,
                    "estimated_value": r.estimated_value,
                    "reason": r.reason,
                    "currency": r.currency,
                }
                for r in recommendations
            ],
        }

        cache.set(cache_key, result, ttl_seconds=300)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/multi-step-recommendations")
async def get_multi_step_recommendations(depth: int = None):
    """
    Get multi-step recommendation sequence.

    Generates a sequence of buy/sell recommendations that build on each other.
    Each step simulates the portfolio state after the previous transaction.

    Args:
        depth: Number of steps (1-5). If None, uses setting value (default: 1).

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

    # Build cache key
    cache_key = f"multi_step_recommendations:{depth or 'default'}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    from app.application.services.rebalancing_service import RebalancingService

    try:
        rebalancing_service = RebalancingService()
        steps = await rebalancing_service.get_multi_step_recommendations(depth=depth)

        if not steps:
            return {
                "depth": depth or 1,
                "steps": [],
                "total_score_improvement": 0.0,
                "final_available_cash": 0.0,
            }

        # Calculate totals
        total_score_improvement = sum(step.score_change for step in steps)
        final_available_cash = steps[-1].available_cash_after

        result = {
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
        }

        # Cache for 5 minutes (same as single recommendations)
        # Cache to both the specific key and :default to ensure execute endpoints can find it
        cache.set(cache_key, result, ttl_seconds=300)
        if cache_key != "multi_step_recommendations:default":
            cache.set("multi_step_recommendations:default", result, ttl_seconds=300)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating multi-step recommendations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def _regenerate_multi_step_cache(cache_key: str = "multi_step_recommendations:default") -> dict:
    """
    Regenerate multi-step recommendations cache if missing.
    
    Args:
        cache_key: Cache key to use (default: "multi_step_recommendations:default")
        
    Returns:
        Cached recommendations dict with steps, depth, totals, etc.
        
    Raises:
        HTTPException: If no recommendations are available
    """
    from app.application.services.rebalancing_service import RebalancingService
    
    logger.info(f"Cache miss for multi-step recommendations, regenerating (key: {cache_key})...")
    rebalancing_service = RebalancingService()
    steps_data = await rebalancing_service.get_multi_step_recommendations(depth=None)
    
    if not steps_data:
        raise HTTPException(
            status_code=404,
            detail="No multi-step recommendations available. Please check your portfolio and settings."
        )
    
    # Rebuild cached format
    total_score_improvement = sum(step.score_change for step in steps_data)
    final_available_cash = steps_data[-1].available_cash_after if steps_data and len(steps_data) > 0 else 0.0
    
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
    from app.services.tradernet import get_tradernet_client

    if step_number < 1:
        raise HTTPException(status_code=400, detail="Step number must be >= 1")
    if step_number > 5:
        raise HTTPException(status_code=400, detail="Step number must be between 1 and 5")

    trade_repo = TradeRepository()
    position_repo = PositionRepository()

    try:
        # Get the cached multi-step recommendations
        cache_key = "multi_step_recommendations:default"
        cached = cache.get(cache_key)
        
        # If cache miss, regenerate recommendations
        if not cached or not cached.get("steps"):
            cached = await _regenerate_multi_step_cache(cache_key)

        steps = cached["steps"]
        if step_number > len(steps):
            raise HTTPException(
                status_code=404,
                detail=f"Step {step_number} not found. Only {len(steps)} steps available."
            )

        step = steps[step_number - 1]  # Convert to 0-indexed

        # Connect to Tradernet
        client = get_tradernet_client()
        if not client.is_connected:
            if not client.connect():
                raise HTTPException(
                    status_code=503,
                    detail="Failed to connect to Tradernet"
                )

        # Check cooldown for BUY orders
        if step["side"] == TRADE_SIDE_BUY:
            from app.domain.constants import BUY_COOLDOWN_DAYS
            recently_bought = await trade_repo.get_recently_bought_symbols(BUY_COOLDOWN_DAYS)
            if step["symbol"] in recently_bought:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot buy {step['symbol']}: cooldown period active (bought within {BUY_COOLDOWN_DAYS} days)"
                )

        # Execute the trade
        result = client.place_order(
            symbol=step["symbol"],
            side=step["side"],
            quantity=step["quantity"],
        )

        if result:
            # Record the trade
            trade_record = Trade(
                symbol=step["symbol"],
                side=step["side"],
                quantity=step["quantity"],
                price=result.price,
                executed_at=datetime.now(),
                order_id=result.order_id,
            )
            await trade_repo.create(trade_record)

            # Update last_sold_at for SELL orders
            if step["side"] == TRADE_SIDE_SELL and position_repo:
                try:
                    await position_repo.update_last_sold_at(step["symbol"])
                except Exception as e:
                    logger.warning(f"Failed to update last_sold_at: {e}")

            # Invalidate cache to force refresh (including limit-specific keys)
            cache.invalidate("multi_step_recommendations:default")
            cache.invalidate("recommendations")
            cache.invalidate("recommendations:3")
            cache.invalidate("recommendations:10")
            cache.invalidate("sell_recommendations")
            cache.invalidate("sell_recommendations:3")
            cache.invalidate("sell_recommendations:20")
            # Invalidate all depth-specific caches
            for depth in range(1, 6):
                cache.invalidate(f"multi_step_recommendations:{depth}")

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
    from app.services.tradernet import get_tradernet_client

    trade_repo = TradeRepository()
    position_repo = PositionRepository()

    try:
        # Get the cached multi-step recommendations
        cache_key = "multi_step_recommendations:default"
        cached = cache.get(cache_key)
        
        # If cache miss, regenerate recommendations
        if not cached or not cached.get("steps"):
            cached = await _regenerate_multi_step_cache(cache_key)

        steps = cached["steps"]
        if not steps:
            raise HTTPException(
                status_code=404,
                detail="No steps available in multi-step recommendations"
            )

        # Connect to Tradernet
        client = get_tradernet_client()
        if not client.is_connected:
            if not client.connect():
                raise HTTPException(
                    status_code=503,
                    detail="Failed to connect to Tradernet"
                )

        # Check cooldown for all BUY steps
        from app.domain.constants import BUY_COOLDOWN_DAYS
        recently_bought = await trade_repo.get_recently_bought_symbols(BUY_COOLDOWN_DAYS)
        buy_steps = [s for s in steps if s["side"] == TRADE_SIDE_BUY]
        blocked_buys = [s for s in buy_steps if s["symbol"] in recently_bought]
        if blocked_buys:
            symbols = ", ".join([s["symbol"] for s in blocked_buys])
            raise HTTPException(
                status_code=400,
                detail=f"Cannot execute: {symbols} in cooldown period (bought within {BUY_COOLDOWN_DAYS} days)"
            )

        results = []

        # Execute each step sequentially
        for idx, step in enumerate(steps, start=1):
            try:
                result = client.place_order(
                    symbol=step["symbol"],
                    side=step["side"],
                    quantity=step["quantity"],
                )

                if result:
                    # Record the trade
                    trade_record = Trade(
                        symbol=step["symbol"],
                        side=step["side"],
                        quantity=step["quantity"],
                        price=result.price,
                        executed_at=datetime.now(),
                        order_id=result.order_id,
                    )
                    await trade_repo.create(trade_record)

                    # Update last_sold_at for SELL orders
                    if step["side"] == TRADE_SIDE_SELL and position_repo:
                        try:
                            await position_repo.update_last_sold_at(step["symbol"])
                        except Exception as e:
                            logger.warning(f"Failed to update last_sold_at: {e}")

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

        # Invalidate cache to force refresh after all steps complete (including limit-specific keys)
        cache.invalidate("multi_step_recommendations:default")
        cache.invalidate("recommendations")
        cache.invalidate("recommendations:3")
        cache.invalidate("recommendations:10")
        cache.invalidate("sell_recommendations")
        cache.invalidate("sell_recommendations:3")
        cache.invalidate("sell_recommendations:20")
        # Invalidate all depth-specific caches
        for depth in range(1, 6):
            cache.invalidate(f"multi_step_recommendations:{depth}")

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
    from app.services.tradernet import get_tradernet_client

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

        # Connect to Tradernet and execute
        client = get_tradernet_client()
        if not client.is_connected:
            if not client.connect():
                raise HTTPException(
                    status_code=503,
                    detail="Failed to connect to Tradernet"
                )

        result = client.place_order(
            symbol=rec.symbol,
            side=TRADE_SIDE_SELL,
            quantity=rec.quantity,
        )

        if result:
            # Record the trade
            trade_record = Trade(
                symbol=symbol,
                side=TRADE_SIDE_SELL,
                quantity=rec.quantity,
                price=result.price,
                executed_at=datetime.now(),
                order_id=result.order_id,
            )
            await trade_repo.create(trade_record)

            # Update last_sold_at
            await position_repo.update_last_sold_at(symbol)

            # Clear cache
            cache.invalidate("sell_recommendations:3")
            cache.invalidate("sell_recommendations:20")
            cache.invalidate("multi_step_recommendations:default")
            # Invalidate all depth-specific caches
            for depth in range(1, 6):
                cache.invalidate(f"multi_step_recommendations:{depth}")

            return {
                "status": "success",
                "order_id": result.order_id,
                "symbol": symbol,
                "side": TRADE_SIDE_SELL,
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
    from app.services.tradernet import get_tradernet_client

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
        client = get_tradernet_client()
        if not client.is_connected:
            if not client.connect():
                raise HTTPException(
                    status_code=503,
                    detail="Failed to connect to Tradernet"
                )

        available_cash = client.get_total_cash_eur()

        # Check if funding is needed
        if available_cash >= rec.amount:
            return {
                "buy_symbol": symbol,
                "buy_amount": rec.amount,
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
            buy_amount_eur=rec.amount,
            available_cash=available_cash,
            exclude_signatures=excluded,
        )

        return {
            "buy_symbol": symbol,
            "buy_amount": rec.amount,
            "cash_available": round(available_cash, 2),
            "cash_needed": round(rec.amount - available_cash, 2),
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
    from app.services.tradernet import get_tradernet_client
    from app.domain.constants import BUY_COOLDOWN_DAYS

    symbol = symbol.upper()
    trade_repo = TradeRepository()
    stock_repo = StockRepository()

    # Check cooldown before executing any trades
    recently_bought = await trade_repo.get_recently_bought_symbols(BUY_COOLDOWN_DAYS)
    if symbol in recently_bought:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot buy {symbol}: cooldown period active (bought within {BUY_COOLDOWN_DAYS} days)"
        )

    try:
        client = get_tradernet_client()
        if not client.is_connected:
            if not client.connect():
                raise HTTPException(
                    status_code=503,
                    detail="Failed to connect to Tradernet"
                )

        # Execute all sells
        sell_results = []
        total_sold_value = 0.0

        for sell in request.sells:
            sell_symbol = sell.symbol.upper()

            result = client.place_order(
                symbol=sell_symbol,
                side=TRADE_SIDE_SELL,
                quantity=sell.quantity,
            )

            if result:
                # Record the trade
                trade_record = Trade(
                    symbol=sell_symbol,
                    side=TRADE_SIDE_SELL,
                    quantity=sell.quantity,
                    price=result.price,
                    executed_at=datetime.now(),
                    order_id=result.order_id,
                )
                await trade_repo.create(trade_record)

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

        buy_result = client.place_order(
            symbol=symbol,
            side=TRADE_SIDE_BUY,
            quantity=quantity,
        )

        if buy_result:
            # Record the buy trade
            trade_record = Trade(
                symbol=symbol,
                side=TRADE_SIDE_BUY,
                quantity=quantity,
                price=buy_result.price,
                executed_at=datetime.now(),
                order_id=buy_result.order_id,
            )
            await trade_repo.create(trade_record)

            # Clear recommendation cache
            cache.invalidate("recommendations:3")
            cache.invalidate("recommendations:10")
            cache.invalidate("sell_recommendations:3")
            cache.invalidate("sell_recommendations:20")
            cache.invalidate("multi_step_recommendations:default")
            # Invalidate all depth-specific caches
            for depth in range(1, 6):
                cache.invalidate(f"multi_step_recommendations:{depth}")

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
