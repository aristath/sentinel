"""Converters between JSON data structures and pandas DataFrames."""

import pandas as pd
from typing import List, Tuple, Dict
from app.models import TimeSeriesData


def timeseries_to_dataframe(ts: TimeSeriesData) -> pd.DataFrame:
    """
    Convert TimeSeriesData to pandas DataFrame.

    Args:
        ts: TimeSeriesData with dates and symbol->values mapping

    Returns:
        DataFrame with dates as index, symbols as columns

    Example:
        Input: TimeSeriesData(
            dates=["2025-01-01", "2025-01-02"],
            data={"AAPL": [150.0, 151.5], "MSFT": [380.0, 382.5]}
        )
        Output: DataFrame with index=dates, columns=['AAPL', 'MSFT']
    """
    df = pd.DataFrame(ts.data, index=pd.to_datetime(ts.dates))
    return df


def matrix_to_dataframe(matrix: List[List[float]], symbols: List[str]) -> pd.DataFrame:
    """
    Convert nested list covariance matrix to DataFrame.

    Args:
        matrix: Nested list representing N×N covariance matrix
        symbols: List of symbols (must match matrix dimensions)

    Returns:
        DataFrame with symbols as both index and columns

    Example:
        Input: matrix=[[0.04, 0.02], [0.02, 0.05]], symbols=["AAPL", "MSFT"]
        Output: DataFrame with index/columns=['AAPL', 'MSFT']
    """
    return pd.DataFrame(matrix, index=symbols, columns=symbols)


def dataframe_to_matrix(df: pd.DataFrame) -> Tuple[List[List[float]], List[str]]:
    """
    Convert DataFrame to nested list and symbol list.

    Args:
        df: DataFrame with symbols as index and columns

    Returns:
        Tuple of (nested list matrix, symbols list)

    Example:
        Input: DataFrame with index/columns=['AAPL', 'MSFT']
        Output: ([[0.04, 0.02], [0.02, 0.05]], ['AAPL', 'MSFT'])
    """
    return df.values.tolist(), df.columns.tolist()


def dict_to_series(data: Dict[str, float]) -> pd.Series:
    """
    Convert dictionary to pandas Series.

    Args:
        data: Symbol to value mapping

    Returns:
        Series with symbols as index

    Example:
        Input: {"AAPL": 0.12, "MSFT": 0.10}
        Output: Series with index=['AAPL', 'MSFT'], values=[0.12, 0.10]
    """
    return pd.Series(data)
