"""Tests for PortfolioOptimizer service.

These tests are CRITICAL for the retirement fund as they verify
the portfolio weight calculation and optimization logic.
"""

from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pandas as pd
import pytest

from app.application.services.optimization.portfolio_optimizer import (
    PortfolioOptimizer,
)
from app.domain.models import Position, Stock


def create_optimizer() -> PortfolioOptimizer:
    """Create optimizer with mocked dependencies."""
    mock_returns = AsyncMock()
    mock_risk = AsyncMock()
    mock_constraints = MagicMock()
    return PortfolioOptimizer(
        expected_returns_calc=mock_returns,
        risk_model_builder=mock_risk,
        constraints_manager=mock_constraints,
    )


class TestPortfolioOptimizerWeightBlending:
    """Test the weight blending logic (MV + HRP)."""

    def test_blend_weights_pure_mv_when_blend_is_zero(self):
        """Test that blend=0.0 gives pure Mean-Variance weights."""
        optimizer = create_optimizer()
        mv_weights = {"AAPL": 0.4, "GOOGL": 0.3, "MSFT": 0.3}
        hrp_weights = {"AAPL": 0.2, "GOOGL": 0.4, "MSFT": 0.4}

        result = optimizer._blend_weights(mv_weights, hrp_weights, blend=0.0)

        assert result["AAPL"] == pytest.approx(0.4, rel=1e-6)
        assert result["GOOGL"] == pytest.approx(0.3, rel=1e-6)
        assert result["MSFT"] == pytest.approx(0.3, rel=1e-6)

    def test_blend_weights_pure_hrp_when_blend_is_one(self):
        """Test that blend=1.0 gives pure HRP weights."""
        optimizer = create_optimizer()
        mv_weights = {"AAPL": 0.4, "GOOGL": 0.3, "MSFT": 0.3}
        hrp_weights = {"AAPL": 0.2, "GOOGL": 0.4, "MSFT": 0.4}

        result = optimizer._blend_weights(mv_weights, hrp_weights, blend=1.0)

        assert result["AAPL"] == pytest.approx(0.2, rel=1e-6)
        assert result["GOOGL"] == pytest.approx(0.4, rel=1e-6)
        assert result["MSFT"] == pytest.approx(0.4, rel=1e-6)

    def test_blend_weights_fifty_fifty(self):
        """Test that blend=0.5 averages the weights."""
        optimizer = create_optimizer()
        mv_weights = {"AAPL": 0.4, "GOOGL": 0.2}
        hrp_weights = {"AAPL": 0.2, "GOOGL": 0.4}

        result = optimizer._blend_weights(mv_weights, hrp_weights, blend=0.5)

        assert result["AAPL"] == pytest.approx(0.3, rel=1e-6)
        assert result["GOOGL"] == pytest.approx(0.3, rel=1e-6)

    def test_blend_weights_handles_different_symbol_sets(self):
        """Test blending when MV and HRP have different symbols."""
        optimizer = create_optimizer()
        mv_weights = {"AAPL": 0.5, "GOOGL": 0.5}
        hrp_weights = {"GOOGL": 0.4, "MSFT": 0.6}

        result = optimizer._blend_weights(mv_weights, hrp_weights, blend=0.5)

        # AAPL: only in MV, so 0.5 * (1-0.5) = 0.25
        assert result["AAPL"] == pytest.approx(0.25, rel=1e-6)
        # GOOGL: in both, so 0.5*0.5 + 0.5*0.4 = 0.45
        assert result["GOOGL"] == pytest.approx(0.45, rel=1e-6)
        # MSFT: only in HRP, so 0.5 * 0.6 = 0.3
        assert result["MSFT"] == pytest.approx(0.3, rel=1e-6)


