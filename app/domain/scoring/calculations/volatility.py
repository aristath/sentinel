"""Volatility calculation functions.

Pure calculation functions for volatility metrics using empyrical.
"""

from typing import Optional

import numpy as np
import empyrical


def calculate_volatility(
    closes: np.ndarray,
    annualize: bool = True
) -> Optional[float]:
    """
    Calculate annualized volatility using empyrical.

    Args:
        closes: Array of closing prices
        annualize: Whether to annualize (default True)

    Returns:
        Annualized volatility or None if insufficient data
    """
    if len(closes) < 30:
        return None

    # Validate no zero/negative prices
    if np.any(closes[:-1] <= 0):
        return None

    returns = np.diff(closes) / closes[:-1]

    try:
        vol = float(empyrical.annual_volatility(returns))
        if not np.isfinite(vol) or vol < 0:
            return None
        return vol
    except Exception:
        return None

