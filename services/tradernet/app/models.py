"""Pydantic models for request/response handling."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ServiceResponse(BaseModel):
    """Standard response format for all endpoints."""

    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# Trading requests
class PlaceOrderRequest(BaseModel):
    """Request model for placing an order."""

    symbol: str = Field(..., min_length=1, description="Security symbol (e.g., AAPL.US)")
    side: str = Field(..., pattern="^(BUY|SELL)$", description="Order side: BUY or SELL")
    quantity: float = Field(..., gt=0, description="Quantity to trade")


class BatchQuotesRequest(BaseModel):
    """Request model for batch quote retrieval."""

    symbols: list[str] = Field(..., min_items=1, max_items=100, description="List of symbols")


# Response models
class OrderResult(BaseModel):
    """Order execution result."""

    order_id: str
    symbol: str
    side: str
    quantity: float
    price: float


class Position(BaseModel):
    """Portfolio position."""

    symbol: str
    quantity: float
    avg_price: float
    current_price: float
    market_value: float
    market_value_eur: float
    unrealized_pnl: float
    currency: str
    currency_rate: float


class CashBalance(BaseModel):
    """Cash balance in a currency."""

    currency: str
    amount: float


class Quote(BaseModel):
    """Market quote."""

    symbol: str
    price: float
    change: float
    change_pct: float
    volume: int
    timestamp: datetime


class OHLC(BaseModel):
    """OHLC candle."""

    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class Trade(BaseModel):
    """Executed trade."""

    order_id: str
    symbol: str
    side: str
    quantity: float
    price: float
    executed_at: str


class PendingOrder(BaseModel):
    """Pending order."""

    id: str
    symbol: str
    side: str
    quantity: float
    price: float
    currency: str


class CashTransaction(BaseModel):
    """Cash flow transaction."""

    transaction_id: str
    type_doc_id: str
    transaction_type: str
    date: str
    amount: float
    currency: str
    amount_eur: float
    status: str
    description: str


class SecurityInfo(BaseModel):
    """Security information."""

    symbol: str
    name: Optional[str] = None
    isin: Optional[str] = None
    currency: Optional[str] = None
    market: Optional[str] = None
    exchange_code: Optional[str] = None
