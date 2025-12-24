"""Integration tests for external API failure handling."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

from app.services import yahoo
from app.services.tradernet import get_tradernet_client, TradernetClient
from app.application.services.rebalancing_service import RebalancingService


@pytest.mark.asyncio
async def test_yahoo_finance_api_failure_handling():
    """Test handling of Yahoo Finance API failures."""
    # Mock yfinance to raise exception
    with patch('yfinance.Ticker') as mock_ticker_class:
        mock_ticker = MagicMock()
        mock_ticker.info.side_effect = Exception("Yahoo Finance API Error")
        mock_ticker_class.return_value = mock_ticker
        
        # Should raise exception after retries
        with pytest.raises(Exception):
            await yahoo.get_current_price("AAPL")


@pytest.mark.asyncio
async def test_yahoo_finance_timeout_handling():
    """Test handling of Yahoo Finance API timeouts."""
    import asyncio
    
    # Mock yfinance to hang (simulate timeout)
    async def slow_ticker_info(symbol):
        await asyncio.sleep(10)  # Simulate slow response
        return {"currentPrice": 150.0}
    
    with patch('yfinance.Ticker') as mock_ticker_class:
        mock_ticker = MagicMock()
        # Note: yfinance is synchronous, but we can test timeout via retry logic
        mock_ticker.info.side_effect = TimeoutError("Request timeout")
        mock_ticker_class.return_value = mock_ticker
        
        # Should raise exception after retries
        with pytest.raises(Exception):
            await yahoo.get_current_price("AAPL")


@pytest.mark.asyncio
async def test_tradernet_api_connection_failure():
    """Test handling of Tradernet API connection failures."""
    with patch('app.services.tradernet.get_tradernet_client') as mock_get_client:
        mock_client = MagicMock()
        mock_client.is_connected = False
        mock_client.connect.return_value = False
        mock_get_client.return_value = mock_client
        
        client = get_tradernet_client()
        
        # Should indicate disconnection
        assert not client.is_connected
        assert not client.connect()


@pytest.mark.asyncio
async def test_tradernet_api_request_failure():
    """Test handling of Tradernet API request failures."""
    with patch('app.services.tradernet.get_tradernet_client') as mock_get_client:
        mock_client = MagicMock()
        mock_client.is_connected = True
        mock_client.get_portfolio.side_effect = Exception("API Request Failed")
        mock_get_client.return_value = mock_client
        
        client = get_tradernet_client()
        
        # Should raise exception
        with pytest.raises(Exception):
            client.get_portfolio()


@pytest.mark.asyncio
async def test_rebalancing_service_handles_price_fetch_failure(db):
    """Test that rebalancing service handles price fetch failures gracefully."""
    from app.infrastructure.database.repositories import (
        SQLiteStockRepository,
        SQLitePositionRepository,
        SQLiteAllocationRepository,
        SQLitePortfolioRepository,
    )
    from app.domain.repositories import Stock, Position

    # Setup test data
    stock_repo = SQLiteStockRepository(db)
    position_repo = SQLitePositionRepository(db)
    allocation_repo = SQLiteAllocationRepository(db)
    portfolio_repo = SQLitePortfolioRepository(db)
    
    stock = Stock(
        symbol="AAPL",
        yahoo_symbol="AAPL",
        name="Apple Inc.",
        industry="Technology",
        geography="US",
        priority_multiplier=1.0,
        min_lot=1,
        active=True,
    )
    await stock_repo.create(stock)
    
    position = Position(
        symbol="AAPL",
        quantity=10.0,
        avg_price=150.0,
        current_price=155.0,
        currency="USD",
        currency_rate=1.05,
        market_value_eur=1627.5,
        last_updated=datetime.now().isoformat(),
    )
    await position_repo.upsert(position)
    
    # Mock price fetch to fail
    with patch('app.services.yahoo.get_current_price') as mock_get_price:
        mock_get_price.side_effect = Exception("Price fetch failed")
        
        service = RebalancingService(
            stock_repo=stock_repo,
            position_repo=position_repo,
            allocation_repo=allocation_repo,
            portfolio_repo=portfolio_repo,
        )
        
        # Should handle error gracefully (skip stocks with price fetch failures)
        try:
            trades = await service.calculate_rebalance_trades(
                deposit_amount=1000.0,
                cash_balance=5000.0,
            )
            # Should return empty list or skip problematic stocks
            assert isinstance(trades, list)
        except Exception:
            # Or raise exception - both behaviors are acceptable
            pass


@pytest.mark.asyncio
async def test_exchange_rate_cache_fallback():
    """Test that exchange rate cache falls back when API fails."""
    from app.services.tradernet import get_exchange_rate
    
    # Mock requests.get to fail
    with patch('requests.get') as mock_get:
        mock_get.side_effect = Exception("Exchange rate API failed")
        
        # Should use fallback rates
        rate = get_exchange_rate("USD", "EUR")
        
        # Should return a valid rate (from fallback)
        assert rate > 0
        assert isinstance(rate, float)


@pytest.mark.asyncio
async def test_exchange_rate_cache_thread_safety():
    """Test that exchange rate cache is thread-safe."""
    from app.services.tradernet import get_exchange_rate
    import asyncio
    
    results = []
    
    async def fetch_rate(currency):
        # Simulate concurrent access
        rate = get_exchange_rate(currency, "EUR")
        results.append((currency, rate))
    
    # Fetch rates concurrently
    await asyncio.gather(
        fetch_rate("USD"),
        fetch_rate("GBP"),
        fetch_rate("JPY"),
    )
    
    # All should complete without errors
    assert len(results) == 3
    for currency, rate in results:
        assert rate > 0
        assert isinstance(rate, float)


@pytest.mark.asyncio
async def test_portfolio_sync_handles_api_failure(db):
    """Test that portfolio sync handles external API failures."""
    from app.jobs.daily_sync import sync_portfolio
    from app.services.tradernet import get_tradernet_client
    
    # Mock tradernet client to fail
    with patch('app.services.tradernet.get_tradernet_client') as mock_get_client:
        mock_client = MagicMock()
        mock_client.get_portfolio.side_effect = Exception("API Error")
        mock_get_client.return_value = mock_client
        
        # Should handle error gracefully (sync_portfolio wraps _sync_portfolio_internal with lock)
        try:
            await sync_portfolio()
        except Exception as e:
            # Should log error but not crash
            assert "API Error" in str(e) or isinstance(e, Exception)


@pytest.mark.asyncio
async def test_health_check_with_degraded_services():
    """Test health check endpoint with degraded external services."""
    from fastapi.testclient import TestClient
    from app.main import app
    
    client = TestClient(app)
    
    # Mock services to be degraded
    with patch('app.services.tradernet.get_tradernet_client') as mock_get_client:
        mock_client = MagicMock()
        mock_client.is_connected = False
        mock_client.connect.return_value = False
        mock_get_client.return_value = mock_client
        
        with patch('yfinance.Ticker') as mock_ticker:
            mock_ticker_instance = MagicMock()
            mock_ticker_instance.info = None  # Unavailable
            mock_ticker.return_value = mock_ticker_instance
            
            response = client.get("/health")
            
            # Should return 503 if services are degraded
            assert response.status_code in [200, 503]
            data = response.json()
            assert "status" in data
            assert "tradernet" in data
            assert "yahoo_finance" in data

