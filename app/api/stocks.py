"""Stock universe API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
import aiosqlite
from app.database import get_db
from app.services.allocator import get_portfolio_summary, parse_industries

router = APIRouter()


class StockCreate(BaseModel):
    """Request model for creating a stock."""
    symbol: str
    yahoo_symbol: Optional[str] = None  # Explicit Yahoo Finance symbol override
    name: str
    geography: str  # EU, ASIA, US
    industry: Optional[str] = None  # Auto-detect if not provided
    min_lot: Optional[int] = 1  # Minimum lot size (e.g., 100 for Japanese stocks)


class StockUpdate(BaseModel):
    """Request model for updating a stock."""
    name: Optional[str] = None
    yahoo_symbol: Optional[str] = None  # Explicit Yahoo Finance symbol override
    geography: Optional[str] = None
    industry: Optional[str] = None
    priority_multiplier: Optional[float] = None  # Manual priority adjustment (0.1 to 3.0)
    min_lot: Optional[int] = None  # Minimum lot size for trading
    active: Optional[bool] = None


@router.get("")
async def get_stocks(db: aiosqlite.Connection = Depends(get_db)):
    """Get all stocks in universe with current scores, position data, and priority."""
    # Get allocation weights for priority calculation
    summary = await get_portfolio_summary(db)
    # target_pct now stores weights (-1 to +1) instead of percentages
    geo_weights = {g.name: g.target_pct for g in summary.geographic_allocations}
    ind_weights = {i.name: i.target_pct for i in summary.industry_allocations}

    total_value = summary.total_value or 1  # Avoid division by zero

    cursor = await db.execute("""
        SELECT s.*, sc.technical_score, sc.analyst_score,
               sc.fundamental_score, sc.total_score, sc.volatility,
               sc.calculated_at,
               p.quantity as shares, p.current_price, p.avg_price,
               p.market_value_eur as position_value
        FROM stocks s
        LEFT JOIN scores sc ON s.symbol = sc.symbol
        LEFT JOIN positions p ON s.symbol = p.symbol
        WHERE s.active = 1
    """)
    rows = await cursor.fetchall()

    stocks = []
    for row in rows:
        stock = dict(row)
        stock_score = stock.get("total_score") or 0
        volatility = stock.get("volatility")
        multiplier = stock.get("priority_multiplier") or 1.0
        geo = stock.get("geography")
        industries = parse_industries(stock.get("industry"))
        position_value = stock.get("position_value") or 0

        # 1. Stock quality with conviction boost (high scorers get extra)
        conviction_boost = max(0, (stock_score - 0.5) * 0.4) if stock_score > 0.5 else 0
        quality = stock_score + conviction_boost

        # 2. Allocation weight boost
        # Get weight for this stock's geography and industries
        # Weight ranges from -1 (avoid) to +1 (prioritize), 0 = neutral
        geo_weight = geo_weights.get(geo, 0)  # Default 0 = neutral
        geo_boost = calculate_weight_boost(geo_weight)

        ind_boost = 0.5  # Default neutral
        if industries:
            ind_boosts = [calculate_weight_boost(ind_weights.get(ind, 0)) for ind in industries]
            ind_boost = sum(ind_boosts) / len(ind_boosts)

        # Combined allocation boost (weighted average of geo and industry)
        allocation_boost = geo_boost * 0.6 + ind_boost * 0.4

        # 3. Diversification penalty (reduce priority for concentrated positions)
        position_pct = position_value / total_value if total_value > 0 else 0
        # Higher weight = ok to have more, lower weight = penalize concentration more
        geo_concentration_penalty = position_pct * (1 - geo_boost)
        diversification = 1.0 - min(0.5, geo_concentration_penalty * 3)

        # 4. Risk adjustment based on volatility (lower vol = higher score)
        risk_adj = calculate_risk_adjustment(volatility)

        # Weighted combination (quality 40%, allocation 30%, diversification 15%, risk 15%)
        raw_priority = (
            quality * 0.40 +
            allocation_boost * 0.30 +
            diversification * 0.15 +
            risk_adj * 0.15
        )

        # Apply manual multiplier
        priority_score = raw_priority * multiplier
        stock["priority_score"] = round(priority_score, 3)

        stocks.append(stock)

    return stocks


def calculate_weight_boost(weight: float) -> float:
    """
    Convert allocation weight (-1 to +1) to priority boost (0 to 1).

    Weight scale:
    - weight = +1 → boost = 1.0 (strong buy signal)
    - weight = 0 → boost = 0.5 (neutral)
    - weight = -1 → boost = 0.0 (avoid)
    """
    # Clamp weight to valid range
    weight = max(-1, min(1, weight))
    # Linear mapping: -1 → 0, 0 → 0.5, +1 → 1.0
    return (weight + 1) / 2


def calculate_risk_adjustment(volatility: float) -> float:
    """Lower score for higher volatility."""
    if volatility is None:
        return 0.5  # Neutral if unknown
    # 15% vol = 1.0, 50% vol = 0.0
    return max(0, min(1, 1 - (volatility - 0.15) / 0.35))


@router.get("/{symbol}")
async def get_stock(symbol: str, db: aiosqlite.Connection = Depends(get_db)):
    """Get detailed stock info with score breakdown."""
    cursor = await db.execute("""
        SELECT s.*, sc.technical_score, sc.analyst_score,
               sc.fundamental_score, sc.total_score, sc.calculated_at
        FROM stocks s
        LEFT JOIN scores sc ON s.symbol = sc.symbol
        WHERE s.symbol = ?
    """, (symbol,))
    row = await cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Stock not found")

    # Get position if any
    cursor = await db.execute("""
        SELECT * FROM positions WHERE symbol = ?
    """, (symbol,))
    position = await cursor.fetchone()

    return {
        **dict(row),
        "position": dict(position) if position else None,
    }


@router.post("/{symbol}/refresh")
async def refresh_stock_score(symbol: str, db: aiosqlite.Connection = Depends(get_db)):
    """Trigger score recalculation for a stock."""
    # Check stock exists and get yahoo_symbol
    cursor = await db.execute(
        "SELECT yahoo_symbol FROM stocks WHERE symbol = ?",
        (symbol,)
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Stock not found")

    yahoo_symbol = row[0]  # May be None

    from app.services.scorer import calculate_stock_score

    score = calculate_stock_score(symbol, yahoo_symbol)
    if score:
        await db.execute(
            """
            INSERT OR REPLACE INTO scores
            (symbol, technical_score, analyst_score, fundamental_score,
             total_score, volatility, calculated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                symbol,
                score.technical.total,
                score.analyst.total,
                score.fundamental.total,
                score.total_score,
                score.technical.volatility_raw,
                score.calculated_at.isoformat(),
            ),
        )
        await db.commit()

        return {
            "symbol": symbol,
            "total_score": score.total_score,
            "technical": score.technical.total,
            "analyst": score.analyst.total,
            "fundamental": score.fundamental.total,
            "volatility": score.technical.volatility_raw,
        }

    raise HTTPException(status_code=500, detail="Failed to calculate score")


