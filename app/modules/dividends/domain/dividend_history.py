"""
Dividend History Analysis - Evaluates dividend stability and cuts.

This module analyzes dividend payment history to identify:
- Big dividend cuts (>20% year-over-year)
- Consistent dividend growers
- Dividend stability relative to portfolio average

Used by the holistic planner to assess long-term income reliability.
"""

import logging
from typing import Dict, List, Optional, Tuple

from app.modules.scoring.domain.constants import DIVIDEND_CUT_THRESHOLD

logger = logging.getLogger(__name__)


def has_big_dividend_cut(dividend_history: List[float]) -> Tuple[bool, Optional[int]]:
    """
    Check for significant dividend cuts (>20% year-over-year).

    Args:
        dividend_history: List of annual dividend amounts (oldest first)

    Returns:
        Tuple of (has_cut: bool, years_since_cut: Optional[int])
    """
    if len(dividend_history) < 2:
        return False, None

    for i in range(1, len(dividend_history)):
        prev_div = dividend_history[i - 1]
        curr_div = dividend_history[i]

        if prev_div > 0:
            change = (curr_div - prev_div) / prev_div
            if change < -DIVIDEND_CUT_THRESHOLD:
                years_since_cut = len(dividend_history) - i
                return True, years_since_cut

    return False, None


def calculate_dividend_growth_rate(dividend_history: List[float]) -> Optional[float]:
    """
    Calculate compound annual dividend growth rate.

    Args:
        dividend_history: List of annual dividend amounts (oldest first)

    Returns:
        CAGR of dividends, or None if insufficient data
    """
    if len(dividend_history) < 2:
        return None

    # Filter out zero/negative values at the start
    start_idx = 0
    for i, div in enumerate(dividend_history):
        if div > 0:
            start_idx = i
            break
    else:
        return None  # All zeros

    valid_history = dividend_history[start_idx:]
    if len(valid_history) < 2:
        return None

    start_div = valid_history[0]
    end_div = valid_history[-1]
    years = len(valid_history) - 1

    if start_div <= 0 or years <= 0:
        return None

    try:
        cagr = (end_div / start_div) ** (1 / years) - 1
        return cagr
    except (ValueError, ZeroDivisionError):
        return None


def _calculate_cut_penalty(
    has_cut: bool, years_since: Optional[int], dividend_history: List[float]
) -> tuple[float, float]:
    """Calculate penalty for dividend cuts and bonus for no cuts."""
    if has_cut:
        if years_since is not None and years_since <= 2:
            return 0.40, 0.0  # Full penalty for recent cuts
        elif years_since is not None and years_since <= 5:
            return 0.25, 0.0  # Partial penalty
        else:
            return 0.10, 0.0  # Old cut, less penalty
    else:
        # Bonus for no cuts in history
        if len(dividend_history) >= 5:
            return 0.0, 0.15  # Long track record without cuts
        elif len(dividend_history) >= 3:
            return 0.0, 0.10
        else:
            return 0.0, 0.0


def _calculate_growth_bonus(growth_rate: Optional[float]) -> float:
    """Calculate bonus based on dividend growth rate."""
    if growth_rate is None:
        return 0.0

    if growth_rate >= 0.05:  # 5%+ annual growth
        return 0.30
    elif growth_rate >= 0.02:  # 2-5% growth
        return 0.20
    elif growth_rate >= 0:  # Stable
        return 0.10
    else:  # Declining
        return 0.0


def _calculate_yield_bonus(
    current_yield: Optional[float], portfolio_avg_yield: float
) -> tuple[float, bool]:
    """Calculate bonus based on yield vs portfolio average."""
    if current_yield is None or current_yield <= 0:
        return 0.0, False

    above_avg = current_yield >= portfolio_avg_yield
    if current_yield >= portfolio_avg_yield * 1.5:
        return 0.30, above_avg  # Significantly above average
    elif current_yield >= portfolio_avg_yield:
        return 0.15, above_avg  # Above average
    else:
        return 0.0, above_avg


def calculate_dividend_stability_score(
    dividend_history: List[float],
    portfolio_avg_yield: float = 0.03,
    current_yield: Optional[float] = None,
) -> Tuple[float, Dict]:
    """
    Calculate dividend stability score.

    Components:
    - No big cuts (40%): Penalize if >20% cuts found
    - Growth trend (30%): Reward consistent growth
    - Above portfolio average (30%): Bonus if yield > portfolio avg

    Args:
        dividend_history: List of annual dividend amounts (oldest first)
        portfolio_avg_yield: Average dividend yield of portfolio
        current_yield: Current dividend yield of this security

    Returns:
        Tuple of (stability_score, details_dict)
    """
    details = {
        "has_big_cut": False,
        "years_since_cut": None,
        "dividend_growth_rate": None,
        "above_portfolio_avg": False,
        "cut_penalty": 0.0,
        "growth_bonus": 0.0,
        "yield_bonus": 0.0,
    }

    score = 0.5  # Base score

    # Check for big cuts (40% weight)
    has_cut, years_since = has_big_dividend_cut(dividend_history)
    details["has_big_cut"] = has_cut
    details["years_since_cut"] = years_since

    cut_penalty, no_cut_bonus = _calculate_cut_penalty(
        has_cut, years_since, dividend_history
    )
    details["cut_penalty"] = cut_penalty
    score -= cut_penalty
    score += no_cut_bonus

    # Check growth trend (30% weight)
    growth_rate = calculate_dividend_growth_rate(dividend_history)
    details["dividend_growth_rate"] = growth_rate
    growth_bonus = _calculate_growth_bonus(growth_rate)
    details["growth_bonus"] = growth_bonus
    score += growth_bonus

    # Check vs portfolio average (30% weight)
    yield_bonus, above_avg = _calculate_yield_bonus(current_yield, portfolio_avg_yield)
    details["yield_bonus"] = yield_bonus
    details["above_portfolio_avg"] = above_avg
    score += yield_bonus

    score = max(0.0, min(1.0, score))  # Clamp to valid range
    return round(score, 3), details


