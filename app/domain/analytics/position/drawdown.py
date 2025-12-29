"""Position drawdown analysis.

Analyzes drawdown periods for individual positions.
"""

import logging
from typing import Dict, Optional

import numpy as np
import pandas as pd

from app.repositories import HistoryRepository

logger = logging.getLogger(__name__)


async def get_position_drawdown(
    symbol: str, start_date: str, end_date: str
) -> Dict[str, Optional[float]]:
    """
    Analyze drawdown periods for a specific position.

    Args:
        symbol: Stock symbol
        start_date: Start date for analysis
        end_date: End date for analysis

    Returns:
        Dict with max_drawdown, current_drawdown, days_in_drawdown, recovery_date
    """
    try:
        history_repo = HistoryRepository(symbol)
        prices = await history_repo.get_daily_range(start_date, end_date)

        if len(prices) < 2:
            return {
                "max_drawdown": None,
                "current_drawdown": None,
                "days_in_drawdown": None,
                "recovery_date": None,
            }

        # Calculate returns and drawdowns
        closes = pd.Series(
            [p.close_price for p in prices],
            index=[pd.to_datetime(p.date) for p in prices],
        )
        returns = closes.pct_change().dropna()

        # Calculate cumulative returns
        cumulative = (1 + returns).cumprod()

        # Calculate running maximum
        running_max = cumulative.expanding().max()

        # Calculate drawdown
        drawdown = (cumulative - running_max) / running_max

        max_drawdown = float(drawdown.min()) if not drawdown.empty else 0.0
        current_drawdown = (
            float(drawdown.iloc[-1].item()) if not drawdown.empty else 0.0
        )

        # Calculate days in current drawdown
        days_in_drawdown = None
        recovery_date = None

        if current_drawdown < 0:
            # Find when drawdown started
            drawdown_start_idx = None
            for i in range(len(drawdown) - 1, -1, -1):
                if drawdown.iloc[i] >= 0:
                    drawdown_start_idx = i + 1
                    break

            if drawdown_start_idx is not None:
                days_in_drawdown = len(drawdown) - drawdown_start_idx
            else:
                days_in_drawdown = len(drawdown)

        return {
            "max_drawdown": max_drawdown if np.isfinite(max_drawdown) else None,
            "current_drawdown": (
                current_drawdown if np.isfinite(current_drawdown) else None
            ),
            "days_in_drawdown": days_in_drawdown,
            "recovery_date": recovery_date,
        }
    except Exception as e:
        logger.debug(f"Error calculating drawdown for {symbol}: {e}")
        return {
            "max_drawdown": None,
            "current_drawdown": None,
            "days_in_drawdown": None,
            "recovery_date": None,
        }
