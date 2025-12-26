"""Stock universe API endpoints."""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.domain.events import StockAddedEvent, get_event_bus
from app.domain.factories.stock_factory import StockFactory
from app.domain.services.priority_calculator import (
    PriorityCalculator,
    PriorityInput,
)
from app.infrastructure.cache import cache
from app.infrastructure.dependencies import (
    PortfolioServiceDep,
    PositionRepositoryDep,
    ScoreRepositoryDep,
    ScoringServiceDep,
    StockRepositoryDep,
)
from app.infrastructure.recommendation_cache import get_recommendation_cache

router = APIRouter()
logger = logging.getLogger(__name__)


class StockCreate(BaseModel):
    """Request model for creating a stock."""

    symbol: str
    yahoo_symbol: Optional[str] = None
    name: str
    geography: str
    industry: Optional[str] = None
    min_lot: Optional[int] = 1
    allow_buy: Optional[bool] = True
    allow_sell: Optional[bool] = False


class StockUpdate(BaseModel):
    """Request model for updating a stock."""

    new_symbol: Optional[str] = None
    name: Optional[str] = None
    yahoo_symbol: Optional[str] = None
    geography: Optional[str] = None
    industry: Optional[str] = None
    priority_multiplier: Optional[float] = None
    min_lot: Optional[int] = None
    active: Optional[bool] = None
    allow_buy: Optional[bool] = None
    allow_sell: Optional[bool] = None


@router.get("")
async def get_stocks(
    stock_repo: StockRepositoryDep,
    portfolio_service: PortfolioServiceDep,
):
    """Get all stocks in universe with current scores, position data, and priority."""
    cached = cache.get("stocks_with_scores")
    if cached is not None:
        return cached
    summary = await portfolio_service.get_portfolio_summary()

    geo_weights = {g.name: g.target_pct for g in summary.geographic_allocations}
    ind_weights = {i.name: i.target_pct for i in summary.industry_allocations}

    stocks_data = await stock_repo.get_with_scores()

    priority_inputs = []
    stock_dicts = []

    for stock in stocks_data:
        stock_dict = dict(stock)
        stock_score = stock_dict.get("total_score") or 0
        volatility = stock_dict.get("volatility")
        multiplier = stock_dict.get("priority_multiplier") or 1.0
        geo = stock_dict.get("geography")
        industry = stock_dict.get("industry")
        quality_score = stock_dict.get("quality_score")
        opportunity_score = stock_dict.get("opportunity_score")
        allocation_fit_score = stock_dict.get("allocation_fit_score")

        priority_inputs.append(
            PriorityInput(
                symbol=stock_dict["symbol"],
                name=stock_dict["name"],
                geography=geo,
                industry=industry,
                stock_score=stock_score,
                volatility=volatility,
                multiplier=multiplier,
                quality_score=quality_score,
                opportunity_score=opportunity_score,
                allocation_fit_score=allocation_fit_score,
            )
        )
        stock_dicts.append(stock_dict)

    priority_results = PriorityCalculator.calculate_priorities(
        priority_inputs,
        geo_weights,
        ind_weights,
    )

    priority_map = {r.symbol: r.combined_priority for r in priority_results}
    for stock_dict in stock_dicts:
        stock_dict["priority_score"] = round(
            priority_map.get(stock_dict["symbol"], 0), 3
        )

    cache.set("stocks_with_scores", stock_dicts, ttl_seconds=120)
    return stock_dicts


@router.get("/{symbol}")
async def get_stock(
    symbol: str,
    stock_repo: StockRepositoryDep,
    position_repo: PositionRepositoryDep,
    score_repo: ScoreRepositoryDep,
):
    """Get detailed stock info with score breakdown."""

    stock = await stock_repo.get_by_symbol(symbol)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    score = await score_repo.get_by_symbol(symbol)
    position = await position_repo.get_by_symbol(symbol)

    result = {
        "symbol": stock.symbol,
        "yahoo_symbol": stock.yahoo_symbol,
        "name": stock.name,
        "industry": stock.industry,
        "geography": stock.geography,
        "priority_multiplier": stock.priority_multiplier,
        "min_lot": stock.min_lot,
        "active": stock.active,
        "allow_buy": stock.allow_buy,
        "allow_sell": stock.allow_sell,
    }

    if score:
        result.update(
            {
                "quality_score": score.quality_score,
                "opportunity_score": score.opportunity_score,
                "analyst_score": score.analyst_score,
                "allocation_fit_score": score.allocation_fit_score,
                "total_score": score.total_score,
                "cagr_score": score.cagr_score,
                "consistency_score": score.consistency_score,
                "history_years": score.history_years,
                "volatility": score.volatility,
                "calculated_at": (
                    score.calculated_at.isoformat()
                    if score.calculated_at is not None
                    else None
                ),
                "technical_score": score.technical_score,
                "fundamental_score": score.fundamental_score,
            }
        )

    if position:
        result["position"] = {
            "symbol": position.symbol,
            "quantity": position.quantity,
            "avg_price": position.avg_price,
            "current_price": position.current_price,
            "currency": position.currency,
            "market_value_eur": position.market_value_eur,
        }
    else:
        result["position"] = None

    return result


