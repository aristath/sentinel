"""Stock universe API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
import aiosqlite
from app.database import get_db

router = APIRouter()


@router.get("")
async def get_stocks(db: aiosqlite.Connection = Depends(get_db)):
    """Get all stocks in universe with current scores."""
    cursor = await db.execute("""
        SELECT s.*, sc.technical_score, sc.analyst_score,
               sc.fundamental_score, sc.total_score, sc.calculated_at
        FROM stocks s
        LEFT JOIN scores sc ON s.symbol = sc.symbol
        WHERE s.active = 1
        ORDER BY sc.total_score DESC NULLS LAST
    """)
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


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
    # Check stock exists
    cursor = await db.execute("SELECT 1 FROM stocks WHERE symbol = ?", (symbol,))
    if not await cursor.fetchone():
        raise HTTPException(status_code=404, detail="Stock not found")

    # TODO: Trigger scoring service
    return {"message": f"Score refresh queued for {symbol}"}
