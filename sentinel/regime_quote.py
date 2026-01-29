"""
Regime detection and ML prediction dampening.

Uses real-time quote data to detect per-security market regime
and dampen ML predictions when regime disagrees with prediction direction.
"""

import json
import logging
from typing import TYPE_CHECKING, Tuple

if TYPE_CHECKING:
    from sentinel.database import Database

logger = logging.getLogger(__name__)


def calculate_regime_score(quote_data: dict) -> float:
    """
    Calculate continuous regime score from -1 (bearish) to +1 (bullish).

    Args:
        quote_data: Raw Tradernet quote response with chg5, chg22, etc.

    Returns:
        Regime score between -1.0 and +1.0
    """
    chg5 = quote_data.get("chg5", 0) or 0
    chg22 = quote_data.get("chg22", 0) or 0
    chg110 = quote_data.get("chg110", 0) or 0
    chg220 = quote_data.get("chg220", 0) or 0

    # Multi-timeframe momentum (weighted toward medium-term)
    # Normalize each timeframe by typical range
    momentum = (
        0.10 * (chg5 / 10)  # 5-day, +/-10% typical
        + 0.25 * (chg22 / 20)  # 1-month, +/-20% typical
        + 0.40 * (chg110 / 40)  # ~6-month, heaviest weight
        + 0.25 * (chg220 / 60)  # ~1-year, +/-60% typical
    )
    momentum = max(-1.0, min(1.0, momentum))

    # Position in 52-week range (0 = at lows, 1 = at highs)
    ltp = quote_data.get("ltp", 0) or 0
    x_max = quote_data.get("x_max", 0) or 0
    x_min = quote_data.get("x_min", 0) or 0

    if x_max > x_min and ltp > 0:
        position = (ltp - x_min) / (x_max - x_min)
    else:
        position = 0.5  # Neutral if data missing

    # Combine: 70% momentum, 30% position-adjusted
    regime_score = momentum * 0.7 + (position - 0.5) * 0.6
    return max(-1.0, min(1.0, regime_score))


def apply_regime_dampening(ml_return: float, regime_score: float, max_dampening: float = 0.4) -> float:
    """
    Apply regime-based dampening to ML return prediction.

    Only dampens when regime disagrees with prediction direction.

    Args:
        ml_return: ML predicted return (e.g., 0.05 for 5%)
        regime_score: Regime score from -1 to +1
        max_dampening: Maximum reduction factor (default 0.4 = 40%)

    Returns:
        Adjusted return prediction
    """
    if ml_return > 0 and regime_score < 0:
        # ML bullish, regime bearish
        disagreement = abs(regime_score)
        dampening = disagreement * max_dampening
    elif ml_return < 0 and regime_score > 0:
        # ML bearish, regime bullish
        disagreement = regime_score
        dampening = disagreement * max_dampening
    else:
        dampening = 0

    return ml_return * (1 - dampening)


async def get_regime_adjusted_return(symbol: str, ml_return: float, db: "Database") -> Tuple[float, float, float]:
    """
    Get regime-adjusted return for a symbol.

    Args:
        symbol: Security symbol
        ml_return: Raw ML prediction
        db: Database instance

    Returns:
        Tuple of (adjusted_return, regime_score, dampening_applied)
    """
    security = await db.get_security(symbol)

    if not security or not security.get("quote_data"):
        # No quote data available - return ML prediction unchanged
        logger.debug(f"{symbol}: No quote data, using raw ML prediction")
        return ml_return, 0.0, 0.0

    try:
        quote_data = json.loads(security["quote_data"])
    except (json.JSONDecodeError, TypeError):
        return ml_return, 0.0, 0.0

    regime_score = calculate_regime_score(quote_data)
    adjusted = apply_regime_dampening(ml_return, regime_score)

    # Calculate actual dampening applied
    if ml_return != 0:
        dampening = 1 - (adjusted / ml_return)
    else:
        dampening = 0

    if dampening > 0:
        logger.debug(
            f"{symbol}: ML={ml_return:.2%}, regime={regime_score:.2f}, "
            f"dampening={dampening:.1%}, adjusted={adjusted:.2%}"
        )

    return adjusted, regime_score, dampening
