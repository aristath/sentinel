"""Security universe API endpoints."""

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.cache.cache import cache
from app.domain.events import SecurityAddedEvent, get_event_bus
from app.infrastructure.dependencies import (
    PortfolioServiceDep,
    PositionRepositoryDep,
    ScoreRepositoryDep,
    ScoringServiceDep,
    SecurityRepositoryDep,
    SecuritySetupServiceDep,
)
from app.infrastructure.recommendation_cache import get_recommendation_cache
from app.modules.universe.domain.priority_calculator import (
    PriorityCalculator,
    PriorityInput,
)
from app.modules.universe.domain.security_factory import SecurityFactory
from app.modules.universe.domain.symbol_resolver import is_isin

router = APIRouter()
logger = logging.getLogger(__name__)


class SecurityCreate(BaseModel):
    """Request model for creating a security."""

    symbol: str
    yahoo_symbol: Optional[str] = None
    name: str
    # country and fullExchangeName are auto-detected from Yahoo Finance
    min_lot: Optional[int] = 1
    allow_buy: Optional[bool] = True
    allow_sell: Optional[bool] = False


class SecurityAddByIdentifier(BaseModel):
    """Request model for adding a security by identifier (symbol or ISIN)."""

    identifier: str  # Symbol or ISIN
    min_lot: Optional[int] = 1
    allow_buy: Optional[bool] = True
    allow_sell: Optional[bool] = True


class SecurityUpdate(BaseModel):
    """Request model for updating a security."""

    new_symbol: Optional[str] = None
    name: Optional[str] = None
    yahoo_symbol: Optional[str] = None
    product_type: Optional[str] = None  # Manual override for misclassifications
    country: Optional[str] = None  # Manual entry for securities where Yahoo has no data
    industry: Optional[str] = (
        None  # Manual entry for securities where Yahoo has no data
    )
    fullExchangeName: Optional[str] = None  # Manual entry if needed
    priority_multiplier: Optional[float] = None
    min_lot: Optional[int] = None
    active: Optional[bool] = None
    allow_buy: Optional[bool] = None
    allow_sell: Optional[bool] = None
    min_portfolio_target: Optional[float] = None
    max_portfolio_target: Optional[float] = None