async def get_dividend_analysis(
    symbol: str,
    portfolio_avg_yield: float = 0.03,
) -> Dict:
    """
    Get complete dividend analysis for a security.

    Fetches dividend data and calculates stability metrics.

    Args:
        symbol: Stock symbol
        portfolio_avg_yield: Average yield of portfolio for comparison

    Returns:
        Dict with dividend analysis
    """
    from app.repositories.calculations import CalculationsRepository

    calc_repo = CalculationsRepository()

    # Get current dividend yield
    current_yield = await calc_repo.get_metric(symbol, "DIVIDEND_YIELD")
    if current_yield is None:
        current_yield = 0.0

    # Get payout ratio for additional context
    payout_ratio = await calc_repo.get_metric(symbol, "PAYOUT_RATIO")

    # Note: In a full implementation, we'd fetch dividend history from yfinance
    # For now, we estimate based on available metrics
    # This is a simplified version - a more complete implementation would
    # store actual dividend history in the database

    # Estimate dividend stability from payout ratio
    if payout_ratio is not None:
        # Sustainable payout (30-60%) suggests stable dividends
        if 0.30 <= payout_ratio <= 0.60:
            estimated_stability = 0.85
        elif 0.20 <= payout_ratio < 0.30:
            estimated_stability = 0.70
        elif 0.60 < payout_ratio <= 0.80:
            estimated_stability = 0.60
        elif payout_ratio > 0.80:
            estimated_stability = 0.40  # High payout = risk of cuts
        else:
            estimated_stability = 0.50
    else:
        estimated_stability = 0.50

    # Adjust for yield comparison
    above_avg = current_yield >= portfolio_avg_yield if current_yield else False
    if above_avg and current_yield >= portfolio_avg_yield * 1.5:
        yield_assessment = "significantly_above_average"
    elif above_avg:
        yield_assessment = "above_average"
    elif current_yield > 0:
        yield_assessment = "below_average"
    else:
        yield_assessment = "no_dividend"

    # Cache the stability score
    await calc_repo.set_metric(symbol, "DIVIDEND_STABILITY", estimated_stability)

    return {
        "symbol": symbol,
        "current_yield_pct": round((current_yield or 0) * 100, 2),
        "portfolio_avg_yield_pct": round(portfolio_avg_yield * 100, 2),
        "payout_ratio_pct": (
            round((payout_ratio or 0) * 100, 1) if payout_ratio else None
        ),
        "stability_score": round(estimated_stability, 3),
        "yield_assessment": yield_assessment,
        "above_portfolio_avg": above_avg,
        "recommendation": _get_dividend_recommendation(
            estimated_stability, yield_assessment, payout_ratio
        ),
    }


def _get_dividend_recommendation(
    stability: float,
    yield_assessment: str,
    payout_ratio: Optional[float],
) -> str:
    """Generate human-readable dividend recommendation."""
    if yield_assessment == "no_dividend":
        return "Non-dividend security - income not a factor"

    if stability >= 0.80:
        if yield_assessment == "significantly_above_average":
            return "Excellent: High yield with sustainable payout"
        elif yield_assessment == "above_average":
            return "Good: Above-average yield, stable history"
        else:
            return "Stable dividend, but yield below portfolio average"

    if stability >= 0.60:
        if payout_ratio and payout_ratio > 0.70:
            return "Caution: High payout ratio may be unsustainable"
        return "Moderate stability - monitor for changes"

    if stability >= 0.40:
        return "Warning: Dividend may be at risk"

    return "High risk: Dividend appears unsustainable"


def is_dividend_consistent(
    symbol_yield: float,
    portfolio_avg_yield: float,
    stability_score: float,
    min_stability: float = 0.60,
) -> bool:
    """
    Quick check if a security has consistent dividends.

    Used by the holistic planner to identify reliable income securities.

    Args:
        symbol_yield: Stock's current dividend yield
        portfolio_avg_yield: Portfolio average yield
        stability_score: Pre-calculated stability score
        min_stability: Minimum stability to be considered consistent

    Returns:
        True if dividend is considered consistent
    """
    # Must have some yield
    if symbol_yield <= 0:
        return False

    # Must meet minimum stability
    if stability_score < min_stability:
        return False

    # Bonus points if above average (but not required)
    return True
