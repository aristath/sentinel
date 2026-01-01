"""
Windfall Detection - Identifies excess gains vs expected growth.

This module distinguishes between:
- Consistent growers: Stocks performing at their historical rate
- Windfalls: Unexpected gains significantly above historical average

Used by the holistic planner to decide when to take profits
without selling consistent performers prematurely.
"""

import logging
from typing import Any, Dict, Optional, Tuple

from app.modules.scoring.domain.constants import (
    CONSISTENT_DOUBLE_SELL_PCT,
    WINDFALL_EXCESS_HIGH,
    WINDFALL_EXCESS_MEDIUM,
    WINDFALL_SELL_PCT_HIGH,
    WINDFALL_SELL_PCT_MEDIUM,
)

logger = logging.getLogger(__name__)


def calculate_excess_gain(
    current_gain: float,
    years_held: float,
    historical_cagr: float,
) -> float:
    """
    Calculate excess gain above expected based on historical CAGR.

    Excess gain = actual gain - expected gain from historical growth

    Example 1: Consistent grower
        held 3 years, up 61%, historical CAGR = 17%
        expected = (1.17^3) - 1 = 60%
        excess = 61% - 60% = 1%  -> No windfall

    Example 2: Sudden spike
        held 1 year, up 80%, historical CAGR = 10%
        expected = 10%
        excess = 80% - 10% = 70%  -> Windfall!

    Args:
        current_gain: Current profit percentage (e.g., 0.80 = 80% gain)
        years_held: Number of years position has been held
        historical_cagr: Security's historical compound annual growth rate

    Returns:
        Excess gain as decimal (can be negative if underperforming)
    """
    if years_held <= 0:
        return current_gain  # No history = all excess

    if historical_cagr <= -1:
        # Invalid CAGR (would cause math error)
        return current_gain

    try:
        expected_gain = ((1 + historical_cagr) ** years_held) - 1
        excess = current_gain - expected_gain
        return excess
    except (ValueError, OverflowError):
        return current_gain


async def calculate_windfall_score(
    symbol: str,
    current_gain: Optional[float] = None,
    years_held: Optional[float] = None,
    historical_cagr: Optional[float] = None,
) -> Tuple[float, Dict[str, Any]]:
    """
    Calculate windfall score (0-1) based on excess gain.

    Higher score = more of a windfall = stronger signal to take profits.

    Args:
        symbol: Security symbol (for cache lookup)
        current_gain: Current profit percentage (optional)
        years_held: Years position held (optional)
        historical_cagr: Historical CAGR (optional, will fetch from cache)

    Returns:
        Tuple of (windfall_score, details_dict)
    """
    from app.repositories.calculations import CalculationsRepository

    calc_repo = CalculationsRepository()

    # Get historical CAGR from cache if not provided
    if historical_cagr is None:
        historical_cagr = await calc_repo.get_metric(symbol, "CAGR_5Y")
        if historical_cagr is None:
            # Try 10-year CAGR
            historical_cagr = await calc_repo.get_metric(symbol, "CAGR_10Y")
        if historical_cagr is None:
            # Default to market average
            historical_cagr = 0.10

    # If we don't have current gain or years held, return neutral
    if current_gain is None or years_held is None:
        return 0.0, {
            "status": "insufficient_data",
            "historical_cagr": round(historical_cagr, 4),
        }

    # Calculate excess gain
    excess = calculate_excess_gain(current_gain, years_held, historical_cagr)
    expected_gain = ((1 + historical_cagr) ** years_held) - 1 if years_held > 0 else 0

    # Calculate score based on excess
    if excess >= WINDFALL_EXCESS_HIGH:  # 50%+ excess
        windfall_score = 1.0
    elif excess >= WINDFALL_EXCESS_MEDIUM:  # 25-50% excess
        # Linear interpolation from 0.5 to 1.0
        windfall_score = (
            0.5
            + (
                (excess - WINDFALL_EXCESS_MEDIUM)
                / (WINDFALL_EXCESS_HIGH - WINDFALL_EXCESS_MEDIUM)
            )
            * 0.5
        )
    elif excess > 0:  # 0-25% excess
        # Linear interpolation from 0.0 to 0.5
        windfall_score = (excess / WINDFALL_EXCESS_MEDIUM) * 0.5
    else:
        # No excess or underperforming
        windfall_score = 0.0

    # Cache the result
    await calc_repo.set_metric(symbol, "EXCESS_GAIN", excess)
    await calc_repo.set_metric(symbol, "WINDFALL_SCORE", windfall_score)

    details = {
        "current_gain": round(current_gain, 4),
        "years_held": round(years_held, 2),
        "historical_cagr": round(historical_cagr, 4),
        "expected_gain": round(expected_gain, 4),
        "excess_gain": round(excess, 4),
        "windfall_score": round(windfall_score, 3),
    }

    return round(windfall_score, 3), details


