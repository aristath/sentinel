"""Tests for YFinance routes in unified service."""

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
class TestYFinanceRoutes:
    """Test YFinance routes under /api/yfinance prefix."""

    def test_get_quote(self):
        """Test GET /api/yfinance/api/quotes/{symbol}."""
        response = client.get("/api/yfinance/api/quotes/AAPL.US")

        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "data" in data

    def test_batch_quotes(self):
        """Test POST /api/yfinance/api/quotes/batch."""
        response = client.post(
            "/api/yfinance/api/quotes/batch",
            json={"symbols": ["AAPL.US", "MSFT.US"], "yahoo_overrides": None},
        )

        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "quotes" in data["data"]

    def test_historical_prices_get(self):
        """Test GET /api/yfinance/api/historical/{symbol}."""
        response = client.get(
            "/api/yfinance/api/historical/AAPL.US?period=1y&interval=1d"
        )

        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "prices" in data["data"]

    def test_historical_prices_post(self):
        """Test POST /api/yfinance/api/historical."""
        response = client.post(
            "/api/yfinance/api/historical",
            json={
                "symbol": "AAPL.US",
                "yahoo_symbol": None,
                "period": "1y",
                "interval": "1d",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "prices" in data["data"]

    def test_fundamentals(self):
        """Test GET /api/yfinance/api/fundamentals/{symbol}."""
        response = client.get("/api/yfinance/api/fundamentals/AAPL.US")

        assert response.status_code == 200
        data = response.json()
        assert "success" in data

    def test_analyst_data(self):
        """Test GET /api/yfinance/api/analyst/{symbol}."""
        response = client.get("/api/yfinance/api/analyst/AAPL.US")

        assert response.status_code == 200
        data = response.json()
        assert "success" in data

    def test_security_industry(self):
        """Test GET /api/yfinance/api/security/industry/{symbol}."""
        response = client.get("/api/yfinance/api/security/industry/AAPL.US")

        assert response.status_code == 200
        data = response.json()
        assert "success" in data

    def test_security_country_exchange(self):
        """Test GET /api/yfinance/api/security/country-exchange/{symbol}."""
        response = client.get("/api/yfinance/api/security/country-exchange/AAPL.US")

        assert response.status_code == 200
        data = response.json()
        assert "success" in data

    def test_security_info(self):
        """Test GET /api/yfinance/api/security/info/{symbol}."""
        response = client.get("/api/yfinance/api/security/info/AAPL.US")

        assert response.status_code == 200
        data = response.json()
        assert "success" in data

    def test_lookup_ticker_from_isin(self):
        """Test GET /api/yfinance/api/security/lookup-ticker/{isin}."""
        response = client.get("/api/yfinance/api/security/lookup-ticker/US0378331005")

        assert response.status_code == 200
        data = response.json()
        assert "success" in data

    def test_quote_name(self):
        """Test GET /api/yfinance/api/security/quote-name/{symbol}."""
        response = client.get("/api/yfinance/api/security/quote-name/AAPL.US")

        assert response.status_code == 200
        data = response.json()
        assert "success" in data

    def test_quote_type(self):
        """Test GET /api/yfinance/api/security/quote-type/{symbol}."""
        response = client.get("/api/yfinance/api/security/quote-type/AAPL.US")

        assert response.status_code == 200
        data = response.json()
        assert "success" in data
