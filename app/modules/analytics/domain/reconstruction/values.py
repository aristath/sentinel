"""Portfolio values reconstruction.

Reconstructs daily portfolio values from positions, prices, and cash.
"""

import logging

import pandas as pd

from app.modules.analytics.domain.reconstruction.cash import reconstruct_cash_balance
from app.modules.analytics.domain.reconstruction.positions import (
    reconstruct_historical_positions,
)
from app.repositories import HistoryRepository

logger = logging.getLogger(__name__)


async def _batch_load_prices(
    symbols: list[str], start_date: str, end_date: str
) -> dict[str, dict[str, float]]:
    """
    Batch-load all prices for given symbols and date range.

    Returns:
        Dict[symbol][date] = price (with "_last" key for forward-fill)
    """
    prices: dict[str, dict[str, float]] = {}

    for symbol in symbols:
        try:
            history_repo = HistoryRepository(symbol)
            price_data = await history_repo.get_daily_range(start_date, end_date)

            prices[symbol] = {}
            last_price = None
            for p in price_data:
                prices[symbol][p.date] = p.close_price
                last_price = p.close_price

            # Store last known price for forward-fill
            if last_price:
                prices[symbol]["_last"] = last_price
        except Exception as e:
            logger.debug(f"Could not load prices for {symbol}: {e}")
            prices[symbol] = {}

    return prices


async def reconstruct_portfolio_values(
    start_date: str, end_date: str, initial_cash: float = 0.0
) -> pd.Series:
    """
    Reconstruct daily portfolio values from positions + prices + cash.

    Uses batch price loading for performance and forward-fill for missing prices.

    Args:
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        initial_cash: Starting cash balance

    Returns:
        Series with date index and portfolio values
    """
    # Get position history
    positions_df = await reconstruct_historical_positions(start_date, end_date)

    # Get cash balance history
    cash_series = await reconstruct_cash_balance(start_date, end_date, initial_cash)

    # Get all unique dates
    dates = pd.date_range(start=start_date, end=end_date, freq="D")
    portfolio_values = pd.Series(0.0, index=dates)

    # Get all symbols that had positions
    symbols = positions_df["symbol"].unique() if not positions_df.empty else []

    # Batch load all prices upfront (performance optimization)
    all_prices = await _batch_load_prices(list(symbols), start_date, end_date)

    # For each date, calculate portfolio value
    for date in dates:
        date_str = date.strftime("%Y-%m-%d")

        # Get positions on this date (latest position before or on date)
        date_positions = positions_df[positions_df["date"] <= date]
        if not date_positions.empty:
            latest_positions = date_positions.groupby("symbol").last()

            # Calculate total position value
            total_position_value = 0.0
            for symbol, row in latest_positions.iterrows():
                quantity = row["quantity"]
                if quantity <= 0:
                    continue

                # Get price for this date (forward-fill if missing)
                symbol_prices = all_prices.get(symbol, {})
                price = None

                # Try exact date first
                if date_str in symbol_prices:
                    price = symbol_prices[date_str]
                else:
                    # Forward-fill: find latest price before this date
                    for prev_date, prev_price in sorted(symbol_prices.items()):
                        if prev_date != "_last" and prev_date <= date_str:
                            price = prev_price

                    # If still no price, use last known price
                    if price is None and "_last" in symbol_prices:
                        price = symbol_prices["_last"]

                if price and price > 0:
                    total_position_value += quantity * price

        # Portfolio value = positions + cash
        cash_value = cash_series[date] if date in cash_series.index else 0.0
        portfolio_values[date] = total_position_value + cash_value

    return portfolio_values
