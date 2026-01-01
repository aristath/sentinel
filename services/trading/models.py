"""Pydantic models for Trading service REST API."""

from typing import List, Optional

from pydantic import BaseModel, Field


# Request Models


class ExecuteTradeRequest(BaseModel):
    """Request to execute a trade."""

    account_id: str = Field(default="default", description="Account identifier")
    isin: Optional[str] = None
    symbol: str
    side: str = Field(..., description="BUY or SELL")
    quantity: int = Field(..., gt=0, description="Number of shares")
    limit_price: Optional[float] = Field(default=None, description="Limit price (None for market order)")


class BatchExecuteTradesRequest(BaseModel):
    """Request to execute multiple trades."""

    trades: List[ExecuteTradeRequest]


class ValidateTradeRequest(BaseModel):
    """Request to validate a trade before execution."""

    account_id: str = Field(default="default", description="Account identifier")
    isin: Optional[str] = None
    symbol: str
    side: str = Field(..., description="BUY or SELL")
    quantity: int = Field(..., gt=0, description="Number of shares")
    limit_price: Optional[float] = None


# Response Models


class TradeExecution(BaseModel):
    """Trade execution details."""

    trade_id: str
    isin: Optional[str] = None
    symbol: str
    side: str
    quantity_requested: int
    quantity_filled: int
    average_price: float


class ExecuteTradeResponse(BaseModel):
    """Response from trade execution."""

    success: bool
    trade_id: str
    status: str  # EXECUTED, FAILED, PENDING
    message: str
    execution: Optional[TradeExecution] = None


class BatchExecuteTradesResponse(BaseModel):
    """Response from batch trade execution."""

    all_success: bool
    results: List[ExecuteTradeResponse]
    successful: int
    failed: int


class TradeStatusResponse(BaseModel):
    """Trade status response."""

    found: bool
    trade_id: Optional[str] = None
    status: str  # EXECUTED, FAILED, PENDING, CANCELLED, UNKNOWN
    message: str


class TradeHistoryResponse(BaseModel):
    """Trade history response."""

    executions: List[TradeExecution]
    total: int


class CancelTradeResponse(BaseModel):
    """Cancel trade response."""

    success: bool
    message: str


class ValidateTradeResponse(BaseModel):
    """Trade validation response."""

    valid: bool
    errors: List[str] = []
    warnings: List[str] = []


class HealthResponse(BaseModel):
    """Health check response."""

    healthy: bool
    version: str
    status: str
    checks: dict = {}
