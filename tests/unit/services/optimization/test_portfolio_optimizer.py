"""Tests for PortfolioOptimizer service.

These tests are CRITICAL for the retirement fund as they verify
the portfolio weight calculation and optimization logic.
"""

from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pandas as pd
import pytest

from app.domain.models import Position, Security
from app.modules.optimization.services.portfolio_optimizer import PortfolioOptimizer


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
        """Test that optimization fails gracefully with no securities."""
        optimizer = create_optimizer()

        result = await optimizer.optimize(
            securities=[],
            positions={},
            portfolio_value=10000,
            current_prices={},
            cash_balance=1000,
        )

        assert result.success is False
        assert result.error == "No active securities"
        assert result.target_weights == {}

    @pytest.mark.asyncio
    async def test_optimize_returns_error_when_no_expected_returns(self):
        """Test failure when expected returns calculation fails."""
        mock_returns_calc = AsyncMock()
        mock_returns_calc.calculate_expected_returns.return_value = {}

        optimizer = PortfolioOptimizer(expected_returns_calc=mock_returns_calc)

        securities = [MagicMock(spec=Security, symbol="AAPL", active=True)]

        result = await optimizer.optimize(
            securities=securities,
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

        securities = [MagicMock(spec=Security, symbol="AAPL", active=True)]

        result = await optimizer.optimize(
            securities=securities,
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
        mock_constraints.build_sector_constraints = AsyncMock(return_value=([], []))
        mock_constraints.get_constraint_summary.return_value = {}

        optimizer = PortfolioOptimizer(
            expected_returns_calc=mock_returns_calc,
            risk_model_builder=mock_risk_builder,
            constraints_manager=mock_constraints,
        )

        # Create test securities
        securities = [
            MagicMock(spec=Security, symbol="AAPL", active=True),
            MagicMock(spec=Security, symbol="GOOGL", active=True),
            MagicMock(spec=Security, symbol="MSFT", active=True),
        ]

        # Use a low target return to ensure feasibility with random data
        result = await optimizer.optimize(
            securities=securities,
            positions={},
            portfolio_value=100000,
            current_prices={"AAPL": 150, "GOOGL": 2800, "MSFT": 330},
            cash_balance=10000,
            blend=0.5,
            target_return=0.05,  # Low target to ensure achievability
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
        mock_constraints.build_sector_constraints = AsyncMock(return_value=([], []))
        mock_constraints.get_constraint_summary.return_value = {}

        optimizer = PortfolioOptimizer(
            expected_returns_calc=mock_returns_calc,
            risk_model_builder=mock_risk_builder,
            constraints_manager=mock_constraints,
        )

        securities = [
            MagicMock(spec=Security, symbol="AAPL", active=True),
            MagicMock(spec=Security, symbol="GOOGL", active=True),
        ]

        portfolio_value = 10000
        min_cash_reserve = 1000  # 10% reserve

        # Use a low target return to ensure feasibility with random data
        result = await optimizer.optimize(
            securities=securities,
            positions={},
            portfolio_value=portfolio_value,
            current_prices={"AAPL": 150, "GOOGL": 2800},
            cash_balance=2000,
            min_cash_reserve=min_cash_reserve,
            target_return=0.05,  # Low target to ensure achievability
        )

        assert result.success is True
        # Total weights should be approximately 90% (1 - 10% cash reserve)
        total_weight = sum(result.target_weights.values())
        expected_investable = 1.0 - (min_cash_reserve / portfolio_value)
        assert total_weight == pytest.approx(expected_investable, rel=0.01)


class TestPortfolioOptimizerBoundsClamping:
    """Test bounds clamping functionality for portfolio targets."""

    def test_clamp_weights_to_bounds_respects_max(self):
        """Test that weights above max_portfolio_target are clamped."""
        optimizer = create_optimizer()
        weights = {"AAPL": 0.10, "GOOGL": 0.05}  # AAPL exceeds max
        bounds = {
            "AAPL": (0.0, 0.03),  # Max 3%
            "GOOGL": (0.0, 0.10),  # Max 10%
        }

        result = optimizer._clamp_weights_to_bounds(weights, bounds)

        # AAPL should be clamped to 3%
        assert result["AAPL"] == 0.03
        # GOOGL within bounds, unchanged
        assert result["GOOGL"] == 0.05

    def test_clamp_weights_to_bounds_respects_min(self):
        """Test that weights below min_portfolio_target are clamped."""
        optimizer = create_optimizer()
        weights = {"AAPL": 0.01, "GOOGL": 0.05}  # AAPL below min
        bounds = {
            "AAPL": (0.05, 0.20),  # Min 5%
            "GOOGL": (0.0, 0.10),  # Min 0%
        }

        result = optimizer._clamp_weights_to_bounds(weights, bounds)

        # AAPL should be clamped to 5%
        assert result["AAPL"] == 0.05
        # GOOGL within bounds, unchanged
        assert result["GOOGL"] == 0.05

    def test_clamp_weights_to_bounds_within_bounds_unchanged(self):
        """Test that weights within bounds are not changed."""
        optimizer = create_optimizer()
        weights = {"AAPL": 0.05, "GOOGL": 0.08}
        bounds = {
            "AAPL": (0.03, 0.10),  # 5% is within bounds
            "GOOGL": (0.05, 0.15),  # 8% is within bounds
        }

        result = optimizer._clamp_weights_to_bounds(weights, bounds)

        # Both should be unchanged
        assert result["AAPL"] == 0.05
        assert result["GOOGL"] == 0.08

    def test_clamp_weights_to_bounds_handles_missing_symbols(self):
        """Test that symbols not in bounds dict are left unchanged."""
        optimizer = create_optimizer()
        weights = {"AAPL": 0.10, "GOOGL": 0.05, "MSFT": 0.15}
        bounds = {
            "AAPL": (0.0, 0.05),  # Will be clamped
            "GOOGL": (0.0, 0.10),  # Within bounds
            # MSFT not in bounds
        }

        result = optimizer._clamp_weights_to_bounds(weights, bounds)

        # AAPL clamped to 5%
        assert result["AAPL"] == 0.05
        # GOOGL unchanged
        assert result["GOOGL"] == 0.05
        # MSFT unchanged (not in bounds)
        assert result["MSFT"] == 0.15

    def test_clamp_weights_to_bounds_edge_cases(self):
        """Test edge cases for bounds clamping."""
        optimizer = create_optimizer()
        weights = {"AAPL": 0.0, "GOOGL": 0.20}
        bounds = {
            "AAPL": (0.0, 0.10),  # 0% is at lower bound
            "GOOGL": (0.0, 0.15),  # 20% exceeds upper bound
        }

        result = optimizer._clamp_weights_to_bounds(weights, bounds)

        # AAPL at lower bound, unchanged
        assert result["AAPL"] == 0.0
        # GOOGL clamped to upper bound
        assert result["GOOGL"] == 0.15

    def test_clamp_weights_after_normalization(self):
        """Test that normalization followed by clamping respects bounds."""
        optimizer = create_optimizer()
        # Weights that sum to 0.6, will be normalized to 0.9 (investable fraction)
        # This will scale AAPL from 0.4 to 0.6, which exceeds max of 0.5
        weights = {"AAPL": 0.4, "GOOGL": 0.2}  # Sum = 0.6
        bounds = {
            "AAPL": (0.0, 0.5),  # Max 50%
            "GOOGL": (0.0, 0.6),  # Max 60%
        }
        investable_fraction = 0.9

        # Normalize first
        normalized = optimizer._normalize_weights(weights, investable_fraction)
        # Then clamp
        result = optimizer._clamp_weights_to_bounds(normalized, bounds)

        # AAPL should be clamped to 0.5 (was 0.6 after normalization)
        assert result["AAPL"] == 0.5
        # GOOGL should be within bounds
        assert result["GOOGL"] <= 0.6
        # Total may be less than investable_fraction after clamping (acceptable)
        assert sum(result.values()) <= investable_fraction


class TestPortfolioOptimizerSectorConstraints:
    """Test that sector constraints are applied to EfficientFrontier."""

    @pytest.mark.asyncio
    async def test_add_sector_constraints_called_with_country_constraints(
        self,
    ):
        """Test that add_sector_constraints() is called with country constraints."""
        from unittest.mock import patch

        from app.modules.optimization.services.constraints_manager import (
            SectorConstraint,
        )

        optimizer = create_optimizer()

        # Create sample constraints
        country_constraints = [
            SectorConstraint(
                name="United States",
                symbols=["AAPL", "GOOGL"],
                target=0.5,
                lower=0.4,
                upper=0.6,
            ),
            SectorConstraint(
                name="Germany",
                symbols=["SAP"],
                target=0.3,
                lower=0.2,
                upper=0.4,
            ),
        ]
        ind_constraints = []

        expected_returns = {"AAPL": 0.10, "GOOGL": 0.12, "SAP": 0.08}
        cov_matrix = pd.DataFrame(
            np.eye(3),
            index=["AAPL", "GOOGL", "SAP"],
            columns=["AAPL", "GOOGL", "SAP"],
        )
        bounds = {
            "AAPL": (0.0, 0.3),
            "GOOGL": (0.0, 0.3),
            "SAP": (0.0, 0.3),
        }
        target_return = 0.11

        # Patch in the module where it's used, not where it's defined
        with patch(
            "app.modules.optimization.services.portfolio_optimizer.EfficientFrontier"
        ) as mock_ef_class:
            mock_ef = MagicMock()
            mock_ef_class.return_value = mock_ef
            mock_ef.efficient_return.return_value = None
            mock_ef.clean_weights.return_value = {"AAPL": 0.3, "GOOGL": 0.3, "SAP": 0.2}

            await optimizer._run_mean_variance(
                expected_returns=expected_returns,
                cov_matrix=cov_matrix,
                bounds=bounds,
                target_return=target_return,
                country_constraints=country_constraints,
                ind_constraints=ind_constraints,
            )

            # Verify EfficientFrontier was created
            assert mock_ef_class.called

            # Verify add_sector_constraints was called with country constraints
            add_sector_calls = [
                call
                for call in mock_ef.method_calls
                if call[0] == "add_sector_constraints"
            ]
            assert len(add_sector_calls) >= 1

            # Check first call (country constraints)
            country_call = add_sector_calls[0]
            country_mapper = country_call[1][0]  # First positional arg
            country_lower = country_call[1][1]  # Second positional arg
            country_upper = country_call[1][2]  # Third positional arg

            # Verify mapper maps symbols to country names
            assert country_mapper["AAPL"] == "United States"
            assert country_mapper["GOOGL"] == "United States"
            assert country_mapper["SAP"] == "Germany"

            # Verify bounds
            assert country_lower["United States"] == 0.4
            assert country_upper["United States"] == 0.6
            assert country_lower["Germany"] == 0.2
            assert country_upper["Germany"] == 0.4

    @pytest.mark.asyncio
    async def test_add_sector_constraints_called_with_industry_constraints(
        self,
    ):
        """Test that add_sector_constraints() is called with industry constraints."""
        from unittest.mock import patch

        from app.modules.optimization.services.constraints_manager import (
            SectorConstraint,
        )

        optimizer = create_optimizer()

        country_constraints = []
        ind_constraints = [
            SectorConstraint(
                name="Technology",
                symbols=["AAPL", "GOOGL"],
                target=0.6,
                lower=0.5,
                upper=0.7,
            ),
            SectorConstraint(
                name="Finance",
                symbols=["JPM"],
                target=0.2,
                lower=0.1,
                upper=0.3,
            ),
        ]

        expected_returns = {"AAPL": 0.10, "GOOGL": 0.12, "JPM": 0.08}
        cov_matrix = pd.DataFrame(
            np.eye(3),
            index=["AAPL", "GOOGL", "JPM"],
            columns=["AAPL", "GOOGL", "JPM"],
        )
        bounds = {
            "AAPL": (0.0, 0.3),
            "GOOGL": (0.0, 0.3),
            "JPM": (0.0, 0.3),
        }
        target_return = 0.11

        # Patch in the module where it's used, not where it's defined
        with patch(
            "app.modules.optimization.services.portfolio_optimizer.EfficientFrontier"
        ) as mock_ef_class:
            mock_ef = MagicMock()
            mock_ef_class.return_value = mock_ef
            mock_ef.efficient_return.return_value = None
            mock_ef.clean_weights.return_value = {"AAPL": 0.3, "GOOGL": 0.3, "JPM": 0.2}

            await optimizer._run_mean_variance(
                expected_returns=expected_returns,
                cov_matrix=cov_matrix,
                bounds=bounds,
                target_return=target_return,
                country_constraints=country_constraints,
                ind_constraints=ind_constraints,
            )

            # Verify add_sector_constraints was called with industry constraints
            add_sector_calls = [
                call
                for call in mock_ef.method_calls
                if call[0] == "add_sector_constraints"
            ]
            assert len(add_sector_calls) >= 1

            # Check industry constraints call
            ind_call = add_sector_calls[0]
            ind_mapper = ind_call[1][0]
            ind_lower = ind_call[1][1]
            ind_upper = ind_call[1][2]

            # Verify mapper maps symbols to industry names
            assert ind_mapper["AAPL"] == "Technology"
            assert ind_mapper["GOOGL"] == "Technology"
            assert ind_mapper["JPM"] == "Finance"

            # Verify bounds
            assert ind_lower["Technology"] == 0.5
            assert ind_upper["Technology"] == 0.7
            assert ind_lower["Finance"] == 0.1
            assert ind_upper["Finance"] == 0.3

    @pytest.mark.asyncio
    async def test_sector_constraints_applied_to_both_optimization_attempts(
        self,
    ):
        """Test that constraints are applied to both efficient_return and max_sharpe attempts."""
        from unittest.mock import patch

        from pypfopt.exceptions import OptimizationError

        from app.modules.optimization.services.constraints_manager import (
            SectorConstraint,
        )

        optimizer = create_optimizer()

        country_constraints = [
            SectorConstraint(
                name="United States",
                symbols=["AAPL"],
                target=0.5,
                lower=0.4,
                upper=0.6,
            ),
        ]
        ind_constraints = []

        expected_returns = {"AAPL": 0.10}
        cov_matrix = pd.DataFrame(np.array([[0.04]]), index=["AAPL"], columns=["AAPL"])
        bounds = {"AAPL": (0.0, 1.0)}
        target_return = 0.11

        with patch(
            "app.modules.optimization.services.portfolio_optimizer.EfficientFrontier"
        ) as mock_ef_class:
            mock_ef = MagicMock()
            mock_ef_class.return_value = mock_ef

            # First attempt (efficient_return) fails
            mock_ef.efficient_return.side_effect = OptimizationError("Failed")
            # Second attempt (max_sharpe) succeeds
            mock_ef.max_sharpe.return_value = None
            mock_ef.clean_weights.return_value = {"AAPL": 0.5}

            await optimizer._run_mean_variance(
                expected_returns=expected_returns,
                cov_matrix=cov_matrix,
                bounds=bounds,
                target_return=target_return,
                country_constraints=country_constraints,
                ind_constraints=ind_constraints,
            )

            # Verify EfficientFrontier was created (may be created twice)
            assert mock_ef_class.call_count >= 1

            # Verify add_sector_constraints was called
            # (should be called for each EfficientFrontier instance)
            add_sector_calls = [
                call
                for call in mock_ef.method_calls
                if call[0] == "add_sector_constraints"
            ]
            # Should be called at least once (for efficient_return attempt)
            assert len(add_sector_calls) >= 1

    @pytest.mark.asyncio
    async def test_sector_mappers_built_correctly_from_constraints(self):
        """Test that sector mappers are built correctly from constraints."""
        from unittest.mock import patch

        from app.modules.optimization.services.constraints_manager import (
            SectorConstraint,
        )

        optimizer = create_optimizer()

        # Multiple symbols per constraint
        country_constraints = [
            SectorConstraint(
                name="United States",
                symbols=["AAPL", "GOOGL", "MSFT"],
                target=0.6,
                lower=0.5,
                upper=0.7,
            ),
        ]
        ind_constraints = []

        expected_returns = {"AAPL": 0.10, "GOOGL": 0.12, "MSFT": 0.11}
        cov_matrix = pd.DataFrame(
            np.eye(3),
            index=["AAPL", "GOOGL", "MSFT"],
            columns=["AAPL", "GOOGL", "MSFT"],
        )
        bounds = {
            "AAPL": (0.0, 0.3),
            "GOOGL": (0.0, 0.3),
            "MSFT": (0.0, 0.3),
        }
        target_return = 0.11

        with patch(
            "app.modules.optimization.services.portfolio_optimizer.EfficientFrontier"
        ) as mock_ef_class:
            mock_ef = MagicMock()
            mock_ef_class.return_value = mock_ef
            mock_ef.efficient_return.return_value = None
            mock_ef.clean_weights.return_value = {
                "AAPL": 0.2,
                "GOOGL": 0.2,
                "MSFT": 0.2,
            }

            await optimizer._run_mean_variance(
                expected_returns=expected_returns,
                cov_matrix=cov_matrix,
                bounds=bounds,
                target_return=target_return,
                country_constraints=country_constraints,
                ind_constraints=ind_constraints,
            )

            # Verify mapper includes all symbols
            add_sector_calls = [
                call
                for call in mock_ef.method_calls
                if call[0] == "add_sector_constraints"
            ]
            assert len(add_sector_calls) >= 1

            country_call = add_sector_calls[0]
            country_mapper = country_call[1][0]

            # All three symbols should map to "United States"
            assert country_mapper["AAPL"] == "United States"
            assert country_mapper["GOOGL"] == "United States"
            assert country_mapper["MSFT"] == "United States"

    @pytest.mark.asyncio
    async def test_sector_bounds_built_correctly_from_constraints(self):
        """Test that sector bounds (lower/upper) are built correctly from constraints."""
        from unittest.mock import patch

        from app.modules.optimization.services.constraints_manager import (
            SectorConstraint,
        )

        optimizer = create_optimizer()

        country_constraints = [
            SectorConstraint(
                name="United States",
                symbols=["AAPL"],
                target=0.5,
                lower=0.4,
                upper=0.6,
            ),
            SectorConstraint(
                name="Germany",
                symbols=["SAP"],
                target=0.3,
                lower=0.2,
                upper=0.4,
            ),
        ]
        ind_constraints = []

        expected_returns = {"AAPL": 0.10, "SAP": 0.08}
        cov_matrix = pd.DataFrame(
            np.eye(2), index=["AAPL", "SAP"], columns=["AAPL", "SAP"]
        )
        bounds = {"AAPL": (0.0, 0.6), "SAP": (0.0, 0.4)}
        target_return = 0.11

        with patch(
            "app.modules.optimization.services.portfolio_optimizer.EfficientFrontier"
        ) as mock_ef_class:
            mock_ef = MagicMock()
            mock_ef_class.return_value = mock_ef
            mock_ef.efficient_return.return_value = None
            mock_ef.clean_weights.return_value = {"AAPL": 0.5, "SAP": 0.3}

            await optimizer._run_mean_variance(
                expected_returns=expected_returns,
                cov_matrix=cov_matrix,
                bounds=bounds,
                target_return=target_return,
                country_constraints=country_constraints,
                ind_constraints=ind_constraints,
            )

            # Verify bounds are correct
            add_sector_calls = [
                call
                for call in mock_ef.method_calls
                if call[0] == "add_sector_constraints"
            ]
            assert len(add_sector_calls) >= 1

            country_call = add_sector_calls[0]
            country_lower = country_call[1][1]
            country_upper = country_call[1][2]

            # Verify bounds match constraint values
            assert country_lower["United States"] == 0.4
            assert country_upper["United States"] == 0.6
            assert country_lower["Germany"] == 0.2
            assert country_upper["Germany"] == 0.4


class TestPortfolioOptimizerRetirementFallbacks:
    """Test retirement-appropriate fallback strategies."""

    @pytest.mark.asyncio
    async def test_fallback_to_min_volatility_when_efficient_return_fails(self):
        """Test that min_volatility() is used as fallback when efficient_return fails."""
        from unittest.mock import patch

        from pypfopt.exceptions import OptimizationError

        optimizer = create_optimizer()

        expected_returns = {"AAPL": 0.10}
        cov_matrix = pd.DataFrame(np.array([[0.04]]), index=["AAPL"], columns=["AAPL"])
        bounds = {"AAPL": (0.0, 1.0)}
        target_return = 0.11
        country_constraints = []
        ind_constraints = []

        with patch(
            "app.modules.optimization.services.portfolio_optimizer.EfficientFrontier"
        ) as mock_ef_class:
            mock_ef = MagicMock()
            mock_ef_class.return_value = mock_ef

            # efficient_return fails
            mock_ef.efficient_return.side_effect = OptimizationError("Failed")
            # min_volatility succeeds
            mock_ef.min_volatility.return_value = None
            mock_ef.clean_weights.return_value = {"AAPL": 0.5}

            weights, fallback = await optimizer._run_mean_variance(
                expected_returns=expected_returns,
                cov_matrix=cov_matrix,
                bounds=bounds,
                target_return=target_return,
                country_constraints=country_constraints,
                ind_constraints=ind_constraints,
            )

            # Verify min_volatility was called
            mock_ef.min_volatility.assert_called_once()
            # Verify fallback is reported
            assert fallback == "min_volatility"
            assert weights == {"AAPL": 0.5}

    @pytest.mark.asyncio
    async def test_fallback_to_efficient_risk_when_min_volatility_fails(self):
        """Test that efficient_risk() is used as fallback when min_volatility fails."""
        from unittest.mock import patch

        from pypfopt.exceptions import OptimizationError

        optimizer = create_optimizer()

        expected_returns = {"AAPL": 0.10}
        cov_matrix = pd.DataFrame(np.array([[0.04]]), index=["AAPL"], columns=["AAPL"])
        bounds = {"AAPL": (0.0, 1.0)}
        target_return = 0.11
        country_constraints = []
        ind_constraints = []

        with patch(
            "app.modules.optimization.services.portfolio_optimizer.EfficientFrontier"
        ) as mock_ef_class:
            mock_ef = MagicMock()
            mock_ef_class.return_value = mock_ef

            # efficient_return fails
            mock_ef.efficient_return.side_effect = OptimizationError("Failed")
            # min_volatility fails
            mock_ef.min_volatility.side_effect = OptimizationError("Failed")
            # efficient_risk succeeds
            mock_ef.efficient_risk.return_value = None
            mock_ef.clean_weights.return_value = {"AAPL": 0.5}

            weights, fallback = await optimizer._run_mean_variance(
                expected_returns=expected_returns,
                cov_matrix=cov_matrix,
                bounds=bounds,
                target_return=target_return,
                country_constraints=country_constraints,
                ind_constraints=ind_constraints,
            )

            # Verify efficient_risk was called with target volatility
            mock_ef.efficient_risk.assert_called_once()
            # Check that target_volatility=0.15 was passed
            call_args = mock_ef.efficient_risk.call_args
            assert call_args.kwargs["target_volatility"] == 0.15
            # Verify fallback is reported
            assert fallback == "efficient_risk"
            assert weights == {"AAPL": 0.5}

    @pytest.mark.asyncio
    async def test_fallback_to_max_sharpe_when_efficient_risk_fails(self):
        """Test that max_sharpe() is used as fallback when efficient_risk fails."""
        from unittest.mock import patch

        from pypfopt.exceptions import OptimizationError

        optimizer = create_optimizer()

        expected_returns = {"AAPL": 0.10}
        cov_matrix = pd.DataFrame(np.array([[0.04]]), index=["AAPL"], columns=["AAPL"])
        bounds = {"AAPL": (0.0, 1.0)}
        target_return = 0.11
        country_constraints = []
        ind_constraints = []

        with patch(
            "app.modules.optimization.services.portfolio_optimizer.EfficientFrontier"
        ) as mock_ef_class:
            mock_ef = MagicMock()
            mock_ef_class.return_value = mock_ef

            # efficient_return fails
            mock_ef.efficient_return.side_effect = OptimizationError("Failed")
            # min_volatility fails
            mock_ef.min_volatility.side_effect = OptimizationError("Failed")
            # efficient_risk fails
            mock_ef.efficient_risk.side_effect = OptimizationError("Failed")
            # max_sharpe succeeds
            mock_ef.max_sharpe.return_value = None
            mock_ef.clean_weights.return_value = {"AAPL": 0.5}

            weights, fallback = await optimizer._run_mean_variance(
                expected_returns=expected_returns,
                cov_matrix=cov_matrix,
                bounds=bounds,
                target_return=target_return,
                country_constraints=country_constraints,
                ind_constraints=ind_constraints,
            )

            # Verify max_sharpe was called
            mock_ef.max_sharpe.assert_called_once()
            # Verify fallback is reported
            assert fallback == "max_sharpe"
            assert weights == {"AAPL": 0.5}

    @pytest.mark.asyncio
    async def test_returns_none_when_all_fallbacks_fail(self):
        """Test that returns None when all MV methods fail (will use pure HRP)."""
        from unittest.mock import patch

        from pypfopt.exceptions import OptimizationError

        optimizer = create_optimizer()

        expected_returns = {"AAPL": 0.10}
        cov_matrix = pd.DataFrame(np.array([[0.04]]), index=["AAPL"], columns=["AAPL"])
        bounds = {"AAPL": (0.0, 1.0)}
        target_return = 0.11
        country_constraints = []
        ind_constraints = []

        with patch(
            "app.modules.optimization.services.portfolio_optimizer.EfficientFrontier"
        ) as mock_ef_class:
            mock_ef = MagicMock()
            mock_ef_class.return_value = mock_ef

            # All methods fail
            mock_ef.efficient_return.side_effect = OptimizationError("Failed")
            mock_ef.min_volatility.side_effect = OptimizationError("Failed")
            mock_ef.efficient_risk.side_effect = OptimizationError("Failed")
            mock_ef.max_sharpe.side_effect = OptimizationError("Failed")

            weights, fallback = await optimizer._run_mean_variance(
                expected_returns=expected_returns,
                cov_matrix=cov_matrix,
                bounds=bounds,
                target_return=target_return,
                country_constraints=country_constraints,
                ind_constraints=ind_constraints,
            )

            # Should return None (will use pure HRP)
            assert weights is None
            assert fallback is None
