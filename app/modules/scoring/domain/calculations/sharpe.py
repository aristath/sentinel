"""Sharpe ratio calculation functions.

Pure calculation functions for risk-adjusted return metrics using empyrical.
"""

from typing import Optional

import empyrical
import numpy as np

from app.modules.scoring.domain.constants import TRADING_DAYS_PER_YEAR


def calculate_sharpe_ratio(
    closes: np.ndarray, risk_free_rate: float = 0.0
) -> Optional[float]:
    """
    Calculate Sharpe ratio using empyrical.

    Args:
        closes: Array of closing prices
        risk_free_rate: Risk-free rate (default 0)

    Returns:
        Annualized Sharpe ratio or None if insufficient data
    """
    if len(closes) < 50:
        return None

    # Validate no zero/negative prices
    if np.any(closes[:-1] <= 0):
        return None

    returns = np.diff(closes) / closes[:-1]

    try:
        sharpe = float(
            empyrical.sharpe_ratio(
                returns, risk_free=risk_free_rate, annualization=TRADING_DAYS_PER_YEAR
            )
        )
        if not np.isfinite(sharpe):
            return None
        return sharpe
    except Exception:
        return None
