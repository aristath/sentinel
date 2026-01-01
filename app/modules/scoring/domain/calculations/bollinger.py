"""Bollinger Bands calculation functions.

Pure calculation functions for Bollinger Bands using pandas-ta.
"""

from typing import Any, Optional, Tuple, cast

import numpy as np
import pandas as pd
import pandas_ta as ta

from app.modules.scoring.domain.constants import BOLLINGER_LENGTH, BOLLINGER_STD


def calculate_bollinger_bands(
    closes: np.ndarray, length: int = BOLLINGER_LENGTH, std: float = BOLLINGER_STD
) -> Optional[Tuple[float, float, float]]:
    """
    Calculate Bollinger Bands.

    Args:
        closes: Array of closing prices
        length: BB period (default 20)
        std: Standard deviation multiplier (default 2)

    Returns:
        Tuple of (lower, middle, upper) or None if insufficient data
    """
    if len(closes) < length:
        return None

    series = pd.Series(closes)
    # pandas-ta bbands accepts float for std, but type stubs are incorrect
    bb = cast(Any, ta.bbands)(series, length=length, std=std)

    if bb is None or len(bb) == 0:
        return None

    # Extract the last values for each band
    try:
        lower_col = f"BBL_{length}_{std}.0"
        middle_col = f"BBM_{length}_{std}.0"
        upper_col = f"BBU_{length}_{std}.0"

        lower = bb[lower_col].iloc[-1] if lower_col in bb.columns else None
        middle = bb[middle_col].iloc[-1] if middle_col in bb.columns else None
        upper = bb[upper_col].iloc[-1] if upper_col in bb.columns else None

        if any(pd.isna([lower, middle, upper])):
            return None

        if lower is None or middle is None or upper is None:
            return None

        return float(lower), float(middle), float(upper)
    except (KeyError, IndexError, ValueError):
        return None
