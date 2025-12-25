"""
Long-term Performance Score - Historical returns and risk-adjusted performance.

Components:
- CAGR (40%): Compound Annual Growth Rate
- Sortino Ratio (35%): Downside risk-adjusted returns (from PyFolio)
- Sharpe Ratio (25%): Overall risk-adjusted returns
"""

import logging
from typing import Optional, List, Dict

import numpy as np

from app.domain.scoring.constants import (
    OPTIMAL_CAGR,
    BELL_CURVE_SIGMA_LEFT,
    BELL_CURVE_SIGMA_RIGHT,
    BELL_CURVE_FLOOR,
    SHARPE_EXCELLENT,
    SHARPE_GOOD,
    SHARPE_OK,
    MIN_MONTHS_FOR_CAGR,
)
import math

logger = logging.getLogger(__name__)

# Internal weights for sub-components (hardcoded)
WEIGHT_CAGR = 0.40
WEIGHT_SORTINO = 0.35
WEIGHT_SHARPE = 0.25


def calculate_cagr(prices: List[Dict], months: int) -> Optional[float]:
    """
    Calculate CAGR from monthly prices.

    Args:
        prices: List of dicts with year_month and avg_adj_close
        months: Number of months to use (e.g., 60 for 5 years)

    Returns:
        CAGR as decimal or None if insufficient data
    """
    if len(prices) < MIN_MONTHS_FOR_CAGR:
        return None

    use_months = min(months, len(prices))
    price_slice = prices[-use_months:]

    start_price = price_slice[0].get("avg_adj_close")
    end_price = price_slice[-1].get("avg_adj_close")

    if not start_price or not end_price or start_price <= 0:
        return None

    years = use_months / 12.0
    if years < 0.25:
        return (end_price / start_price) - 1

    try:
        return (end_price / start_price) ** (1 / years) - 1
    except (ValueError, ZeroDivisionError):
        return None


def score_cagr(cagr: float, target: float = OPTIMAL_CAGR) -> float:
    """
    Bell curve scoring for CAGR.

    Peak at target (default 11%). Uses asymmetric Gaussian.

    Returns:
        Score from 0.15 to 1.0
    """
    if cagr <= 0:
        return BELL_CURVE_FLOOR

    sigma = BELL_CURVE_SIGMA_LEFT if cagr < target else BELL_CURVE_SIGMA_RIGHT
    raw_score = math.exp(-((cagr - target) ** 2) / (2 * sigma ** 2))

    return BELL_CURVE_FLOOR + raw_score * (1 - BELL_CURVE_FLOOR)


def score_sharpe(sharpe_ratio: Optional[float]) -> float:
    """
    Convert Sharpe ratio to score.

    Sharpe > 2.0 is excellent, > 1.0 is good.

    Returns:
        Score from 0 to 1.0
    """
    if sharpe_ratio is None:
        return 0.5

    if sharpe_ratio >= SHARPE_EXCELLENT:
        return 1.0
    elif sharpe_ratio >= SHARPE_GOOD:
        return 0.7 + (sharpe_ratio - SHARPE_GOOD) * 0.3
    elif sharpe_ratio >= SHARPE_OK:
        return 0.4 + (sharpe_ratio - SHARPE_OK) * 0.6
    elif sharpe_ratio >= 0:
        return sharpe_ratio * 0.8
    else:
        return 0.0


def score_sortino(sortino_ratio: Optional[float]) -> float:
    """
    Convert Sortino ratio to score.

    Sortino > 2.0 is excellent (focuses on downside risk).

    Returns:
        Score from 0 to 1.0
    """
    if sortino_ratio is None:
        return 0.5

    if sortino_ratio >= 2.0:
        return 1.0
    elif sortino_ratio >= 1.5:
        return 0.8 + (sortino_ratio - 1.5) * 0.4
    elif sortino_ratio >= 1.0:
        return 0.6 + (sortino_ratio - 1.0) * 0.4
    elif sortino_ratio >= 0.5:
        return 0.4 + (sortino_ratio - 0.5) * 0.4
    elif sortino_ratio >= 0:
        return sortino_ratio * 0.8
    else:
        return 0.0


async def calculate_long_term_score(
    symbol: str,
    monthly_prices: List[Dict],
    daily_prices: List[Dict],
    sortino_ratio: Optional[float] = None,
    target_annual_return: float = OPTIMAL_CAGR,
) -> tuple:
    """
    Calculate long-term performance score.

    Args:
        symbol: Stock symbol (for cache lookup)
        monthly_prices: Monthly price data for CAGR
        daily_prices: Daily price data for Sharpe
        sortino_ratio: Pre-calculated Sortino from PyFolio (optional)
        target_annual_return: Target return for CAGR scoring

    Returns:
        Tuple of (total_score, sub_components_dict)
        sub_components_dict: {"cagr": float, "sortino": float, "sharpe": float}
    """
    from app.repositories.calculations import CalculationsRepository
    from app.domain.scoring.technical import get_sharpe_ratio

    calc_repo = CalculationsRepository()

    # Get CAGR from cache or calculate
    cagr_5y = await calc_repo.get_metric(symbol, "CAGR_5Y")
    if cagr_5y is None:
        cagr_5y = calculate_cagr(monthly_prices, 60)  # 5 years
        if cagr_5y is None:
            cagr_5y = calculate_cagr(monthly_prices, len(monthly_prices))
        if cagr_5y is not None:
            await calc_repo.set_metric(symbol, "CAGR_5Y", cagr_5y)
    cagr_score = score_cagr(cagr_5y or 0, target_annual_return)

    # Get Sharpe from cache or calculate
    sharpe_ratio = None
    if len(daily_prices) >= 50:
        closes = np.array([p["close"] for p in daily_prices])
        sharpe_ratio = await get_sharpe_ratio(symbol, closes)
    sharpe_score = score_sharpe(sharpe_ratio)

    # Get Sortino from cache or use provided value
    sortino_ratio_cached = await calc_repo.get_metric(symbol, "SORTINO")
    if sortino_ratio_cached is not None:
        sortino_ratio = sortino_ratio_cached
    elif sortino_ratio is not None:
        # Store provided Sortino if not cached
        await calc_repo.set_metric(symbol, "SORTINO", sortino_ratio)
    sortino_score = score_sortino(sortino_ratio)

    # Combine with internal weights
    total = (
        cagr_score * WEIGHT_CAGR +
        sortino_score * WEIGHT_SORTINO +
        sharpe_score * WEIGHT_SHARPE
    )

    sub_components = {
        "cagr": round(cagr_score, 3),
        "sortino": round(sortino_score, 3),
        "sharpe": round(sharpe_score, 3),
    }

    return round(min(1.0, total), 3), sub_components
