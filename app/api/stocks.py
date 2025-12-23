"""Stock universe API endpoints."""

import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.infrastructure.dependencies import (
    get_stock_repository,
    get_score_repository,
    get_allocation_repository,
    get_position_repository,
    get_portfolio_repository,
)
from app.infrastructure.cache import cache
from app.domain.repositories import (
    StockRepository,
    ScoreRepository,
    AllocationRepository,
    PositionRepository,
    PortfolioRepository,
)
from app.application.services.portfolio_service import PortfolioService
from app.domain.services.priority_calculator import (
    PriorityCalculator,
    PriorityInput,
)

router = APIRouter()
logger = logging.getLogger(__name__)


class StockCreate(BaseModel):
    """Request model for creating a stock."""
    symbol: str
    yahoo_symbol: Optional[str] = None  # Explicit Yahoo Finance symbol override
    name: str
    geography: str  # EU, ASIA, US
    industry: Optional[str] = None  # Auto-detect if not provided
    min_lot: Optional[int] = 1  # Minimum lot size (e.g., 100 for Japanese stocks)
    allow_buy: Optional[bool] = True  # Include in buy recommendations
    allow_sell: Optional[bool] = False  # Include in sell recommendations


class StockUpdate(BaseModel):
    """Request model for updating a stock."""
    new_symbol: Optional[str] = None  # New symbol for renaming
    name: Optional[str] = None
    yahoo_symbol: Optional[str] = None  # Explicit Yahoo Finance symbol override
    geography: Optional[str] = None
    industry: Optional[str] = None
    priority_multiplier: Optional[float] = None  # Manual priority adjustment (0.1 to 3.0)
    min_lot: Optional[int] = None  # Minimum lot size for trading
    active: Optional[bool] = None
    allow_buy: Optional[bool] = None  # Include in buy recommendations
    allow_sell: Optional[bool] = None  # Include in sell recommendations


@router.get("")
async def get_stocks(
    stock_repo: StockRepository = Depends(get_stock_repository),
    portfolio_repo: PortfolioRepository = Depends(get_portfolio_repository),
    position_repo: PositionRepository = Depends(get_position_repository),
    allocation_repo: AllocationRepository = Depends(get_allocation_repository),
):
    """Get all stocks in universe with current scores, position data, and priority.
    Cached for 2 minutes.
    """
    # Check cache first
    cached = cache.get("stocks_with_scores")
    if cached is not None:
        return cached

    # Get portfolio summary for allocation weights
    portfolio_service = PortfolioService(
        portfolio_repo,
        position_repo,
        allocation_repo,
    )
    summary = await portfolio_service.get_portfolio_summary()
    
    # target_pct now stores weights (-1 to +1) instead of percentages
    geo_weights = {g.name: g.target_pct for g in summary.geographic_allocations}
    ind_weights = {i.name: i.target_pct for i in summary.industry_allocations}
    total_value = summary.total_value or 1  # Avoid division by zero

    # Get stocks with scores and positions
    stocks_data = await stock_repo.get_with_scores()

    # Calculate priorities using domain service
    priority_inputs = []
    stock_dicts = []

    for stock in stocks_data:
        stock_dict = dict(stock)
        stock_score = stock_dict.get("total_score") or 0
        volatility = stock_dict.get("volatility")
        multiplier = stock_dict.get("priority_multiplier") or 1.0
        geo = stock_dict.get("geography")
        industry = stock_dict.get("industry")

        # New scoring breakdown fields
        quality_score = stock_dict.get("quality_score")
        opportunity_score = stock_dict.get("opportunity_score")
        allocation_fit_score = stock_dict.get("allocation_fit_score")

        priority_inputs.append(PriorityInput(
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
        ))
        stock_dicts.append(stock_dict)

    # Calculate priorities
    priority_results = PriorityCalculator.calculate_priorities(
        priority_inputs,
        geo_weights,
        ind_weights,
    )

    # Map priorities back to stocks
    priority_map = {r.symbol: r.combined_priority for r in priority_results}
    for stock_dict in stock_dicts:
        stock_dict["priority_score"] = round(priority_map.get(stock_dict["symbol"], 0), 3)

    # Cache for 2 minutes
    cache.set("stocks_with_scores", stock_dicts, ttl_seconds=120)
    return stock_dicts