class TestPortfolioOptimizerWeightNormalization:
    """Test weight normalization logic."""

    def test_normalize_weights_to_one(self):
        """Test normalizing weights to sum to 1.0."""
        optimizer = create_optimizer()
        weights = {"AAPL": 0.2, "GOOGL": 0.3, "MSFT": 0.1}  # Sum = 0.6

        result = optimizer._normalize_weights(weights, target_sum=1.0)

        assert sum(result.values()) == pytest.approx(1.0, rel=1e-6)
        # Proportions should be preserved
        assert result["GOOGL"] / result["AAPL"] == pytest.approx(1.5, rel=1e-6)

    def test_normalize_weights_to_target_sum(self):
        """Test normalizing weights to a custom sum (for cash reserve)."""
        optimizer = create_optimizer()
        weights = {"AAPL": 0.5, "GOOGL": 0.5}  # Sum = 1.0

        # Reserve 10% cash, so target is 0.9
        result = optimizer._normalize_weights(weights, target_sum=0.9)

        assert sum(result.values()) == pytest.approx(0.9, rel=1e-6)

    def test_normalize_weights_handles_zero_sum(self):
        """Test that zero-sum weights don't cause division by zero."""
        optimizer = create_optimizer()
        weights = {"AAPL": 0.0, "GOOGL": 0.0}

        result = optimizer._normalize_weights(weights, target_sum=1.0)

        # Should return unchanged (can't normalize zero-sum)
        assert result == weights


class TestPortfolioOptimizerWeightChanges:
    """Test weight change calculation logic."""

    def test_calculate_weight_changes_basic(self):
        """Test basic weight change calculation."""
        optimizer = create_optimizer()
        target_weights = {"AAPL": 0.30, "GOOGL": 0.20}

        # Current position: AAPL is 20%, GOOGL is 30%
        positions = {
            "AAPL": MagicMock(spec=Position, market_value_eur=2000),
            "GOOGL": MagicMock(spec=Position, market_value_eur=3000),
        }
        portfolio_value = 10000

        changes = optimizer._calculate_weight_changes(
            target_weights, positions, portfolio_value
        )

        # Sort by symbol for predictable testing
        changes_dict = {c.symbol: c for c in changes}

        # AAPL: target 30%, current 20% = +10% change
        assert changes_dict["AAPL"].change == pytest.approx(0.10, abs=0.001)
        # GOOGL: target 20%, current 30% = -10% change
        assert changes_dict["GOOGL"].change == pytest.approx(-0.10, abs=0.001)

    def test_calculate_weight_changes_new_position(self):
        """Test weight change for a new position (not currently held)."""
        optimizer = create_optimizer()
        target_weights = {"AAPL": 0.20, "NEWSTOCK": 0.10}
        positions = {"AAPL": MagicMock(spec=Position, market_value_eur=2000)}
        portfolio_value = 10000

        changes = optimizer._calculate_weight_changes(
            target_weights, positions, portfolio_value
        )

        changes_dict = {c.symbol: c for c in changes}

        # NEWSTOCK: target 10%, current 0% = +10% change
        assert "NEWSTOCK" in changes_dict
        assert changes_dict["NEWSTOCK"].change == pytest.approx(0.10, abs=0.001)
        assert changes_dict["NEWSTOCK"].current_weight == 0.0

    def test_calculate_weight_changes_position_to_close(self):
        """Test weight change for a position that should be closed."""
        optimizer = create_optimizer()
        target_weights = {"AAPL": 0.30}  # GOOGL not in target (should close)
        positions = {
            "AAPL": MagicMock(spec=Position, market_value_eur=2000),
            "GOOGL": MagicMock(spec=Position, market_value_eur=3000),
        }
        portfolio_value = 10000

        changes = optimizer._calculate_weight_changes(
            target_weights, positions, portfolio_value
        )

        changes_dict = {c.symbol: c for c in changes}

        # GOOGL: not in target, current 30% = -30% change (close position)
        assert "GOOGL" in changes_dict
        assert changes_dict["GOOGL"].change == pytest.approx(-0.30, abs=0.001)
        assert changes_dict["GOOGL"].target_weight == 0.0

    def test_calculate_weight_changes_ignores_tiny_changes(self):
        """Test that very small changes (< 0.1%) are ignored."""
        optimizer = create_optimizer()
        target_weights = {"AAPL": 0.2005}  # Nearly exactly matches current
        positions = {"AAPL": MagicMock(spec=Position, market_value_eur=2000)}
        portfolio_value = 10000  # Current: 20%

        changes = optimizer._calculate_weight_changes(
            target_weights, positions, portfolio_value
        )

        # Change of 0.05% should be ignored
        assert len(changes) == 0


