"""Drawdown calculation functions.

Pure calculation functions for drawdown metrics using empyrical.
"""

from typing import Optional

import numpy as np
import empyrical


def calculate_max_drawdown(closes: np.ndarray) -> Optional[float]:
    """
    Calculate maximum drawdown using empyrical.

    Args:
        closes: Array of closing prices

    Returns:
        Maximum drawdown as negative percentage (e.g., -0.20 = 20% drawdown)
        or None if insufficient data
    """
    if len(closes) < 30:
        return None

    # Validate no zero/negative prices
    if np.any(closes <= 0):
        return None

    returns = np.diff(closes) / closes[:-1]

    try:
        mdd = float(empyrical.max_drawdown(returns))
        if not np.isfinite(mdd):
            return None
        return mdd
    except Exception:
        return None

