"""Tests for DataFrame converters."""

import pandas as pd
import pytest
from app.converters import (
    timeseries_to_dataframe,
    matrix_to_dataframe,
    dataframe_to_matrix,
    dict_to_series
)
from app.models import TimeSeriesData


class TestTimeSeriesConverter:
    """Test timeseries_to_dataframe conversion."""

    def test_basic_conversion(self):
        """Test basic time series to DataFrame conversion."""
        ts = TimeSeriesData(
            dates=["2025-01-01", "2025-01-02", "2025-01-03"],
            data={
                "AAPL": [150.0, 151.5, 152.0],
                "MSFT": [380.0, 382.5, 381.0]
            }
        )

        df = timeseries_to_dataframe(ts)

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3
        assert list(df.columns) == ["AAPL", "MSFT"]
        assert df.loc["2025-01-01", "AAPL"] == 150.0
        assert df.loc["2025-01-02", "MSFT"] == 382.5

    def test_index_is_datetime(self):
        """Test that index is converted to datetime."""
        ts = TimeSeriesData(
            dates=["2025-01-01"],
            data={"AAPL": [150.0]}
        )

        df = timeseries_to_dataframe(ts)

        assert isinstance(df.index, pd.DatetimeIndex)


class TestMatrixConverter:
    """Test matrix_to_dataframe and dataframe_to_matrix conversions."""

    def test_matrix_to_dataframe(self):
        """Test converting nested list matrix to DataFrame."""
        matrix = [
            [0.04, 0.02, 0.01],
            [0.02, 0.05, 0.015],
            [0.01, 0.015, 0.03]
        ]
        symbols = ["AAPL", "MSFT", "GOOGL"]

        df = matrix_to_dataframe(matrix, symbols)

        assert isinstance(df, pd.DataFrame)
        assert list(df.index) == symbols
        assert list(df.columns) == symbols
        assert df.loc["AAPL", "MSFT"] == 0.02
        assert df.loc["GOOGL", "GOOGL"] == 0.03

    def test_dataframe_to_matrix(self):
        """Test converting DataFrame back to matrix."""
        df = pd.DataFrame(
            [[0.04, 0.02], [0.02, 0.05]],
            index=["AAPL", "MSFT"],
            columns=["AAPL", "MSFT"]
        )

        matrix, symbols = dataframe_to_matrix(df)

        assert isinstance(matrix, list)
        assert isinstance(symbols, list)
        assert matrix == [[0.04, 0.02], [0.02, 0.05]]
        assert symbols == ["AAPL", "MSFT"]

    def test_round_trip_conversion(self):
        """Test that conversion is lossless."""
        original_matrix = [
            [0.04, 0.02],
            [0.02, 0.05]
        ]
        original_symbols = ["AAPL", "MSFT"]

        df = matrix_to_dataframe(original_matrix, original_symbols)
        matrix, symbols = dataframe_to_matrix(df)

        assert matrix == original_matrix
        assert symbols == original_symbols


class TestDictToSeries:
    """Test dict_to_series conversion."""

    def test_basic_conversion(self):
        """Test converting dict to pandas Series."""
        data = {"AAPL": 0.12, "MSFT": 0.10, "GOOGL": 0.15}

        series = dict_to_series(data)

        assert isinstance(series, pd.Series)
        assert len(series) == 3
        assert series["AAPL"] == 0.12
        assert series["MSFT"] == 0.10

    def test_empty_dict(self):
        """Test converting empty dict."""
        series = dict_to_series({})

        assert isinstance(series, pd.Series)
        assert len(series) == 0
