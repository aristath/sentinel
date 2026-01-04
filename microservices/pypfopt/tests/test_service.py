"""Tests for PyPortfolioOpt service logic."""

import pandas as pd
import pytest
from pypfopt import exceptions

from app.service import PyPortfolioOptService


@pytest.fixture
def service():
    """Create service instance."""
    return PyPortfolioOptService()


@pytest.fixture
def sample_data():
    """Sample portfolio data for testing."""
    symbols = ["AAPL", "MSFT", "GOOGL"]

    mu = pd.Series({
        "AAPL": 0.12,
        "MSFT": 0.10,
        "GOOGL": 0.15
    })

    cov_matrix = pd.DataFrame(
        [
            [0.04, 0.02, 0.01],
            [0.02, 0.05, 0.015],
            [0.01, 0.015, 0.03]
        ],
        index=symbols,
        columns=symbols
    )

    weight_bounds = [(0.02, 0.50), (0.02, 0.50), (0.02, 0.50)]

    return mu, cov_matrix, weight_bounds


@pytest.fixture
def sample_returns():
    """Sample returns data for HRP testing."""
    dates = pd.date_range("2024-01-01", periods=100, freq="D")
    data = {
        "AAPL": [0.01 * (i % 5 - 2) for i in range(100)],
        "MSFT": [0.008 * (i % 7 - 3) for i in range(100)],
        "GOOGL": [0.012 * (i % 3 - 1) for i in range(100)]
    }
    return pd.DataFrame(data, index=dates)


class TestMeanVarianceOptimization:
    """Test mean-variance optimization methods."""

    def test_min_volatility(self, service, sample_data):
        """Test min_volatility strategy."""
        mu, cov_matrix, weight_bounds = sample_data

        result = service.mean_variance_optimize(
            mu, cov_matrix, weight_bounds,
            sector_constraints=[],
            strategy="min_volatility"
        )

        assert "weights" in result
        assert "achieved_return" in result
        assert "achieved_volatility" in result
        assert len(result["weights"]) == 3
        assert abs(sum(result["weights"].values()) - 1.0) < 0.01  # Weights sum to 1

    def test_efficient_return(self, service, sample_data):
        """Test efficient_return strategy."""
        mu, cov_matrix, weight_bounds = sample_data

        result = service.mean_variance_optimize(
            mu, cov_matrix, weight_bounds,
            sector_constraints=[],
            strategy="efficient_return",
            target_return=0.11
        )

        assert "weights" in result
        assert len(result["weights"]) == 3
        assert abs(sum(result["weights"].values()) - 1.0) < 0.01

    def test_efficient_return_requires_target(self, service, sample_data):
        """Test that efficient_return requires target_return."""
        mu, cov_matrix, weight_bounds = sample_data

        with pytest.raises(ValueError, match="target_return required"):
            service.mean_variance_optimize(
                mu, cov_matrix, weight_bounds,
                sector_constraints=[],
                strategy="efficient_return"
            )

    def test_max_sharpe(self, service, sample_data):
        """Test max_sharpe strategy."""
        mu, cov_matrix, weight_bounds = sample_data

        result = service.mean_variance_optimize(
            mu, cov_matrix, weight_bounds,
            sector_constraints=[],
            strategy="max_sharpe"
        )

        assert "weights" in result
        assert len(result["weights"]) == 3

    def test_unknown_strategy(self, service, sample_data):
        """Test that unknown strategy raises error."""
        mu, cov_matrix, weight_bounds = sample_data

        with pytest.raises(ValueError, match="Unknown strategy"):
            service.mean_variance_optimize(
                mu, cov_matrix, weight_bounds,
                sector_constraints=[],
                strategy="invalid_strategy"
            )

    def test_with_sector_constraints(self, service, sample_data):
        """Test optimization with sector constraints."""
        mu, cov_matrix, weight_bounds = sample_data

        sector_constraints = [{
            "sector_mapper": {"AAPL": "US", "MSFT": "US", "GOOGL": "US"},
            "sector_lower": {"US": 0.50},
            "sector_upper": {"US": 1.00}
        }]

        result = service.mean_variance_optimize(
            mu, cov_matrix, weight_bounds,
            sector_constraints=sector_constraints,
            strategy="min_volatility"
        )

        assert "weights" in result
        assert len(result["weights"]) == 3


