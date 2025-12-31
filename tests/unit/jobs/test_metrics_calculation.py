"""Tests for metrics calculation job.

These tests validate the batch calculation of technical indicators,
CAGR, momentum, and other metrics for stocks.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest


class TestCalculateTechnicalIndicators:
    """Test technical indicator calculation."""

    @pytest.mark.asyncio
    async def test_counts_all_calculated_metrics(self):
        """Test that all successfully calculated metrics are counted."""
        from app.jobs.metrics_calculation import _calculate_technical_indicators

        closes = np.array([100.0] * 100)
        highs = np.array([105.0] * 100)
        lows = np.array([95.0] * 100)

        with patch("app.jobs.metrics_calculation.get_rsi", return_value=50.0):
            with patch("app.jobs.metrics_calculation.get_ema", return_value=100.0):
                with patch(
                    "app.jobs.metrics_calculation.get_bollinger_bands",
                    return_value=(95, 100, 105),
                ):
                    with patch(
                        "app.jobs.metrics_calculation.get_sharpe_ratio",
                        return_value=1.5,
                    ):
                        with patch(
                            "app.jobs.metrics_calculation.get_max_drawdown",
                            return_value=-0.15,
                        ):
                            with patch(
                                "app.jobs.metrics_calculation.get_52_week_high",
                                return_value=110.0,
                            ):
                                with patch(
                                    "app.jobs.metrics_calculation.get_52_week_low",
                                    return_value=90.0,
                                ):
                                    count, ema_200, high_52w, bands = (
                                        await _calculate_technical_indicators(
                                            "TEST.US", closes, highs, lows
                                        )
                                    )

        # RSI + 2 EMAs + 3 bollinger + sharpe + drawdown + 52w high + 52w low = 11
        assert count >= 5  # At least some metrics calculated
        assert ema_200 == 100.0
        assert high_52w == 110.0
        assert bands == (95, 100, 105)

    @pytest.mark.asyncio
    async def test_handles_none_values_gracefully(self):
        """Test that None metrics don't crash calculation."""
        from app.jobs.metrics_calculation import _calculate_technical_indicators

        closes = np.array([100.0] * 100)
        highs = np.array([105.0] * 100)
        lows = np.array([95.0] * 100)

        with patch("app.jobs.metrics_calculation.get_rsi", return_value=None):
            with patch("app.jobs.metrics_calculation.get_ema", return_value=None):
                with patch(
                    "app.jobs.metrics_calculation.get_bollinger_bands",
                    return_value=None,
                ):
                    with patch(
                        "app.jobs.metrics_calculation.get_sharpe_ratio",
                        return_value=None,
                    ):
                        with patch(
                            "app.jobs.metrics_calculation.get_max_drawdown",
                            return_value=None,
                        ):
                            with patch(
                                "app.jobs.metrics_calculation.get_52_week_high",
                                return_value=None,
                            ):
                                with patch(
                                    "app.jobs.metrics_calculation.get_52_week_low",
                                    return_value=None,
                                ):
                                    count, ema_200, high_52w, bands = (
                                        await _calculate_technical_indicators(
                                            "TEST.US", closes, highs, lows
                                        )
                                    )

        assert count == 0
        assert ema_200 is None
        assert high_52w is None
        assert bands is None


class TestCalculateCagrMetrics:
    """Test CAGR metrics calculation."""

    @pytest.mark.asyncio
    async def test_returns_zero_for_insufficient_data(self):
        """Test that empty or short monthly data returns 0."""
        from app.jobs.metrics_calculation import _calculate_cagr_metrics

        mock_repo = AsyncMock()

        count = await _calculate_cagr_metrics(mock_repo, "TEST.US", [])
        assert count == 0

        # Less than 12 months
        short_data = [MagicMock(year_month="2024-01", avg_adj_close=100.0)] * 6
        count = await _calculate_cagr_metrics(mock_repo, "TEST.US", short_data)
        assert count == 0

    @pytest.mark.asyncio
    async def test_calculates_5y_cagr(self):
        """Test 5-year CAGR calculation."""
        from app.jobs.metrics_calculation import _calculate_cagr_metrics

        mock_repo = AsyncMock()

        # Create 60 months of data
        monthly_data = []
        for i in range(60):
            mock_price = MagicMock()
            mock_price.year_month = f"2020-{(i % 12) + 1:02d}"
            mock_price.avg_adj_close = 100.0 * (1.0 + i * 0.01)  # Growing prices
            monthly_data.append(mock_price)

        with patch("app.jobs.metrics_calculation.calculate_cagr", return_value=0.10):
            count = await _calculate_cagr_metrics(mock_repo, "TEST.US", monthly_data)

        assert count >= 1
        mock_repo.set_metric.assert_called()


