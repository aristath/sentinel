"""Portfolio returns calculation.

Pure functions for calculating returns from portfolio values.
"""

import pandas as pd


def calculate_portfolio_returns(portfolio_values: pd.Series) -> pd.Series:
    """
    Calculate daily returns from portfolio values.

    Args:
        portfolio_values: Series with date index and portfolio values

    Returns:
        Series with daily returns (as decimal, e.g., 0.01 = 1%)
    """
    returns = portfolio_values.pct_change().dropna()

    # Ensure date index is datetime
    returns.index = pd.to_datetime(returns.index)
    return returns
