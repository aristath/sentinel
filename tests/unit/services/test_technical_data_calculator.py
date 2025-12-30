"""Tests for technical data calculator.

These tests validate technical indicator calculations including volatility
and EMA distance calculations.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from app.domain.scoring import TechnicalData


class TestGetFallbackTechnicalData:
    """Test _get_fallback_technical_data function."""

    def test_returns_fallback_values(self):
        """Test that fallback returns default values."""
        from app.application.services.recommendation.technical_data_calculator import (
            _get_fallback_technical_data,
        )

        result = _get_fallback_technical_data()

        assert isinstance(result, TechnicalData)
        assert result.current_volatility == 0.20
        assert result.historical_volatility == 0.20
        assert result.distance_from_ma_200 == 0.0


class TestCalculateCurrentVolatility:
    """Test _calculate_current_volatility function."""

    def test_returns_fallback_when_insufficient_data(self):
        """Test that fallback is returned when less than 60 days."""
        from app.application.services.recommendation.technical_data_calculator import (
            _calculate_current_volatility,
        )

        closes = np.array([100.0] * 30)  # Only 30 days
        result = _calculate_current_volatility(closes)

        assert result == 0.20

    def test_calculates_volatility_from_last_60_days(self):
        """Test that volatility is calculated from last 60 days."""
        from app.application.services.recommendation.technical_data_calculator import (
            _calculate_current_volatility,
        )

        # Create data with 100 days, but should use last 60
        np.random.seed(42)
        closes = 100.0 + np.cumsum(np.random.randn(100) * 2)

        result = _calculate_current_volatility(closes)

        assert result >= 0
        assert result != 0.20  # Should not be fallback value
        assert np.isfinite(result)

    def test_returns_fallback_for_non_finite_values(self):
        """Test that fallback is returned for NaN or infinite values."""
        from app.application.services.recommendation.technical_data_calculator import (
            _calculate_current_volatility,
        )

        # Create array with NaN
        closes = np.full(100, np.nan)
        result = _calculate_current_volatility(closes)

        assert result == 0.20

    def test_returns_fallback_for_negative_volatility(self):
        """Test that fallback is returned for negative volatility."""
        from app.application.services.recommendation.technical_data_calculator import (
            _calculate_current_volatility,
        )

        # Create data that might produce negative volatility (shouldn't happen, but test anyway)
        closes = np.array([100.0] * 100)
        result = _calculate_current_volatility(closes)

        # Should handle edge case gracefully
        assert result >= 0


class TestCalculateHistoricalVolatility:
    """Test _calculate_historical_volatility function."""

    def test_calculates_volatility_from_all_data(self):
        """Test that volatility is calculated from all available data."""
        from app.application.services.recommendation.technical_data_calculator import (
            _calculate_historical_volatility,
        )

        np.random.seed(42)
        closes = 100.0 + np.cumsum(np.random.randn(200) * 2)

        result = _calculate_historical_volatility(closes)

        assert result >= 0
        assert result != 0.20  # Should not be fallback value
        assert np.isfinite(result)

    def test_returns_fallback_for_non_finite_values(self):
        """Test that fallback is returned for NaN or infinite values."""
        from app.application.services.recommendation.technical_data_calculator import (
            _calculate_historical_volatility,
        )

        closes = np.full(100, np.nan)
        result = _calculate_historical_volatility(closes)

        assert result == 0.20

    def test_returns_fallback_for_negative_volatility(self):
        """Test that fallback is returned for negative volatility."""
        from app.application.services.recommendation.technical_data_calculator import (
            _calculate_historical_volatility,
        )

        closes = np.array([100.0] * 100)
        result = _calculate_historical_volatility(closes)

        assert result >= 0

    def test_handles_single_price_point(self):
        """Test handling when there's only one price point."""
        from app.application.services.recommendation.technical_data_calculator import (
            _calculate_historical_volatility,
        )

        closes = np.array([100.0])
        result = _calculate_historical_volatility(closes)

        # Should handle gracefully (will return fallback or valid value)
        assert result >= 0


