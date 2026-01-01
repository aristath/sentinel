"""Pydantic models for Universe service REST API."""

from typing import List, Optional

from pydantic import BaseModel, Field


# Request Models


class SyncPricesRequest(BaseModel):
    """Request to sync security prices."""

    isins: List[str] = Field(..., description="List of ISINs to sync")


class SyncFundamentalsRequest(BaseModel):
    """Request to sync security fundamentals."""

    isins: List[str] = Field(..., description="List of ISINs to sync")


class AddSecurityRequest(BaseModel):
    """Request to add a new security."""

    isin: str
    symbol: str
    name: str
    exchange: Optional[str] = None


class AddSecurityResponse(BaseModel):
    """Response for adding a security."""

    success: bool
    message: str


class RemoveSecurityResponse(BaseModel):
    """Response for removing a security."""

    success: bool
    message: str


# Response Models


class SecurityResponse(BaseModel):
    """Security information response."""

    symbol: str
    name: str
    isin: Optional[str] = None
    exchange: Optional[str] = None
    product_type: Optional[str] = None
    currency: Optional[str] = None
    active: bool
    allow_buy: bool
    allow_sell: bool
    priority_multiplier: float
    min_lot: int

    class Config:
        from_attributes = True  # Allow conversion from domain models


class UniverseResponse(BaseModel):
    """Response with list of securities."""

    securities: List[SecurityResponse]
    total: int


class SyncResult(BaseModel):
    """Result of sync operation."""

    success: bool
    synced_count: int
    failed_count: int
    errors: List[str] = []


class MarketDataPoint(BaseModel):
    """Single market data point."""

    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class MarketDataResponse(BaseModel):
    """Market data response."""

    isin: str
    symbol: str
    data_points: List[MarketDataPoint]


class HealthResponse(BaseModel):
    """Health check response."""

    healthy: bool
    version: str
    status: str
    checks: dict = {}
