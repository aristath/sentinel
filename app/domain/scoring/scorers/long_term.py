"""Long-term performance scorers.

Convert CAGR, Sharpe, and Sortino ratios to normalized scores.
"""

import math
from typing import Optional

from app.domain.scoring.constants import (
    BELL_CURVE_FLOOR,
    BELL_CURVE_SIGMA_LEFT,
    BELL_CURVE_SIGMA_RIGHT,
    OPTIMAL_CAGR,
    SHARPE_EXCELLENT,
    SHARPE_GOOD,
    SHARPE_OK,
)


def score_cagr(cagr: float, target: float = OPTIMAL_CAGR) -> float:
    """
    Bell curve scoring for CAGR.

    Peak at target (default 11%). Uses asymmetric Gaussian.

    Returns:
        Score from 0.15 to 1.0
    """
    if cagr <= 0:
        return BELL_CURVE_FLOOR

    sigma = BELL_CURVE_SIGMA_LEFT if cagr < target else BELL_CURVE_SIGMA_RIGHT
    raw_score = math.exp(-((cagr - target) ** 2) / (2 * sigma**2))

    return BELL_CURVE_FLOOR + raw_score * (1 - BELL_CURVE_FLOOR)


def score_sharpe(sharpe_ratio: Optional[float]) -> float:
    """
    Convert Sharpe ratio to score.

    Sharpe > 2.0 is excellent, > 1.0 is good.

    Returns:
        Score from 0 to 1.0
    """
    if sharpe_ratio is None:
        return 0.5

    if sharpe_ratio >= SHARPE_EXCELLENT:
        return 1.0
    elif sharpe_ratio >= SHARPE_GOOD:
        return 0.7 + (sharpe_ratio - SHARPE_GOOD) * 0.3
    elif sharpe_ratio >= SHARPE_OK:
        return 0.4 + (sharpe_ratio - SHARPE_OK) * 0.6
    elif sharpe_ratio >= 0:
        return sharpe_ratio * 0.8
    else:
        return 0.0


def score_sortino(sortino_ratio: Optional[float]) -> float:
    """
    Convert Sortino ratio to score.

    Sortino > 2.0 is excellent (focuses on downside risk).

    Returns:
        Score from 0 to 1.0
    """
    if sortino_ratio is None:
        return 0.5

    if sortino_ratio >= 2.0:
        return 1.0
    elif sortino_ratio >= 1.5:
        return 0.8 + (sortino_ratio - 1.5) * 0.4
    elif sortino_ratio >= 1.0:
        return 0.6 + (sortino_ratio - 1.0) * 0.4
    elif sortino_ratio >= 0.5:
        return 0.4 + (sortino_ratio - 0.5) * 0.4
    elif sortino_ratio >= 0:
        return sortino_ratio * 0.8
    else:
        return 0.0
