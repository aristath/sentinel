"""Pattern generator modules.

Auto-imports all patterns to trigger registration.
"""

# Import all patterns to trigger auto-registration
from app.modules.planning.domain.calculations.patterns import (  # noqa: F401
    adaptive,
    averaging_down,
    cash_generation,
    cost_optimized,
    deep_rebalance,
    direct_buy,
    market_regime,
    mixed_strategy,
    multi_sell,
    opportunity_first,
    profit_taking,
    rebalance,
    single_best,
)

__all__ = [
    "adaptive",
    "averaging_down",
    "cash_generation",
    "cost_optimized",
    "deep_rebalance",
    "direct_buy",
    "market_regime",
    "mixed_strategy",
    "multi_sell",
    "opportunity_first",
    "profit_taking",
    "rebalance",
    "single_best",
]
