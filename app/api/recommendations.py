"""Trade recommendation API endpoints.

Handles buy and sell recommendations, including generation, listing, and dismissal.
"""

import logging

from fastapi import APIRouter, HTTPException

from app.infrastructure.cache import cache
from app.infrastructure.dependencies import (
    RebalancingServiceDep,
    RecommendationRepositoryDep,
    TradeExecutionServiceDep,
    TradeSafetyServiceDep,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/debug")
async def debug_recommendations(
    rebalancing_service: RebalancingServiceDep,
):
    """
    Debug endpoint to see why recommendations are filtered out.
    """
    debug_info = await rebalancing_service.get_recommendations_debug()
    return debug_info


@router.get("")
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


@router.post("/{uuid}/dismiss")
async def dismiss_recommendation(
    uuid: str,
    recommendation_repo: RecommendationRepositoryDep,
):
    """
    Dismiss a recommendation by UUID.

    Marks the recommendation as dismissed, preventing it from appearing again.
    """
    from app.infrastructure.cache_invalidation import get_cache_invalidation_service

    try:
        # Check if recommendation exists
        rec = await recommendation_repo.get_by_uuid(uuid)
        if not rec:
            raise HTTPException(
                status_code=404, detail=f"Recommendation {uuid} not found"
            )

        # Mark as dismissed
        await recommendation_repo.mark_dismissed(uuid)

        # Invalidate caches
        cache_service = get_cache_invalidation_service()
        cache_service.invalidate_recommendation_caches()

        return {
            "status": "success",
            "uuid": uuid,
            "message": "Recommendation dismissed",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error dismissing recommendation {uuid}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sell")
async def get_sell_recommendations(
    rebalancing_service: RebalancingServiceDep,
    recommendation_repo: RecommendationRepositoryDep,
    limit: int = 3,
):
    """
    Get top N sell recommendations from database (status='pending').

    Returns prioritized list of positions to sell, with reasons.
    Recommendations are generated and stored when this endpoint is called,
    then filtered to exclude dismissed ones.
    Cached for 5 minutes.
    """
    # Check cache first, but validate it has UUIDs (invalidate if old format)
    cache_key = f"sell_recommendations:{limit}"
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
        logger.error(f"Error getting sell recommendations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sell/{uuid}/dismiss")
async def dismiss_sell_recommendation(
    uuid: str,
    recommendation_repo: RecommendationRepositoryDep,
):
    """
    Dismiss a sell recommendation by UUID.

    Marks the recommendation as dismissed, preventing it from appearing again.
    """
    from app.infrastructure.cache_invalidation import get_cache_invalidation_service

    try:
        # Check if recommendation exists
        rec = await recommendation_repo.get_by_uuid(uuid)
        if not rec:
            raise HTTPException(
                status_code=404, detail=f"Recommendation {uuid} not found"
            )

        # Mark as dismissed
        await recommendation_repo.mark_dismissed(uuid)

        # Invalidate caches
        cache_service = get_cache_invalidation_service()
        cache_service.invalidate_recommendation_caches()

        return {
            "status": "success",
            "uuid": uuid,
            "message": "Sell recommendation dismissed",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error dismissing sell recommendation {uuid}: {e}", exc_info=True)
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


@router.post("/sell/{symbol}/execute")
async def execute_sell_recommendation(
    symbol: str,
    rebalancing_service: RebalancingServiceDep,
    safety_service: TradeSafetyServiceDep,
    trade_execution_service: TradeExecutionServiceDep,
):
    """
    Execute a sell recommendation for a specific symbol.

    Gets the current sell recommendation and executes it via Tradernet.
    """
    from app.domain.value_objects.trade_side import TradeSide
    from app.infrastructure.cache_invalidation import get_cache_invalidation_service
    from app.infrastructure.external.tradernet_connection import (
        ensure_tradernet_connected,
    )

    symbol = symbol.upper()

    try:
        recommendations = await rebalancing_service.calculate_sell_recommendations(
            limit=20
        )

        # Find the recommendation for the requested symbol
        rec = next((r for r in recommendations if r.symbol == symbol), None)
        if not rec:
            raise HTTPException(
                status_code=404, detail=f"No sell recommendation found for {symbol}"
            )

        # Ensure connection
        client = await ensure_tradernet_connected()

        # Safety checks
        await safety_service.validate_trade(
            symbol=rec.symbol,
            side=TradeSide.SELL,
            quantity=rec.quantity,
            client=client,
            raise_on_error=True,
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
