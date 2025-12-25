"""
Opportunity Score - Value and dip-buying signals.

Components:
- Below 52-week High (50%): Distance from peak - dip opportunity
- P/E vs Market (50%): Below average = undervalued

Note: Technical indicators (RSI, Bollinger, EMA) moved to technicals.py
"""

import logging
from typing import Optional, List, Dict

import numpy as np

from app.domain.scoring.constants import (
    DEFAULT_MARKET_AVG_PE,
    BELOW_HIGH_EXCELLENT,
    BELOW_HIGH_GOOD,
    BELOW_HIGH_OK,
    MIN_DAYS_FOR_OPPORTUNITY,
)
logger = logging.getLogger(__name__)


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
    market_avg_pe: float = DEFAULT_MARKET_AVG_PE
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
        return 0.5  # Neutral if no P/E

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


async def calculate_opportunity_score(
    symbol: str,
    daily_prices: List[Dict],
    fundamentals,
    market_avg_pe: float = DEFAULT_MARKET_AVG_PE
) -> tuple:
    """
    Calculate opportunity score (value/dip signals).

    Args:
        symbol: Stock symbol (for cache lookup)
        daily_prices: List of daily price dicts
        fundamentals: Yahoo fundamentals data
        market_avg_pe: Market average P/E for comparison

    Returns:
        Tuple of (total_score, sub_components_dict)
        sub_components_dict: {"below_52w_high": float, "pe_ratio": float}
    """
    from app.repositories.calculations import CalculationsRepository
    from app.domain.scoring.technical import get_52_week_high

    if len(daily_prices) < MIN_DAYS_FOR_OPPORTUNITY:
        logger.warning(f"Insufficient daily data: {len(daily_prices)} days")
        sub_components = {"below_52w_high": 0.5, "pe_ratio": 0.5}
        return 0.5, sub_components

    calc_repo = CalculationsRepository()

    # Extract price arrays
    closes = np.array([p["close"] for p in daily_prices])
    highs = np.array([p.get("high") or p["close"] for p in daily_prices])
    current_price = closes[-1]

    # 1. Below 52-week high score (50%) - get from cache
    high_52w = await get_52_week_high(symbol, highs)
    below_52w_score = score_below_52w_high(current_price, high_52w)

    # Calculate distance from 52W high and cache it
    distance_from_52w = (high_52w - current_price) / high_52w if high_52w > 0 else 0
    await calc_repo.set_metric(symbol, "DISTANCE_FROM_52W_HIGH", distance_from_52w)

    # 2. P/E ratio score (50%) - cache P/E ratios
    pe_ratio = fundamentals.pe_ratio if fundamentals else None
    forward_pe = fundamentals.forward_pe if fundamentals else None

    if pe_ratio is not None:
        await calc_repo.set_metric(symbol, "PE_RATIO", pe_ratio)
    if forward_pe is not None:
        await calc_repo.set_metric(symbol, "FORWARD_PE", forward_pe)

    pe_score = score_pe_ratio(pe_ratio, forward_pe, market_avg_pe)

    # Combined score (50/50 split)
    total = below_52w_score * 0.50 + pe_score * 0.50

    sub_components = {
        "below_52w_high": round(below_52w_score, 3),
        "pe_ratio": round(pe_score, 3),
    }

    return round(min(1.0, total), 3), sub_components
