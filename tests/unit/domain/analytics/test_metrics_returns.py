"""Tests for portfolio returns calculation.

These tests validate the calculation of daily returns from portfolio values.
"""

import pandas as pd
import pytest


class TestCalculatePortfolioReturns:
    """Test calculate_portfolio_returns function."""

    def test_calculates_daily_returns(self):
        """Test that daily returns are calculated correctly."""
        from app.modules.analytics.domain.metrics.returns import (
            calculate_portfolio_returns,
        )

        # Portfolio values: 100, 105, 110, 100
        values = pd.Series(
            [100.0, 105.0, 110.0, 100.0],
            index=pd.date_range("2024-01-01", periods=4, freq="D"),
        )

        returns = calculate_portfolio_returns(values)

        # First value is NaN (no previous value), so dropna() removes it
        # Day 2: (105 - 100) / 100 = 0.05
        # Day 3: (110 - 105) / 105 = 0.047619...
        # Day 4: (100 - 110) / 110 = -0.090909...
        assert len(returns) == 3
        assert returns.iloc[0] == pytest.approx(0.05, rel=1e-5)
        assert returns.iloc[1] == pytest.approx(0.047619, rel=1e-3)
        assert returns.iloc[2] == pytest.approx(-0.090909, rel=1e-3)

    def test_handles_single_value(self):
        """Test that single value returns empty series."""
        from app.modules.analytics.domain.metrics.returns import (
            calculate_portfolio_returns,
        )

        values = pd.Series(
            [100.0], index=pd.date_range("2024-01-01", periods=1, freq="D")
        )

        returns = calculate_portfolio_returns(values)

        assert len(returns) == 0
        assert returns.empty

    def test_handles_empty_series(self):
        """Test that empty series returns empty series."""
        from app.modules.analytics.domain.metrics.returns import (
            calculate_portfolio_returns,
        )

        values = pd.Series([], dtype=float)

        returns = calculate_portfolio_returns(values)

        assert returns.empty

    def test_handles_zero_initial_value(self):
        """Test handling of zero initial value."""
        from app.modules.analytics.domain.metrics.returns import (
            calculate_portfolio_returns,
        )

        values = pd.Series(
            [0.0, 100.0, 105.0],
            index=pd.date_range("2024-01-01", periods=3, freq="D"),
        )

        returns = calculate_portfolio_returns(values)

        # First return: (100 - 0) / 0 = inf, which gets dropped
        # Should handle gracefully
        assert len(returns) >= 1

    def test_preserves_datetime_index(self):
        """Test that datetime index is preserved."""
        from app.modules.analytics.domain.metrics.returns import (
            calculate_portfolio_returns,
        )

        values = pd.Series(
            [100.0, 105.0, 110.0],
            index=pd.date_range("2024-01-01", periods=3, freq="D"),
        )

        returns = calculate_portfolio_returns(values)

        assert isinstance(returns.index, pd.DatetimeIndex)
        assert len(returns.index) == 2

    def test_handles_string_index_and_converts_to_datetime(self):
        """Test that string index is converted to datetime."""
        from app.modules.analytics.domain.metrics.returns import (
            calculate_portfolio_returns,
        )

        values = pd.Series(
            [100.0, 105.0, 110.0], index=["2024-01-01", "2024-01-02", "2024-01-03"]
        )

        returns = calculate_portfolio_returns(values)

        assert isinstance(returns.index, pd.DatetimeIndex)
        assert len(returns.index) == 2

    def test_handles_negative_values(self):
        """Test handling of negative portfolio values."""
        from app.modules.analytics.domain.metrics.returns import (
            calculate_portfolio_returns,
        )

        values = pd.Series(
            [100.0, -50.0, -25.0],
            index=pd.date_range("2024-01-01", periods=3, freq="D"),
        )

        returns = calculate_portfolio_returns(values)

        # Day 2: (-50 - 100) / 100 = -1.5 (150% loss)
        # Day 3: (-25 - (-50)) / (-50) = 0.5 (50% gain, but still negative)
        assert len(returns) == 2
        assert returns.iloc[0] == pytest.approx(-1.5, rel=1e-5)

    def test_handles_constant_values(self):
        """Test handling of constant portfolio values (zero returns)."""
        from app.modules.analytics.domain.metrics.returns import (
            calculate_portfolio_returns,
        )

        values = pd.Series(
            [100.0, 100.0, 100.0, 100.0],
            index=pd.date_range("2024-01-01", periods=4, freq="D"),
        )

        returns = calculate_portfolio_returns(values)

        # All returns should be zero
        assert len(returns) == 3
        assert (returns == 0.0).all()