@router.post("")
async def create_stock(
    stock_data: StockCreate,
    stock_repo: StockRepositoryDep,
    score_repo: ScoreRepositoryDep,
    scoring_service: ScoringServiceDep,
):
    """Add a new stock to the universe."""

    existing = await stock_repo.get_by_symbol(stock_data.symbol.upper())
    if existing:
        raise HTTPException(status_code=400, detail="Stock already exists")

    # Use factory to create stock
    stock_dict = {
        "symbol": stock_data.symbol,
        "name": stock_data.name,
        "geography": stock_data.geography,
        "industry": stock_data.industry,
        "yahoo_symbol": stock_data.yahoo_symbol,
        "min_lot": stock_data.min_lot,
        "allow_buy": stock_data.allow_buy,
        "allow_sell": stock_data.allow_sell,
    }

    # Detect industry if not provided
    if not stock_data.industry:
        from app.infrastructure.external import yahoo_finance as yahoo

        industry = yahoo.get_stock_industry(stock_data.symbol, stock_data.yahoo_symbol)
        new_stock = StockFactory.create_with_industry_detection(stock_dict, industry)
    else:
        new_stock = StockFactory.create_from_api_request(stock_dict)

    await stock_repo.create(new_stock)

    # Publish domain event
    event_bus = get_event_bus()
    event_bus.publish(StockAddedEvent(stock=new_stock))

    score = await scoring_service.calculate_and_save_score(
        stock_data.symbol.upper(), stock_data.yahoo_symbol
    )

    cache.invalidate("stocks_with_scores")

    return {
        "message": f"Stock {stock_data.symbol.upper()} added to universe",
        "symbol": stock_data.symbol.upper(),
        "yahoo_symbol": stock_data.yahoo_symbol,
        "name": stock_data.name,
        "geography": stock_data.geography.upper(),
        "industry": industry,
        "min_lot": new_stock.min_lot,
        "total_score": score.total_score if score else None,
    }


