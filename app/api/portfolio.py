"""Portfolio API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
import aiosqlite
from app.database import get_db

router = APIRouter()


class ManualDeposits(BaseModel):
    """Model for setting manual deposits."""
    amount: float


@router.get("")
async def get_portfolio(db: aiosqlite.Connection = Depends(get_db)):
    """Get current portfolio positions with values."""
    cursor = await db.execute("""
        SELECT p.*, s.name as stock_name, s.industry, s.geography
        FROM positions p
        LEFT JOIN stocks s ON p.symbol = s.symbol
        ORDER BY (p.quantity * p.current_price) DESC
    """)
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


def infer_geography(symbol: str) -> str:
    """Infer geography from symbol suffix."""
    symbol = symbol.upper()
    if symbol.endswith(".GR") or symbol.endswith(".DE") or symbol.endswith(".PA"):
        return "EU"
    elif symbol.endswith(".AS") or symbol.endswith(".HK") or symbol.endswith(".T"):
        return "ASIA"
    elif symbol.endswith(".US"):
        return "US"
    return "OTHER"


@router.get("/summary")
async def get_portfolio_summary(db: aiosqlite.Connection = Depends(get_db)):
    """Get portfolio summary: total value, cash, allocation percentages."""
    # Get all positions with optional geography from stocks table
    cursor = await db.execute("""
        SELECT p.symbol, p.quantity, p.current_price, p.avg_price, p.market_value_eur, s.geography
        FROM positions p
        LEFT JOIN stocks s ON p.symbol = s.symbol
    """)
    rows = await cursor.fetchall()

    # Calculate values by geography
    geo_values = {"EU": 0.0, "ASIA": 0.0, "US": 0.0}
    total_value = 0.0

    for row in rows:
        # Use stored EUR value if available, otherwise fallback to calculation
        value = row["market_value_eur"] or (row["quantity"] * (row["current_price"] or row["avg_price"] or 0))
        total_value += value

        geo = row["geography"] or infer_geography(row["symbol"])
        if geo in geo_values:
            geo_values[geo] += value

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
            "EU": geo_values.get("EU", 0) / total_value * 100 if total_value else 0,
            "ASIA": geo_values.get("ASIA", 0) / total_value * 100 if total_value else 0,
            "US": geo_values.get("US", 0) / total_value * 100 if total_value else 0,
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


@router.get("/deposits")
async def get_manual_deposits(db: aiosqlite.Connection = Depends(get_db)):
    """Get manual deposits setting."""
    cursor = await db.execute(
        "SELECT value FROM settings WHERE key = 'manual_deposits'"
    )
    row = await cursor.fetchone()
    amount = float(row["value"]) if row else 0.0
    return {"amount": amount}


@router.put("/deposits")
async def set_manual_deposits(
    deposits: ManualDeposits,
    db: aiosqlite.Connection = Depends(get_db)
):
    """Set manual deposits amount (EUR)."""
    await db.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES ('manual_deposits', ?)",
        (str(deposits.amount),)
    )
    await db.commit()
    return {"message": "Manual deposits updated", "amount": deposits.amount}


@router.get("/pnl")
async def get_portfolio_pnl(db: aiosqlite.Connection = Depends(get_db)):
    """
    Get portfolio profit/loss.

    Calculates: Total P&L = Current Total Value - Net Deposits
    Where Net Deposits = Manual Deposits - Withdrawals
    """
    from app.services.tradernet import get_tradernet_client

    client = get_tradernet_client()
    if not client.is_connected:
        if not client.connect():
            return {
                "error": "Not connected to Tradernet",
                "pnl": None,
                "pnl_pct": None,
            }

    try:
        # Get current total portfolio value (positions + cash)
        total_value = client.get_total_portfolio_value_eur()

        # Get withdrawal history from API
        cash_movements = client.get_cash_movements()
        total_withdrawals = cash_movements.get("total_withdrawals", 0)

        # Get manual deposits from database
        cursor = await db.execute(
            "SELECT value FROM settings WHERE key = 'manual_deposits'"
        )
        row = await cursor.fetchone()
        manual_deposits = float(row["value"]) if row else 0.0

        # Calculate net deposits (manual deposits - withdrawals)
        net_deposits = manual_deposits - total_withdrawals

        # Calculate P&L
        pnl = total_value - net_deposits
        pnl_pct = (pnl / net_deposits * 100) if net_deposits > 0 else 0

        return {
            "total_value": round(total_value, 2),
            "manual_deposits": manual_deposits,
            "total_withdrawals": total_withdrawals,
            "net_deposits": round(net_deposits, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "deposits_set": manual_deposits > 0,
        }
    except Exception as e:
        return {
            "error": str(e),
            "pnl": None,
            "pnl_pct": None,
        }
