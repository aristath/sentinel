"""Performance attribution calculation.

Calculates performance attribution by geography and industry.
"""

import logging
from typing import Dict

import numpy as np
import pandas as pd

from app.domain.analytics.reconstruction.positions import (
    reconstruct_historical_positions,
)
from app.repositories import HistoryRepository, StockRepository

logger = logging.getLogger(__name__)


async def get_performance_attribution(
    returns: pd.Series, start_date: str, end_date: str
) -> Dict[str, Dict[str, float]]:
    """
    Calculate performance attribution by geography and industry.

    Args:
        returns: Daily portfolio returns
        start_date: Start date for analysis
        end_date: End date for analysis

    Returns:
        Dict with 'geography' and 'industry' keys, each containing
        attribution by category (e.g., {'EU': 0.08, 'ASIA': 0.15})
    """
    if returns.empty:
        return {"geography": {}, "industry": {}}

    # Get position history
    positions_df = await reconstruct_historical_positions(start_date, end_date)

    if positions_df.empty:
        return {"geography": {}, "industry": {}}

    # Get stock info for geography/industry
    stock_repo = StockRepository()
    stocks = await stock_repo.get_all()
    stock_info = {
        s.symbol: {"geography": s.geography, "industry": s.industry} for s in stocks
    }

    # Calculate returns by geography and industry
    # Only process dates where we have returns data (more efficient)
    geo_returns = {}
    industry_returns = {}

    return_dates = returns.index.tolist()

    for date in return_dates:
        date_str = date.strftime("%Y-%m-%d")
        date_positions = positions_df[positions_df["date"] <= date]
        if date_positions.empty:
            continue

        latest_positions = date_positions.groupby("symbol").last()
        total_value, position_values = await _calculate_position_values(
            latest_positions, stock_info, date_str
        )

        if total_value == 0:
            continue

        daily_return = returns[date]
        _attribute_return_by_category(
            position_values, total_value, daily_return, geo_returns, industry_returns
        )

    attribution = _calculate_annualized_attribution(geo_returns, industry_returns)

    return attribution
