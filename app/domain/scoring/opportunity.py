"""
Opportunity Score - Buy-the-dip signal detection.

INVERTED from typical momentum scoring - we WANT stocks that are:
- Below their 52-week high (temporary dip)
- Below their 200-day EMA (undervalued)
- Trading at low P/E vs historical (cheap)
- RSI indicates oversold (< 30 is ideal)
- Near lower Bollinger Band (buy opportunity)

Components:
- Below 52-week High (30%): Distance from peak
- EMA Distance (25%): Below 200-EMA = opportunity
- P/E vs Historical (25%): Below average = opportunity
- RSI Position (10%): Oversold = opportunity
- Bollinger Position (10%): Near lower band = opportunity
"""

import logging
from typing import Optional, List, Dict

import numpy as np

from app.domain.scoring.models import OpportunityScore
from app.domain.scoring.constants import (
    DEFAULT_MARKET_AVG_PE,
    BELOW_HIGH_EXCELLENT,
    BELOW_HIGH_GOOD,
    BELOW_HIGH_OK,
    EMA_VERY_BELOW,
    EMA_BELOW,
    EMA_VERY_ABOVE,
    RSI_OVERSOLD,
    RSI_OVERBOUGHT,
    OPPORTUNITY_WEIGHT_52W_HIGH,
    OPPORTUNITY_WEIGHT_EMA,
    OPPORTUNITY_WEIGHT_PE,
    OPPORTUNITY_WEIGHT_RSI,
    OPPORTUNITY_WEIGHT_BOLLINGER,
    MIN_DAYS_FOR_OPPORTUNITY,
)
from app.domain.scoring.technical import (
    calculate_ema,
    calculate_rsi,
    calculate_bollinger_position,
    get_52_week_high,
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


def score_ema_distance(current_price: float, ema_value: float) -> float:
    """
    Score based on distance from 200-day EMA.

    Below EMA = HIGHER score (buying opportunity).

    Args:
        current_price: Current price
        ema_value: 200-day EMA value

    Returns:
        Score from 0.2 to 1.0
    """
    if ema_value <= 0:
        return 0.5

    pct_from_ema = (current_price - ema_value) / ema_value

    if pct_from_ema >= EMA_VERY_ABOVE:  # 10%+ above
        return 0.2  # Expensive
    elif pct_from_ema >= 0:  # 0-10% above
        return 0.5 - (pct_from_ema / EMA_VERY_ABOVE) * 0.3  # 0.5-0.2
    elif pct_from_ema >= EMA_BELOW:  # 0-5% below
        return 0.5 + (abs(pct_from_ema) / 0.05) * 0.2  # 0.5-0.7
    elif pct_from_ema >= EMA_VERY_BELOW:  # 5-10% below
        return 0.7 + ((abs(pct_from_ema) - 0.05) / 0.05) * 0.3  # 0.7-1.0
    else:  # 10%+ below
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


def score_rsi(rsi_value: Optional[float]) -> float:
    """
    Score based on RSI.

    Oversold (< 30) = buying opportunity = 1.0
    Overbought (> 70) = poor time to buy = 0.0

    Args:
        rsi_value: RSI value (0-100)

    Returns:
        Score from 0 to 1.0
    """
    if rsi_value is None:
        return 0.5  # Neutral if no data

    if rsi_value < RSI_OVERSOLD:  # < 30
        return 1.0  # Oversold - good buying opportunity
    elif rsi_value > RSI_OVERBOUGHT:  # > 70
        return 0.0  # Overbought - poor time to buy
    else:
        # Linear scale between 30-70
        return 1.0 - ((rsi_value - RSI_OVERSOLD) / (RSI_OVERBOUGHT - RSI_OVERSOLD))


def score_bollinger(bollinger_position: float) -> float:
    """
    Score based on position within Bollinger Bands.

    Near lower band = buying opportunity = higher score.

    Args:
        bollinger_position: Position from 0 (lower) to 1 (upper)

    Returns:
        Score from 0 to 1.0 (inverted from position)
    """
    # Lower position = better score
    return max(0.0, min(1.0, 1.0 - bollinger_position))


def calculate_opportunity_score(
    daily_prices: List[Dict],
    fundamentals,
    market_avg_pe: float = DEFAULT_MARKET_AVG_PE
) -> Optional[OpportunityScore]:
    """
    Calculate complete opportunity score.

    Args:
        daily_prices: List of daily price dicts
        fundamentals: Yahoo fundamentals data
        market_avg_pe: Market average P/E for comparison

    Returns:
        OpportunityScore or None if insufficient data
    """
    if len(daily_prices) < MIN_DAYS_FOR_OPPORTUNITY:
        logger.warning(f"Insufficient daily data: {len(daily_prices)} days")
        return None

    # Extract price arrays
    closes = np.array([p["close"] for p in daily_prices])
    highs = np.array([p.get("high") or p["close"] for p in daily_prices])
    current_price = closes[-1]

    # 1. Below 52-week high score
    high_52w = get_52_week_high(highs)
    below_52w_score = score_below_52w_high(current_price, high_52w)

    # 2. EMA distance score
    ema_value = calculate_ema(closes)
    ema_score = score_ema_distance(current_price, ema_value or current_price)

    # 3. P/E ratio score
    pe_ratio = fundamentals.pe_ratio if fundamentals else None
    forward_pe = fundamentals.forward_pe if fundamentals else None
    pe_score = score_pe_ratio(pe_ratio, forward_pe, market_avg_pe)

    # 4. RSI score
    rsi_value = calculate_rsi(closes)
    rsi_score = score_rsi(rsi_value)

    # 5. Bollinger score
    bb_position = calculate_bollinger_position(closes)
    bollinger_score = score_bollinger(bb_position)

    # Combined score
    total = (
        below_52w_score * OPPORTUNITY_WEIGHT_52W_HIGH +
        ema_score * OPPORTUNITY_WEIGHT_EMA +
        pe_score * OPPORTUNITY_WEIGHT_PE +
        rsi_score * OPPORTUNITY_WEIGHT_RSI +
        bollinger_score * OPPORTUNITY_WEIGHT_BOLLINGER
    )

    return OpportunityScore(
        below_52w_high=round(below_52w_score, 3),
        ema_distance=round(ema_score, 3),
        pe_vs_historical=round(pe_score, 3),
        rsi_score=round(rsi_score, 3),
        bollinger_score=round(bollinger_score, 3),
        total=round(total, 3),
    )
