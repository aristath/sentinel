"""Trade execution API endpoints."""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from enum import Enum
from app.domain.constants import TRADE_SIDE_BUY, TRADE_SIDE_SELL
from app.infrastructure.dependencies import (
    get_portfolio_repository,
    get_position_repository,
    get_allocation_repository,
    get_trade_repository,
    get_stock_repository,
)
from app.domain.repositories import (
    PortfolioRepository,
    PositionRepository,
    AllocationRepository,
    TradeRepository,
    StockRepository,
)
from app.infrastructure.cache import cache

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
async def get_trades(
    limit: int = 50,
    trade_repo: TradeRepository = Depends(get_trade_repository),
):
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
    stock_repo: StockRepository = Depends(get_stock_repository),
    trade_repo: TradeRepository = Depends(get_trade_repository),
):
    """Execute a manual trade."""
    # Side is now validated by Pydantic enum

    # Check stock exists
    stock = await stock_repo.get_by_symbol(trade.symbol)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    from app.services.tradernet import get_tradernet_client
    from app.domain.repositories import Trade

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
async def get_allocation(
    portfolio_repo: PortfolioRepository = Depends(get_portfolio_repository),
    position_repo: PositionRepository = Depends(get_position_repository),
    allocation_repo: AllocationRepository = Depends(get_allocation_repository),
):
    """Get current portfolio allocation vs targets."""
    from app.application.services.portfolio_service import PortfolioService

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
async def get_recommendations(
    limit: int = 3,
    stock_repo: StockRepository = Depends(get_stock_repository),
    position_repo: PositionRepository = Depends(get_position_repository),
    allocation_repo: AllocationRepository = Depends(get_allocation_repository),
    portfolio_repo: PortfolioRepository = Depends(get_portfolio_repository),
    trade_repo: TradeRepository = Depends(get_trade_repository),
):
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
        rebalancing_service = RebalancingService(
            stock_repo,
            position_repo,
            allocation_repo,
            portfolio_repo,
            trade_repo,
        )
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
async def execute_recommendation(
    symbol: str,
    stock_repo: StockRepository = Depends(get_stock_repository),
    position_repo: PositionRepository = Depends(get_position_repository),
    allocation_repo: AllocationRepository = Depends(get_allocation_repository),
    portfolio_repo: PortfolioRepository = Depends(get_portfolio_repository),
    trade_repo: TradeRepository = Depends(get_trade_repository),
):
    """
    Execute a single recommendation by symbol.

    Gets the current recommendation for the symbol and executes it.
    """
    from app.application.services.rebalancing_service import RebalancingService
    from app.services.tradernet import get_tradernet_client
    from app.domain.repositories import Trade

    symbol = symbol.upper()

    try:
        # Get recommendations to find this symbol
        rebalancing_service = RebalancingService(
            stock_repo,
            position_repo,
            allocation_repo,
            portfolio_repo,
            trade_repo,
        )
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
async def get_sell_recommendations(
    limit: int = 3,
    stock_repo: StockRepository = Depends(get_stock_repository),
    position_repo: PositionRepository = Depends(get_position_repository),
    allocation_repo: AllocationRepository = Depends(get_allocation_repository),
    portfolio_repo: PortfolioRepository = Depends(get_portfolio_repository),
):
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
        rebalancing_service = RebalancingService(
            stock_repo,
            position_repo,
            allocation_repo,
            portfolio_repo,
        )
        recommendations = await rebalancing_service.calculate_sell_recommendations(
            limit=limit
        )

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


@router.post("/sell-recommendations/{symbol}/execute")
async def execute_sell_recommendation(
    symbol: str,
    stock_repo: StockRepository = Depends(get_stock_repository),
    position_repo: PositionRepository = Depends(get_position_repository),
    allocation_repo: AllocationRepository = Depends(get_allocation_repository),
    portfolio_repo: PortfolioRepository = Depends(get_portfolio_repository),
    trade_repo: TradeRepository = Depends(get_trade_repository),
):
    """
    Execute a sell recommendation for a specific symbol.

    Gets the current sell recommendation and executes it via Tradernet.
    """
    from app.application.services.rebalancing_service import RebalancingService
    from app.services.tradernet import get_tradernet_client
    from app.domain.repositories import Trade

    try:
        rebalancing_service = RebalancingService(
            stock_repo,
            position_repo,
            allocation_repo,
            portfolio_repo,
            trade_repo,
        )

        # Get sell recommendations (fetch more to find the symbol)
        recommendations = await rebalancing_service.calculate_sell_recommendations(
            limit=20
        )

        # Find the recommendation for the requested symbol
        rec = next((r for r in recommendations if r.symbol == symbol.upper()), None)
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
                symbol=symbol.upper(),
                side=TRADE_SIDE_SELL,
                quantity=rec.quantity,
                price=result.price,
                executed_at=datetime.now(),
                order_id=result.order_id,
            )
            await trade_repo.create(trade_record)

            # Update last_sold_at
            if hasattr(position_repo, 'update_last_sold_at'):
                await position_repo.update_last_sold_at(symbol.upper())

            # Clear cache
            cache.delete(f"sell_recommendations:3")
            cache.delete(f"sell_recommendations:20")

            return {
                "status": "success",
                "order_id": result.order_id,
                "symbol": symbol.upper(),
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
