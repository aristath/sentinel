"""Pydantic models for Coordinator Service API."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ActionCandidateModel(BaseModel):
    """Action candidate in a plan."""

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


class PortfolioContextInput(BaseModel):
    """Portfolio context for planning."""

    total_value_eur: float
    available_cash: float
    invested_value: float
    num_positions: int
    target_allocation: Optional[Dict[str, float]] = None


class PositionInput(BaseModel):
    """Current position for planning."""

    symbol: str
    quantity: int
    average_cost: float
    current_price: float
    value_eur: float
    currency: str
    unrealized_gain_loss: float
    unrealized_gain_loss_percent: float


class SecurityInput(BaseModel):
    """Security information for planning."""

    symbol: str
    name: str
    current_price: float
    currency: str
    market_cap: Optional[float] = None
    sector: Optional[str] = None
    industry: Optional[str] = None


class PlanningParameters(BaseModel):
    """Parameters for plan creation."""

    max_depth: int = Field(default=4, ge=1, le=10)
    beam_width: int = Field(default=10, ge=1, le=100)
    batch_size: int = Field(default=500, ge=10, le=5000)
    transaction_cost_fixed: float = Field(default=2.0, ge=0.0)
    transaction_cost_percent: float = Field(default=0.002, ge=0.0, le=0.1)
    enable_monte_carlo: bool = False
    enable_correlation_aware: bool = True
    # Early termination settings
    enable_early_termination: bool = True
    min_batches_to_evaluate: int = Field(default=2, ge=1, le=20)
    plateau_threshold: int = Field(default=3, ge=1, le=10)


class EvaluatorConfig(BaseModel):
    """Configuration for evaluator instances."""

    urls: List[str] = Field(
        default_factory=lambda: [
            "http://localhost:8010",
            "http://localhost:8020",
            "http://localhost:8030",
        ]
    )
    load_balancing: str = Field(default="round_robin")


class CreatePlanRequest(BaseModel):
    """Request to create a holistic plan."""

    portfolio_context: PortfolioContextInput
    positions: List[PositionInput]
    securities: List[SecurityInput]
    available_cash: float
    target_weights: Optional[Dict[str, float]] = None
    current_prices: Optional[Dict[str, float]] = None
    parameters: PlanningParameters = Field(default_factory=PlanningParameters)
    evaluator_config: EvaluatorConfig = Field(default_factory=EvaluatorConfig)


class HolisticStepModel(BaseModel):
    """Individual step in a holistic plan."""

    step_number: int
    action: ActionCandidateModel
    narrative: str
    reason: str
    cumulative_cost: float
    cumulative_cash_change: float


class HolisticPlanModel(BaseModel):
    """Complete holistic plan."""

    steps: List[HolisticStepModel]
    narrative: str
    total_score: float
    end_state_score: float
    diversification_score: float
    risk_score: float
    total_cost: float
    cash_required: float
    feasible: bool
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExecutionStats(BaseModel):
    """Statistics about plan execution."""

    total_time_seconds: float
    opportunities_identified: int
    sequences_generated: int
    sequences_evaluated: int
    batches_processed: int
    evaluators_used: int


class CreatePlanResponse(BaseModel):
    """Response with created plan and stats."""

    plan: HolisticPlanModel
    stats: ExecutionStats


class HealthResponse(BaseModel):
    """Health check response."""

    healthy: bool
    version: str
    status: str
    checks: Dict[str, str] = Field(default_factory=dict)
