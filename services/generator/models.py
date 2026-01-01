"""Pydantic models for Generator Service API."""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ActionCandidateModel(BaseModel):
    """Action candidate for sequence generation."""

    side: str  # "BUY" or "SELL"
    symbol: str
    name: str
    quantity: int
    price: float
    value_eur: float
    currency: str
    priority: float
    reason: str
    tags: List[str] = Field(default_factory=list)


class OpportunitiesInput(BaseModel):
    """Categorized opportunities for sequence generation."""

    profit_taking: List[ActionCandidateModel] = Field(default_factory=list)
    averaging_down: List[ActionCandidateModel] = Field(default_factory=list)
    rebalance_sells: List[ActionCandidateModel] = Field(default_factory=list)
    rebalance_buys: List[ActionCandidateModel] = Field(default_factory=list)
    opportunity_buys: List[ActionCandidateModel] = Field(default_factory=list)


class CombinatorialSettings(BaseModel):
    """Settings for combinatorial sequence generation."""

    max_depth: int = Field(default=4, ge=1, le=10)
    max_combinations: int = Field(default=1000, ge=10, le=10000)
    max_opportunities_per_category: int = Field(default=5, ge=1, le=20)
    enable_weighted_combinations: bool = True
    enable_adaptive_patterns: bool = True
    enable_partial_execution: bool = True
    enable_constraint_relaxation: bool = True
    enable_market_regime: bool = False


class FilterSettings(BaseModel):
    """Settings for sequence filtering."""

    enable_correlation_aware: bool = True
    correlation_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    min_sequence_value: float = Field(default=100.0, ge=0.0)
    max_sequence_value: Optional[float] = None


class FeasibilitySettings(BaseModel):
    """Settings for feasibility filtering."""

    available_cash: float = Field(ge=0.0)
    transaction_cost_fixed: float = Field(default=2.0, ge=0.0)
    transaction_cost_percent: float = Field(default=0.002, ge=0.0, le=0.1)
    min_trade_value: float = Field(default=100.0, ge=0.0)
    priority_threshold: float = Field(default=0.3, ge=0.0, le=1.0)


class PortfolioContextInput(BaseModel):
    """Portfolio context for adaptive pattern generation."""

    total_value: float
    positions: Dict[str, float]  # symbol -> value_eur
    country_weights: Dict[str, float] = Field(default_factory=dict)
    industry_weights: Dict[str, float] = Field(default_factory=dict)


class PositionInput(BaseModel):
    """Position information for constraint relaxation."""

    symbol: str
    quantity: int
    avg_price: float
    market_value_eur: float


class SecurityInput(BaseModel):
    """Security information for adaptive patterns and correlation filtering."""

    symbol: str
    name: str
    country: Optional[str] = None
    industry: Optional[str] = None
    allow_buy: bool = True
    allow_sell: bool = True


class GenerateSequencesRequest(BaseModel):
    """Request to generate action sequences."""

    opportunities: OpportunitiesInput
    feasibility: FeasibilitySettings
    combinatorial: CombinatorialSettings = Field(default_factory=CombinatorialSettings)
    filters: FilterSettings = Field(default_factory=FilterSettings)
    batch_size: int = Field(default=500, ge=10, le=5000)
    # Optional fields for advanced pattern generation
    portfolio_context: Optional[PortfolioContextInput] = None
    positions: List[PositionInput] = Field(default_factory=list)
    securities: List[SecurityInput] = Field(default_factory=list)
    market_regime: Optional[str] = Field(
        default=None, description="Market regime: 'bull', 'bear', or 'sideways'"
    )


class SequenceBatch(BaseModel):
    """Batch of generated sequences for streaming."""

    batch_number: int
    sequences: List[List[ActionCandidateModel]]
    total_batches: int
    more_available: bool


class HealthResponse(BaseModel):
    """Health check response."""

    healthy: bool
    version: str
    status: str
    checks: Dict[str, str] = Field(default_factory=dict)
