"""Data models for the planner package."""

from dataclasses import dataclass


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
    expected_return: float  # The security's expected return score
    priority: float  # Higher = more urgent to act on
    reason: str  # Human-readable explanation


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