def should_take_profits(
    current_gain: float,
    years_held: float,
    historical_cagr: float,
) -> Tuple[bool, float, str]:
    """
    Determine if profits should be taken and how much.

    Rules:
    1. If doubled money (100%+ gain):
       - Windfall doubler (excess > 30%): sell 50%
       - Consistent doubler: sell 30%
    2. If excess gain > 50%: sell 40%
    3. If excess gain > 25%: sell 20%
    4. Otherwise: don't sell based on gains

    Args:
        current_gain: Current profit percentage
        years_held: Years position held
        historical_cagr: Historical CAGR

    Returns:
        Tuple of (should_sell: bool, sell_pct: float, reason: str)
    """
    excess = calculate_excess_gain(current_gain, years_held, historical_cagr)

    # Doubled money rule
    if current_gain >= 1.0:  # 100%+ gain
        if excess > 0.30:  # Significant windfall component
            return (
                True,
                0.50,
                f"Windfall doubler: {current_gain*100:.0f}% gain with {excess*100:.0f}% excess",
            )
        else:
            return (
                True,
                CONSISTENT_DOUBLE_SELL_PCT,
                f"Consistent doubler: {current_gain*100:.0f}% gain, taking {CONSISTENT_DOUBLE_SELL_PCT*100:.0f}%",
            )

    # Windfall rules
    if excess >= WINDFALL_EXCESS_HIGH:  # 50%+ above expected
        return (
            True,
            WINDFALL_SELL_PCT_HIGH,
            f"High windfall: {excess*100:.0f}% above expected growth",
        )
    elif excess >= WINDFALL_EXCESS_MEDIUM:  # 25-50% above expected
        return (
            True,
            WINDFALL_SELL_PCT_MEDIUM,
            f"Medium windfall: {excess*100:.0f}% above expected growth",
        )

    # No windfall - don't sell
    if excess > 0:
        reason = f"Performing {excess*100:.0f}% above expected, but within normal range"
    elif excess > -0.10:
        reason = "Performing near expectations"
    else:
        reason = f"Underperforming by {abs(excess)*100:.0f}%"

    return (False, 0.0, reason)


async def get_windfall_recommendation(
    symbol: str,
    current_price: float,
    avg_price: float,
    first_bought_at: Optional[str] = None,
) -> Dict:
    """
    Get complete windfall analysis for a position.

    Convenience function that calculates all windfall metrics
    and returns a recommendation.

    Args:
        symbol: Security symbol
        current_price: Current market price
        avg_price: Average purchase price
        first_bought_at: ISO date string of first purchase (optional)

    Returns:
        Dict with windfall analysis and recommendation
    """
    from datetime import datetime

    # Calculate current gain
    if avg_price <= 0:
        return {"error": "Invalid average price"}

    current_gain = (current_price - avg_price) / avg_price

    # Calculate years held
    years_held = 1.0  # Default
    if first_bought_at:
        try:
            bought_date = datetime.fromisoformat(first_bought_at.replace("Z", "+00:00"))
            if bought_date.tzinfo:
                bought_date = bought_date.replace(tzinfo=None)
            days_held = (datetime.now() - bought_date).days
            years_held = max(0.1, days_held / 365.0)  # Minimum 0.1 years
        except (ValueError, TypeError):
            pass

    # Get windfall score
    windfall_score, details = await calculate_windfall_score(
        symbol=symbol,
        current_gain=current_gain,
        years_held=years_held,
    )

    # Get recommendation
    historical_cagr = details.get("historical_cagr", 0.10)
    should_sell, sell_pct, reason = should_take_profits(
        current_gain, years_held, historical_cagr
    )

    return {
        "symbol": symbol,
        "current_gain_pct": round(current_gain * 100, 1),
        "years_held": round(years_held, 2),
        "windfall_score": windfall_score,
        "excess_gain_pct": round(details.get("excess_gain", 0) * 100, 1),
        "expected_gain_pct": round(details.get("expected_gain", 0) * 100, 1),
        "historical_cagr_pct": round(historical_cagr * 100, 1),
        "recommendation": {
            "take_profits": should_sell,
            "suggested_sell_pct": round(sell_pct * 100, 0) if should_sell else 0,
            "reason": reason,
        },
    }
