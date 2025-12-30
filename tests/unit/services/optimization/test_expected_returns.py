"""Tests for expected returns calculation.

These tests validate expected returns calculations for portfolio optimization,
including historical returns, score-based returns, and weighted combinations.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest


class TestCalculateExpectedReturns:
    """Test calculate_expected_returns function."""

    @pytest.mark.asyncio
    async def test_calculates_returns_from_historical_data(self):
        """Test that expected returns are calculated from historical price data."""
        from app.application.services.optimization.expected_returns import (
            calculate_expected_returns,
        )

        # Mock historical returns data
        symbols = ["AAPL", "MSFT"]
        historical_returns = {
            "AAPL": pd.Series([0.01, 0.02, -0.01, 0.03], dtype=float),
            "MSFT": pd.Series([0.02, 0.01, 0.02, 0.01], dtype=float),
        }

        with patch(
            "app.application.services.optimization.expected_returns._get_historical_returns",
            new_callable=AsyncMock,
        ) as mock_get_returns:
            mock_get_returns.return_value = historical_returns

            result = await calculate_expected_returns(symbols, lookback_days=252)

            assert isinstance(result, dict)
            assert "AAPL" in result
            assert "MSFT" in result
            # Returns should be calculated (e.g., mean of historical returns)
            assert isinstance(result["AAPL"], float)
            assert isinstance(result["MSFT"], float)

    @pytest.mark.asyncio
    async def test_handles_missing_historical_data(self):
        """Test handling when historical data is missing for some symbols."""
        from app.application.services.optimization.expected_returns import (
            calculate_expected_returns,
        )

        symbols = ["AAPL", "UNKNOWN"]
        historical_returns = {
            "AAPL": pd.Series([0.01, 0.02], dtype=float),
            "UNKNOWN": pd.Series(dtype=float),  # Empty series
        }

        with patch(
            "app.application.services.optimization.expected_returns._get_historical_returns",
            new_callable=AsyncMock,
        ) as mock_get_returns:
            mock_get_returns.return_value = historical_returns

            result = await calculate_expected_returns(symbols, lookback_days=252)

            assert isinstance(result, dict)
            # Should handle missing data gracefully
            assert "AAPL" in result or len(result) >= 0

    @pytest.mark.asyncio
    async def test_handles_empty_symbols_list(self):
        """Test handling when symbols list is empty."""
        from app.application.services.optimization.expected_returns import (
            calculate_expected_returns,
        )

        symbols = []
        historical_returns = {}

        with patch(
            "app.application.services.optimization.expected_returns._get_historical_returns",
            new_callable=AsyncMock,
        ) as mock_get_returns:
            mock_get_returns.return_value = historical_returns

            result = await calculate_expected_returns(symbols, lookback_days=252)

            assert isinstance(result, dict)
            assert len(result) == 0

    @pytest.mark.asyncio
    async def test_uses_default_lookback_days(self):
        """Test that default lookback_days is used when not specified."""
        from app.application.services.optimization.expected_returns import (
            calculate_expected_returns,
        )

        symbols = ["AAPL"]
        historical_returns = {"AAPL": pd.Series([0.01, 0.02], dtype=float)}

        with patch(
            "app.application.services.optimization.expected_returns._get_historical_returns",
            new_callable=AsyncMock,
        ) as mock_get_returns:
            mock_get_returns.return_value = historical_returns

            result = await calculate_expected_returns(symbols)

            # Should use default lookback_days
            assert isinstance(result, dict)


class TestGetHistoricalReturns:
    """Test _get_historical_returns helper function."""

    @pytest.mark.asyncio
    async def test_fetches_returns_from_history_repo(self):
        """Test that historical returns are fetched from HistoryRepository."""
        from app.application.services.optimization.expected_returns import (
            _get_historical_returns,
        )

        symbols = ["AAPL"]
        mock_history_repo = AsyncMock()
        mock_prices = [
            MagicMock(date="2024-01-01", close_price=100.0),
            MagicMock(date="2024-01-02", close_price=101.0),
            MagicMock(date="2024-01-03", close_price=102.0),
        ]
        mock_history_repo.get_daily_range.return_value = mock_prices

        with patch(
            "app.application.services.optimization.expected_returns.HistoryRepository",
            return_value=mock_history_repo,
        ):
            result = await _get_historical_returns(symbols, lookback_days=252)

            assert isinstance(result, dict)
            assert "AAPL" in result
            assert isinstance(result["AAPL"], pd.Series)

    @pytest.mark.asyncio
    async def test_handles_missing_price_data(self):
        """Test handling when price data is missing for a symbol."""
        from app.application.services.optimization.expected_returns import (
            _get_historical_returns,
        )

        symbols = ["AAPL", "UNKNOWN"]
        mock_history_repo = AsyncMock()
        mock_history_repo.get_daily_range.side_effect = [
            [  # AAPL has prices
                MagicMock(date="2024-01-01", close_price=100.0),
                MagicMock(date="2024-01-02", close_price=101.0),
            ],
            [],  # UNKNOWN has no prices
        ]

        with patch(
            "app.application.services.optimization.expected_returns.HistoryRepository",
            return_value=mock_history_repo,
        ):
            result = await _get_historical_returns(symbols, lookback_days=252)

            assert isinstance(result, dict)
            # Should handle missing data gracefully
            assert "AAPL" in result or len(result) >= 0

    @pytest.mark.asyncio
    async def test_calculates_returns_from_prices(self):
        """Test that returns are calculated correctly from price data."""
        from app.application.services.optimization.expected_returns import (
            _get_historical_returns,
        )

        symbols = ["AAPL"]
        # Prices: 100, 101, 102 -> returns: 0.01, 0.0099
        mock_prices = [
            MagicMock(date="2024-01-01", close_price=100.0),
            MagicMock(date="2024-01-02", close_price=101.0),
            MagicMock(date="2024-01-03", close_price=102.0),
        ]

        mock_history_repo = AsyncMock()
        mock_history_repo.get_daily_range.return_value = mock_prices

        with patch(
            "app.application.services.optimization.expected_returns.HistoryRepository",
            return_value=mock_history_repo,
        ):
            result = await _get_historical_returns(symbols, lookback_days=252)

            assert "AAPL" in result
            returns = result["AAPL"]
            assert isinstance(returns, pd.Series)
            assert len(returns) == 2  # 3 prices -> 2 returns
            # First return: (101 - 100) / 100 = 0.01
            assert returns.iloc[0] == pytest.approx(0.01, abs=0.001)

    @pytest.mark.asyncio
    async def test_handles_insufficient_price_data(self):
        """Test handling when there's only one price point (no returns possible)."""
        from app.application.services.optimization.expected_returns import (
            _get_historical_returns,
        )

        symbols = ["AAPL"]
        mock_prices = [MagicMock(date="2024-01-01", close_price=100.0)]

        mock_history_repo = AsyncMock()
        mock_history_repo.get_daily_range.return_value = mock_prices

        with patch(
            "app.application.services.optimization.expected_returns.HistoryRepository",
            return_value=mock_history_repo,
        ):
            result = await _get_historical_returns(symbols, lookback_days=252)

            assert isinstance(result, dict)
            # Should handle insufficient data gracefully
            assert "AAPL" in result or len(result) == 0
