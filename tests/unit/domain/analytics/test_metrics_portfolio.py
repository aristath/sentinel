"""Tests for portfolio metrics calculation.

These tests validate comprehensive portfolio performance metrics calculation
using empyrical library.
"""

import numpy as np
import pandas as pd
import pytest


class TestGetPortfolioMetrics:
    """Test get_portfolio_metrics function."""

    @pytest.mark.asyncio
    async def test_calculates_metrics_for_valid_returns(self):
        """Test that metrics are calculated for valid returns."""
        from app.modules.analytics.domain.metrics.portfolio import get_portfolio_metrics

        # Create a simple returns series (1% daily return)
        returns = pd.Series(
            [0.01] * 252, index=pd.date_range("2024-01-01", periods=252, freq="D")
        )

        metrics = await get_portfolio_metrics(returns)

        assert "annual_return" in metrics
        assert "volatility" in metrics
        assert "sharpe_ratio" in metrics
        assert "sortino_ratio" in metrics
        assert "calmar_ratio" in metrics
        assert "max_drawdown" in metrics
        assert isinstance(metrics["annual_return"], float)
        assert isinstance(metrics["volatility"], float)

    @pytest.mark.asyncio
    async def test_returns_zero_metrics_for_empty_returns(self):
        """Test that zero metrics are returned for empty returns."""
        from app.modules.analytics.domain.metrics.portfolio import get_portfolio_metrics

        returns = pd.Series([], dtype=float)

        metrics = await get_portfolio_metrics(returns)

        assert metrics["annual_return"] == 0.0
        assert metrics["volatility"] == 0.0
        assert metrics["sharpe_ratio"] == 0.0
        assert metrics["sortino_ratio"] == 0.0
        assert metrics["calmar_ratio"] == 0.0
        assert metrics["max_drawdown"] == 0.0

    @pytest.mark.asyncio
    async def test_returns_zero_metrics_for_single_value(self):
        """Test that zero metrics are returned for single value (insufficient data)."""
        from app.modules.analytics.domain.metrics.portfolio import get_portfolio_metrics

        returns = pd.Series(
            [0.01], index=pd.date_range("2024-01-01", periods=1, freq="D")
        )

        metrics = await get_portfolio_metrics(returns)

        assert metrics["annual_return"] == 0.0
        assert metrics["volatility"] == 0.0
        assert metrics["sharpe_ratio"] == 0.0
        assert metrics["sortino_ratio"] == 0.0
        assert metrics["calmar_ratio"] == 0.0
        assert metrics["max_drawdown"] == 0.0

    @pytest.mark.asyncio
    async def test_handles_negative_returns(self):
        """Test handling of negative returns."""
        from app.modules.analytics.domain.metrics.portfolio import get_portfolio_metrics

        # Negative returns (declining portfolio)
        returns = pd.Series(
            [-0.01] * 100, index=pd.date_range("2024-01-01", periods=100, freq="D")
        )

        metrics = await get_portfolio_metrics(returns)

        assert metrics["annual_return"] < 0.0
        assert metrics["volatility"] > 0.0
        assert metrics["max_drawdown"] < 0.0

    @pytest.mark.asyncio
    async def test_handles_risk_free_rate(self):
        """Test that risk-free rate is used in Sharpe/Sortino calculations."""
        from app.modules.analytics.domain.metrics.portfolio import get_portfolio_metrics

        returns = pd.Series(
            [0.01] * 100, index=pd.date_range("2024-01-01", periods=100, freq="D")
        )

        metrics_with_rf = await get_portfolio_metrics(returns, risk_free_rate=0.02)
        metrics_without_rf = await get_portfolio_metrics(returns, risk_free_rate=0.0)

        # Sharpe ratio should be different when risk-free rate is included
        assert metrics_with_rf["sharpe_ratio"] != metrics_without_rf["sharpe_ratio"]
        assert metrics_with_rf["sortino_ratio"] != metrics_without_rf["sortino_ratio"]

    @pytest.mark.asyncio
    async def test_handles_benchmark(self):
        """Test that benchmark parameter is accepted (even if not fully used)."""
        from app.modules.analytics.domain.metrics.portfolio import get_portfolio_metrics

        returns = pd.Series(
            [0.01] * 100, index=pd.date_range("2024-01-01", periods=100, freq="D")
        )
        benchmark = pd.Series(
            [0.005] * 100, index=pd.date_range("2024-01-01", periods=100, freq="D")
        )

        # Should not raise error
        metrics = await get_portfolio_metrics(returns, benchmark=benchmark)

        assert metrics["annual_return"] is not None

    @pytest.mark.asyncio
    async def test_handles_infinite_values_gracefully(self):
        """Test that infinite values are converted to 0.0."""
        from app.modules.analytics.domain.metrics.portfolio import get_portfolio_metrics

        # Create returns that might produce infinite values
        returns = pd.Series(
            [0.0] * 100, index=pd.date_range("2024-01-01", periods=100, freq="D")
        )

        metrics = await get_portfolio_metrics(returns)

        # All metrics should be finite
        assert np.isfinite(metrics["annual_return"])
        assert np.isfinite(metrics["volatility"])
        assert np.isfinite(metrics["sharpe_ratio"])
        assert np.isfinite(metrics["sortino_ratio"])
        assert np.isfinite(metrics["calmar_ratio"])
        assert np.isfinite(metrics["max_drawdown"])

    @pytest.mark.asyncio
    async def test_handles_nan_values_gracefully(self):
        """Test that NaN values are handled gracefully."""
        from app.modules.analytics.domain.metrics.portfolio import get_portfolio_metrics

        # Returns with some NaN values
        returns = pd.Series(
            [0.01, np.nan, 0.02, 0.01, 0.015],
            index=pd.date_range("2024-01-01", periods=5, freq="D"),
        )

        # Should not raise error, empyrical should handle NaN
        metrics = await get_portfolio_metrics(returns)

        assert all(
            key in metrics for key in ["annual_return", "volatility", "sharpe_ratio"]
        )

    @pytest.mark.asyncio
    async def test_calmar_ratio_handles_zero_drawdown(self):
        """Test that Calmar ratio handles zero drawdown correctly."""
        from app.modules.analytics.domain.metrics.portfolio import get_portfolio_metrics

        # Returns with no drawdown (always positive)
        returns = pd.Series(
            [0.01] * 100, index=pd.date_range("2024-01-01", periods=100, freq="D")
        )

        metrics = await get_portfolio_metrics(returns)

        # If max_drawdown is 0, calmar_ratio should be 0.0 (not division by zero)
        if metrics["max_drawdown"] == 0.0:
            assert metrics["calmar_ratio"] == 0.0
        else:
            # Otherwise it should be finite
            assert np.isfinite(metrics["calmar_ratio"])

    @pytest.mark.asyncio
    async def test_error_handling_returns_zero_metrics(self):
        """Test that exceptions during calculation return zero metrics."""
        from unittest.mock import patch

        from app.modules.analytics.domain.metrics.portfolio import get_portfolio_metrics

        returns = pd.Series(
            [0.01] * 100, index=pd.date_range("2024-01-01", periods=100, freq="D")
        )

        # Mock empyrical to raise an exception
        with patch("empyrical.annual_return", side_effect=Exception("Test error")):
            with patch(
                "app.modules.analytics.domain.metrics.portfolio.logger"
            ) as mock_logger:
                metrics = await get_portfolio_metrics(returns)

                # Should return zero metrics
                assert metrics["annual_return"] == 0.0
                assert metrics["volatility"] == 0.0
                assert metrics["sharpe_ratio"] == 0.0
                # Error should be logged
                mock_logger.error.assert_called_once()
