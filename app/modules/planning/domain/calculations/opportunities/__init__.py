"""Opportunity calculator modules.

Auto-imports all calculators to trigger registration.
"""

# Import all calculators to trigger auto-registration
from app.modules.planning.domain.calculations.opportunities import (  # noqa: F401
    averaging_down,
    opportunity_buys,
    profit_taking,
    rebalance_buys,
    rebalance_sells,
    weight_based,
)

__all__ = [
    "averaging_down",
    "opportunity_buys",
    "profit_taking",
    "rebalance_buys",
    "rebalance_sells",
    "weight_based",
]
