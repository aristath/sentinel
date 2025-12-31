"""Technical indicator scorers.

Convert RSI, Bollinger Bands, and EMA distance to normalized scores.
"""

from typing import Optional

from app.modules.scoring.domain.constants import (
    EMA_BELOW,
    EMA_VERY_ABOVE,
    EMA_VERY_BELOW,
    RSI_OVERBOUGHT,
    RSI_OVERSOLD,
)


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
