"""
Short-term Performance Score - Recent trends and momentum.

Components:
- Recent Momentum (50%): Price performance over last 30/90 days
- Max Drawdown (50%): Recent drawdown severity
"""

import logging
from typing import Optional, List, Dict

import numpy as np

from app.domain.scoring.constants import (
    DRAWDOWN_EXCELLENT,
    DRAWDOWN_GOOD,
    DRAWDOWN_OK,
    DRAWDOWN_POOR,
)
logger = logging.getLogger(__name__)


def calculate_recent_momentum(daily_prices: List[Dict]) -> Optional[float]:
    """
    Calculate momentum over last 30 and 90 days.

    Returns:
        Momentum score from 0 to 1.0
    """
    if len(daily_prices) < 30:
        return None

    closes = [p["close"] for p in daily_prices]
    current = closes[-1]

    # 30-day momentum
    price_30d = closes[-30] if len(closes) >= 30 else closes[0]
    momentum_30d = (current - price_30d) / price_30d if price_30d > 0 else 0

    # 90-day momentum
    price_90d = closes[-90] if len(closes) >= 90 else closes[0]
    momentum_90d = (current - price_90d) / price_90d if price_90d > 0 else 0

    # Blend (60% 30-day, 40% 90-day)
    blended = momentum_30d * 0.6 + momentum_90d * 0.4

    return blended


def score_momentum(momentum: Optional[float]) -> float:
    """
    Score momentum value.

    Positive momentum = higher score, but very high = caution.

    Returns:
        Score from 0 to 1.0
    """
    if momentum is None:
        return 0.5

    # Optimal: 5-15% gain over period
    if 0.05 <= momentum <= 0.15:
        return 1.0
    elif 0 <= momentum < 0.05:
        return 0.6 + (momentum / 0.05) * 0.4
    elif 0.15 < momentum <= 0.30:
        # Still good but watch for overextension
        return 0.8 + (0.30 - momentum) / 0.15 * 0.2
    elif momentum > 0.30:
        # Too fast, might be overextended
        return max(0.5, 0.8 - (momentum - 0.30) * 2)
    elif -0.10 <= momentum < 0:
        # Small dip, could be opportunity
        return 0.5 + (momentum + 0.10) / 0.10 * 0.1
    else:
        # Significant decline
        return max(0.2, 0.5 + momentum * 3)


def score_drawdown(max_drawdown: Optional[float]) -> float:
    """
    Score based on max drawdown severity.

    Lower drawdown = higher score (better resilience).

    Returns:
        Score from 0 to 1.0
    """
    if max_drawdown is None:
        return 0.5

    dd_pct = abs(max_drawdown)

    if dd_pct <= DRAWDOWN_EXCELLENT:  # <= 10%
        return 1.0
    elif dd_pct <= DRAWDOWN_GOOD:  # <= 20%
        return 0.8 + (DRAWDOWN_GOOD - dd_pct) * 2
    elif dd_pct <= DRAWDOWN_OK:  # <= 30%
        return 0.6 + (DRAWDOWN_OK - dd_pct) * 2
    elif dd_pct <= DRAWDOWN_POOR:  # <= 50%
        return 0.2 + (DRAWDOWN_POOR - dd_pct) * 2
    else:
        return max(0.0, 0.2 - (dd_pct - DRAWDOWN_POOR))


async def calculate_short_term_score(
    symbol: str,
    daily_prices: List[Dict],
    pyfolio_drawdown: Optional[float] = None,
) -> tuple:
    """
    Calculate short-term performance score.

    Args:
        symbol: Stock symbol (for cache lookup)
        daily_prices: Daily price data
        pyfolio_drawdown: Current drawdown from PyFolio (optional)

    Returns:
        Tuple of (total_score, sub_components_dict)
        sub_components_dict: {"momentum": float, "drawdown": float}
    """
    from app.repositories.calculations import CalculationsRepository
    from app.domain.scoring.technical import get_max_drawdown

    calc_repo = CalculationsRepository()

    # Momentum - calculate and cache
    momentum_30d = None
    momentum_90d = None
    if len(daily_prices) >= 30:
        closes = [p["close"] for p in daily_prices]
        current = closes[-1]

        # 30-day momentum
        price_30d = closes[-30] if len(closes) >= 30 else closes[0]
        momentum_30d = (current - price_30d) / price_30d if price_30d > 0 else 0
        await calc_repo.set_metric(symbol, "MOMENTUM_30D", momentum_30d)

        # 90-day momentum
        if len(closes) >= 90:
            price_90d = closes[-90]
            momentum_90d = (current - price_90d) / price_90d if price_90d > 0 else 0
            await calc_repo.set_metric(symbol, "MOMENTUM_90D", momentum_90d)

    # Blend momentum
    momentum = None
    if momentum_30d is not None and momentum_90d is not None:
        momentum = momentum_30d * 0.6 + momentum_90d * 0.4
    elif momentum_30d is not None:
        momentum = momentum_30d
    else:
        momentum = calculate_recent_momentum(daily_prices)

    momentum_score = score_momentum(momentum)

    # Drawdown - get from cache or calculate
    max_dd = None
    if pyfolio_drawdown is not None:
        max_dd = pyfolio_drawdown
        await calc_repo.set_metric(symbol, "MAX_DRAWDOWN", max_dd)
    elif len(daily_prices) >= 30:
        closes = np.array([p["close"] for p in daily_prices])
        max_dd = await get_max_drawdown(symbol, closes)
    else:
        max_dd = None

    drawdown_score = score_drawdown(max_dd)

    # 50% momentum, 50% drawdown
    total = momentum_score * 0.50 + drawdown_score * 0.50

    sub_components = {
        "momentum": round(momentum_score, 3),
        "drawdown": round(drawdown_score, 3),
    }

    return round(min(1.0, total), 3), sub_components