@router.post("/refresh-all")
async def refresh_all_scores(db: aiosqlite.Connection = Depends(get_db)):
    """Recalculate scores for all stocks in universe and update industries."""
    from app.services.scorer import score_all_stocks
    from app.services import yahoo

    try:
        # Get all active stocks with yahoo_symbol overrides
        cursor = await db.execute(
            "SELECT symbol, yahoo_symbol, industry FROM stocks WHERE active = 1"
        )
        rows = await cursor.fetchall()

        # Update industries from Yahoo Finance for stocks without industry
        for row in rows:
            symbol = row[0]
            yahoo_symbol = row[1]  # May be None
            industry = row[2]

            if not industry:  # No industry set
                detected_industry = yahoo.get_stock_industry(symbol, yahoo_symbol)
                if detected_industry:
                    await db.execute(
                        "UPDATE stocks SET industry = ? WHERE symbol = ?",
                        (detected_industry, symbol)
                    )

        await db.commit()

        # Now calculate scores
        scores = await score_all_stocks(db)
        return {
            "message": f"Refreshed scores for {len(scores)} stocks",
            "scores": [
                {"symbol": s.symbol, "total_score": s.total_score}
                for s in scores
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
async def create_stock(stock: StockCreate, db: aiosqlite.Connection = Depends(get_db)):
    """Add a new stock to the universe."""
    # Check if already exists
    cursor = await db.execute(
        "SELECT 1 FROM stocks WHERE symbol = ?",
        (stock.symbol.upper(),)
    )
    if await cursor.fetchone():
        raise HTTPException(status_code=400, detail="Stock already exists")

    # Validate geography against allocation targets
    cursor = await db.execute(
        "SELECT name FROM allocation_targets WHERE type = 'geography'"
    )
    valid_geos = [row[0] for row in await cursor.fetchall()]
    if stock.geography.upper() not in valid_geos:
        raise HTTPException(
            status_code=400,
            detail=f"Geography must be one of: {', '.join(valid_geos)}"
        )

    # Auto-detect industry if not provided
    industry = stock.industry
    if not industry:
        from app.services import yahoo
        industry = yahoo.get_stock_industry(stock.symbol, stock.yahoo_symbol)

    # Validate min_lot
    min_lot = max(1, stock.min_lot or 1)

    # Insert stock
    await db.execute(
        """
        INSERT INTO stocks (symbol, yahoo_symbol, name, geography, industry, min_lot, active)
        VALUES (?, ?, ?, ?, ?, ?, 1)
        """,
        (
            stock.symbol.upper(),
            stock.yahoo_symbol,
            stock.name,
            stock.geography.upper(),
            industry,
            min_lot,
        )
    )
    await db.commit()

    # Auto-calculate score for new stock
    from app.services.scorer import calculate_stock_score
    score = calculate_stock_score(stock.symbol.upper(), stock.yahoo_symbol)
    if score:
        await db.execute(
            """
            INSERT OR REPLACE INTO scores
            (symbol, technical_score, analyst_score, fundamental_score,
             total_score, volatility, calculated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                stock.symbol.upper(),
                score.technical.total,
                score.analyst.total,
                score.fundamental.total,
                score.total_score,
                score.technical.volatility_raw,
                score.calculated_at.isoformat(),
            ),
        )
        await db.commit()

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


@router.put("/{symbol}")
async def update_stock(
    symbol: str,
    update: StockUpdate,
    db: aiosqlite.Connection = Depends(get_db)
):
    """Update stock details."""
    # Check stock exists
    cursor = await db.execute(
        "SELECT * FROM stocks WHERE symbol = ?",
        (symbol.upper(),)
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Stock not found")

    # Build update query
    updates = []
    values = []

    if update.name is not None:
        updates.append("name = ?")
        values.append(update.name)

    if update.yahoo_symbol is not None:
        # Allow setting to empty string to clear the override
        updates.append("yahoo_symbol = ?")
        values.append(update.yahoo_symbol if update.yahoo_symbol else None)

    if update.geography is not None:
        # Validate geography against allocation targets
        cursor = await db.execute(
            "SELECT name FROM allocation_targets WHERE type = 'geography'"
        )
        valid_geos = [row[0] for row in await cursor.fetchall()]
        if update.geography.upper() not in valid_geos:
            raise HTTPException(
                status_code=400,
                detail=f"Geography must be one of: {', '.join(valid_geos)}"
            )
        updates.append("geography = ?")
        values.append(update.geography.upper())

    if update.industry is not None:
        updates.append("industry = ?")
        values.append(update.industry)

    if update.priority_multiplier is not None:
        # Clamp multiplier between 0.1 and 3.0
        multiplier = max(0.1, min(3.0, update.priority_multiplier))
        updates.append("priority_multiplier = ?")
        values.append(multiplier)

    if update.min_lot is not None:
        # Ensure min_lot is at least 1
        min_lot = max(1, update.min_lot)
        updates.append("min_lot = ?")
        values.append(min_lot)

    if update.active is not None:
        updates.append("active = ?")
        values.append(1 if update.active else 0)

    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    values.append(symbol.upper())

    await db.execute(
        f"UPDATE stocks SET {', '.join(updates)} WHERE symbol = ?",
        values
    )
    await db.commit()

    # Get updated stock data
    cursor = await db.execute(
        "SELECT * FROM stocks WHERE symbol = ?",
        (symbol.upper(),)
    )
    row = await cursor.fetchone()
    stock_data = dict(row)

    # Auto-refresh score after update
    from app.services.scorer import calculate_stock_score
    score = calculate_stock_score(symbol.upper(), stock_data.get('yahoo_symbol'))
    if score:
        await db.execute(
            """
            INSERT OR REPLACE INTO scores
            (symbol, technical_score, analyst_score, fundamental_score,
             total_score, volatility, calculated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                symbol.upper(),
                score.technical.total,
                score.analyst.total,
                score.fundamental.total,
                score.total_score,
                score.technical.volatility_raw,
                score.calculated_at.isoformat(),
            ),
        )
        await db.commit()
        stock_data['total_score'] = score.total_score

    return stock_data


@router.delete("/{symbol}")
async def delete_stock(symbol: str, db: aiosqlite.Connection = Depends(get_db)):
    """Remove a stock from the universe (soft delete by setting active=0)."""
    # Check stock exists
    cursor = await db.execute(
        "SELECT 1 FROM stocks WHERE symbol = ?",
        (symbol.upper(),)
    )
    if not await cursor.fetchone():
        raise HTTPException(status_code=404, detail="Stock not found")

    # Soft delete - set active = 0
    await db.execute(
        "UPDATE stocks SET active = 0 WHERE symbol = ?",
        (symbol.upper(),)
    )
    await db.commit()

    return {"message": f"Stock {symbol.upper()} removed from universe"}