class TestPortfolioOptimizerErrorHandling:
    """Test error handling in the optimizer."""

    @pytest.mark.asyncio
    async def test_optimize_returns_error_when_no_stocks(self):
        """Test that optimization fails gracefully with no stocks."""
        optimizer = create_optimizer()

        result = await optimizer.optimize(
            stocks=[],
            positions={},
            portfolio_value=10000,
            current_prices={},
            cash_balance=1000,
        )

        assert result.success is False
        assert result.error == "No active stocks"
        assert result.target_weights == {}

    @pytest.mark.asyncio
    async def test_optimize_returns_error_when_no_expected_returns(self):
        """Test failure when expected returns calculation fails."""
        mock_returns_calc = AsyncMock()
        mock_returns_calc.calculate_expected_returns.return_value = {}

        optimizer = PortfolioOptimizer(expected_returns_calc=mock_returns_calc)

        stocks = [MagicMock(spec=Stock, symbol="AAPL", active=True)]

        result = await optimizer.optimize(
            stocks=stocks,
            positions={},
            portfolio_value=10000,
            current_prices={"AAPL": 150.0},
            cash_balance=1000,
        )

        assert result.success is False
        assert result.error == "No expected returns data"

    @pytest.mark.asyncio
    async def test_optimize_returns_error_when_insufficient_history(self):
        """Test failure when there's insufficient price history."""
        mock_returns_calc = AsyncMock()
        mock_returns_calc.calculate_expected_returns.return_value = {"AAPL": 0.11}

        mock_risk_builder = AsyncMock()
        mock_risk_builder.build_covariance_matrix.return_value = (None, pd.DataFrame())

        optimizer = PortfolioOptimizer(
            expected_returns_calc=mock_returns_calc,
            risk_model_builder=mock_risk_builder,
        )

        stocks = [MagicMock(spec=Stock, symbol="AAPL", active=True)]

        result = await optimizer.optimize(
            stocks=stocks,
            positions={},
            portfolio_value=10000,
            current_prices={"AAPL": 150.0},
            cash_balance=1000,
        )

        assert result.success is False
        assert result.error == "Insufficient price history"


class TestPortfolioOptimizerHRP:
    """Test Hierarchical Risk Parity optimization."""

    def test_hrp_requires_at_least_two_symbols(self):
        """Test that HRP fails with less than 2 symbols."""
        optimizer = create_optimizer()

        # Create returns DataFrame with just one symbol
        returns_df = pd.DataFrame({"AAPL": [0.01, 0.02, -0.01, 0.015, 0.005] * 50})

        result = optimizer._run_hrp(returns_df, ["AAPL"])

        assert result is None

    def test_hrp_with_valid_data(self):
        """Test HRP with valid returns data."""
        optimizer = create_optimizer()

        # Create realistic returns data for 2 symbols
        np.random.seed(42)  # For reproducibility
        returns_data = {
            "AAPL": np.random.normal(0.001, 0.02, 252),
            "GOOGL": np.random.normal(0.001, 0.015, 252),
        }
        returns_df = pd.DataFrame(returns_data)

        result = optimizer._run_hrp(returns_df, ["AAPL", "GOOGL"])

        assert result is not None
        assert "AAPL" in result
        assert "GOOGL" in result
        # Weights should be positive and sum to approximately 1
        assert all(w >= 0 for w in result.values())
        assert sum(result.values()) == pytest.approx(1.0, rel=0.01)


