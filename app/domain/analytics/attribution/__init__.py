"""Performance attribution functions.

Functions for analyzing performance attribution by geography, industry, and factors.
"""

from app.domain.analytics.attribution.performance import get_performance_attribution
from app.domain.analytics.attribution.factors import get_factor_attribution

__all__ = [
    "get_performance_attribution",
    "get_factor_attribution",
]

