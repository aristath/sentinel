"""API endpoint tests."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "tradernet-service"
    assert "version" in data
    assert "timestamp" in data
    assert "tradernet_connected" in data


def test_get_pending_orders():
    """Test get pending orders endpoint."""
    response = client.get("/api/trading/pending-orders")
    assert response.status_code == 200
    data = response.json()
    assert "success" in data
    assert "data" in data
    assert "timestamp" in data


def test_get_portfolio_positions():
    """Test get portfolio positions endpoint."""
    response = client.get("/api/portfolio/positions")
    assert response.status_code == 200
    data = response.json()
    assert "success" in data
    assert "data" in data


def test_get_cash_balances():
    """Test get cash balances endpoint."""
    response = client.get("/api/portfolio/cash-balances")
    assert response.status_code == 200
    data = response.json()
    assert "success" in data
    assert "data" in data


def test_place_order_validation():
    """Test place order request validation."""
    # Missing required fields
    response = client.post("/api/trading/place-order", json={})
    assert response.status_code == 422  # Validation error

    # Invalid side
    response = client.post("/api/trading/place-order", json={
        "symbol": "AAPL.US",
        "side": "INVALID",
        "quantity": 10
    })
    assert response.status_code == 422


def test_get_quote():
    """Test get quote endpoint."""
    response = client.get("/api/market-data/quote/AAPL.US")
    assert response.status_code == 200
    data = response.json()
    assert "success" in data


def test_find_symbol():
    """Test find symbol endpoint."""
    response = client.get("/api/securities/find?symbol=AAPL")
    assert response.status_code == 200
    data = response.json()
    assert "success" in data
    assert "data" in data


def test_get_executed_trades():
    """Test get executed trades endpoint."""
    response = client.get("/api/transactions/executed-trades?limit=50")
    assert response.status_code == 200
    data = response.json()
    assert "success" in data
    assert "data" in data


def test_batch_quotes():
    """Test batch quotes endpoint."""
    response = client.post("/api/market-data/quotes", json={
        "symbols": ["AAPL.US", "TSLA.US"]
    })
    assert response.status_code == 200
    data = response.json()
    assert "success" in data


def test_get_historical():
    """Test get historical data endpoint."""
    response = client.get(
        "/api/market-data/historical/AAPL.US?start=2025-01-01&end=2025-12-31"
    )
    assert response.status_code == 200
    data = response.json()
    assert "success" in data
