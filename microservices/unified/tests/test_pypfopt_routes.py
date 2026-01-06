"""Tests for PyPFOpt routes in unified service."""

import pytest
from fastapi.testclient import TestClient

# Import will fail until we create routers - that's expected in TDD
try:
    from app.main import app
except ImportError:
    app = None

if app:
    client = TestClient(app)
else:
    client = None


@pytest.fixture
def mean_variance_request():
    """Sample mean-variance optimization request."""
    return {
        "expected_returns": {"AAPL": 0.12, "MSFT": 0.10, "GOOGL": 0.15},
        "covariance_matrix": [
            [0.04, 0.02, 0.01],
            [0.02, 0.05, 0.015],
            [0.01, 0.015, 0.03],
        ],
        "symbols": ["AAPL", "MSFT", "GOOGL"],
        "weight_bounds": [[0.02, 0.50], [0.02, 0.50], [0.02, 0.50]],
        "sector_constraints": [],
        "strategy": "min_volatility",
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
                "GOOGL": [0.02, -0.005, 0.01],
            },
        }
    }


@pytest.fixture
def covariance_request():
    """Sample covariance calculation request."""
    return {
        "prices": {
            "dates": ["2025-01-01", "2025-01-02", "2025-01-03"],
            "data": {"AAPL": [150.0, 151.5, 152.0], "MSFT": [380.0, 382.5, 381.0]},
        }
    }


@pytest.mark.skipif(client is None, reason="App not yet implemented")
class TestPyPFOptRoutes:
    """Test PyPFOpt routes under /api/pypfopt prefix."""

    def test_optimize_mean_variance(self, mean_variance_request):
        """Test POST /api/pypfopt/optimize/mean-variance."""
        response = client.post(
            "/api/pypfopt/optimize/mean-variance", json=mean_variance_request
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "weights" in data["data"]
        assert "strategy_used" in data["data"]
        assert data["data"]["strategy_used"] == "min_volatility"
        assert len(data["data"]["weights"]) == 3

    def test_optimize_hrp(self, hrp_request):
        """Test POST /api/pypfopt/optimize/hrp."""
        response = client.post("/api/pypfopt/optimize/hrp", json=hrp_request)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "weights" in data["data"]
        assert len(data["data"]["weights"]) == 3

    def test_optimize_progressive(self, mean_variance_request):
        """Test POST /api/pypfopt/optimize/progressive."""
        mean_variance_request["target_return"] = 0.11
        response = client.post(
            "/api/pypfopt/optimize/progressive", json=mean_variance_request
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "weights" in data["data"]
        assert "strategy_used" in data["data"]
        assert "constraint_level" in data["data"]
        assert "attempts" in data["data"]

    def test_covariance(self, covariance_request):
        """Test POST /api/pypfopt/risk-model/covariance."""
        response = client.post(
            "/api/pypfopt/risk-model/covariance", json=covariance_request
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "covariance_matrix" in data["data"]
        assert "symbols" in data["data"]
        assert len(data["data"]["symbols"]) == 2