@router.get("")
async def get_stocks(
    security_repo: SecurityRepositoryDep,
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

    securities_data = await security_repo.get_with_scores()

    priority_inputs = []
    stock_dicts = []

    for security in securities_data:
        stock_dict = dict(security)
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


@router.get("/{isin}")
async def get_stock(
    isin: str,
    security_repo: SecurityRepositoryDep,
    position_repo: PositionRepositoryDep,
    score_repo: ScoreRepositoryDep,
):
    """Get detailed security info with score breakdown.

    Args:
        isin: Security ISIN (e.g., US0378331005)
    """
    # Validate ISIN format
    isin = isin.strip().upper()
    if not is_isin(isin):
        raise HTTPException(status_code=400, detail="Invalid ISIN format")

    security = await security_repo.get_by_isin(isin)
    if not security:
        raise HTTPException(status_code=404, detail="Security not found")

    # Use the resolved symbol for other lookups
    symbol = security.symbol
    score = await score_repo.get_by_symbol(symbol)
    position = await position_repo.get_by_symbol(symbol)

    result: dict[str, Any] = {
        "symbol": security.symbol,
        "isin": security.isin,
        "yahoo_symbol": security.yahoo_symbol,
        "name": security.name,
        "industry": security.industry,
        "country": security.country,
        "fullExchangeName": security.fullExchangeName,
        "priority_multiplier": security.priority_multiplier,
        "min_lot": security.min_lot,
        "active": security.active,
        "allow_buy": security.allow_buy,
        "allow_sell": security.allow_sell,
        "min_portfolio_target": security.min_portfolio_target,
        "max_portfolio_target": security.max_portfolio_target,
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
    security_data: SecurityCreate,
    security_repo: SecurityRepositoryDep,
    score_repo: ScoreRepositoryDep,
    scoring_service: ScoringServiceDep,
):
    """Add a new security to the universe."""

    existing = await security_repo.get_by_symbol(security_data.symbol.upper())
    if existing:
        raise HTTPException(status_code=400, detail="Security already exists")

    # Auto-detect country, exchange, and industry from Yahoo Finance
    from app.infrastructure.external import yahoo_finance as yahoo

    country, full_exchange_name = yahoo.get_security_country_and_exchange(
        security_data.symbol, security_data.yahoo_symbol
    )
    industry = yahoo.get_security_industry(
        security_data.symbol, security_data.yahoo_symbol
    )

    # Use factory to create security
    stock_dict = {
        "symbol": security_data.symbol,
        "name": security_data.name,
        "country": country,
        "fullExchangeName": full_exchange_name,
        "industry": industry,
        "yahoo_symbol": security_data.yahoo_symbol,
        "min_lot": security_data.min_lot,
        "allow_buy": security_data.allow_buy,
        "allow_sell": security_data.allow_sell,
    }

    new_stock = SecurityFactory.create_from_api_request(stock_dict)

    await security_repo.create(new_stock)

    # Publish domain event
    event_bus = get_event_bus()
    event_bus.publish(SecurityAddedEvent(security=new_stock))

    score = await scoring_service.calculate_and_save_score(
        security_data.symbol.upper(), security_data.yahoo_symbol
    )

    cache.invalidate("stocks_with_scores")

    return {
        "message": f"Security {security_data.symbol.upper()} added to universe",
        "symbol": security_data.symbol.upper(),
        "isin": new_stock.isin,
        "yahoo_symbol": security_data.yahoo_symbol,
        "name": security_data.name,
        "country": new_stock.country,
        "fullExchangeName": new_stock.fullExchangeName,
        "industry": industry,
        "min_lot": new_stock.min_lot,
        "total_score": score.total_score if score else None,
    }


@router.post("/add-by-identifier")
async def add_stock_by_identifier(
    security_data: SecurityAddByIdentifier,
    stock_setup_service: SecuritySetupServiceDep,
    score_repo: ScoreRepositoryDep,
):
    """Add a new security to the universe by symbol or ISIN.

    This endpoint accepts either:
    - Tradernet symbol (e.g., "AAPL.US")
    - ISIN (e.g., "US0378331005")

    The method will automatically:
    1. Resolve the identifier to get all necessary symbols
    2. Fetch data from Tradernet (symbol, name, currency, ISIN)
    3. Fetch data from Yahoo Finance (country, exchange, industry)
    4. Create the security in the database
    5. Fetch historical price data (10 years initial seed)
    6. Calculate and save the initial security score

    Args:
        security_data: Request containing identifier and optional settings
        stock_setup_service: Security setup service
        score_repo: Score repository for retrieving calculated score

    Returns:
        Created security data with score
    """
    try:
        # Validate identifier format (basic check)
        identifier = security_data.identifier.strip().upper()
        if not identifier:
            raise HTTPException(status_code=400, detail="Identifier cannot be empty")

        # Note: Security existence check is handled in the service, but we do it here
        # to provide better error messages before starting the setup process

        # Add the security
        security = await stock_setup_service.add_security_by_identifier(
            identifier=identifier,
            min_lot=security_data.min_lot or 1,
            allow_buy=(
                security_data.allow_buy if security_data.allow_buy is not None else True
            ),
            allow_sell=(
                security_data.allow_sell
                if security_data.allow_sell is not None
                else True
            ),
        )

        # Get the calculated score
        score = await score_repo.get_by_symbol(security.symbol)

        cache.invalidate("stocks_with_scores")

        return {
            "message": f"Security {security.symbol} added to universe",
            "symbol": security.symbol,
            "yahoo_symbol": security.yahoo_symbol,
            "isin": security.isin,
            "name": security.name,
            "country": security.country,
            "fullExchangeName": security.fullExchangeName,
            "industry": security.industry,
            "currency": str(security.currency) if security.currency else None,
            "min_lot": security.min_lot,
            "total_score": score.total_score if score else None,
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(
            status_code=503, detail=f"Tradernet connection failed: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Failed to add security by identifier: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to add security: {str(e)}")


@router.post("/refresh-all")
async def refresh_all_scores(
    security_repo: SecurityRepositoryDep,
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
        stocks = await security_repo.get_all_active()

        for security in stocks:
            if not security.industry:
                detected_industry = yahoo.get_security_industry(
                    security.symbol, security.yahoo_symbol
                )
                if detected_industry:
                    await security_repo.update(
                        security.symbol, industry=detected_industry
                    )

        scores = await scoring_service.score_all_stocks()

        return {
            "message": f"Refreshed scores for {len(scores)} stocks",
            "scores": [
                {"symbol": s.symbol, "total_score": s.total_score} for s in scores
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{isin}/refresh-data")
async def refresh_security_data(
    isin: str,
    security_repo: SecurityRepositoryDep,
):
    """Trigger full data refresh for a security.

    Runs the complete data pipeline:
    1. Sync historical prices from Yahoo
    2. Calculate technical metrics (RSI, EMA, CAGR, etc.)
    3. Refresh security score

    This bypasses the last_synced check and immediately processes the security.

    Args:
        isin: Security ISIN (e.g., US0378331005)
    """
    from app.jobs.securities_data_sync import refresh_single_security

    # Validate ISIN format
    isin = isin.strip().upper()
    if not is_isin(isin):
        raise HTTPException(status_code=400, detail="Invalid ISIN format")

    security = await security_repo.get_by_isin(isin)
    if not security:
        raise HTTPException(status_code=404, detail="Security not found")

    symbol = security.symbol

    # Invalidate recommendation cache so new data affects recommendations
    recommendation_cache = get_recommendation_cache()
    await recommendation_cache.invalidate_all_recommendations()

    # Run the full pipeline
    result = await refresh_single_security(symbol)

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


@router.post("/{isin}/refresh")
async def refresh_stock_score(
    isin: str,
    security_repo: SecurityRepositoryDep,
    scoring_service: ScoringServiceDep,
):
    """Trigger score recalculation for a security (quick, no historical data sync).

    Args:
        isin: Security ISIN (e.g., US0378331005)
    """
    # Validate ISIN format
    isin = isin.strip().upper()
    if not is_isin(isin):
        raise HTTPException(status_code=400, detail="Invalid ISIN format")

    # Invalidate recommendation cache so new score affects recommendations immediately
    recommendation_cache = get_recommendation_cache()
    await recommendation_cache.invalidate_all_recommendations()

    security = await security_repo.get_by_isin(isin)
    if not security:
        raise HTTPException(status_code=404, detail="Security not found")

    symbol = security.symbol
    score = await scoring_service.calculate_and_save_score(
        symbol,
        security.yahoo_symbol,
        country=security.country,
        industry=security.industry,
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
    old_symbol: str, new_symbol: str, security_repo: SecurityRepositoryDep
) -> None:
    """Validate that new symbol doesn't already exist."""
    if new_symbol != old_symbol:
        existing = await security_repo.get_by_symbol(new_symbol)
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
    update: SecurityUpdate, new_symbol: str | None
) -> dict[str, str | float | int | bool | None]:
    """Build dictionary of fields to update."""
    updates: dict[str, str | float | int | bool | None] = {}

    _apply_string_update(updates, "name", update.name)
    _apply_string_update(
        updates, "yahoo_symbol", update.yahoo_symbol, lambda v: v if v else None
    )
    _apply_string_update(updates, "product_type", update.product_type)
    _apply_string_update(updates, "country", update.country)
    _apply_string_update(updates, "industry", update.industry)
    _apply_string_update(updates, "fullExchangeName", update.fullExchangeName)

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


def _format_stock_response(security, score) -> dict:
    """Format security data for API response."""
    security_data = {
        "symbol": security.symbol,
        "isin": security.isin,
        "yahoo_symbol": security.yahoo_symbol,
        "name": security.name,
        "industry": security.industry,
        "country": security.country,
        "fullExchangeName": security.fullExchangeName,
        "priority_multiplier": security.priority_multiplier,
        "min_lot": security.min_lot,
        "active": security.active,
        "allow_buy": security.allow_buy,
        "allow_sell": security.allow_sell,
    }
    if score:
        security_data["total_score"] = score.total_score
    return security_data


@router.put("/{isin}")
async def update_stock(
    isin: str,
    update: SecurityUpdate,
    security_repo: SecurityRepositoryDep,
    scoring_service: ScoringServiceDep,
):
    """Update security details.

    Args:
        isin: Security ISIN (e.g., US0378331005)
    """
    try:
        # Validate ISIN format
        isin = isin.strip().upper()
        if not is_isin(isin):
            raise HTTPException(status_code=400, detail="Invalid ISIN format")

        security = await security_repo.get_by_isin(isin)
        if not security:
            raise HTTPException(status_code=404, detail="Security not found")

        old_symbol = security.symbol

        new_symbol = None
        if update.new_symbol is not None:
            new_symbol = update.new_symbol.upper()
            await _validate_symbol_change(old_symbol, new_symbol, security_repo)

        updates = _build_update_dict(
            update, new_symbol if new_symbol != old_symbol else None
        )
        if not updates:
            raise HTTPException(status_code=400, detail="No updates provided")

        await security_repo.update(old_symbol, **updates)

        final_symbol = (
            new_symbol if new_symbol and new_symbol != old_symbol else old_symbol
        )
        updated_stock = await security_repo.get_by_symbol(final_symbol)
        if not updated_stock:
            raise HTTPException(
                status_code=404, detail="Security not found after update"
            )

        try:
            score = await scoring_service.calculate_and_save_score(
                final_symbol,
                updated_stock.yahoo_symbol,
                country=updated_stock.country,
                industry=updated_stock.industry,
            )
        except Exception as e:
            logger.error(
                f"Failed to calculate score for {final_symbol}: {e}", exc_info=True
            )
            # Continue without score rather than failing the update
            score = None

        cache.invalidate("stocks_with_scores")

        return _format_stock_response(updated_stock, score)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update security {isin}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to update security: {str(e)}"
        )


@router.delete("/{isin}")
async def delete_stock(
    isin: str,
    security_repo: SecurityRepositoryDep,
):
    """Remove a security from the universe (soft delete by setting active=0).

    Args:
        isin: Security ISIN (e.g., US0378331005)
    """
    # Validate ISIN format
    isin = isin.strip().upper()
    if not is_isin(isin):
        raise HTTPException(status_code=400, detail="Invalid ISIN format")

    logger.info(f"DELETE /api/securities/{isin} - Attempting to delete security")

    security = await security_repo.get_by_isin(isin)
    if not security:
        logger.warning(f"DELETE /api/securities/{isin} - Security not found")
        raise HTTPException(status_code=404, detail="Security not found")

    symbol = security.symbol
    logger.info(
        f"DELETE /api/securities/{isin} - Soft deleting security {symbol} (setting active=0)"
    )
    await security_repo.delete(symbol)

    cache.invalidate("stocks_with_scores")

    logger.info(
        f"DELETE /api/securities/{isin} - Security {symbol} successfully deleted"
    )
    return {"message": f"Security {symbol} removed from universe"}
