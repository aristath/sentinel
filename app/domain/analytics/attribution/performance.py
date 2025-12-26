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

    # Get unique dates from returns (only trading days)
    return_dates = returns.index.tolist()

    for date in return_dates:
        date_str = date.strftime("%Y-%m-%d")

        # Get positions on this date
        date_positions = positions_df[positions_df["date"] <= date]
        if date_positions.empty:
            continue

        latest_positions = date_positions.groupby("symbol").last()

        # Calculate position values and weights
        total_value = 0.0
        position_values = {}

        for symbol, row in latest_positions.iterrows():
            quantity = row["quantity"]
            if quantity <= 0:
                continue

            info = stock_info.get(symbol, {})
            geography = info.get("geography", "UNKNOWN")
            industry = info.get("industry")

            # Get price
            try:
                history_repo = HistoryRepository(symbol)
                price_data = await history_repo.get_daily_range(date_str, date_str)

                if price_data:
                    price = price_data[0].close_price
                    value = quantity * price
                    total_value += value
                    position_values[symbol] = {
                        "value": value,
                        "geography": geography,
                        "industry": industry,
                    }
            except Exception:
                continue

        if total_value == 0:
            continue

        # Get return for this date
        daily_return = returns[date]

        # Attribute return by geography/industry
        for symbol, data in position_values.items():
            weight = data["value"] / total_value
            geo = data["geography"]
            ind = data["industry"]

            contribution = daily_return * weight

            if geo not in geo_returns:
                geo_returns[geo] = []
            geo_returns[geo].append(contribution)

            if ind:
                if ind not in industry_returns:
                    industry_returns[ind] = []
                industry_returns[ind].append(contribution)

    # Calculate average returns (annualized)
    attribution = {"geography": {}, "industry": {}}

    for geo, contributions in geo_returns.items():
        if contributions:
            total_return = sum(contributions)
            # Use compound annualization: (1 + r)^(252/n) - 1
            # Guard against total loss (return <= -1) which would cause invalid power
            if total_return <= -1:
                annualized = -1.0  # Cap at -100% loss
            elif len(contributions) > 0:
                annualized = (1 + total_return) ** (252 / len(contributions)) - 1
            else:
                annualized = 0.0
            attribution["geography"][geo] = (
                float(annualized) if np.isfinite(annualized) else 0.0
            )

    for ind, contributions in industry_returns.items():
        if contributions:
            total_return = sum(contributions)
            # Use compound annualization: (1 + r)^(252/n) - 1
            # Guard against total loss (return <= -1) which would cause invalid power
            if total_return <= -1:
                annualized = -1.0  # Cap at -100% loss
            elif len(contributions) > 0:
                annualized = (1 + total_return) ** (252 / len(contributions)) - 1
            else:
                annualized = 0.0
            attribution["industry"][ind] = (
                float(annualized) if np.isfinite(annualized) else 0.0
            )

    return attribution
