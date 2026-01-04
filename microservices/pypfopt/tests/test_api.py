"""Tests for FastAPI endpoints."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture
def mean_variance_request():
    """Sample mean-variance optimization request."""
    return {
        "expected_returns": {
            "AAPL": 0.12,
            "MSFT": 0.10,
            "GOOGL": 0.15
        },
        "covariance_matrix": [
            [0.04, 0.02, 0.01],
            [0.02, 0.05, 0.015],
            [0.01, 0.015, 0.03]
        ],
        "symbols": ["AAPL", "MSFT", "GOOGL"],
        "weight_bounds": [[0.02, 0.50], [0.02, 0.50], [0.02, 0.50]],
        "sector_constraints": [],
        "strategy": "min_volatility"
    }


@pytest.fixture
def hrp_request():
    """Sample HRP optimization request."""
    return {
        "returns": {
            "dates": ["2025-01-01", "2025-01-02", "2025-01-03"],
            "data": {
                "AAPL": [0.01, -0.02, 0.015],
                "MSFT": [0.005, 0.015, -0.01],
                "GOOGL": [0.02, -0.005, 0.01]
            }
        }
    }


@pytest.fixture
def covariance_request():
    """Sample covariance calculation request."""
    return {
        "prices": {
            "dates": ["2025-01-01", "2025-01-02", "2025-01-03"],
            "data": {
                "AAPL": [150.0, 151.5, 152.0],
                "MSFT": [380.0, 382.5, 381.0]
            }
        }
    }


class TestHealthCheck:
    """Test health check endpoint."""

    def test_health_check(self):
        """Test GET /health returns healthy status."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "pypfopt"
        assert data["version"] == "1.0.0"
        assert "timestamp" in data


class TestMeanVarianceEndpoint:
    """Test POST /optimize/mean-variance endpoint."""

    def test_min_volatility_success(self, mean_variance_request):
        """Test successful min_volatility optimization."""
        response = client.post("/optimize/mean-variance", json=mean_variance_request)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "weights" in data["data"]
        assert "strategy_used" in data["data"]
        assert data["data"]["strategy_used"] == "min_volatility"
        assert len(data["data"]["weights"]) == 3

    def test_efficient_return_success(self, mean_variance_request):
        """Test successful efficient_return optimization."""
        mean_variance_request["strategy"] = "efficient_return"
        mean_variance_request["target_return"] = 0.11

        response = client.post("/optimize/mean-variance", json=mean_variance_request)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["strategy_used"] == "efficient_return"

    def test_efficient_return_missing_target(self, mean_variance_request):
        """Test efficient_return without target_return fails."""
        mean_variance_request["strategy"] = "efficient_return"
        mean_variance_request["target_return"] = None

        response = client.post("/optimize/mean-variance", json=mean_variance_request)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "error" in data
        assert "target_return required" in data["error"]

    def test_with_sector_constraints(self, mean_variance_request):
        """Test optimization with sector constraints."""
        mean_variance_request["sector_constraints"] = [{
            "sector_mapper": {"AAPL": "US", "MSFT": "US", "GOOGL": "US"},
            "sector_lower": {"US": 0.50},
            "sector_upper": {"US": 1.00}
        }]

        response = client.post("/optimize/mean-variance", json=mean_variance_request)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_invalid_strategy(self, mean_variance_request):
        """Test invalid strategy is rejected by Pydantic validation."""
        mean_variance_request["strategy"] = "invalid_strategy"

        response = client.post("/optimize/mean-variance", json=mean_variance_request)

        # Pydantic validates strategy as a Literal, so invalid values return 422
        assert response.status_code == 422


class TestHRPEndpoint:
    """Test POST /optimize/hrp endpoint."""

    def test_hrp_success(self, hrp_request):
        """Test successful HRP optimization."""
        response = client.post("/optimize/hrp", json=hrp_request)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "weights" in data["data"]
        assert len(data["data"]["weights"]) == 3

    def test_hrp_with_more_securities(self):
        """Test HRP with larger portfolio."""
        request = {
            "returns": {
                "dates": [f"2025-01-{i:02d}" for i in range(1, 31)],
                "data": {
                    f"STOCK{i}": [0.01 * (j % 5 - 2) for j in range(30)]
                    for i in range(1, 11)
                }
            }
        }

        response = client.post("/optimize/hrp", json=request)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["weights"]) == 10