@router.post("/refresh-all")
async def refresh_all_scores(
    stock_repo: StockRepositoryDep,
    scoring_service: ScoringServiceDep,
):
    """Recalculate scores for all stocks in universe and update industries."""
    from app.infrastructure.external import yahoo_finance as yahoo

    # Invalidate recommendation cache so new scores affect recommendations immediately
    recommendation_cache = get_recommendation_cache()
    await recommendation_cache.invalidate_all_recommendations()
    logger.info("Invalidated recommendation cache for score refresh")

    # Invalidate in-memory recommendation caches
    cache.invalidate_prefix("recommendations")
    cache.invalidate_prefix("sell_recommendations")
    cache.invalidate_prefix("multi_step_recommendations")
    logger.info("Invalidated in-memory recommendation caches")

    try:
        stocks = await stock_repo.get_all_active()

        for stock in stocks:
            if not stock.industry:
                detected_industry = yahoo.get_stock_industry(
                    stock.symbol, stock.yahoo_symbol
                )
                if detected_industry:
                    await stock_repo.update(stock.symbol, industry=detected_industry)

        scores = await scoring_service.score_all_stocks()

        return {
            "message": f"Refreshed scores for {len(scores)} stocks",
            "scores": [
                {"symbol": s.symbol, "total_score": s.total_score} for s in scores
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{symbol}/refresh")
async def refresh_stock_score(
    symbol: str,
    stock_repo: StockRepositoryDep,
    scoring_service: ScoringServiceDep,
):
    """Trigger score recalculation for a stock."""
    # Invalidate recommendation cache so new score affects recommendations immediately
    recommendation_cache = get_recommendation_cache()
    await recommendation_cache.invalidate_all_recommendations()

    stock = await stock_repo.get_by_symbol(symbol)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    score = await scoring_service.calculate_and_save_score(
        symbol,
        stock.yahoo_symbol,
        geography=stock.geography,
        industry=stock.industry,
    )
    if score:
        return {
            "symbol": symbol,
            "total_score": score.total_score,
            "quality": (
                (
                    score.group_scores.get("long_term", 0)
                    + score.group_scores.get("fundamentals", 0)
                )
                / 2
                if score.group_scores
                else None
            ),
            "opportunity": (
                score.group_scores.get("opportunity") if score.group_scores else None
            ),
            "analyst": (
                score.group_scores.get("opinion") if score.group_scores else None
            ),
            "allocation_fit": (
                score.group_scores.get("diversification")
                if score.group_scores
                else None
            ),
            "volatility": score.volatility,
            "cagr_score": (
                score.sub_scores.get("long_term", {}).get("cagr")
                if score.sub_scores
                else None
            ),
            "consistency_score": (
                score.sub_scores.get("fundamentals", {}).get("consistency")
                if score.sub_scores
                else None
            ),
            "dividend_bonus": (
                score.sub_scores.get("dividends", {}).get("yield")
                if score.sub_scores
                else None
            ),
            "history_years": (
                5.0
                if score.sub_scores
                and score.sub_scores.get("long_term", {}).get("cagr")
                else None
            ),
        }

    raise HTTPException(status_code=500, detail="Failed to calculate score")


@router.put("/{symbol}")
async def update_stock(
    symbol: str,
    update: StockUpdate,
    stock_repo: StockRepositoryDep,
    scoring_service: ScoringServiceDep,
):
    """Update stock details."""

    old_symbol = symbol.upper()
    stock = await stock_repo.get_by_symbol(old_symbol)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    new_symbol = None
    if update.new_symbol is not None:
        new_symbol = update.new_symbol.upper()
        if new_symbol != old_symbol:
            existing = await stock_repo.get_by_symbol(new_symbol)
            if existing:
                raise HTTPException(
                    status_code=400, detail=f"Symbol {new_symbol} already exists"
                )

    updates = {}
    if update.name is not None:
        updates["name"] = update.name
    if update.yahoo_symbol is not None:
        updates["yahoo_symbol"] = update.yahoo_symbol if update.yahoo_symbol else None
    if update.geography is not None:
        updates["geography"] = update.geography.upper()
    if update.industry is not None:
        updates["industry"] = update.industry
    if update.priority_multiplier is not None:
        updates["priority_multiplier"] = max(0.1, min(3.0, update.priority_multiplier))
    if update.min_lot is not None:
        updates["min_lot"] = max(1, update.min_lot)
    if update.active is not None:
        updates["active"] = update.active
    if update.allow_buy is not None:
        updates["allow_buy"] = update.allow_buy
    if update.allow_sell is not None:
        updates["allow_sell"] = update.allow_sell

    if new_symbol and new_symbol != old_symbol:
        updates["symbol"] = new_symbol

    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    await stock_repo.update(old_symbol, **updates)

    final_symbol = new_symbol if new_symbol and new_symbol != old_symbol else old_symbol
    updated_stock = await stock_repo.get_by_symbol(final_symbol)

    score = await scoring_service.calculate_and_save_score(
        final_symbol, updated_stock.yahoo_symbol
    )

    cache.invalidate("stocks_with_scores")

    stock_data = {
        "symbol": updated_stock.symbol,
        "yahoo_symbol": updated_stock.yahoo_symbol,
        "name": updated_stock.name,
        "industry": updated_stock.industry,
        "geography": updated_stock.geography,
        "priority_multiplier": updated_stock.priority_multiplier,
        "min_lot": updated_stock.min_lot,
        "active": updated_stock.active,
        "allow_buy": updated_stock.allow_buy,
        "allow_sell": updated_stock.allow_sell,
    }

    if score:
        stock_data["total_score"] = score.total_score

    return stock_data


@router.delete("/{symbol}")
async def delete_stock(
    symbol: str,
    stock_repo: StockRepositoryDep,
):
    """Remove a stock from the universe (soft delete by setting active=0)."""

    logger.info(f"DELETE /api/stocks/{symbol} - Attempting to delete stock")

    stock = await stock_repo.get_by_symbol(symbol.upper())
    if not stock:
        logger.warning(f"DELETE /api/stocks/{symbol} - Stock not found")
        raise HTTPException(status_code=404, detail="Stock not found")

    logger.info(f"DELETE /api/stocks/{symbol} - Soft deleting stock (setting active=0)")
    await stock_repo.delete(symbol.upper())

    cache.invalidate("stocks_with_scores")

    logger.info(f"DELETE /api/stocks/{symbol} - Stock successfully deleted")
    return {"message": f"Stock {symbol.upper()} removed from universe"}
