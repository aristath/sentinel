"""Pydantic models for API request/response validation and documentation."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# Portfolio Response Models
class PortfolioPosition(BaseModel):
    """Portfolio position with stock information."""

    symbol: str
    name: str
    quantity: float
    avg_price: float
    current_price: float
    market_value: float
    market_value_eur: float
    unrealized_pnl: float
    currency: str
    currency_rate: float


class PortfolioSummary(BaseModel):
    """Portfolio summary information."""

    total_value: float
    invested_value: float
    unrealized_pnl: float
    cash_balance: float
    position_count: int


class CashBalance(BaseModel):
    """Cash balance in a currency."""

    currency: str
    amount: float


class CashBreakdownResponse(BaseModel):
    """Cash breakdown response."""

    balances: List[CashBalance]
    total_eur: float


class DailyReturn(BaseModel):
    """Daily return data point."""

    date: str
    return_: float = Field(..., alias="return", description="Return value")


class MonthlyReturn(BaseModel):
    """Monthly return data point."""

    month: str
    return_: float = Field(..., alias="return", description="Return value")


class ReturnsData(BaseModel):
    """Returns data for analytics."""

    daily: List[DailyReturn]
    monthly: List[MonthlyReturn]
    annual: float


class RiskMetrics(BaseModel):
    """Risk metrics for portfolio."""

    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    volatility: float
    max_drawdown: float


class AttributionData(BaseModel):
    """Performance attribution data."""

    country: Dict[str, Any]
    industry: Dict[str, Any]


class PeriodInfo(BaseModel):
    """Analytics period information."""

    start_date: str
    end_date: str
    days: int


class PortfolioAnalyticsResponse(BaseModel):
    """Portfolio analytics response."""

    returns: ReturnsData
    risk_metrics: RiskMetrics
    attribution: AttributionData
    period: PeriodInfo


class PortfolioAnalyticsErrorResponse(BaseModel):
    """Portfolio analytics error response."""

    error: str
    returns: Dict[str, Any]
    risk_metrics: Dict[str, Any]
    attribution: Dict[str, Any]


# Status Response Models
class StatusResponse(BaseModel):
    """System status response."""

    status: str
    last_sync: Optional[str] = None
    stock_universe_count: int
    active_positions: int
    cash_balance: float
    check_interval_minutes: int


class DatabaseSize(BaseModel):
    """Database size information."""

    name: str
    size_mb: float


class DatabaseStatsResponse(BaseModel):
    """Database statistics response."""

    status: str
    # Additional fields are dynamic and come from get_database_stats()
    # Using model_config to allow extra fields
    model_config = {"extra": "allow"}


class MarketStatus(BaseModel):
    """Market status information."""

    geography: str
    is_open: bool
    timezone: str


class MarketsStatusResponse(BaseModel):
    """Markets status response."""

    status: str
    open_markets: List[str]
    markets: List[Dict[str, Any]]  # Market status is a list of dicts


class DiskUsageResponse(BaseModel):
    """Disk usage response."""

    status: str
    disk: Dict[str, Any]
    databases: Dict[str, Any]
    data_directory: Dict[str, Any]
    backups: Dict[str, Any]


class JobStatus(BaseModel):
    """Job status information."""

    name: str
    next_run: Optional[str] = None
    enabled: bool


class JobsStatusResponse(BaseModel):
    """Jobs status response."""

    status: str
    jobs: List[Dict[str, Any]]  # Job status is a list of dicts from scheduler
