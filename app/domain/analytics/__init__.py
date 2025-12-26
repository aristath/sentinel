"""
Portfolio Analytics - PyFolio integration for performance analysis.

This module provides portfolio performance analytics by reconstructing
portfolio history from trades and generating comprehensive metrics.
"""

from app.domain.analytics.attribution import (
    get_factor_attribution,
    get_performance_attribution,
)
from app.domain.analytics.metrics import (
    calculate_portfolio_returns,
    get_portfolio_metrics,
)
from app.domain.analytics.position import (
    get_position_drawdown,
    get_position_risk_metrics,
)

# Import from modularized submodules
from app.domain.analytics.reconstruction import (
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
