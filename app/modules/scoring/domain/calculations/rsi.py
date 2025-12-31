"""RSI (Relative Strength Index) calculation functions.

Pure calculation functions for RSI using pandas-ta.
"""

from typing import Optional

import numpy as np
import pandas as pd
import pandas_ta as ta

from app.modules.scoring.domain.constants import RSI_LENGTH


def calculate_rsi(closes: np.ndarray, length: int = RSI_LENGTH) -> Optional[float]:
    """
    Calculate Relative Strength Index.

    Args:
        closes: Array of closing prices
        length: RSI period (default 14)

    Returns:
        Current RSI value (0-100) or None if insufficient data
    """
    if len(closes) < length + 1:
        return None

    series = pd.Series(closes)
    rsi = ta.rsi(series, length=length)

    if rsi is not None and len(rsi) > 0 and not pd.isna(rsi.iloc[-1]):
        return float(rsi.iloc[-1].item())

    return None
