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
    allocation_delta: float  # Target - Current (positive = underweight)
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
