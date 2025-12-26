"""Short-term performance scorers.

Convert momentum and drawdown metrics to normalized scores.
"""

from typing import Optional

from app.domain.scoring.constants import (
    DRAWDOWN_EXCELLENT,
    DRAWDOWN_GOOD,
    DRAWDOWN_OK,
    DRAWDOWN_POOR,
)


def score_momentum(momentum: Optional[float]) -> float:
    """
    Score momentum value.

    Positive momentum = higher score, but very high = caution.

    Returns:
        Score from 0 to 1.0
    """
    if momentum is None:
        return 0.5

    # Optimal: 5-15% gain over period
    if 0.05 <= momentum <= 0.15:
        return 1.0
    elif 0 <= momentum < 0.05:
        return 0.6 + (momentum / 0.05) * 0.4
    elif 0.15 < momentum <= 0.30:
        # Still good but watch for overextension
        return 0.8 + (0.30 - momentum) / 0.15 * 0.2
    elif momentum > 0.30:
        # Too fast, might be overextended
        return max(0.5, 0.8 - (momentum - 0.30) * 2)
    elif -0.10 <= momentum < 0:
        # Small dip, could be opportunity
        return 0.5 + (momentum + 0.10) / 0.10 * 0.1
    else:
        # Significant decline
        return max(0.2, 0.5 + momentum * 3)


def score_drawdown(max_drawdown: Optional[float]) -> float:
    """
    Score based on max drawdown severity.

    Lower drawdown = higher score (better resilience).

    Returns:
        Score from 0 to 1.0
    """
    if max_drawdown is None:
        return 0.5

    dd_pct = abs(max_drawdown)

    if dd_pct <= DRAWDOWN_EXCELLENT:  # <= 10%
        return 1.0
    elif dd_pct <= DRAWDOWN_GOOD:  # <= 20%
        return 0.8 + (DRAWDOWN_GOOD - dd_pct) * 2
    elif dd_pct <= DRAWDOWN_OK:  # <= 30%
        return 0.6 + (DRAWDOWN_OK - dd_pct) * 2
    elif dd_pct <= DRAWDOWN_POOR:  # <= 50%
        return 0.2 + (DRAWDOWN_POOR - dd_pct) * 2
    else:
        return max(0.0, 0.2 - (dd_pct - DRAWDOWN_POOR))
