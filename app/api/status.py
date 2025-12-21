"""System status API endpoints."""

from datetime import datetime
from fastapi import APIRouter, Depends
import aiosqlite
from app.database import get_db
from app.config import settings

router = APIRouter()


@router.get("")
async def get_status(db: aiosqlite.Connection = Depends(get_db)):
    """Get system health and status."""
    # Get last sync time
    cursor = await db.execute("""
        SELECT date FROM portfolio_snapshots ORDER BY date DESC LIMIT 1
    """)
    row = await cursor.fetchone()
    last_sync = row["date"] if row else None

    # Get stock count
    cursor = await db.execute("SELECT COUNT(*) as count FROM stocks WHERE active = 1")
    stock_count = (await cursor.fetchone())["count"]

    # Get position count
    cursor = await db.execute("SELECT COUNT(*) as count FROM positions")
    position_count = (await cursor.fetchone())["count"]

    # Calculate next rebalance date
    today = datetime.now()
    if today.day >= settings.monthly_rebalance_day:
        # Next month
        if today.month == 12:
            next_rebalance = datetime(today.year + 1, 1, settings.monthly_rebalance_day)
        else:
            next_rebalance = datetime(today.year, today.month + 1, settings.monthly_rebalance_day)
    else:
        next_rebalance = datetime(today.year, today.month, settings.monthly_rebalance_day)

    return {
        "status": "healthy",
        "last_sync": last_sync,
        "next_rebalance": next_rebalance.isoformat(),
        "stock_universe_count": stock_count,
        "active_positions": position_count,
        "monthly_deposit": settings.monthly_deposit,
    }


@router.get("/led")
async def get_led_status():
    """Get current LED matrix state."""
    # TODO: Get actual LED state from MCU
    return {
        "mode": "idle",
        "message": "LED display not connected",
    }
