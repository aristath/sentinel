"""
Portfolio Analytics - PyFolio integration for performance analysis.

This module re-exports all analytics functions from their modularized locations
for backward compatibility. New code should import directly from the submodules.
"""

from app.modules.analytics.domain.attribution import (
    get_factor_attribution,
    get_performance_attribution,
)
from app.modules.analytics.domain.metrics import (
    calculate_portfolio_returns,
    get_portfolio_metrics,
)
from app.modules.analytics.domain.position import (
    get_position_drawdown,
    get_position_risk_metrics,
)

# Re-export all functions for backward compatibility
from app.modules.analytics.domain.reconstruction import (
    reconstruct_cash_balance,
    reconstruct_historical_positions,
    reconstruct_portfolio_values,
)

__all__ = [
    "reconstruct_historical_positions",
    "reconstruct_cash_balance",
    "reconstruct_portfolio_values",
    "calculate_portfolio_returns",
    "get_portfolio_metrics",
    "get_performance_attribution",
    "get_position_risk_metrics",
    "get_position_drawdown",
    "get_factor_attribution",
]
