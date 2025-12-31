"""Recommendation service helpers.

Helper modules for recommendation generation and portfolio context building.
"""

from app.application.services.recommendation.performance_adjustment_calculator import (
    get_performance_adjusted_weights,
)
from app.application.services.recommendation.technical_data_calculator import (
    get_technical_data_for_positions,
)

# Backward compatibility re-export (temporary - will be removed in Phase 5)
from app.modules.planning.services.portfolio_context_builder import (
    build_portfolio_context,
)

__all__ = [
    "build_portfolio_context",
    "get_technical_data_for_positions",
    "get_performance_adjusted_weights",
]
