"""Data models for the planner package."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class TradeRecommendation:
    """A recommended trade to move toward ideal portfolio."""

    symbol: str
    action: str  # 'buy' or 'sell'
    current_allocation: float  # Current % of portfolio
    target_allocation: float  # Target % of portfolio
    allocation_delta: float  # EUR gap as share of current portfolio (positive = buy)
    current_value_eur: float
    target_value_eur: float
    value_delta_eur: float  # Amount to buy (+) or sell (-)
    quantity: int  # Number of shares/units to trade (rounded to lot size)
    price: float  # Current price per share
    currency: str  # Security's trading currency
    lot_size: int  # Minimum lot size
    contrarian_score: float  # Deterministic contrarian signal strength
    priority: float  # Higher = more urgent to act on
    reason: str  # Human-readable explanation
    reason_code: Optional[str] = None
    sleeve: Optional[str] = None
    lot_class: Optional[str] = None
    ticket_pct: Optional[float] = None
    core_floor_active: Optional[bool] = None
    memory_entry: Optional[bool] = None
    user_multiplier: Optional[float] = None
    clara_target_pct: Optional[float] = None
    baseline_target_pct: Optional[float] = None
    opportunity_target_pct: Optional[float] = None
    profit_amount_eur: Optional[float] = None  # Profit amount for sell recommendations
    profits_first: Optional[bool] = None  # True if selling profits only


@dataclass
class PlannerState:
    """Portfolio-side inputs for a planner run.

    Live planning can omit this and read from the normal DB/portfolio services.
    Forecast planning can provide it to run the same planner logic over simulated
    cash and positions without writing those assumptions back to the database.
    """

    positions: list[dict]
    cash_balances: dict[str, float]
    avg_monthly_net_deposit_eur: float | None = None

    def cash_eur(self) -> float:
        """Return the EUR cash balance, rejecting mixed-currency planner state."""
        non_eur_currencies = sorted(currency for currency in self.cash_balances if currency != "EUR")
        if non_eur_currencies:
            joined = ", ".join(non_eur_currencies)
            raise ValueError(f"PlannerState cash must be EUR-only; got non-EUR balance(s): {joined}")
        return float(self.cash_balances.get("EUR", 0.0) or 0.0)

    def eur_cash_balances(self) -> dict[str, float]:
        """Return a normalized EUR-only cash balance mapping."""
        return {"EUR": self.cash_eur()}


@dataclass
class RebalanceSummary:
    """Summary of portfolio alignment with ideal allocations."""

    total_securities: int
    aligned_count: int
    needs_adjustment_count: int
    total_deviation: float
    max_deviation: float
    average_deviation: float
    status: str  # 'aligned', 'minor_drift', 'needs_rebalance'
