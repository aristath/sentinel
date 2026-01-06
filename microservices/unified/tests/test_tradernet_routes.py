"""Tests for Tradernet routes in unified service."""

from typing import Optional

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Import will fail until we create routers - that's expected in TDD
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
class TestTradernetRoutes:
    """Test Tradernet routes under /api/tradernet prefix."""

    def test_get_pending_orders(self):
        """Test GET /api/tradernet/api/trading/pending-orders."""
        response = client.get("/api/tradernet/api/trading/pending-orders")

        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "data" in data
        assert "timestamp" in data

    def test_get_portfolio_positions(self):
        """Test GET /api/tradernet/api/portfolio/positions."""
        response = client.get("/api/tradernet/api/portfolio/positions")

        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "data" in data

    def test_get_cash_balances(self):
        """Test GET /api/tradernet/api/portfolio/cash-balances."""
        response = client.get("/api/tradernet/api/portfolio/cash-balances")

        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "data" in data

    def test_get_quote(self):
        """Test GET /api/tradernet/api/market-data/quote/{symbol}."""
        response = client.get("/api/tradernet/api/market-data/quote/AAPL.US")

        assert response.status_code == 200
        data = response.json()
        assert "success" in data

    def test_batch_quotes(self):
        """Test POST /api/tradernet/api/market-data/quotes."""
        response = client.post(
            "/api/tradernet/api/market-data/quotes",
            json={"symbols": ["AAPL.US", "TSLA.US"]},
        )

        assert response.status_code == 200
        data = response.json()
        assert "success" in data

    def test_place_order_validation(self):
        """Test POST /api/tradernet/api/trading/place-order validation."""
        # Missing required fields
        response = client.post("/api/tradernet/api/trading/place-order", json={})
        assert response.status_code == 422  # Validation error

        # Invalid side
        response = client.post(
            "/api/tradernet/api/trading/place-order",
            json={"symbol": "AAPL.US", "side": "INVALID", "quantity": 10},
        )
        assert response.status_code == 422
