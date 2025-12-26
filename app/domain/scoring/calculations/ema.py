"""EMA (Exponential Moving Average) calculation functions.

Pure calculation functions for EMA using pandas-ta.
"""

from typing import Optional

import numpy as np
import pandas as pd
import pandas_ta as ta

from app.domain.scoring.constants import EMA_LENGTH


def calculate_ema(closes: np.ndarray, length: int = EMA_LENGTH) -> Optional[float]:
    """
    Calculate Exponential Moving Average.

    Args:
        closes: Array of closing prices
        length: EMA period (default 200)

    Returns:
        Current EMA value or None if insufficient data
    """
    if len(closes) < length:
        # Fallback to SMA if not enough data for EMA
        return float(np.mean(closes))

    series = pd.Series(closes)
    ema = ta.ema(series, length=length)

    if ema is not None and len(ema) > 0 and not pd.isna(ema.iloc[-1]):
        return float(ema.iloc[-1])

    # Fallback to SMA
    return float(np.mean(closes[-length:]))
