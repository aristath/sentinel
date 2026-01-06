"""Tests for unified health check endpoint."""

import pytest
from fastapi.testclient import TestClient

# Import will fail until we create main.py - that's expected in TDD
try:
    from app.main import app
except ImportError:
    app = None

if app:
    client = TestClient(app)
else:
    client = None


@pytest.mark.skipif(client is None, reason="App not yet implemented")
class TestHealthCheck:
    """Test unified health check endpoint."""

    def test_health_check(self):
        """Test GET /health returns healthy status."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "unified-microservice"
        assert data["version"] == "1.0.0"
        assert "timestamp" in data
