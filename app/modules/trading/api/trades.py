"""Trade execution API endpoints."""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.domain.value_objects.trade_side import TradeSide
from app.infrastructure.cache_invalidation import get_cache_invalidation_service
from app.infrastructure.dependencies import (
    ConcentrationAlertServiceDep,
    PortfolioServiceDep,
    PositionRepositoryDep,
    SecurityRepositoryDep,
    TradeExecutionServiceDep,
    TradeRepositoryDep,
    TradeSafetyServiceDep,
)
from app.infrastructure.external.tradernet_connection import ensure_tradernet_connected
from app.modules.universe.domain.symbol_resolver import is_isin

logger = logging.getLogger(__name__)
router = APIRouter()


class TradeRequest(BaseModel):
    symbol: str = Field(
        ..., min_length=1, description="Stock ISIN (e.g., US0378331005)"
    )  # ISIN only
    side: TradeSide = Field(..., description="Trade side: BUY or SELL")
    quantity: float = Field(
        ..., gt=0, description="Quantity to trade (must be positive)"
    )

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        """Validate and normalize ISIN."""
        v = v.upper().strip()
        if not is_isin(v):
            raise ValueError(
                "Symbol must be a valid ISIN (12 characters, e.g., US0378331005)"
            )
        return v

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, v: float) -> float:
        """Validate quantity is reasonable."""
        if v <= 0:
            raise ValueError("Quantity must be greater than 0")
        if v > 1000000:  # Reasonable upper limit
            raise ValueError("Quantity exceeds maximum allowed (1,000,000)")
        return v


def _is_currency_conversion(symbol: str) -> bool:
    """Check if symbol is a currency conversion pair."""
    return "/" in symbol and len(symbol.split("/")) == 2


def _get_currency_conversion_name(symbol: str) -> str:
    """Get display name for currency conversion."""
    parts = symbol.split("/")
    if len(parts) == 2:
        from_curr, to_curr = parts
        return f"{from_curr} → {to_curr}"
    return symbol


@router.get("")
async def get_trades(
    trade_repo: TradeRepositoryDep,
    stock_repo: SecurityRepositoryDep,
    limit: int = 50,
):
    """Get trade history."""
    trades = await trade_repo.get_history(limit=limit)

    # Build symbol to name mapping for stocks
    stock_names = {}
    for trade in trades:
        if not _is_currency_conversion(trade.symbol):
            if trade.symbol not in stock_names:
                stock = await stock_repo.get_by_symbol(trade.symbol)
                stock_names[trade.symbol] = stock.name if stock else trade.symbol

    return [
        {
            "id": t.id,
            "symbol": t.symbol,
            "name": (
                _get_currency_conversion_name(t.symbol)
                if _is_currency_conversion(t.symbol)
                else stock_names.get(t.symbol, t.symbol)
            ),
            "side": t.side,
            "quantity": t.quantity,
            "price": t.price,
            "executed_at": t.executed_at.isoformat() if t.executed_at else None,
            "order_id": t.order_id,
        }
        for t in trades
    ]


@router.post("/execute")
async def execute_trade(
    trade: TradeRequest,
    stock_repo: SecurityRepositoryDep,
    trade_repo: TradeRepositoryDep,
    position_repo: PositionRepositoryDep,
    safety_service: TradeSafetyServiceDep,
    trade_execution_service: TradeExecutionServiceDep,
):
    """Execute a manual trade.

    The symbol field must be an ISIN.
    """
    # Check stock exists - trade.symbol is validated as ISIN by the model
    stock = await stock_repo.get_by_isin(trade.symbol)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    # Use the resolved symbol for trading
    symbol = stock.symbol

    # Ensure connection
    client = await ensure_tradernet_connected()
    await safety_service.validate_trade(
        symbol=symbol,
        side=trade.side,
        quantity=trade.quantity,
        client=client,
        raise_on_error=True,
    )

    result = client.place_order(
        symbol=symbol,
        side=trade.side.value,
        quantity=trade.quantity,
    )

    if result:
        # Record trade using service
        await trade_execution_service.record_trade(
            symbol=symbol,
            side=trade.side,
            quantity=trade.quantity,
            price=result.price,
            order_id=result.order_id,
        )

        # Invalidate caches
        cache_service = get_cache_invalidation_service()
        cache_service.invalidate_trade_caches()

        return {
            "status": "success",
            "order_id": result.order_id,
            "symbol": symbol,
            "side": trade.side,
            "quantity": trade.quantity,
            "price": result.price,
        }

    raise HTTPException(status_code=500, detail="Trade execution failed")


@router.get("/allocation")
async def get_allocation(
    portfolio_service: PortfolioServiceDep,
    alert_service: ConcentrationAlertServiceDep,
):
    """Get current portfolio allocation vs targets."""
    summary = await portfolio_service.get_portfolio_summary()
    alerts = await alert_service.detect_alerts(summary)

    return {
        "total_value": summary.total_value,
        "cash_balance": summary.cash_balance,
        "country": [
            {
                "name": a.name,
                "target_pct": a.target_pct,
                "current_pct": a.current_pct,
                "current_value": a.current_value,
                "deviation": a.deviation,
            }
            for a in summary.country_allocations
        ],
        "industry": [
            {
                "name": a.name,
                "target_pct": a.target_pct,
                "current_pct": a.current_pct,
                "current_value": a.current_value,
                "deviation": a.deviation,
            }
            for a in summary.industry_allocations
        ],
        "alerts": [
            {
                "type": alert.type,
                "name": alert.name,
                "current_pct": alert.current_pct,
                "limit_pct": alert.limit_pct,
                "alert_threshold_pct": alert.alert_threshold_pct,
                "severity": alert.severity,
            }
            for alert in alerts
        ],
    }