class TestCovarianceEndpoint:
    """Test POST /risk-model/covariance endpoint."""

    def test_covariance_success(self, covariance_request):
        """Test successful covariance calculation."""
        response = client.post("/risk-model/covariance", json=covariance_request)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "covariance_matrix" in data["data"]
        assert "symbols" in data["data"]
        assert len(data["data"]["symbols"]) == 2
        assert len(data["data"]["covariance_matrix"]) == 2
        assert len(data["data"]["covariance_matrix"][0]) == 2

    def test_covariance_matrix_is_symmetric(self, covariance_request):
        """Test that covariance matrix is symmetric."""
        response = client.post("/risk-model/covariance", json=covariance_request)

        assert response.status_code == 200
        data = response.json()
        matrix = data["data"]["covariance_matrix"]

        # Check symmetry
        assert abs(matrix[0][1] - matrix[1][0]) < 1e-10


class TestProgressiveEndpoint:
    """Test POST /optimize/progressive endpoint."""

    def test_progressive_success(self, mean_variance_request):
        """Test successful progressive optimization."""
        mean_variance_request["target_return"] = 0.11

        response = client.post("/optimize/progressive", json=mean_variance_request)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "weights" in data["data"]
        assert "strategy_used" in data["data"]
        assert "constraint_level" in data["data"]
        assert "attempts" in data["data"]

    def test_progressive_with_constraints(self, mean_variance_request):
        """Test progressive optimization with sector constraints."""
        mean_variance_request["target_return"] = 0.11
        mean_variance_request["sector_constraints"] = [{
            "sector_mapper": {"AAPL": "US", "MSFT": "US", "GOOGL": "US"},
            "sector_lower": {"US": 0.80},
            "sector_upper": {"US": 1.00}
        }]

        response = client.post("/optimize/progressive", json=mean_variance_request)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_progressive_defaults_target_return(self, mean_variance_request):
        """Test that progressive defaults target_return to 0.11."""
        mean_variance_request["target_return"] = None

        response = client.post("/optimize/progressive", json=mean_variance_request)

        assert response.status_code == 200
        data = response.json()
        # Should succeed with default target_return
        assert data["success"] is True


class TestRequestValidation:
    """Test Pydantic request validation."""

    def test_missing_required_field(self):
        """Test that missing required fields are rejected."""
        invalid_request = {
            "expected_returns": {"AAPL": 0.12},
            # Missing covariance_matrix, symbols, weight_bounds, strategy
        }

        response = client.post("/optimize/mean-variance", json=invalid_request)

        assert response.status_code == 422  # Validation error

    def test_invalid_data_type(self):
        """Test that invalid data types are rejected."""
        invalid_request = {
            "expected_returns": "invalid",  # Should be dict
            "covariance_matrix": [[0.04]],
            "symbols": ["AAPL"],
            "weight_bounds": [[0.02, 0.10]],
            "strategy": "min_volatility"
        }

        response = client.post("/optimize/mean-variance", json=invalid_request)

        assert response.status_code == 422

    def test_invalid_strategy_value(self, mean_variance_request):
        """Test that invalid strategy literal is rejected."""
        mean_variance_request["strategy"] = "not_a_valid_strategy"

        response = client.post("/optimize/mean-variance", json=mean_variance_request)

        # Pydantic should reject invalid literal
        assert response.status_code == 422


class TestResponseFormat:
    """Test that all responses follow ServiceResponse format."""

    def test_success_response_format(self, mean_variance_request):
        """Test successful response format."""
        response = client.post("/optimize/mean-variance", json=mean_variance_request)

        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "data" in data
        assert "error" in data
        assert "timestamp" in data
        assert data["success"] is True
        assert data["error"] is None

    def test_error_response_format(self, mean_variance_request):
        """Test error response format."""
        mean_variance_request["strategy"] = "efficient_return"
        mean_variance_request["target_return"] = None

        response = client.post("/optimize/mean-variance", json=mean_variance_request)

        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "data" in data
        assert "error" in data
        assert "timestamp" in data
        assert data["success"] is False
        assert data["error"] is not None
        assert isinstance(data["error"], str)
