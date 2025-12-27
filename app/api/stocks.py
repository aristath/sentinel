"""Stock universe API endpoints."""

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.domain.events import StockAddedEvent, get_event_bus
from app.domain.factories.stock_factory import StockFactory
from app.domain.services.priority_calculator import PriorityCalculator, PriorityInput
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
        geo = stock_dict.get("geography") or ""
        industry = stock_dict.get("industry") or ""
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

    result: dict[str, Any] = {
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
            "symbol": str(position.symbol),
            "quantity": float(position.quantity),
            "avg_price": position.avg_price,
            "current_price": position.current_price,
            "currency": str(position.currency) if position.currency else None,
            "market_value_eur": position.market_value_eur,
            "last_updated": position.last_updated,
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
        industry = stock_data.industry
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
    cache.invalidate_prefix("recommendations")  # Unified recommendations cache
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


@router.post("/{symbol}/refresh-data")
async def refresh_stock_data(
    symbol: str,
    stock_repo: StockRepositoryDep,
):
    """Trigger full data refresh for a stock.

    Runs the complete data pipeline:
    1. Sync historical prices from Yahoo
    2. Calculate technical metrics (RSI, EMA, CAGR, etc.)
    3. Refresh stock score

    This bypasses the last_synced check and immediately processes the stock.
    """
    from app.jobs.daily_pipeline import refresh_single_stock

    stock = await stock_repo.get_by_symbol(symbol)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    # Invalidate recommendation cache so new data affects recommendations
    recommendation_cache = get_recommendation_cache()
    await recommendation_cache.invalidate_all_recommendations()

    # Run the full pipeline
    result = await refresh_single_stock(symbol.upper())

    if result.get("status") == "success":
        return {
            "status": "success",
            "symbol": symbol.upper(),
            "message": f"Full data refresh completed for {symbol.upper()}",
        }
    else:
        raise HTTPException(
            status_code=500,
            detail=result.get("reason", "Data refresh failed"),
        )


@router.post("/{symbol}/refresh")
async def refresh_stock_score(
    symbol: str,
    stock_repo: StockRepositoryDep,
    scoring_service: ScoringServiceDep,
):
    """Trigger score recalculation for a stock (quick, no historical data sync)."""
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


async def _validate_symbol_change(
    old_symbol: str, new_symbol: str, stock_repo: StockRepositoryDep
) -> None:
    """Validate that new symbol doesn't already exist."""
    if new_symbol != old_symbol:
        existing = await stock_repo.get_by_symbol(new_symbol)
        if existing:
            raise HTTPException(
                status_code=400, detail=f"Symbol {new_symbol} already exists"
            )


def _apply_string_update(
    updates: dict,
    field_name: str,
    value: str | None,
    transform=None,
    allow_none: bool = False,
) -> None:
    """Apply a string field update with optional transformation.

    Args:
        updates: Dictionary to update
        field_name: Name of the field
        value: Value to set (can be None or empty string to clear)
        transform: Optional transformation function
        allow_none: If True, allow None values to be set (for clearing fields)
    """
    if value is not None:
        updates[field_name] = transform(value) if transform else value
    elif allow_none:
        # Explicitly allow None to clear the field
        updates[field_name] = None


def _apply_numeric_update(
    updates: dict, field_name: str, value: float | int | None, clamp=None
) -> None:
    """Apply a numeric field update with optional clamping."""
    if value is not None:
        if clamp:
            updates[field_name] = clamp(value)
        else:
            updates[field_name] = value


def _apply_boolean_update(updates: dict, field_name: str, value: bool | None) -> None:
    """Apply a boolean field update."""
    if value is not None:
        updates[field_name] = value


def _build_update_dict(
    update: StockUpdate, new_symbol: str | None
) -> dict[str, str | float | int | bool | None]:
    """Build dictionary of fields to update."""
    updates: dict[str, str | float | int | bool | None] = {}

    _apply_string_update(updates, "name", update.name)
    _apply_string_update(
        updates, "yahoo_symbol", update.yahoo_symbol, lambda v: v if v else None
    )
    _apply_string_update(updates, "geography", update.geography, str.upper)
    # Handle industry: allow None/empty string to clear the field
    # Check if industry was explicitly provided in the request (not just default None)
    if hasattr(update, "model_fields_set") and "industry" in update.model_fields_set:
        # Industry was explicitly provided in the request
        if update.industry is None or (
            isinstance(update.industry, str) and not update.industry.strip()
        ):
            # Empty string or None -> clear the field
            updates["industry"] = None
        else:
            # Non-empty value -> set it (trimmed)
            updates["industry"] = update.industry.strip()

    _apply_numeric_update(
        updates,
        "priority_multiplier",
        update.priority_multiplier,
        lambda v: max(0.1, min(3.0, v)),
    )
    _apply_numeric_update(updates, "min_lot", update.min_lot, lambda v: max(1, v))

    _apply_boolean_update(updates, "active", update.active)
    _apply_boolean_update(updates, "allow_buy", update.allow_buy)
    _apply_boolean_update(updates, "allow_sell", update.allow_sell)

    if new_symbol:
        updates["symbol"] = new_symbol

    return updates


def _format_stock_response(stock, score) -> dict:
    """Format stock data for API response."""
    stock_data = {
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
        stock_data["total_score"] = score.total_score
    return stock_data


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
        await _validate_symbol_change(old_symbol, new_symbol, stock_repo)

    updates = _build_update_dict(
        update, new_symbol if new_symbol != old_symbol else None
    )
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    await stock_repo.update(old_symbol, **updates)

    final_symbol = new_symbol if new_symbol and new_symbol != old_symbol else old_symbol
    updated_stock = await stock_repo.get_by_symbol(final_symbol)
    if not updated_stock:
        raise HTTPException(status_code=404, detail="Stock not found after update")

    score = await scoring_service.calculate_and_save_score(
        final_symbol, updated_stock.yahoo_symbol
    )

    cache.invalidate("stocks_with_scores")

    return _format_stock_response(updated_stock, score)


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