@router.get("/{symbol}")
async def get_stock(
    symbol: str,
    stock_repo: StockRepository = Depends(get_stock_repository),
    position_repo: PositionRepository = Depends(get_position_repository),
    score_repo: ScoreRepository = Depends(get_score_repository),
):
    """Get detailed stock info with score breakdown."""
    stock = await stock_repo.get_by_symbol(symbol)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    # Get score
    score = await score_repo.get_by_symbol(symbol)
    
    # Get position if any
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
        result.update({
            # New scoring breakdown
            "quality_score": score.quality_score,
            "opportunity_score": score.opportunity_score,
            "analyst_score": score.analyst_score,
            "allocation_fit_score": score.allocation_fit_score,
            "total_score": score.total_score,
            # Additional details
            "cagr_score": score.cagr_score,
            "consistency_score": score.consistency_score,
            "history_years": score.history_years,
            "volatility": score.volatility,
            "calculated_at": score.calculated_at.isoformat() if score.calculated_at is not None else None,
            # Legacy fields for backwards compatibility
            "technical_score": score.technical_score,
            "fundamental_score": score.fundamental_score,
        })

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
    stock: StockCreate,
    stock_repo: StockRepository = Depends(get_stock_repository),
    score_repo: ScoreRepository = Depends(get_score_repository),
):
    """Add a new stock to the universe."""
    # Check if already exists
    existing = await stock_repo.get_by_symbol(stock.symbol.upper())
    if existing:
        raise HTTPException(status_code=400, detail="Stock already exists")

    # Auto-detect industry if not provided
    industry = stock.industry
    if not industry:
        from app.services import yahoo
        industry = yahoo.get_stock_industry(stock.symbol, stock.yahoo_symbol)

    # Validate min_lot
    min_lot = max(1, stock.min_lot or 1)

    # Create stock domain model
    from app.domain.repositories import Stock
    new_stock = Stock(
        symbol=stock.symbol.upper(),
        yahoo_symbol=stock.yahoo_symbol,
        name=stock.name,
        geography=stock.geography.upper(),
        industry=industry,
        priority_multiplier=1.0,
        min_lot=min_lot,
        active=True,
        allow_buy=stock.allow_buy if stock.allow_buy is not None else True,
        allow_sell=stock.allow_sell if stock.allow_sell is not None else False,
    )

    # Insert stock
    await stock_repo.create(new_stock)

    # Auto-calculate score for new stock
    from app.application.services.scoring_service import ScoringService
    scoring_service = ScoringService(stock_repo, score_repo)
    score = await scoring_service.calculate_and_save_score(
        stock.symbol.upper(),
        stock.yahoo_symbol
    )

    # Invalidate cache
    cache.invalidate("stocks_with_scores")

    return {
        "message": f"Stock {stock.symbol.upper()} added to universe",
        "symbol": stock.symbol.upper(),
        "yahoo_symbol": stock.yahoo_symbol,
        "name": stock.name,
        "geography": stock.geography.upper(),
        "industry": industry,
        "min_lot": min_lot,
        "total_score": score.total_score if score else None,
    }