class TestCalculateMomentumMetrics:
    """Test momentum metrics calculation."""

    @pytest.mark.asyncio
    async def test_returns_zero_for_short_data(self):
        """Test that short price data returns 0 metrics."""
        from app.jobs.metrics_calculation import _calculate_momentum_metrics

        mock_repo = AsyncMock()
        closes = [100.0] * 10  # Only 10 days

        count = await _calculate_momentum_metrics(mock_repo, "TEST.US", closes)
        assert count == 0

    @pytest.mark.asyncio
    async def test_calculates_30d_momentum(self):
        """Test 30-day momentum calculation."""
        from app.jobs.metrics_calculation import _calculate_momentum_metrics

        mock_repo = AsyncMock()
        # 30 days from 100 to 110 = 10% momentum
        closes = [100.0] * 29 + [110.0]

        count = await _calculate_momentum_metrics(mock_repo, "TEST.US", closes)

        assert count >= 1
        # Verify set_metric was called with MOMENTUM_30D
        calls = mock_repo.set_metric.call_args_list
        assert any("MOMENTUM_30D" in str(call) for call in calls)

    @pytest.mark.asyncio
    async def test_calculates_90d_momentum_if_enough_data(self):
        """Test 90-day momentum calculation with sufficient data."""
        from app.jobs.metrics_calculation import _calculate_momentum_metrics

        mock_repo = AsyncMock()
        closes = [100.0] * 89 + [115.0]  # 90 days of data

        count = await _calculate_momentum_metrics(mock_repo, "TEST.US", closes)

        assert count == 2  # Both 30d and 90d
        calls = mock_repo.set_metric.call_args_list
        assert any("MOMENTUM_90D" in str(call) for call in calls)


class TestCalculateDistanceMetrics:
    """Test distance metrics calculation."""

    @pytest.mark.asyncio
    async def test_calculates_distance_from_52w_high(self):
        """Test distance from 52-week high calculation."""
        from app.jobs.metrics_calculation import _calculate_distance_metrics

        mock_repo = AsyncMock()
        closes = [100.0]  # Current price
        high_52w = 120.0  # 20% above current

        count = await _calculate_distance_metrics(
            mock_repo, "TEST.US", closes, None, high_52w
        )

        assert count == 1
        calls = mock_repo.set_metric.call_args_list
        # Distance should be (120 - 100) / 120 = 0.167
        assert any("DISTANCE_FROM_52W_HIGH" in str(call) for call in calls)

    @pytest.mark.asyncio
    async def test_calculates_distance_from_ema(self):
        """Test distance from EMA 200 calculation."""
        from app.jobs.metrics_calculation import _calculate_distance_metrics

        mock_repo = AsyncMock()
        closes = [100.0]  # Current price
        ema_200 = 95.0  # Below current (bullish)

        count = await _calculate_distance_metrics(
            mock_repo, "TEST.US", closes, ema_200, None
        )

        assert count == 1
        calls = mock_repo.set_metric.call_args_list
        # Distance should be (100 - 95) / 95 = 0.053
        assert any("DISTANCE_FROM_EMA_200" in str(call) for call in calls)

    @pytest.mark.asyncio
    async def test_calculates_both_metrics(self):
        """Test both distance metrics calculated when data available."""
        from app.jobs.metrics_calculation import _calculate_distance_metrics

        mock_repo = AsyncMock()
        closes = [100.0]

        count = await _calculate_distance_metrics(
            mock_repo, "TEST.US", closes, 95.0, 110.0
        )

        assert count == 2


class TestCalculateBollingerPosition:
    """Test Bollinger Band position calculation."""

    @pytest.mark.asyncio
    async def test_returns_zero_for_no_bands(self):
        """Test that missing bands returns 0."""
        from app.jobs.metrics_calculation import _calculate_bollinger_position

        mock_repo = AsyncMock()

        count = await _calculate_bollinger_position(mock_repo, "TEST.US", [100.0], None)
        assert count == 0

    @pytest.mark.asyncio
    async def test_calculates_position_in_band(self):
        """Test position calculation within Bollinger bands."""
        from app.jobs.metrics_calculation import _calculate_bollinger_position

        mock_repo = AsyncMock()
        closes = [100.0]  # Middle of bands
        bands = (90.0, 100.0, 110.0)  # Lower, middle, upper

        count = await _calculate_bollinger_position(mock_repo, "TEST.US", closes, bands)

        assert count == 1
        # Position should be (100 - 90) / (110 - 90) = 0.5
        mock_repo.set_metric.assert_called_once()
        call_args = mock_repo.set_metric.call_args
        assert call_args[0][0] == "TEST.US"
        assert call_args[0][1] == "BB_POSITION"
        assert 0.45 <= call_args[0][2] <= 0.55  # Approximately 0.5

    @pytest.mark.asyncio
    async def test_clamps_position_to_0_1(self):
        """Test that position is clamped to [0, 1] range."""
        from app.jobs.metrics_calculation import _calculate_bollinger_position

        mock_repo = AsyncMock()
        closes = [120.0]  # Above upper band
        bands = (90.0, 100.0, 110.0)

        count = await _calculate_bollinger_position(mock_repo, "TEST.US", closes, bands)

        assert count == 1
        call_args = mock_repo.set_metric.call_args
        assert call_args[0][2] == 1.0  # Clamped to max


