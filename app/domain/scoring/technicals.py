"""
Technicals Score - Technical indicator signals.

Components:
- RSI Position (35%): Oversold/overbought
- Bollinger Position (35%): Position within bands
- EMA Distance (30%): Distance from 200-day EMA
"""

import logging
from typing import Optional, List, Dict

import numpy as np

from app.domain.scoring.constants import (
    RSI_OVERSOLD,
    RSI_OVERBOUGHT,
    EMA_VERY_BELOW,
    EMA_BELOW,
    EMA_VERY_ABOVE,
)
# Technical functions are imported in calculate_technicals_score

logger = logging.getLogger(__name__)


def score_rsi(rsi_value: Optional[float]) -> float:
    """
    Score based on RSI.

    Oversold (< 30) = buying opportunity = 1.0
    Overbought (> 70) = poor time to buy = 0.0

    Returns:
        Score from 0 to 1.0
    """
    if rsi_value is None:
        return 0.5

    if rsi_value < RSI_OVERSOLD:  # < 30
        return 1.0
    elif rsi_value > RSI_OVERBOUGHT:  # > 70
        return 0.0
    else:
        # Linear scale between 30-70
        return 1.0 - ((rsi_value - RSI_OVERSOLD) / (RSI_OVERBOUGHT - RSI_OVERSOLD))


def score_bollinger(bollinger_position: Optional[float]) -> float:
    """
    Score based on position within Bollinger Bands.

    Near lower band = buying opportunity = higher score.

    Returns:
        Score from 0 to 1.0
    """
    if bollinger_position is None:
        return 0.5

    # Lower position = better score
    return max(0.0, min(1.0, 1.0 - bollinger_position))


def score_ema_distance(current_price: float, ema_value: float) -> float:
    """
    Score based on distance from 200-day EMA.

    Below EMA = HIGHER score (buying opportunity).

    Returns:
        Score from 0.2 to 1.0
    """
    if ema_value <= 0:
        return 0.5

    pct_from_ema = (current_price - ema_value) / ema_value

    if pct_from_ema >= EMA_VERY_ABOVE:  # 10%+ above
        return 0.2
    elif pct_from_ema >= 0:  # 0-10% above
        return 0.5 - (pct_from_ema / EMA_VERY_ABOVE) * 0.3
    elif pct_from_ema >= EMA_BELOW:  # 0-5% below
        return 0.5 + (abs(pct_from_ema) / 0.05) * 0.2
    elif pct_from_ema >= EMA_VERY_BELOW:  # 5-10% below
        return 0.7 + ((abs(pct_from_ema) - 0.05) / 0.05) * 0.3
    else:  # 10%+ below
        return 1.0


async def calculate_technicals_score(symbol: str, daily_prices: List[Dict]) -> tuple:
    """
    Calculate technicals score.

    Args:
        symbol: Stock symbol (for cache lookup)
        daily_prices: Daily price data

    Returns:
        Tuple of (total_score, sub_components_dict)
        sub_components_dict: {"rsi": float, "bollinger": float, "ema": float}
    """
    from app.repositories.calculations import CalculationsRepository
    from app.domain.scoring.technical import (
        get_rsi,
        get_bollinger_bands,
        get_ema,
        calculate_distance_from_ma,
    )

    if len(daily_prices) < 20:
        sub_components = {"rsi": 0.5, "bollinger": 0.5, "ema": 0.5}
        return 0.5, sub_components

    calc_repo = CalculationsRepository()
    closes = np.array([p["close"] for p in daily_prices])
    current_price = closes[-1]

    # RSI - get from cache
    rsi_value = await get_rsi(symbol, closes)
    rsi_score = score_rsi(rsi_value)

    # Bollinger position - get from cache
    bands = await get_bollinger_bands(symbol, closes)
    if bands:
        lower, middle, upper = bands
        if upper > lower:
            bb_position = (current_price - lower) / (upper - lower)
            bb_position = max(0.0, min(1.0, bb_position))
        else:
            bb_position = 0.5
        await calc_repo.set_metric(symbol, "BB_POSITION", bb_position)
    else:
        bb_position = 0.5
    bb_score = score_bollinger(bb_position)

    # EMA distance - get from cache
    ema_value = await get_ema(symbol, closes)
    if ema_value:
        distance_from_ema = calculate_distance_from_ma(current_price, ema_value)
        await calc_repo.set_metric(symbol, "DISTANCE_FROM_EMA_200", distance_from_ema)
    else:
        ema_value = current_price
    ema_score = score_ema_distance(current_price, ema_value)

    # 35% RSI, 35% Bollinger, 30% EMA
    total = (
        rsi_score * 0.35 +
        bb_score * 0.35 +
        ema_score * 0.30
    )

    sub_components = {
        "rsi": round(rsi_score, 3),
        "bollinger": round(bb_score, 3),
        "ema": round(ema_score, 3),
    }

    return round(min(1.0, total), 3), sub_components
