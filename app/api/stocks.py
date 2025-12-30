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
    StockSetupServiceDep,
)
from app.infrastructure.recommendation_cache import get_recommendation_cache

router = APIRouter()
logger = logging.getLogger(__name__)


class StockCreate(BaseModel):
    """Request model for creating a stock."""

    symbol: str
    yahoo_symbol: Optional[str] = None
    name: str
    # country and fullExchangeName are auto-detected from Yahoo Finance
    min_lot: Optional[int] = 1
    allow_buy: Optional[bool] = True
    allow_sell: Optional[bool] = False


class StockAddByIdentifier(BaseModel):
    """Request model for adding a stock by identifier (symbol or ISIN)."""

    identifier: str  # Symbol or ISIN
    min_lot: Optional[int] = 1
    allow_buy: Optional[bool] = True
    allow_sell: Optional[bool] = True


class StockUpdate(BaseModel):
    """Request model for updating a stock."""

    new_symbol: Optional[str] = None
    name: Optional[str] = None
    yahoo_symbol: Optional[str] = None
    # country and fullExchangeName are auto-detected from Yahoo Finance - not user-editable
    # Industry is now automatically detected from Yahoo Finance - not user-editable
    priority_multiplier: Optional[float] = None
    min_lot: Optional[int] = None
    active: Optional[bool] = None
    allow_buy: Optional[bool] = None
    allow_sell: Optional[bool] = None
    min_portfolio_target: Optional[float] = None
    max_portfolio_target: Optional[float] = None


