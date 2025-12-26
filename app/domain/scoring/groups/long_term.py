"""
Long-term Performance Score - Historical returns and risk-adjusted performance.

Components:
- CAGR (40%): Compound Annual Growth Rate
- Sortino Ratio (35%): Downside risk-adjusted returns (from PyFolio)
- Sharpe Ratio (25%): Overall risk-adjusted returns
"""

import logging
from typing import Dict, List, Optional

import numpy as np

from app.domain.responses import ScoreResult
from app.domain.scoring.calculations import calculate_cagr
from app.domain.scoring.constants import OPTIMAL_CAGR
from app.domain.scoring.scorers.long_term import (
    score_cagr,
    score_sharpe,
    score_sortino,
)

logger = logging.getLogger(__name__)

# Internal weights for sub-components (hardcoded)
WEIGHT_CAGR = 0.40
WEIGHT_SORTINO = 0.35
WEIGHT_SHARPE = 0.25


async def calculate_long_term_score(
    symbol: str,
    monthly_prices: List[Dict],
    daily_prices: List[Dict],
    sortino_ratio: Optional[float] = None,
    target_annual_return: float = OPTIMAL_CAGR,
) -> ScoreResult:
    """
    Calculate long-term performance score.

    Args:
        symbol: Stock symbol (for cache lookup)
        monthly_prices: Monthly price data for CAGR
        daily_prices: Daily price data for Sharpe
        sortino_ratio: Pre-calculated Sortino from PyFolio (optional)
        target_annual_return: Target return for CAGR scoring

    Returns:
        ScoreResult with score and sub_scores
        sub_scores: {"cagr": float, "sortino": float, "sharpe": float}
    """
    from app.domain.scoring.caching import get_sharpe_ratio
    from app.repositories.calculations import CalculationsRepository

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
        cagr_score * WEIGHT_CAGR
        + sortino_score * WEIGHT_SORTINO
        + sharpe_score * WEIGHT_SHARPE
    )

    sub_components = {
        "cagr": round(cagr_score, 3),
        "sortino": round(sortino_score, 3),
        "sharpe": round(sharpe_score, 3),
    }

    return ScoreResult(score=round(min(1.0, total), 3), sub_scores=sub_components)
