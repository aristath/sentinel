"""Portfolio API endpoints."""

from fastapi import APIRouter, Depends
import aiosqlite
from app.database import get_db

router = APIRouter()


@router.get("")
async def get_portfolio(db: aiosqlite.Connection = Depends(get_db)):
    """Get current portfolio positions with values."""
    cursor = await db.execute("""
        SELECT p.*, s.name, s.industry, s.geography
        FROM positions p
        JOIN stocks s ON p.symbol = s.symbol
        ORDER BY (p.quantity * p.current_price) DESC
    """)
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


@router.get("/summary")
async def get_portfolio_summary(db: aiosqlite.Connection = Depends(get_db)):
    """Get portfolio summary: total value, cash, allocation percentages."""
    # Get total portfolio value by geography
    cursor = await db.execute("""
        SELECT
            s.geography,
            SUM(p.quantity * COALESCE(p.current_price, p.avg_price)) as value
        FROM positions p
        JOIN stocks s ON p.symbol = s.symbol
        GROUP BY s.geography
    """)
    geo_values = {row["geography"]: row["value"] for row in await cursor.fetchall()}

    total_value = sum(geo_values.values()) if geo_values else 0

    # Get latest snapshot for cash balance
    cursor = await db.execute("""
        SELECT cash_balance FROM portfolio_snapshots
        ORDER BY date DESC LIMIT 1
    """)
    row = await cursor.fetchone()
    cash_balance = row["cash_balance"] if row else 0

    return {
        "total_value": total_value,
        "cash_balance": cash_balance,
        "allocations": {
            "EU": geo_values.get("EU", 0) / total_value if total_value else 0,
            "ASIA": geo_values.get("ASIA", 0) / total_value if total_value else 0,
            "US": geo_values.get("US", 0) / total_value if total_value else 0,
        },
    }


@router.get("/history")
async def get_portfolio_history(db: aiosqlite.Connection = Depends(get_db)):
    """Get historical portfolio snapshots."""
    cursor = await db.execute("""
        SELECT * FROM portfolio_snapshots
        ORDER BY date DESC
        LIMIT 90
    """)
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]