class TestCalculateAllMetricsForSymbol:
    """Test full metric calculation for a symbol."""

    @pytest.mark.asyncio
    async def test_returns_zero_for_insufficient_data(self):
        """Test that insufficient price data returns 0."""
        from app.jobs.metrics_calculation import calculate_all_metrics_for_symbol

        mock_history_repo = AsyncMock()
        mock_history_repo.get_daily_prices.return_value = []

        with patch("app.jobs.metrics_calculation.CalculationsRepository"):
            with patch(
                "app.jobs.metrics_calculation.HistoryRepository",
                return_value=mock_history_repo,
            ):
                count = await calculate_all_metrics_for_symbol("TEST.US")

        assert count == 0

    @pytest.mark.asyncio
    async def test_handles_exceptions_gracefully(self):
        """Test that exceptions don't crash the calculation."""
        from app.jobs.metrics_calculation import calculate_all_metrics_for_symbol

        mock_history_repo = AsyncMock()
        mock_history_repo.get_daily_prices.side_effect = Exception("Database error")

        with patch("app.jobs.metrics_calculation.CalculationsRepository"):
            with patch(
                "app.jobs.metrics_calculation.HistoryRepository",
                return_value=mock_history_repo,
            ):
                count = await calculate_all_metrics_for_symbol("TEST.US")

        assert count == 0  # Should return 0 on error


class TestCalculateMetricsForAllStocks:
    """Test batch metrics calculation."""

    @pytest.mark.asyncio
    async def test_processes_all_active_stocks(self):
        """Test that all active stocks are processed."""
        from app.jobs.metrics_calculation import calculate_metrics_for_all_stocks

        mock_stock_repo = AsyncMock()
        mock_stock1 = MagicMock()
        mock_stock1.symbol = "AAPL.US"
        mock_stock2 = MagicMock()
        mock_stock2.symbol = "MSFT.US"
        mock_stock_repo.get_all_active.return_value = [mock_stock1, mock_stock2]

        with patch(
            "app.jobs.metrics_calculation.SecurityRepository",
            return_value=mock_stock_repo,
        ):
            with patch(
                "app.jobs.metrics_calculation.calculate_all_metrics_for_symbol",
                new_callable=AsyncMock,
                return_value=10,
            ) as mock_calc:
                stats = await calculate_metrics_for_all_stocks()

        assert stats["processed"] == 2
        assert stats["total_metrics"] == 20
        assert stats["errors"] == 0
        assert mock_calc.call_count == 2

    @pytest.mark.asyncio
    async def test_counts_errors(self):
        """Test that errors are tracked in statistics."""
        from app.jobs.metrics_calculation import calculate_metrics_for_all_stocks

        mock_stock_repo = AsyncMock()
        mock_stock = MagicMock()
        mock_stock.symbol = "FAIL.US"
        mock_stock_repo.get_all_active.return_value = [mock_stock]

        with patch(
            "app.jobs.metrics_calculation.SecurityRepository",
            return_value=mock_stock_repo,
        ):
            with patch(
                "app.jobs.metrics_calculation.calculate_all_metrics_for_symbol",
                new_callable=AsyncMock,
                side_effect=Exception("Test error"),
            ):
                stats = await calculate_metrics_for_all_stocks()

        assert stats["errors"] == 1
        assert stats["processed"] == 0

    @pytest.mark.asyncio
    async def test_returns_empty_stats_for_no_stocks(self):
        """Test empty statistics when no active stocks."""
        from app.jobs.metrics_calculation import calculate_metrics_for_all_stocks

        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_all_active.return_value = []

        with patch(
            "app.jobs.metrics_calculation.SecurityRepository",
            return_value=mock_stock_repo,
        ):
            stats = await calculate_metrics_for_all_stocks()

        assert stats["processed"] == 0
        assert stats["total_metrics"] == 0
        assert stats["errors"] == 0
