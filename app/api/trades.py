"""Trade execution API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import aiosqlite
from app.database import get_db

router = APIRouter()


class TradeRequest(BaseModel):
    symbol: str
    side: str  # BUY or SELL
    quantity: float


class RebalancePreview(BaseModel):
    deposit_amount: float = 1000.0


@router.get("")
async def get_trades(
    limit: int = 50,
    db: aiosqlite.Connection = Depends(get_db)
):
    """Get trade history."""
    cursor = await db.execute("""
        SELECT t.*, s.name
        FROM trades t
        JOIN stocks s ON t.symbol = s.symbol
        ORDER BY t.executed_at DESC
        LIMIT ?
    """, (limit,))
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


@router.post("/execute")
async def execute_trade(
    trade: TradeRequest,
    db: aiosqlite.Connection = Depends(get_db)
):
    """Execute a manual trade."""
    if trade.side not in ("BUY", "SELL"):
        raise HTTPException(status_code=400, detail="Side must be BUY or SELL")

    # Check stock exists
    cursor = await db.execute("SELECT 1 FROM stocks WHERE symbol = ?", (trade.symbol,))
    if not await cursor.fetchone():
        raise HTTPException(status_code=404, detail="Stock not found")

    # TODO: Execute via Tradernet API
    return {"message": f"Trade queued: {trade.side} {trade.quantity} {trade.symbol}"}


@router.post("/rebalance/preview")
async def preview_rebalance(
    request: RebalancePreview,
    db: aiosqlite.Connection = Depends(get_db)
):
    """Preview rebalance trades for deposit."""
    # TODO: Implement rebalance logic
    return {
        "deposit_amount": request.deposit_amount,
        "suggested_trades": [],
        "message": "Rebalance preview - implementation pending",
    }


@router.post("/rebalance/execute")
async def execute_rebalance(db: aiosqlite.Connection = Depends(get_db)):
    """Execute monthly rebalance."""
    # TODO: Implement rebalance execution
    return {"message": "Rebalance execution - implementation pending"}
