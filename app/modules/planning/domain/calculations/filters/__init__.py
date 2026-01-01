"""Filter modules.

Auto-imports all filters to trigger registration.
"""

# Import all filters to trigger auto-registration
from app.modules.planning.domain.calculations.filters import (  # noqa: F401
    correlation_aware,
    diversity,
    eligibility,
    recently_traded,
)

__all__ = [
    "correlation_aware",
    "diversity",
    "eligibility",
    "recently_traded",
]