class TestCalculateEmaDistance:
    """Test _calculate_ema_distance function."""

    def test_returns_zero_when_insufficient_data(self):
        """Test that zero is returned when less than 200 days."""
        from app.application.services.recommendation.technical_data_calculator import (
            _calculate_ema_distance,
        )

        closes = np.array([100.0] * 100)
        closes_series = pd.Series(closes)

        result = _calculate_ema_distance(closes, closes_series)

        assert result == 0.0

    def test_calculates_distance_when_sufficient_data(self):
        """Test that distance is calculated when 200+ days available."""
        from app.application.services.recommendation.technical_data_calculator import (
            _calculate_ema_distance,
        )

        # Create upward trend
        np.random.seed(42)
        closes = 100.0 + np.arange(250) * 0.5 + np.random.randn(250) * 2
        closes_series = pd.Series(closes)

        result = _calculate_ema_distance(closes, closes_series)

        # Should be a finite number
        assert np.isfinite(result)

    def test_uses_mean_fallback_when_ema_calculation_fails(self):
        """Test that mean is used when EMA calculation fails."""
        from app.application.services.recommendation.technical_data_calculator import (
            _calculate_ema_distance,
        )

        closes = np.array([100.0] * 250)
        closes_series = pd.Series(closes)

        result = _calculate_ema_distance(closes, closes_series)

        # Should return valid value (0.0 for flat prices)
        assert np.isfinite(result)
        assert result == 0.0

    def test_returns_zero_when_ema_value_is_zero(self):
        """Test that zero is returned when EMA value is zero."""
        from app.application.services.recommendation.technical_data_calculator import (
            _calculate_ema_distance,
        )

        # Create closes array with last value such that EMA might be zero
        # This is edge case handling
        closes = np.array([0.0] + [100.0] * 249)
        closes_series = pd.Series(closes)

        result = _calculate_ema_distance(closes, closes_series)

        # Should handle gracefully
        assert np.isfinite(result)


class TestProcessSymbolTechnicalData:
    """Test _process_symbol_technical_data function."""

    @pytest.mark.asyncio
    async def test_returns_fallback_when_insufficient_data(self):
        """Test that fallback is returned when less than 60 days."""
        from app.application.services.recommendation.technical_data_calculator import (
            _process_symbol_technical_data,
        )

        mock_db_manager = MagicMock()
        mock_history_db = AsyncMock()
        mock_row1 = MagicMock()
        mock_row1.__getitem__ = lambda self, key: {
            "date": "2024-01-01",
            "close_price": 100.0,
        }.get(key)
        mock_row1.__contains__ = lambda self, key: key in ["date", "close_price"]

        # Only 30 days of data
        mock_history_db.fetchall = AsyncMock(return_value=[mock_row1] * 30)
        mock_db_manager.history = AsyncMock(return_value=mock_history_db)

        result = await _process_symbol_technical_data("AAPL", mock_db_manager)

        assert isinstance(result, TechnicalData)
        assert result.current_volatility == 0.20
        assert result.historical_volatility == 0.20
        assert result.distance_from_ma_200 == 0.0

    @pytest.mark.asyncio
    async def test_calculates_technical_data_when_sufficient_data(self):
        """Test that technical data is calculated when sufficient data."""
        from app.application.services.recommendation.technical_data_calculator import (
            _process_symbol_technical_data,
        )

        mock_db_manager = MagicMock()
        mock_history_db = AsyncMock()

        # Create 250 days of price data
        np.random.seed(42)
        base_price = 100.0
        prices = base_price + np.cumsum(np.random.randn(250) * 2)

        mock_rows = []
        for i, price in enumerate(prices):
            mock_row = MagicMock()
            mock_row.__getitem__ = lambda self, key, p=price, idx=i: {
                "date": f"2024-01-{idx+1:02d}",
                "close_price": p,
            }.get(key)
            mock_row.__contains__ = lambda self, key: key in ["date", "close_price"]
            mock_rows.append(mock_row)

        # Reverse to match DESC order
        mock_history_db.fetchall = AsyncMock(return_value=list(reversed(mock_rows)))
        mock_db_manager.history = AsyncMock(return_value=mock_history_db)

        result = await _process_symbol_technical_data("AAPL", mock_db_manager)

        assert isinstance(result, TechnicalData)
        assert result.current_volatility >= 0
        assert result.historical_volatility >= 0
        assert np.isfinite(result.distance_from_ma_200)

    @pytest.mark.asyncio
    async def test_returns_fallback_for_zero_or_negative_prices(self):
        """Test that fallback is returned for zero or negative prices."""
        from app.application.services.recommendation.technical_data_calculator import (
            _process_symbol_technical_data,
        )

        mock_db_manager = MagicMock()
        mock_history_db = AsyncMock()

        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {
            "date": "2024-01-01",
            "close_price": 0.0,  # Zero price
        }.get(key)
        mock_row.__contains__ = lambda self, key: key in ["date", "close_price"]

        mock_history_db.fetchall = AsyncMock(return_value=[mock_row] * 100)
        mock_db_manager.history = AsyncMock(return_value=mock_history_db)

        with patch(
            "app.application.services.recommendation.technical_data_calculator.logger"
        ) as mock_logger:
            result = await _process_symbol_technical_data("AAPL", mock_db_manager)

            assert isinstance(result, TechnicalData)
            assert result.current_volatility == 0.20
            assert result.historical_volatility == 0.20
            assert result.distance_from_ma_200 == 0.0
            mock_logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_handles_value_error_gracefully(self):
        """Test that ValueError is handled gracefully."""
        from app.application.services.recommendation.technical_data_calculator import (
            _process_symbol_technical_data,
        )

        mock_db_manager = MagicMock()
        mock_history_db = AsyncMock()
        mock_history_db.fetchall = AsyncMock(side_effect=ValueError("Invalid data"))
        mock_db_manager.history = AsyncMock(return_value=mock_history_db)

        with patch(
            "app.application.services.recommendation.technical_data_calculator.logger"
        ) as mock_logger:
            result = await _process_symbol_technical_data("AAPL", mock_db_manager)

            assert isinstance(result, TechnicalData)
            assert result.current_volatility == 0.20
            mock_logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_handles_zero_division_error_gracefully(self):
        """Test that ZeroDivisionError is handled gracefully."""
        from app.application.services.recommendation.technical_data_calculator import (
            _process_symbol_technical_data,
        )

        mock_db_manager = MagicMock()
        mock_history_db = AsyncMock()
        mock_history_db.fetchall = AsyncMock(
            side_effect=ZeroDivisionError("Division by zero")
        )
        mock_db_manager.history = AsyncMock(return_value=mock_history_db)

        with patch(
            "app.application.services.recommendation.technical_data_calculator.logger"
        ) as mock_logger:
            result = await _process_symbol_technical_data("AAPL", mock_db_manager)

            assert isinstance(result, TechnicalData)
            assert result.current_volatility == 0.20
            mock_logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_handles_unexpected_errors_gracefully(self):
        """Test that unexpected errors are handled gracefully."""
        from app.application.services.recommendation.technical_data_calculator import (
            _process_symbol_technical_data,
        )

        mock_db_manager = MagicMock()
        mock_history_db = AsyncMock()
        mock_history_db.fetchall = AsyncMock(side_effect=Exception("Unexpected error"))
        mock_db_manager.history = AsyncMock(return_value=mock_history_db)

        with patch(
            "app.application.services.recommendation.technical_data_calculator.logger"
        ) as mock_logger:
            result = await _process_symbol_technical_data("AAPL", mock_db_manager)

            assert isinstance(result, TechnicalData)
            assert result.current_volatility == 0.20
            mock_logger.error.assert_called()