class TestHRPOptimization:
    """Test Hierarchical Risk Parity optimization."""

    def test_basic_hrp(self, service, sample_returns):
        """Test basic HRP optimization."""
        weights = service.hrp_optimize(sample_returns)

        assert isinstance(weights, dict)
        assert len(weights) == 3
        assert abs(sum(weights.values()) - 1.0) < 0.01  # Weights sum to 1
        assert all(w >= 0 for w in weights.values())  # All weights non-negative


class TestCovarianceCalculation:
    """Test covariance matrix calculation."""

    def test_basic_covariance(self, service):
        """Test basic covariance calculation."""
        dates = pd.date_range("2024-01-01", periods=100, freq="D")
        prices = pd.DataFrame({
            "AAPL": [150 + i * 0.5 for i in range(100)],
            "MSFT": [380 + i * 0.3 for i in range(100)]
        }, index=dates)

        cov_matrix = service.calculate_covariance(prices)

        assert isinstance(cov_matrix, pd.DataFrame)
        assert cov_matrix.shape == (2, 2)
        assert list(cov_matrix.index) == ["AAPL", "MSFT"]
        assert list(cov_matrix.columns) == ["AAPL", "MSFT"]
        # Matrix should be symmetric
        assert abs(cov_matrix.loc["AAPL", "MSFT"] - cov_matrix.loc["MSFT", "AAPL"]) < 1e-10


class TestProgressiveOptimization:
    """Test progressive optimization with fallbacks."""

    def test_progressive_success_first_try(self, service, sample_data):
        """Test progressive optimization succeeding on first try."""
        mu, cov_matrix, weight_bounds = sample_data

        result = service.progressive_optimize(
            mu, cov_matrix, weight_bounds,
            sector_constraints=[],
            target_return=0.11
        )

        assert "weights" in result
        assert "strategy_used" in result
        assert "constraint_level" in result
        assert "attempts" in result
        assert result["constraint_level"] == "full"
        assert result["attempts"] >= 1

    def test_progressive_with_constraints(self, service, sample_data):
        """Test progressive optimization with sector constraints."""
        mu, cov_matrix, weight_bounds = sample_data

        sector_constraints = [{
            "sector_mapper": {"AAPL": "US", "MSFT": "US", "GOOGL": "US"},
            "sector_lower": {"US": 0.80},
            "sector_upper": {"US": 1.00}
        }]

        result = service.progressive_optimize(
            mu, cov_matrix, weight_bounds,
            sector_constraints=sector_constraints,
            target_return=0.11
        )

        assert "weights" in result
        assert "constraint_level" in result


class TestConstraintRelaxation:
    """Test constraint relaxation logic."""

    def test_relax_constraints(self, service):
        """Test constraint relaxation by 50%."""
        constraints = [{
            "sector_mapper": {"AAPL": "US", "MSFT": "US"},
            "sector_lower": {"US": 0.60, "EU": 0.40},
            "sector_upper": {"US": 0.80, "EU": 0.60}
        }]

        relaxed = service._relax_constraints(constraints, 0.5)

        assert len(relaxed) == 1
        assert relaxed[0]["sector_lower"]["US"] == 0.30  # 0.60 * 0.5
        assert relaxed[0]["sector_lower"]["EU"] == 0.20  # 0.40 * 0.5
        assert relaxed[0]["sector_upper"]["US"] == 0.80  # Unchanged
        assert relaxed[0]["sector_upper"]["EU"] == 0.60  # Unchanged

    def test_relax_constraints_preserves_mapper(self, service):
        """Test that constraint relaxation preserves sector mapper."""
        constraints = [{
            "sector_mapper": {"AAPL": "US", "MSFT": "US", "ASML": "EU"},
            "sector_lower": {"US": 0.50, "EU": 0.30},
            "sector_upper": {"US": 0.70, "EU": 0.50}
        }]

        relaxed = service._relax_constraints(constraints, 0.5)

        assert relaxed[0]["sector_mapper"] == constraints[0]["sector_mapper"]
