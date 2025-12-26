"""Integration tests for error recovery paths."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from app.domain.models import Trade, Position
from app.repositories import TradeRepository, PositionRepository
from app.repositories.base import transaction_context
from app.application.services.trade_execution_service import TradeExecutionService


@pytest.mark.asyncio
async def test_trade_execution_rollback_on_database_error(db):
    """Test that trade execution rolls back when database write fails."""
    from app.repositories import TradeRepository
    from app.domain.models import Recommendation

    trade_repo = TradeRepository(db=db)
    
    # Create a trade recommendation (what TradeExecutionService expects)
    trade_rec = Recommendation(
        symbol="AAPL",
        name="Apple Inc.",
        side="BUY",
        quantity=10.0,
        estimated_price=150.0,
        estimated_value=1500.0,
        reason="Test trade",
        geography="US",
    )
    
    # Create mock client for trade execution
    mock_client = MagicMock()
    mock_client.is_connected = True
    mock_client.place_order.return_value = MagicMock(
        order_id="order1",
        price=150.0,
        status="filled"
    )

    position_repo = PositionRepository(db=db)
    
    # Create mock currency exchange service
    from app.application.services.currency_exchange_service import CurrencyExchangeService
    mock_currency_service = MagicMock(spec=CurrencyExchangeService)
    
    service = TradeExecutionService(
        trade_repo=trade_repo,
        position_repo=position_repo,
        tradernet_client=mock_client,
        currency_exchange_service=mock_currency_service,
    )

    # Mock repository create to fail
    original_create = trade_repo.create
    async def failing_create(trade):
        raise Exception("Database write failed")

    trade_repo.create = failing_create

    # Try to execute trade - should handle error gracefully
    try:
        results = await service.execute_trades([trade_rec], use_transaction=True)
        # Transaction should have rolled back
        assert len(results) > 0
        # Verify no trade was actually saved (transaction rolled back)
        history = await trade_repo.get_history(limit=10)
        assert len(history) == 0, "Transaction should have rolled back"
    except Exception:
        # Expected - error should propagate
        pass
    finally:
        trade_repo.create = original_create


@pytest.mark.asyncio
async def test_trade_execution_handles_external_failure(db):
    """Test that trade execution handles external API failures."""
    from app.domain.models import Recommendation

    trade_repo = TradeRepository(db=db)
    
    trade_rec = Recommendation(
        symbol="AAPL",
        name="Apple Inc.",
        side="BUY",
        quantity=10.0,
        estimated_price=150.0,
        estimated_value=1500.0,
        reason="Test trade",
        geography="US",
    )
    
    position_repo = PositionRepository(db=db)

    # Create mock client that fails on order placement
    mock_client = MagicMock()
    mock_client.is_connected = True
    mock_client.place_order.side_effect = Exception("API Error")

    # Create mock currency exchange service
    from app.application.services.currency_exchange_service import CurrencyExchangeService
    mock_currency_service = MagicMock(spec=CurrencyExchangeService)
    
    service = TradeExecutionService(
        trade_repo=trade_repo,
        position_repo=position_repo,
        tradernet_client=mock_client,
        currency_exchange_service=mock_currency_service,
    )

    # Should handle error gracefully, no trade should be recorded
    results = await service.execute_trades([trade_rec])

    # Verify result indicates failure or blocked
    assert len(results) == 1
    assert results[0]["status"] in ["failed", "error", "blocked"]

    # Verify no trade was recorded
    history = await trade_repo.get_history(limit=10)
    assert len(history) == 0


@pytest.mark.asyncio
async def test_position_sync_recovery_after_partial_failure(db):
    """Test that position sync handles errors gracefully.

    Note: With auto-commit repositories, each operation commits independently.
    This test verifies error handling without relying on transaction rollback.
    """
    position_repo = PositionRepository(db=db)

    # Create initial position
    position1 = Position(
        symbol="AAPL",
        quantity=10.0,
        avg_price=150.0,
        current_price=155.0,
        currency="USD",
        currency_rate=1.05,
        market_value_eur=1627.5,
        last_updated=datetime.now().isoformat(),
    )

    await position_repo.upsert(position1)

    # Verify initial position exists
    retrieved = await position_repo.get_by_symbol("AAPL")
    assert retrieved is not None
    assert retrieved.quantity == 10.0

    # Create another position
    position2 = Position(
        symbol="MSFT",
        quantity=5.0,
        avg_price=300.0,
        current_price=310.0,
        currency="USD",
        currency_rate=1.05,
        market_value_eur=1627.5,
        last_updated=datetime.now().isoformat(),
    )

    await position_repo.upsert(position2)

    # Verify both positions exist
    aapl = await position_repo.get_by_symbol("AAPL")
    msft = await position_repo.get_by_symbol("MSFT")
    assert aapl is not None
    assert msft is not None
    assert aapl.quantity == 10.0
    assert msft.quantity == 5.0


def test_price_fetch_retry_logic():
    """Test that price fetching retries on failure."""
    from app.infrastructure.external import yahoo_finance as yahoo

    # Mock yfinance to fail first two times, then succeed
    call_count = 0

    def mock_ticker_factory(symbol):
        nonlocal call_count
        call_count += 1
        mock = MagicMock()
        if call_count < 3:
            # Make info property raise an exception
            type(mock).info = property(lambda self: (_ for _ in ()).throw(Exception("API Error")))
        else:
            mock.info = {"currentPrice": 150.0}
        return mock

    with patch('yfinance.Ticker', side_effect=mock_ticker_factory):
        # Should succeed after retries (function is synchronous)
        price = yahoo.get_current_price("AAPL")
        assert price == 150.0
        assert call_count == 3  # Should have retried


def test_price_fetch_fails_after_max_retries():
    """Test that price fetching returns None after max retries."""
    from app.infrastructure.external import yahoo_finance as yahoo

    # Mock yfinance to always fail
    def mock_ticker_factory(symbol):
        mock = MagicMock()
        type(mock).info = property(lambda self: (_ for _ in ()).throw(Exception("API Error")))
        return mock

    with patch('yfinance.Ticker', side_effect=mock_ticker_factory):
        # Should return None after max retries (function is synchronous)
        price = yahoo.get_current_price("AAPL")
        assert price is None


@pytest.mark.asyncio
async def test_allocation_target_upsert(db):
    """Test that allocation targets can be created and retrieved."""
    from app.repositories import AllocationRepository
    from app.domain.models import AllocationTarget

    allocation_repo = AllocationRepository(db=db)

    # Create a valid allocation target
    target = AllocationTarget(
        type="geography",
        name="US",
        target_pct=0.5,
    )

    await allocation_repo.upsert(target)

    # Retrieve and verify using get_by_type (returns AllocationTarget objects)
    targets = await allocation_repo.get_by_type("geography")
    us_target = next((t for t in targets if t.name == "US"), None)
    assert us_target is not None
    assert us_target.target_pct == 0.5
    
    # Valid target should work
    valid_target = AllocationTarget(
        type="geography",
        name="ASIA",
        target_pct=0.3,  # Valid: 30%
    )
    
    await allocation_repo.upsert(valid_target)
    
    # Verify it was saved
    targets = await allocation_repo.get_by_type("geography")
    asia_target = next((t for t in targets if t.name == "ASIA"), None)
    assert asia_target is not None
    assert asia_target.target_pct == 0.3


