"""Position risk metrics calculation.

Calculates risk metrics for individual positions.
"""

import logging
from typing import Dict

import empyrical
import numpy as np
import pandas as pd

from app.repositories import HistoryRepository

logger = logging.getLogger(__name__)


async def get_position_risk_metrics(
    symbol: str, start_date: str, end_date: str
) -> Dict[str, float]:
    """
    Calculate risk metrics for a specific position.

    Uses 72-hour cache to reduce expensive calculations.

    Args:
        symbol: Stock symbol
        start_date: Start date for analysis
        end_date: End date for analysis

    Returns:
        Dict with sortino_ratio, sharpe_ratio, volatility, max_drawdown
    """
    # Check cache first (72-hour TTL for symbol-specific data)
    from app.infrastructure.recommendation_cache import get_recommendation_cache

    rec_cache = get_recommendation_cache()
    cache_key = f"risk:{symbol}"
    cached = await rec_cache.get_analytics(cache_key)
    if cached:
        logger.debug(f"Using cached risk metrics for {symbol}")
        return cached

    try:
        history_repo = HistoryRepository(symbol)
        prices = await history_repo.get_daily_range(start_date, end_date)

        if len(prices) < 2:
            return {
                "sortino_ratio": 0.0,
                "sharpe_ratio": 0.0,
                "volatility": 0.0,
                "max_drawdown": 0.0,
            }

        # Calculate returns
        closes = [p.close_price for p in prices]
        returns = pd.Series(closes).pct_change().dropna()

        if returns.empty:
            return {
                "sortino_ratio": 0.0,
                "sharpe_ratio": 0.0,
                "volatility": 0.0,
                "max_drawdown": 0.0,
            }

        # Calculate metrics
        volatility = float(empyrical.annual_volatility(returns))
        sharpe_ratio = float(empyrical.sharpe_ratio(returns))
        sortino_ratio = float(empyrical.sortino_ratio(returns))
        max_drawdown = float(empyrical.max_drawdown(returns))

        result = {
            "sortino_ratio": sortino_ratio if np.isfinite(sortino_ratio) else 0.0,
            "sharpe_ratio": sharpe_ratio if np.isfinite(sharpe_ratio) else 0.0,
            "volatility": volatility if np.isfinite(volatility) else 0.0,
            "max_drawdown": max_drawdown if np.isfinite(max_drawdown) else 0.0,
        }

        # Cache the result (72-hour TTL for symbol-specific data - historical data changes slowly)
        await rec_cache.set_analytics(cache_key, result, ttl_hours=72)

        return result
    except Exception as e:
        logger.debug(f"Error calculating risk metrics for {symbol}: {e}")
        return {
            "sortino_ratio": 0.0,
            "sharpe_ratio": 0.0,
            "volatility": 0.0,
            "max_drawdown": 0.0,
        }
