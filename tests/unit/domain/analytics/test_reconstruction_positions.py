"""Tests for historical positions reconstruction.

These tests validate the reconstruction of historical position quantities
from trades.
"""

from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest


@pytest.fixture
def mock_trade_repo():
    """Mock TradeRepository."""
    repo = AsyncMock()
    repo.get_position_history.return_value = []
    return repo


class TestReconstructHistoricalPositions:
    """Test reconstruct_historical_positions function."""

    @pytest.mark.asyncio
    async def test_returns_empty_dataframe_when_no_history(self, mock_trade_repo):
        """Test that empty DataFrame is returned when no position history exists."""
        from app.modules.analytics.domain.reconstruction.positions import (
            reconstruct_historical_positions,
        )

        with patch(
            "app.modules.analytics.domain.reconstruction.positions.TradeRepository",
            return_value=mock_trade_repo,
        ):
            result = await reconstruct_historical_positions(
                start_date="2024-01-01", end_date="2024-01-05"
            )

            assert isinstance(result, pd.DataFrame)
            assert result.empty
            assert list(result.columns) == ["date", "symbol", "quantity"]

    @pytest.mark.asyncio
    async def test_returns_dataframe_with_position_history(self, mock_trade_repo):
        """Test that DataFrame is returned with position history."""
        from app.modules.analytics.domain.reconstruction.positions import (
            reconstruct_historical_positions,
        )

        position_history = [
            {"date": "2024-01-01", "symbol": "AAPL", "quantity": 10.0},
            {"date": "2024-01-02", "symbol": "AAPL", "quantity": 15.0},
            {"date": "2024-01-03", "symbol": "MSFT", "quantity": 5.0},
        ]
        mock_trade_repo.get_position_history.return_value = position_history

        with patch(
            "app.modules.analytics.domain.reconstruction.positions.TradeRepository",
            return_value=mock_trade_repo,
        ):
            result = await reconstruct_historical_positions(
                start_date="2024-01-01", end_date="2024-01-05"
            )

            assert isinstance(result, pd.DataFrame)
            assert len(result) == 3
            assert list(result.columns) == ["date", "symbol", "quantity"]
            assert result.iloc[0]["symbol"] == "AAPL"
            assert result.iloc[0]["quantity"] == 10.0
            assert result.iloc[2]["symbol"] == "MSFT"
            assert result.iloc[2]["quantity"] == 5.0

    @pytest.mark.asyncio
    async def test_converts_date_to_datetime(self, mock_trade_repo):
        """Test that date column is converted to datetime."""
        from app.modules.analytics.domain.reconstruction.positions import (
            reconstruct_historical_positions,
        )

        position_history = [{"date": "2024-01-01", "symbol": "AAPL", "quantity": 10.0}]
        mock_trade_repo.get_position_history.return_value = position_history

        with patch(
            "app.modules.analytics.domain.reconstruction.positions.TradeRepository",
            return_value=mock_trade_repo,
        ):
            result = await reconstruct_historical_positions(
                start_date="2024-01-01", end_date="2024-01-05"
            )

            assert pd.api.types.is_datetime64_any_dtype(result["date"])

    @pytest.mark.asyncio
    async def test_handles_multiple_symbols(self, mock_trade_repo):
        """Test handling of multiple symbols in position history."""
        from app.modules.analytics.domain.reconstruction.positions import (
            reconstruct_historical_positions,
        )

        position_history = [
            {"date": "2024-01-01", "symbol": "AAPL", "quantity": 10.0},
            {"date": "2024-01-01", "symbol": "MSFT", "quantity": 5.0},
            {"date": "2024-01-02", "symbol": "GOOG", "quantity": 3.0},
        ]
        mock_trade_repo.get_position_history.return_value = position_history

        with patch(
            "app.modules.analytics.domain.reconstruction.positions.TradeRepository",
            return_value=mock_trade_repo,
        ):
            result = await reconstruct_historical_positions(
                start_date="2024-01-01", end_date="2024-01-05"
            )

            symbols = result["symbol"].unique()
            assert len(symbols) == 3
            assert "AAPL" in symbols
            assert "MSFT" in symbols
            assert "GOOG" in symbols

    @pytest.mark.asyncio
    async def test_handles_zero_quantities(self, mock_trade_repo):
        """Test handling of zero quantities (position closed)."""
        from app.modules.analytics.domain.reconstruction.positions import (
            reconstruct_historical_positions,
        )

        position_history = [
            {"date": "2024-01-01", "symbol": "AAPL", "quantity": 10.0},
            {"date": "2024-01-02", "symbol": "AAPL", "quantity": 0.0},
        ]
        mock_trade_repo.get_position_history.return_value = position_history

        with patch(
            "app.modules.analytics.domain.reconstruction.positions.TradeRepository",
            return_value=mock_trade_repo,
        ):
            result = await reconstruct_historical_positions(
                start_date="2024-01-01", end_date="2024-01-05"
            )

            assert len(result) == 2
            assert result.iloc[1]["quantity"] == 0.0

    @pytest.mark.asyncio
    async def test_handles_negative_quantities(self, mock_trade_repo):
        """Test handling of negative quantities (shouldn't happen, but handle gracefully)."""
        from app.modules.analytics.domain.reconstruction.positions import (
            reconstruct_historical_positions,
        )

        position_history = [
            {"date": "2024-01-01", "symbol": "AAPL", "quantity": -5.0},
        ]
        mock_trade_repo.get_position_history.return_value = position_history

        with patch(
            "app.modules.analytics.domain.reconstruction.positions.TradeRepository",
            return_value=mock_trade_repo,
        ):
            result = await reconstruct_historical_positions(
                start_date="2024-01-01", end_date="2024-01-05"
            )

            assert len(result) == 1
            assert result.iloc[0]["quantity"] == -5.0

    @pytest.mark.asyncio
    async def test_calls_trade_repo_with_correct_parameters(self, mock_trade_repo):
        """Test that TradeRepository is called with correct date range."""
        from app.modules.analytics.domain.reconstruction.positions import (
            reconstruct_historical_positions,
        )

        with patch(
            "app.modules.analytics.domain.reconstruction.positions.TradeRepository",
            return_value=mock_trade_repo,
        ):
            await reconstruct_historical_positions(
                start_date="2024-01-01", end_date="2024-01-31"
            )

            mock_trade_repo.get_position_history.assert_called_once_with(
                "2024-01-01", "2024-01-31"
            )
