"""Historical position reconstruction.

Reconstructs historical position quantities from trades.
"""

import pandas as pd

from app.repositories import TradeRepository


async def reconstruct_historical_positions(
    start_date: str, end_date: str
) -> pd.DataFrame:
    """
    Reconstruct historical position quantities by date from trades.

    Args:
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)

    Returns:
        DataFrame with columns: date, symbol, quantity
    """
    trade_repo = TradeRepository()
    position_history = await trade_repo.get_position_history(start_date, end_date)

    if not position_history:
        return pd.DataFrame(columns=["date", "symbol", "quantity"])

    df = pd.DataFrame(position_history)
    df["date"] = pd.to_datetime(df["date"])
    return df
