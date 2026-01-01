"""Pydantic models for Portfolio service REST API."""

from typing import List, Optional

from pydantic import BaseModel, Field


# Request Models


class GetPositionsRequest(BaseModel):
    """Request to get positions."""

    account_id: str = Field(default="default", description="Account identifier")


class UpdatePositionsRequest(BaseModel):
    """Request to update positions."""

    account_id: str = Field(default="default", description="Account identifier")


# Response Models


class PositionResponse(BaseModel):
    """Single position response."""

    symbol: str
    isin: Optional[str] = None
    quantity: int
    average_price: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: Optional[float] = None


class PositionsResponse(BaseModel):
    """List of positions response."""

    positions: List[PositionResponse]
    total_positions: int


class SummaryResponse(BaseModel):
    """Portfolio summary response."""

    portfolio_hash: str
    total_value: float
    total_cost: float = 0.0
    total_pnl: float
    cash_balance: float
    position_count: int


class PerformanceDataPoint(BaseModel):
    """Single performance data point."""

    date: str
    portfolio_value: float
    cash_balance: float
    total_pnl: float
    daily_return_pct: float = 0.0
    cumulative_return_pct: float = 0.0


class PerformanceResponse(BaseModel):
    """Portfolio performance response."""

    history: List[PerformanceDataPoint]


class CashBalanceResponse(BaseModel):
    """Cash balance response."""

    cash_balance: float
    pending_deposits: float = 0.0
    pending_withdrawals: float = 0.0
    available_for_trading: float


class UpdatePositionsResponse(BaseModel):
    """Update positions operation response."""

    success: bool
    positions_updated: int
    positions_added: int
    positions_removed: int


class HealthResponse(BaseModel):
    """Health check response."""

    healthy: bool
    version: str
    status: str
    checks: dict = {}