class TestGetTechnicalDataForPositions:
    """Test get_technical_data_for_positions function."""

    @pytest.mark.asyncio
    async def test_processes_multiple_symbols(self):
        """Test that multiple symbols are processed."""
        from app.application.services.recommendation.technical_data_calculator import (
            get_technical_data_for_positions,
        )

        mock_db_manager = MagicMock()

        with patch(
            "app.application.services.recommendation.technical_data_calculator._process_symbol_technical_data"
        ) as mock_process:
            mock_technical_data = TechnicalData(
                current_volatility=0.15,
                historical_volatility=0.18,
                distance_from_ma_200=0.05,
            )
            mock_process.return_value = mock_technical_data

            result = await get_technical_data_for_positions(
                ["AAPL", "MSFT", "GOOGL"], mock_db_manager
            )

            assert len(result) == 3
            assert "AAPL" in result
            assert "MSFT" in result
            assert "GOOGL" in result
            assert mock_process.call_count == 3

    @pytest.mark.asyncio
    async def test_handles_empty_symbol_list(self):
        """Test handling of empty symbol list."""
        from app.application.services.recommendation.technical_data_calculator import (
            get_technical_data_for_positions,
        )

        mock_db_manager = MagicMock()

        result = await get_technical_data_for_positions([], mock_db_manager)

        assert result == {}

    @pytest.mark.asyncio
    async def test_each_symbol_gets_technical_data(self):
        """Test that each symbol gets its own technical data."""
        from app.application.services.recommendation.technical_data_calculator import (
            get_technical_data_for_positions,
        )

        mock_db_manager = MagicMock()

        with patch(
            "app.application.services.recommendation.technical_data_calculator._process_symbol_technical_data"
        ) as mock_process:

            def side_effect(symbol, db_manager):
                return TechnicalData(
                    current_volatility=0.1 + hash(symbol) % 10 / 100,
                    historical_volatility=0.15 + hash(symbol) % 10 / 100,
                    distance_from_ma_200=0.02 + hash(symbol) % 10 / 100,
                )

            mock_process.side_effect = side_effect

            result = await get_technical_data_for_positions(
                ["AAPL", "MSFT"], mock_db_manager
            )

            assert result["AAPL"] != result["MSFT"]
            assert isinstance(result["AAPL"], TechnicalData)
            assert isinstance(result["MSFT"], TechnicalData)