@router.post("/refresh-all")
async def refresh_all_scores(
    stock_repo: StockRepository = Depends(get_stock_repository),
    score_repo: ScoreRepository = Depends(get_score_repository),
):
    """Recalculate scores for all stocks in universe and update industries."""
    from app.services import yahoo

    try:
        # Get all active stocks
        stocks = await stock_repo.get_all_active()

        # Update industries from Yahoo Finance for stocks without industry
        for stock in stocks:
            if not stock.industry:  # No industry set
                detected_industry = yahoo.get_stock_industry(stock.symbol, stock.yahoo_symbol)
                if detected_industry:
                    await stock_repo.update(stock.symbol, industry=detected_industry)

        # Calculate scores using application service
        from app.application.services.scoring_service import ScoringService
        scoring_service = ScoringService(stock_repo, score_repo)
        scores = await scoring_service.score_all_stocks()
        
        return {
            "message": f"Refreshed scores for {len(scores)} stocks",
            "scores": [
                {"symbol": s.symbol, "total_score": s.total_score}
                for s in scores
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{symbol}/refresh")
async def refresh_stock_score(
    symbol: str,
    stock_repo: StockRepository = Depends(get_stock_repository),
    score_repo: ScoreRepository = Depends(get_score_repository),
):
    """Trigger score recalculation for a stock."""
    # Check stock exists
    stock = await stock_repo.get_by_symbol(symbol)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    # Calculate and save score using application service
    from app.application.services.scoring_service import ScoringService
    scoring_service = ScoringService(stock_repo, score_repo)
    
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
            "quality": score.quality.total,
            "opportunity": score.opportunity.total,
            "analyst": score.analyst.total,
            "allocation_fit": score.allocation_fit.total if score.allocation_fit else None,
            "volatility": score.volatility,
            # Quality breakdown
            "cagr_score": score.quality.total_return_score,
            "consistency_score": score.quality.consistency_score,
            "dividend_bonus": score.quality.dividend_bonus,
            "history_years": score.quality.history_years,
        }

    raise HTTPException(status_code=500, detail="Failed to calculate score")


@router.put("/{symbol}")
async def update_stock(
    symbol: str,
    update: StockUpdate,
    stock_repo: StockRepository = Depends(get_stock_repository),
    score_repo: ScoreRepository = Depends(get_score_repository),
):
    """Update stock details."""
    old_symbol = symbol.upper()

    # Check stock exists
    stock = await stock_repo.get_by_symbol(old_symbol)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    # Handle symbol rename if new_symbol is provided
    new_symbol = None
    if update.new_symbol is not None:
        new_symbol = update.new_symbol.upper()
        if new_symbol != old_symbol:
            # Check if new symbol already exists
            existing = await stock_repo.get_by_symbol(new_symbol)
            if existing:
                raise HTTPException(
                    status_code=400,
                    detail=f"Symbol {new_symbol} already exists"
                )

    # Build update dict
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
        # Clamp multiplier between 0.1 and 3.0
        updates["priority_multiplier"] = max(0.1, min(3.0, update.priority_multiplier))
    if update.min_lot is not None:
        # Ensure min_lot is at least 1
        updates["min_lot"] = max(1, update.min_lot)
    if update.active is not None:
        updates["active"] = update.active
    if update.allow_buy is not None:
        updates["allow_buy"] = update.allow_buy
    if update.allow_sell is not None:
        updates["allow_sell"] = update.allow_sell

    # Include symbol rename in updates if requested
    if new_symbol and new_symbol != old_symbol:
        updates["symbol"] = new_symbol

    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    # Update stock (repository handles symbol rename with cascading updates)
    await stock_repo.update(old_symbol, **updates)

    # Determine the final symbol
    final_symbol = new_symbol if new_symbol and new_symbol != old_symbol else old_symbol

    # Get updated stock
    updated_stock = await stock_repo.get_by_symbol(final_symbol)

    # Auto-refresh score after update
    from app.application.services.scoring_service import ScoringService
    scoring_service = ScoringService(stock_repo, score_repo)
    score = await scoring_service.calculate_and_save_score(
        final_symbol,
        updated_stock.yahoo_symbol
    )

    # Invalidate cache
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
        stock_data['total_score'] = score.total_score

    return stock_data


@router.delete("/{symbol}")
async def delete_stock(
    symbol: str,
    stock_repo: StockRepository = Depends(get_stock_repository),
):
    """Remove a stock from the universe (soft delete by setting active=0)."""
    logger.info(f"DELETE /api/stocks/{symbol} - Attempting to delete stock")
    
    # Check stock exists
    stock = await stock_repo.get_by_symbol(symbol.upper())
    if not stock:
        logger.warning(f"DELETE /api/stocks/{symbol} - Stock not found")
        raise HTTPException(status_code=404, detail="Stock not found")

    # Soft delete - set active = 0
    logger.info(f"DELETE /api/stocks/{symbol} - Soft deleting stock (setting active=0)")
    await stock_repo.delete(symbol.upper())

    # Invalidate cache
    cache.invalidate("stocks_with_scores")

    logger.info(f"DELETE /api/stocks/{symbol} - Stock successfully deleted")
    return {"message": f"Stock {symbol.upper()} removed from universe"}
