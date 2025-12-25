"""
Dividends Score - Income and dividend quality.

Components:
- Dividend Yield (70%): Current yield level
- Dividend Growth (30%): Consistency and growth of dividends
"""

import logging
from typing import Optional

from app.domain.scoring.constants import (
    HIGH_DIVIDEND_THRESHOLD,
    MID_DIVIDEND_THRESHOLD,
)

logger = logging.getLogger(__name__)


def score_dividend_yield(dividend_yield: Optional[float]) -> float:
    """
    Score based on dividend yield.

    Higher yield = higher score for income-focused investing.

    Returns:
        Score from 0.3 to 1.0
    """
    if not dividend_yield or dividend_yield <= 0:
        return 0.3  # Base score for non-dividend stocks

    if dividend_yield >= HIGH_DIVIDEND_THRESHOLD:  # 6%+ yield
        return 1.0
    elif dividend_yield >= MID_DIVIDEND_THRESHOLD:  # 3-6% yield
        # Linear scale from 0.7 to 1.0
        pct = (dividend_yield - MID_DIVIDEND_THRESHOLD) / (HIGH_DIVIDEND_THRESHOLD - MID_DIVIDEND_THRESHOLD)
        return 0.7 + pct * 0.3
    elif dividend_yield >= 0.01:  # 1-3% yield
        # Linear scale from 0.4 to 0.7
        pct = (dividend_yield - 0.01) / (MID_DIVIDEND_THRESHOLD - 0.01)
        return 0.4 + pct * 0.3
    else:  # 0-1% yield
        return 0.3 + (dividend_yield / 0.01) * 0.1


def score_dividend_consistency(fundamentals) -> float:
    """
    Score based on dividend consistency/growth.

    Uses payout ratio and 5-year dividend growth if available.

    Returns:
        Score from 0.3 to 1.0
    """
    if not fundamentals:
        return 0.5

    # Payout ratio: 30-60% is ideal (sustainable but committed)
    payout = fundamentals.payout_ratio if hasattr(fundamentals, 'payout_ratio') else None
    if payout is not None:
        if 0.3 <= payout <= 0.6:
            payout_score = 1.0
        elif payout < 0.3:
            payout_score = 0.5 + (payout / 0.3) * 0.5
        elif payout <= 0.8:
            payout_score = 1.0 - ((payout - 0.6) / 0.2) * 0.3
        else:
            payout_score = 0.4  # High payout = risky
    else:
        payout_score = 0.5

    # 5-year dividend growth if available
    div_growth = getattr(fundamentals, 'five_year_avg_dividend_yield', None)
    if div_growth is not None:
        growth_score = min(1.0, 0.5 + div_growth * 5)
    else:
        growth_score = 0.5

    return (payout_score * 0.5 + growth_score * 0.5)


async def calculate_dividends_score(symbol: str, fundamentals) -> tuple:
    """
    Calculate dividends score.

    Args:
        symbol: Stock symbol (for cache lookup)
        fundamentals: Yahoo fundamentals data

    Returns:
        Tuple of (total_score, sub_components_dict)
        sub_components_dict: {"yield": float, "consistency": float}
    """
    from app.repositories.calculations import CalculationsRepository

    calc_repo = CalculationsRepository()

    dividend_yield = fundamentals.dividend_yield if fundamentals else None
    payout_ratio = fundamentals.payout_ratio if hasattr(fundamentals, 'payout_ratio') else None

    # Cache dividend metrics
    if dividend_yield is not None:
        await calc_repo.set_metric(symbol, "DIVIDEND_YIELD", dividend_yield, source='yahoo')
    if payout_ratio is not None:
        await calc_repo.set_metric(symbol, "PAYOUT_RATIO", payout_ratio, source='yahoo')

    yield_score = score_dividend_yield(dividend_yield)
    consistency_score = score_dividend_consistency(fundamentals)

    # 70% yield, 30% consistency
    total = yield_score * 0.70 + consistency_score * 0.30

    sub_components = {
        "yield": round(yield_score, 3),
        "consistency": round(consistency_score, 3),
    }

    return round(min(1.0, total), 3), sub_components