class TestPortfolioOptimizerIntegration:
    """Integration tests for the full optimization flow."""

    @pytest.mark.asyncio
    async def test_full_optimization_flow(self):
        """Test the complete optimization flow with mocked dependencies."""
        # Mock expected returns
        mock_returns_calc = AsyncMock()
        mock_returns_calc.calculate_expected_returns.return_value = {
            "AAPL": 0.12,
            "GOOGL": 0.10,
            "MSFT": 0.11,
        }

        # Create realistic covariance matrix
        np.random.seed(42)
        returns_data = {
            "AAPL": np.random.normal(0.001, 0.02, 252),
            "GOOGL": np.random.normal(0.001, 0.015, 252),
            "MSFT": np.random.normal(0.001, 0.018, 252),
        }
        returns_df = pd.DataFrame(returns_data)
        cov_matrix = returns_df.cov() * 252  # Annualized

        mock_risk_builder = MagicMock()
        mock_risk_builder.build_covariance_matrix = AsyncMock(
            return_value=(cov_matrix, returns_df)
        )
        mock_risk_builder.get_correlations.return_value = []  # Sync method

        # Mock constraints manager
        mock_constraints = MagicMock()
        mock_constraints.calculate_weight_bounds.return_value = {
            "AAPL": (0.0, 0.40),
            "GOOGL": (0.0, 0.40),
            "MSFT": (0.0, 0.40),
        }
        mock_constraints.build_sector_constraints.return_value = ([], [])
        mock_constraints.get_constraint_summary.return_value = {}

        optimizer = PortfolioOptimizer(
            expected_returns_calc=mock_returns_calc,
            risk_model_builder=mock_risk_builder,
            constraints_manager=mock_constraints,
        )

        # Create test stocks
        stocks = [
            MagicMock(spec=Stock, symbol="AAPL", active=True),
            MagicMock(spec=Stock, symbol="GOOGL", active=True),
            MagicMock(spec=Stock, symbol="MSFT", active=True),
        ]

        result = await optimizer.optimize(
            stocks=stocks,
            positions={},
            portfolio_value=100000,
            current_prices={"AAPL": 150, "GOOGL": 2800, "MSFT": 330},
            cash_balance=10000,
            blend=0.5,
            target_return=0.11,
            min_cash_reserve=500,
        )

        assert result.success is True
        assert result.target_weights is not None
        assert len(result.target_weights) > 0
        # Weights should be positive
        assert all(w >= 0 for w in result.target_weights.values())
        # Weights should sum to less than 1 (due to cash reserve)
        assert sum(result.target_weights.values()) < 1.0

    @pytest.mark.asyncio
    async def test_optimization_respects_cash_reserve(self):
        """Test that optimization respects minimum cash reserve."""
        mock_returns_calc = AsyncMock()
        mock_returns_calc.calculate_expected_returns.return_value = {
            "AAPL": 0.12,
            "GOOGL": 0.10,
        }

        np.random.seed(42)
        returns_data = {
            "AAPL": np.random.normal(0.001, 0.02, 252),
            "GOOGL": np.random.normal(0.001, 0.015, 252),
        }
        returns_df = pd.DataFrame(returns_data)
        cov_matrix = returns_df.cov() * 252

        mock_risk_builder = MagicMock()
        mock_risk_builder.build_covariance_matrix = AsyncMock(
            return_value=(cov_matrix, returns_df)
        )
        mock_risk_builder.get_correlations.return_value = []  # Sync method

        mock_constraints = MagicMock()
        mock_constraints.calculate_weight_bounds.return_value = {
            "AAPL": (0.0, 0.60),
            "GOOGL": (0.0, 0.60),
        }
        mock_constraints.build_sector_constraints.return_value = ([], [])
        mock_constraints.get_constraint_summary.return_value = {}

        optimizer = PortfolioOptimizer(
            expected_returns_calc=mock_returns_calc,
            risk_model_builder=mock_risk_builder,
            constraints_manager=mock_constraints,
        )

        stocks = [
            MagicMock(spec=Stock, symbol="AAPL", active=True),
            MagicMock(spec=Stock, symbol="GOOGL", active=True),
        ]

        portfolio_value = 10000
        min_cash_reserve = 1000  # 10% reserve

        result = await optimizer.optimize(
            stocks=stocks,
            positions={},
            portfolio_value=portfolio_value,
            current_prices={"AAPL": 150, "GOOGL": 2800},
            cash_balance=2000,
            min_cash_reserve=min_cash_reserve,
        )

        assert result.success is True
        # Total weights should be approximately 90% (1 - 10% cash reserve)
        total_weight = sum(result.target_weights.values())
        expected_investable = 1.0 - (min_cash_reserve / portfolio_value)
        assert total_weight == pytest.approx(expected_investable, rel=0.01)
