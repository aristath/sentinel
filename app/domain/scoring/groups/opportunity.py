"""
Opportunity Score - Value and dip-buying signals.

Components:
- Below 52-week High (50%): Distance from peak - dip opportunity
- P/E vs Market (50%): Below average = undervalued

Note: Technical indicators (RSI, Bollinger, EMA) moved to technicals.py
"""

import logging
from typing import Dict, List, Optional

import numpy as np

from app.domain.constants import MAX_PRICE_VS_52W_HIGH
from app.domain.responses import ScoreResult
from app.domain.scoring.constants import (
    BELOW_HIGH_EXCELLENT,
    BELOW_HIGH_GOOD,
    BELOW_HIGH_OK,
    DEFAULT_MARKET_AVG_PE,
    MIN_DAYS_FOR_OPPORTUNITY,
)

logger = logging.getLogger(__name__)


def is_price_too_high(current_price: float, high_52w: float) -> bool:
    """
    Check if price is too close to 52-week high for buying.

    Guardrail to prevent chasing all-time highs.

    Args:
        current_price: Current stock price
        high_52w: 52-week high price

    Returns:
        True if price is above threshold (should block buy)
    """
    if high_52w <= 0:
        return False  # No data, allow trade
    return current_price >= high_52w * MAX_PRICE_VS_52W_HIGH


# Import scorers from dedicated module
from app.domain.scoring.scorers.opportunity import (
    score_below_52w_high,
    score_pe_ratio,
)


async def calculate_opportunity_score(
    symbol: str,
    daily_prices: List[Dict],
    fundamentals,
    market_avg_pe: float = DEFAULT_MARKET_AVG_PE,
) -> ScoreResult:
    """
    Calculate opportunity score (value/dip signals).

    Args:
        symbol: Stock symbol (for cache lookup)
        daily_prices: List of daily price dicts
        fundamentals: Yahoo fundamentals data
        market_avg_pe: Market average P/E for comparison

    Returns:
        ScoreResult with score and sub_scores
        sub_scores: {"below_52w_high": float, "pe_ratio": float}
    """
    from app.domain.scoring.caching import get_52_week_high
    from app.repositories.calculations import CalculationsRepository

    if len(daily_prices) < MIN_DAYS_FOR_OPPORTUNITY:
        logger.warning(f"Insufficient daily data: {len(daily_prices)} days")
        sub_components = {"below_52w_high": 0.5, "pe_ratio": 0.5}
        return ScoreResult(score=0.5, sub_scores=sub_components)

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

    return ScoreResult(score=round(min(1.0, total), 3), sub_scores=sub_components)
