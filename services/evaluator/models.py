"""Pydantic models for Evaluator Service API."""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ActionCandidateModel(BaseModel):
    """Action candidate in a sequence."""

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
    """Portfolio context for evaluation."""

    total_value_eur: float
    available_cash: float
    invested_value: float
    num_positions: int
    target_allocation: Optional[Dict[str, float]] = None


class PositionInput(BaseModel):
    """Current position for evaluation."""

    symbol: str
    quantity: int
    average_cost: float
    current_price: float
    value_eur: float
    currency: str
    unrealized_gain_loss: float
    unrealized_gain_loss_percent: float


class SecurityInput(BaseModel):
    """Security information for evaluation."""

    symbol: str
    name: str
    current_price: float
    currency: str
    market_cap: Optional[float] = None
    sector: Optional[str] = None
    industry: Optional[str] = None


class EvaluationSettings(BaseModel):
    """Settings for sequence evaluation."""

    beam_width: int = Field(default=10, ge=1, le=100)
    # Transaction costs
    transaction_cost_fixed: float = Field(default=2.0, ge=0.0)
    transaction_cost_percent: float = Field(default=0.002, ge=0.0, le=0.1)
    cost_penalty_factor: float = Field(default=0.1, ge=0.0, le=1.0)
    # Multi-objective optimization
    enable_multi_objective: bool = False
    # Stochastic scenarios
    enable_stochastic_scenarios: bool = False
    stochastic_scenario_shifts: List[float] = Field(
        default=[-0.10, -0.05, 0.0, 0.05, 0.10], description="Price shift percentages"
    )
    # Monte Carlo paths
    enable_monte_carlo: bool = False
    monte_carlo_paths: int = Field(default=100, ge=10, le=500)
    # Multi-timeframe optimization
    enable_multi_timeframe: bool = False
    # Priority sorting
    enable_priority_sorting: bool = True


class EvaluateSequencesRequest(BaseModel):
    """Request to evaluate sequences."""

    sequences: List[List[ActionCandidateModel]]
    portfolio_context: PortfolioContextInput
    positions: List[PositionInput]
    securities: List[SecurityInput]
    current_prices: Optional[Dict[str, float]] = Field(
        default=None, description="Symbol -> current price for stochastic/MC scenarios"
    )
    settings: EvaluationSettings = Field(default_factory=EvaluationSettings)


class SequenceEvaluation(BaseModel):
    """
    Multi-objective sequence evaluation for Pareto frontier.

    Used when enable_multi_objective is True.
    """

    sequence: List[ActionCandidateModel]
    end_score: float
    diversification_score: float
    risk_score: float
    transaction_cost: float
    breakdown: Dict = Field(default_factory=dict)

    def is_dominated_by(self, other: "SequenceEvaluation") -> bool:
        """
        Check if this evaluation is dominated by another.

        One sequence dominates another if it's better in all objectives.
        Objectives: maximize end_score, maximize diversification, maximize risk, minimize cost
        """
        # Convert to comparable objectives (all maximize)
        cost_score_self = -self.transaction_cost  # Minimize cost = maximize negative cost
        cost_score_other = -other.transaction_cost

        # Check if other is better or equal in all objectives
        better_or_equal_count = 0
        strictly_better_count = 0

        # End score
        if other.end_score >= self.end_score:
            better_or_equal_count += 1
            if other.end_score > self.end_score:
                strictly_better_count += 1

        # Diversification
        if other.diversification_score >= self.diversification_score:
            better_or_equal_count += 1
            if other.diversification_score > self.diversification_score:
                strictly_better_count += 1

        # Risk
        if other.risk_score >= self.risk_score:
            better_or_equal_count += 1
            if other.risk_score > self.risk_score:
                strictly_better_count += 1

        # Cost (inverted)
        if cost_score_other >= cost_score_self:
            better_or_equal_count += 1
            if cost_score_other > cost_score_self:
                strictly_better_count += 1

        # Dominated if other is better-or-equal in all AND strictly better in at least one
        return better_or_equal_count == 4 and strictly_better_count > 0


class SequenceEvaluationResult(BaseModel):
    """Evaluation result for a sequence."""

    sequence: List[ActionCandidateModel]
    end_state_score: float
    diversification_score: float
    risk_score: float
    total_score: float
    total_cost: float
    cash_required: float
    feasible: bool
    metrics: Dict = Field(default_factory=dict)


class EvaluateSequencesResponse(BaseModel):
    """Response with top evaluated sequences."""

    top_sequences: List[SequenceEvaluationResult]
    total_evaluated: int
    beam_width: int


class HealthResponse(BaseModel):
    """Health check response."""

    healthy: bool
    version: str
    status: str
    checks: Dict[str, str] = Field(default_factory=dict)
