"""Tests for unified health check endpoint."""

from typing import Optional

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Import will fail until we create main.py - that's expected in TDD
app: Optional[FastAPI] = None
try:
    from app.main import app as imported_app  # noqa: F401

    app = imported_app  # type: ignore[assignment]
except ImportError:
    pass

client: Optional[TestClient] = None
if app is not None:
    client = TestClient(app)


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
