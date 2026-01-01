"""Pydantic models for Opportunity Service API."""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ActionCandidateModel(BaseModel):
    """Serializable ActionCandidate."""

    side: str = Field(..., description="BUY or SELL")
    symbol: str = Field(..., description="Security symbol")
    name: str = Field(..., description="Security name")
    quantity: int = Field(..., description="Number of shares")
    price: float = Field(..., description="Estimated price per share")
    value_eur: float = Field(..., description="Total value in EUR")
    currency: str = Field(..., description="Security currency")
    priority: float = Field(..., description="Priority score (0-1)")
    reason: str = Field(..., description="Reason for this action")
    tags: List[str] = Field(default_factory=list, description="Action tags")


class PortfolioContextInput(BaseModel):
    """Portfolio context for opportunity identification."""

    positions: Dict[str, float] = Field(..., description="Symbol -> value_eur")
    total_value: float = Field(..., description="Total portfolio value in EUR")
    country_weights: Dict[str, float] = Field(
        default_factory=dict, description="Country -> weight"
    )
    industry_weights: Dict[str, float] = Field(
        default_factory=dict, description="Industry -> weight"
    )
    security_countries: Optional[Dict[str, str]] = Field(
        default=None, description="Symbol -> country"
    )
    security_industries: Optional[Dict[str, str]] = Field(
        default=None, description="Symbol -> industry"
    )


class SecurityInput(BaseModel):
    """Simplified security for opportunity identification."""

    symbol: str = Field(..., description="Security symbol")
    name: str = Field(..., description="Security name")
    isin: str = Field(..., description="ISIN")
    country: Optional[str] = Field(default=None, description="Country")
    industry: Optional[str] = Field(default=None, description="Industry")
    allow_buy: bool = Field(default=True, description="Allow buying this security")
    allow_sell: bool = Field(default=True, description="Allow selling this security")


class PositionInput(BaseModel):
    """Current position."""

    symbol: str = Field(..., description="Security symbol")
    quantity: int = Field(..., description="Number of shares held")
    avg_price: float = Field(..., description="Average purchase price")
    market_value_eur: float = Field(..., description="Current market value in EUR")
    unrealized_pnl_pct: float = Field(
        ..., description="Unrealized P&L percentage"
    )


class IdentifyOpportunitiesRequest(BaseModel):
    """Request to identify opportunities."""

    portfolio_context: PortfolioContextInput
    positions: List[PositionInput]
    securities: List[SecurityInput]
    available_cash: float = Field(..., description="Available cash in EUR")
    target_weights: Optional[Dict[str, float]] = Field(
        default=None, description="Symbol -> target weight (0-1)"
    )
    current_prices: Optional[Dict[str, float]] = Field(
        default=None, description="Symbol -> current price"
    )
    transaction_cost_fixed: float = Field(default=2.0, description="Fixed cost per trade")
    transaction_cost_percent: float = Field(
        default=0.002, description="Percentage cost (0.002 = 0.2%)"
    )
    recently_sold: Optional[List[str]] = Field(
        default=None, description="Recently sold symbols (for cooldown)"
    )
    ineligible_symbols: Optional[List[str]] = Field(
        default=None, description="Symbols ineligible for selling"
    )


class IdentifyOpportunitiesResponse(BaseModel):
    """Categorized opportunities."""

    profit_taking: List[ActionCandidateModel] = Field(
        default_factory=list, description="Windfall profit-taking sells"
    )
    averaging_down: List[ActionCandidateModel] = Field(
        default_factory=list, description="Averaging down buys"
    )
    rebalance_sells: List[ActionCandidateModel] = Field(
        default_factory=list, description="Rebalancing sells (overweight)"
    )
    rebalance_buys: List[ActionCandidateModel] = Field(
        default_factory=list, description="Rebalancing buys (underweight)"
    )
    opportunity_buys: List[ActionCandidateModel] = Field(
        default_factory=list, description="General opportunity buys"
    )


class HealthResponse(BaseModel):
    """Health check response."""

    healthy: bool
    version: str
    status: str
    checks: dict = Field(default_factory=dict)
