"""Portfolio metrics calculation.

Calculates comprehensive portfolio performance metrics using PyFolio/empyrical.
"""

import logging
from typing import Optional

import empyrical
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


async def get_portfolio_metrics(
    returns: pd.Series,
    benchmark: Optional[pd.Series] = None,
    risk_free_rate: float = 0.0,
) -> dict[str, float]:
    """
    Calculate comprehensive portfolio metrics using PyFolio.

    Args:
        returns: Daily returns series
        benchmark: Optional benchmark returns for comparison
        risk_free_rate: Risk-free rate (default 0.0)

    Returns:
        Dict with metrics: annual_return, volatility, sharpe_ratio, sortino_ratio,
        calmar_ratio, max_drawdown, etc.
    """
    if returns.empty or len(returns) < 2:
        return {
            "annual_return": 0.0,
            "volatility": 0.0,
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "calmar_ratio": 0.0,
            "max_drawdown": 0.0,
        }

    try:
        # Calculate metrics using empyrical (used by PyFolio)
        annual_return = float(empyrical.annual_return(returns))
        volatility = float(empyrical.annual_volatility(returns))
        sharpe_ratio = float(empyrical.sharpe_ratio(returns, risk_free=risk_free_rate))
        sortino_ratio = float(
            empyrical.sortino_ratio(returns, risk_free=risk_free_rate)
        )
        max_drawdown = float(empyrical.max_drawdown(returns))

        # Calmar ratio = annual return / abs(max drawdown)
        calmar_ratio = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0.0

        return {
            "annual_return": annual_return if np.isfinite(annual_return) else 0.0,
            "volatility": volatility if np.isfinite(volatility) else 0.0,
            "sharpe_ratio": sharpe_ratio if np.isfinite(sharpe_ratio) else 0.0,
            "sortino_ratio": sortino_ratio if np.isfinite(sortino_ratio) else 0.0,
            "calmar_ratio": calmar_ratio if np.isfinite(calmar_ratio) else 0.0,
            "max_drawdown": max_drawdown if np.isfinite(max_drawdown) else 0.0,
        }
    except Exception as e:
        logger.error(f"Error calculating portfolio metrics: {e}")
        return {
            "annual_return": 0.0,
            "volatility": 0.0,
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "calmar_ratio": 0.0,
            "max_drawdown": 0.0,
        }
