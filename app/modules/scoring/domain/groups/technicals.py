"""
Technicals Score - Technical indicator signals.

Components:
- RSI Position (35%): Oversold/overbought
- Bollinger Position (35%): Position within bands
- EMA Distance (30%): Distance from 200-day EMA
"""

import logging
from typing import Dict, List

import numpy as np

from app.domain.responses import ScoreResult
from app.modules.scoring.domain.scorers.technicals import (
    score_bollinger,
    score_ema_distance,
    score_rsi,
)

logger = logging.getLogger(__name__)


async def calculate_technicals_score(
    symbol: str, daily_prices: List[Dict]
) -> ScoreResult:
    """
    Calculate technicals score.

    Args:
        symbol: Security symbol (for cache lookup)
        daily_prices: Daily price data

    Returns:
        ScoreResult with score and sub_scores
        sub_scores: {"rsi": float, "bollinger": float, "ema": float}
    """
    from app.modules.scoring.domain.caching import (
        calculate_distance_from_ma,
        get_bollinger_bands,
        get_ema,
        get_rsi,
    )
    from app.repositories.calculations import CalculationsRepository

    if len(daily_prices) < 20:
        sub_components = {"rsi": 0.5, "bollinger": 0.5, "ema": 0.5}
        return ScoreResult(score=0.5, sub_scores=sub_components)

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
    if ema_value is not None:
        distance_from_ema = calculate_distance_from_ma(current_price, ema_value)
        await calc_repo.set_metric(symbol, "DISTANCE_FROM_EMA_200", distance_from_ema)
        ema_score = score_ema_distance(current_price, ema_value)
    else:
        ema_score = score_ema_distance(current_price, current_price)

    # 35% RSI, 35% Bollinger, 30% EMA
    total = rsi_score * 0.35 + bb_score * 0.35 + ema_score * 0.30

    sub_components = {
        "rsi": round(rsi_score, 3),
        "bollinger": round(bb_score, 3),
        "ema": round(ema_score, 3),
    }

    return ScoreResult(score=round(min(1.0, total), 3), sub_scores=sub_components)
