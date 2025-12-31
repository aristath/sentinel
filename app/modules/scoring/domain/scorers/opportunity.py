"""Opportunity scorers.

Convert 52-week high distance and P/E ratio to normalized scores.
"""

from typing import Optional

from app.modules.scoring.domain.constants import (
    BELOW_HIGH_EXCELLENT,
    BELOW_HIGH_GOOD,
    BELOW_HIGH_OK,
    DEFAULT_MARKET_AVG_PE,
)


def score_below_52w_high(current_price: float, high_52w: float) -> float:
    """
    Score based on distance below 52-week high.

    Further below = HIGHER score (buying opportunity).

    Args:
        current_price: Current price
        high_52w: 52-week high price

    Returns:
        Score from 0.2 to 1.0
    """
    if high_52w <= 0:
        return 0.5

    pct_below = (high_52w - current_price) / high_52w

    if pct_below <= 0:
        return 0.2  # At or above high = expensive
    elif pct_below < BELOW_HIGH_OK:  # 0-10%
        return 0.2 + (pct_below / BELOW_HIGH_OK) * 0.3  # 0.2-0.5
    elif pct_below < BELOW_HIGH_GOOD:  # 10-20%
        return 0.5 + ((pct_below - BELOW_HIGH_OK) / 0.10) * 0.3  # 0.5-0.8
    elif pct_below < BELOW_HIGH_EXCELLENT:  # 20-30%
        return 0.8 + ((pct_below - BELOW_HIGH_GOOD) / 0.10) * 0.2  # 0.8-1.0
    else:  # 30%+ below
        return 1.0


def score_pe_ratio(
    pe_ratio: Optional[float],
    forward_pe: Optional[float],
    market_avg_pe: float = DEFAULT_MARKET_AVG_PE,
) -> float:
    """
    Score based on P/E vs market average.

    Below average = HIGHER score (cheap).

    Args:
        pe_ratio: Current P/E ratio
        forward_pe: Forward P/E ratio
        market_avg_pe: Market average P/E for comparison

    Returns:
        Score from 0.2 to 1.0
    """
    if not pe_ratio or pe_ratio <= 0:
        return 0.3  # Penalty for missing P/E data - unknown = risky

    # Blend current and forward P/E
    if forward_pe and forward_pe > 0:
        effective_pe = (pe_ratio + forward_pe) / 2
    else:
        effective_pe = pe_ratio

    pct_diff = (effective_pe - market_avg_pe) / market_avg_pe

    if pct_diff >= 0.20:  # 20%+ above average
        return 0.2  # Expensive
    elif pct_diff >= 0:  # 0-20% above
        return 0.5 - (pct_diff / 0.20) * 0.3  # 0.5-0.2
    elif pct_diff >= -0.10:  # 0-10% below
        return 0.5 + (abs(pct_diff) / 0.10) * 0.2  # 0.5-0.7
    elif pct_diff >= -0.20:  # 10-20% below
        return 0.7 + ((abs(pct_diff) - 0.10) / 0.10) * 0.3  # 0.7-1.0
    else:  # 20%+ below
        return 1.0
