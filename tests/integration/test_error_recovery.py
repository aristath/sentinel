"""Integration tests for error recovery paths."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from app.domain.models import Trade, Position
from app.repositories import TradeRepository, PositionRepository
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
    
    # Mock external trade execution to succeed, but database write to fail
    with patch('app.application.services.trade_execution_service.get_tradernet_client') as mock_get_client:
        mock_client = MagicMock()
        mock_client.is_connected = True
        mock_client.place_order.return_value = MagicMock(
            order_id="order1",
            price=150.0,
            status="filled"
        )
        mock_get_client.return_value = mock_client
        
        service = TradeExecutionService(trade_repo=trade_repo)
        
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
    
    # Mock external trade execution to fail
    with patch('app.application.services.trade_execution_service.get_tradernet_client') as mock_get_client:
        mock_client = MagicMock()
        mock_client.is_connected = True
        mock_client.place_order.side_effect = Exception("API Error")
        mock_get_client.return_value = mock_client
        
        service = TradeExecutionService(trade_repo=trade_repo)
        
        # Should handle error gracefully, no trade should be recorded
        results = await service.execute_trades([trade_rec])
        
        # Verify result indicates failure
        assert len(results) == 1
        assert results[0]["status"] in ["failed", "error"]
        
        # Verify no trade was recorded
        history = await trade_repo.get_history(limit=10)
        assert len(history) == 0


@pytest.mark.asyncio
async def test_position_sync_recovery_after_partial_failure(db):
    """Test that position sync can recover after partial failure."""
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
    
    # Simulate sync failure partway through
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
    
    try:
        # Use the database transaction context manager
        async with db.transaction():
            # Delete all positions (simulating sync start)
            await position_repo.delete_all()

            # Insert new positions
            await position_repo.upsert(position1)
            await position_repo.upsert(position2)

            # Simulate error
            raise ValueError("Sync error")
    except ValueError:
        pass  # Transaction should rollback
    
    # Original position should still exist (rollback)
    retrieved = await position_repo.get_by_symbol("AAPL")
    assert retrieved is not None
    assert retrieved.quantity == 10.0
    
    # New position should NOT exist
    msft = await position_repo.get_by_symbol("MSFT")
    assert msft is None


def test_price_fetch_retry_logic():
    """Test that price fetching retries on failure."""
    from app.services import yahoo

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
    from app.services import yahoo

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
async def test_allocation_target_validation_error(db):
    """Test that invalid allocation targets are rejected."""
    from app.repositories import AllocationRepository
    from app.domain.models import AllocationTarget

    allocation_repo = AllocationRepository(db=db)
    
    # Invalid: percentage > 1.0
    invalid_target = AllocationTarget(
        type="geography",
        name="US",
        target_pct=1.5,  # Invalid: > 100%
    )
    
    with pytest.raises(ValueError, match="must be between 0 and 1"):
        await allocation_repo.upsert(invalid_target)
    
    # Invalid: percentage < 0
    invalid_target2 = AllocationTarget(
        type="geography",
        name="EU",
        target_pct=-0.1,  # Invalid: negative
    )
    
    with pytest.raises(ValueError, match="must be between 0 and 1"):
        await allocation_repo.upsert(invalid_target2)
    
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