@router.get("")
async def get_stocks(
    stock_repo: StockRepositoryDep,
    portfolio_service: PortfolioServiceDep,
    position_repo: PositionRepositoryDep,
):
    """Get all stocks in universe with current scores, position data, and priority.

    Includes automatic cache validation to detect stale position data:
    - Compares position count in database vs cached data
    - Invalidates cache if positions exist in DB but are missing from cache
    - Falls through to fetch fresh data when cache is invalidated
    """
    cached = cache.get("stocks_with_scores")
    if cached is not None:
        # Validate cached data: check if positions exist in DB but are missing from cache
        # This automatically detects when positions are synced but cache wasn't invalidated
        db_position_count = await position_repo.get_count()
        cached_with_positions = sum(1 for s in cached if s.get("position_value", 0) > 0)

        # If DB has positions but cache shows none, invalidate cache
        if db_position_count > 0 and cached_with_positions == 0:
            logger.warning(
                f"Cache mismatch detected: {db_position_count} positions in DB, "
                f"but cache shows {cached_with_positions}. Invalidating cache."
            )
            cache.invalidate("stocks_with_scores")
        # Allow small differences (e.g., rounding), but flag significant mismatches
        elif abs(db_position_count - cached_with_positions) > 2:
            logger.warning(
                f"Position count mismatch: DB={db_position_count}, "
                f"Cache={cached_with_positions}. Invalidating cache."
            )
            cache.invalidate("stocks_with_scores")
        else:
            # Cache looks valid, return it
            return cached

    stocks_data = await stock_repo.get_with_scores()

    priority_inputs = []
    stock_dicts = []

    for stock in stocks_data:
        stock_dict = dict(stock)
        stock_score = stock_dict.get("total_score") or 0
        volatility = stock_dict.get("volatility")
        multiplier = stock_dict.get("priority_multiplier") or 1.0
        country = stock_dict.get("country")
        industry = stock_dict.get("industry") or ""
        quality_score = stock_dict.get("quality_score")
        opportunity_score = stock_dict.get("opportunity_score")
        allocation_fit_score = stock_dict.get("allocation_fit_score")

        priority_inputs.append(
            PriorityInput(
                symbol=stock_dict["symbol"],
                name=stock_dict["name"],
                country=country,
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

    priority_results = PriorityCalculator.calculate_priorities(priority_inputs)

    priority_map = {r.symbol: r.combined_priority for r in priority_results}
    for stock_dict in stock_dicts:
        stock_dict["priority_score"] = round(
            priority_map.get(stock_dict["symbol"], 0), 3
        )

    cache.set("stocks_with_scores", stock_dicts, ttl_seconds=120)
    return stock_dicts


@router.get("/{identifier}")
async def get_stock(
    identifier: str,
    stock_repo: StockRepositoryDep,
    position_repo: PositionRepositoryDep,
    score_repo: ScoreRepositoryDep,
):
    """Get detailed stock info with score breakdown.

    Args:
        identifier: Stock symbol (e.g., AAPL.US) or ISIN (e.g., US0378331005)
    """
    stock = await stock_repo.get_by_identifier(identifier)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    # Use the resolved symbol for other lookups
    symbol = stock.symbol
    score = await score_repo.get_by_symbol(symbol)
    position = await position_repo.get_by_symbol(symbol)

    result: dict[str, Any] = {
        "symbol": stock.symbol,
        "yahoo_symbol": stock.yahoo_symbol,
        "name": stock.name,
        "industry": stock.industry,
        "country": stock.country,
        "fullExchangeName": stock.fullExchangeName,
        "priority_multiplier": stock.priority_multiplier,
        "min_lot": stock.min_lot,
        "active": stock.active,
        "allow_buy": stock.allow_buy,
        "allow_sell": stock.allow_sell,
        "min_portfolio_target": stock.min_portfolio_target,
        "max_portfolio_target": stock.max_portfolio_target,
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

    existing = await stock_repo.get_by_identifier(stock_data.symbol.upper())
    if existing:
        raise HTTPException(status_code=400, detail="Stock already exists")

    # Auto-detect country, exchange, and industry from Yahoo Finance
    from app.infrastructure.external import yahoo_finance as yahoo

    country, full_exchange_name = yahoo.get_stock_country_and_exchange(
        stock_data.symbol, stock_data.yahoo_symbol
    )
    industry = yahoo.get_stock_industry(stock_data.symbol, stock_data.yahoo_symbol)

    # Use factory to create stock
    stock_dict = {
        "symbol": stock_data.symbol,
        "name": stock_data.name,
        "country": country,
        "fullExchangeName": full_exchange_name,
        "industry": industry,
        "yahoo_symbol": stock_data.yahoo_symbol,
        "min_lot": stock_data.min_lot,
        "allow_buy": stock_data.allow_buy,
        "allow_sell": stock_data.allow_sell,
    }

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
        "country": new_stock.country,
        "fullExchangeName": new_stock.fullExchangeName,
        "industry": industry,
        "min_lot": new_stock.min_lot,
        "total_score": score.total_score if score else None,
    }


@router.post("/add-by-identifier")
async def add_stock_by_identifier(
    stock_data: StockAddByIdentifier,
    stock_setup_service: StockSetupServiceDep,
    score_repo: ScoreRepositoryDep,
):
    """Add a new stock to the universe by symbol or ISIN.

    This endpoint accepts either:
    - Tradernet symbol (e.g., "AAPL.US")
    - ISIN (e.g., "US0378331005")

    The method will automatically:
    1. Resolve the identifier to get all necessary symbols
    2. Fetch data from Tradernet (symbol, name, currency, ISIN)
    3. Fetch data from Yahoo Finance (country, exchange, industry)
    4. Create the stock in the database
    5. Fetch historical price data (10 years initial seed)
    6. Calculate and save the initial stock score

    Args:
        stock_data: Request containing identifier and optional settings
        stock_setup_service: Stock setup service
        score_repo: Score repository for retrieving calculated score

    Returns:
        Created stock data with score
    """
    try:
        # Validate identifier format (basic check)
        identifier = stock_data.identifier.strip().upper()
        if not identifier:
            raise HTTPException(status_code=400, detail="Identifier cannot be empty")

        # Note: Stock existence check is handled in the service, but we do it here
        # to provide better error messages before starting the setup process

        # Add the stock
        stock = await stock_setup_service.add_stock_by_identifier(
            identifier=identifier,
            min_lot=stock_data.min_lot or 1,
            allow_buy=(
                stock_data.allow_buy if stock_data.allow_buy is not None else True
            ),
            allow_sell=(
                stock_data.allow_sell if stock_data.allow_sell is not None else True
            ),
        )

        # Get the calculated score
        score = await score_repo.get_by_symbol(stock.symbol)

        cache.invalidate("stocks_with_scores")

        return {
            "message": f"Stock {stock.symbol} added to universe",
            "symbol": stock.symbol,
            "yahoo_symbol": stock.yahoo_symbol,
            "isin": stock.isin,
            "name": stock.name,
            "country": stock.country,
            "fullExchangeName": stock.fullExchangeName,
            "industry": stock.industry,
            "currency": str(stock.currency) if stock.currency else None,
            "min_lot": stock.min_lot,
            "total_score": score.total_score if score else None,
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(
            status_code=503, detail=f"Tradernet connection failed: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Failed to add stock by identifier: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to add stock: {str(e)}")


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


@router.post("/{identifier}/refresh-data")
async def refresh_stock_data(
    identifier: str,
    stock_repo: StockRepositoryDep,
):
    """Trigger full data refresh for a stock.

    Runs the complete data pipeline:
    1. Sync historical prices from Yahoo
    2. Calculate technical metrics (RSI, EMA, CAGR, etc.)
    3. Refresh stock score

    This bypasses the last_synced check and immediately processes the stock.

    Args:
        identifier: Stock symbol (e.g., AAPL.US) or ISIN (e.g., US0378331005)
    """
    from app.jobs.stocks_data_sync import refresh_single_stock

    stock = await stock_repo.get_by_identifier(identifier)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    symbol = stock.symbol

    # Invalidate recommendation cache so new data affects recommendations
    recommendation_cache = get_recommendation_cache()
    await recommendation_cache.invalidate_all_recommendations()

    # Run the full pipeline
    result = await refresh_single_stock(symbol)

    if result.get("status") == "success":
        return {
            "status": "success",
            "symbol": symbol,
            "message": f"Full data refresh completed for {symbol}",
        }
    else:
        raise HTTPException(
            status_code=500,
            detail=result.get("reason", "Data refresh failed"),
        )


@router.post("/{identifier}/refresh")
async def refresh_stock_score(
    identifier: str,
    stock_repo: StockRepositoryDep,
    scoring_service: ScoringServiceDep,
):
    """Trigger score recalculation for a stock (quick, no historical data sync).

    Args:
        identifier: Stock symbol (e.g., AAPL.US) or ISIN (e.g., US0378331005)
    """
    # Invalidate recommendation cache so new score affects recommendations immediately
    recommendation_cache = get_recommendation_cache()
    await recommendation_cache.invalidate_all_recommendations()

    stock = await stock_repo.get_by_identifier(identifier)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    symbol = stock.symbol
    score = await scoring_service.calculate_and_save_score(
        symbol,
        stock.yahoo_symbol,
        country=stock.country,
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
        existing = await stock_repo.get_by_identifier(new_symbol)
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
    # country and fullExchangeName are automatically detected from Yahoo Finance - not user-editable
    # Industry is now automatically detected from Yahoo Finance - not user-editable

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

    # Portfolio target validation
    if update.min_portfolio_target is not None:
        clamped_min = max(0.0, min(20.0, update.min_portfolio_target))
        updates["min_portfolio_target"] = clamped_min

    if update.max_portfolio_target is not None:
        clamped_max = max(0.0, min(30.0, update.max_portfolio_target))
        updates["max_portfolio_target"] = clamped_max

    # Validate that max >= min when both are provided
    min_target = updates.get("min_portfolio_target")
    max_target = updates.get("max_portfolio_target")
    if min_target is not None and max_target is not None:
        if isinstance(min_target, (int, float)) and isinstance(
            max_target, (int, float)
        ):
            if max_target < min_target:
                raise HTTPException(
                    status_code=400,
                    detail="max_portfolio_target must be >= min_portfolio_target",
                )

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
        "country": stock.country,
        "fullExchangeName": stock.fullExchangeName,
        "priority_multiplier": stock.priority_multiplier,
        "min_lot": stock.min_lot,
        "active": stock.active,
        "allow_buy": stock.allow_buy,
        "allow_sell": stock.allow_sell,
    }
    if score:
        stock_data["total_score"] = score.total_score
    return stock_data


@router.put("/{identifier}")
async def update_stock(
    identifier: str,
    update: StockUpdate,
    stock_repo: StockRepositoryDep,
    scoring_service: ScoringServiceDep,
):
    """Update stock details.

    Args:
        identifier: Stock symbol (e.g., AAPL.US) or ISIN (e.g., US0378331005)
    """
    stock = await stock_repo.get_by_identifier(identifier)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    old_symbol = stock.symbol

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
    updated_stock = await stock_repo.get_by_identifier(final_symbol)
    if not updated_stock:
        raise HTTPException(status_code=404, detail="Stock not found after update")

    score = await scoring_service.calculate_and_save_score(
        final_symbol, updated_stock.yahoo_symbol
    )

    cache.invalidate("stocks_with_scores")

    return _format_stock_response(updated_stock, score)


@router.delete("/{identifier}")
async def delete_stock(
    identifier: str,
    stock_repo: StockRepositoryDep,
):
    """Remove a stock from the universe (soft delete by setting active=0).

    Args:
        identifier: Stock symbol (e.g., AAPL.US) or ISIN (e.g., US0378331005)
    """
    logger.info(f"DELETE /api/stocks/{identifier} - Attempting to delete stock")

    stock = await stock_repo.get_by_identifier(identifier)
    if not stock:
        logger.warning(f"DELETE /api/stocks/{identifier} - Stock not found")
        raise HTTPException(status_code=404, detail="Stock not found")

    symbol = stock.symbol
    logger.info(
        f"DELETE /api/stocks/{identifier} - Soft deleting stock {symbol} (setting active=0)"
    )
    await stock_repo.delete(symbol)

    cache.invalidate("stocks_with_scores")

    logger.info(
        f"DELETE /api/stocks/{identifier} - Stock {symbol} successfully deleted"
    )
    return {"message": f"Stock {symbol} removed from universe"}
