"""End-state scorers.

Convert total return metrics to normalized scores for holistic planning.
"""

import math

from app.modules.scoring.domain.constants import (
    BELL_CURVE_FLOOR,
    BELL_CURVE_SIGMA_LEFT,
    BELL_CURVE_SIGMA_RIGHT,
)


def score_total_return(total_return: float, target: float = 0.12) -> float:
    """
    Bell curve scoring for total return.

    Peak at target (default 12%). Uses asymmetric Gaussian.

    Args:
        total_return: Total return value
        target: Target return (default 12%)

    Returns:
        Score from 0.15 to 1.0
    """
    if total_return <= 0:
        return BELL_CURVE_FLOOR

    # Use slightly wider sigma for total return (more forgiving than CAGR)
    sigma = (
        BELL_CURVE_SIGMA_LEFT if total_return < target else BELL_CURVE_SIGMA_RIGHT * 1.2
    )
    raw_score = math.exp(-((total_return - target) ** 2) / (2 * sigma**2))

    return BELL_CURVE_FLOOR + raw_score * (1 - BELL_CURVE_FLOOR)
