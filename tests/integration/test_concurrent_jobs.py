"""Integration tests for concurrent job execution and locking."""

import asyncio
from datetime import datetime

import pytest

from app.domain.models import Position, Security, Trade
from app.infrastructure.locking import file_lock
from app.repositories import PositionRepository, SecurityRepository, TradeRepository


@pytest.mark.asyncio
async def test_file_lock_prevents_concurrent_execution():
    """Test that file locks prevent concurrent execution of critical operations."""
    lock_name = "test_concurrent_lock"
    execution_order = []

    async def operation1():
        async with file_lock(lock_name, timeout=5.0):
            execution_order.append("start1")
            await asyncio.sleep(0.1)
            execution_order.append("end1")

    async def operation2():
        async with file_lock(lock_name, timeout=5.0):
            execution_order.append("start2")
            await asyncio.sleep(0.1)
            execution_order.append("end2")

    # Run both operations concurrently
    await asyncio.gather(operation1(), operation2())

    # Operations should not interleave
    assert execution_order == [
        "start1",
        "end1",
        "start2",
        "end2",
    ] or execution_order == ["start2", "end2", "start1", "end1"]


@pytest.mark.asyncio
async def test_file_lock_timeout():
    """Test that file locks timeout when held too long."""
    lock_name = "test_timeout_lock"

    async def long_operation():
        async with file_lock(lock_name, timeout=1.0):
            await asyncio.sleep(2.0)  # Hold lock longer than timeout

    async def waiting_operation():
        await asyncio.sleep(0.1)  # Wait a bit for first operation to acquire lock
        try:
            async with file_lock(lock_name, timeout=0.5):
                pytest.fail("Should have timed out")
        except TimeoutError:
            pass  # Expected

    # Start long operation
    task1 = asyncio.create_task(long_operation())
    # Try to acquire lock (should timeout)
    await waiting_operation()
    # Wait for long operation to complete
    await task1


@pytest.mark.asyncio
async def test_concurrent_position_updates_with_lock(db):
    """Test that concurrent position updates are serialized with locking."""
    position_repo = PositionRepository(db=db)
    updates_completed = []

    async def update_position(symbol, quantity, delay):
        async with file_lock("portfolio_sync", timeout=5.0):
            position = Position(
                symbol=symbol,
                quantity=quantity,
                avg_price=150.0,
                current_price=155.0,
                currency="USD",
                currency_rate=1.05,
                market_value_eur=quantity * 155.0 * 1.05,
                last_updated=datetime.now().isoformat(),
            )
            await position_repo.upsert(position)
            await asyncio.sleep(delay)
            updates_completed.append(symbol)

    # Run multiple updates concurrently
    await asyncio.gather(
        update_position("AAPL", 10.0, 0.05),
        update_position("MSFT", 5.0, 0.05),
        update_position("GOOGL", 3.0, 0.05),
    )

    # All updates should complete
    assert len(updates_completed) == 3

    # Verify all positions were saved correctly
    aapl = await position_repo.get_by_symbol("AAPL")
    msft = await position_repo.get_by_symbol("MSFT")
    googl = await position_repo.get_by_symbol("GOOGL")

    assert aapl is not None
    assert msft is not None
    assert googl is not None
    assert aapl.quantity == 10.0
    assert msft.quantity == 5.0
    assert googl.quantity == 3.0


@pytest.mark.asyncio
async def test_concurrent_trade_execution_atomicity(db):
    """Test that concurrent trade executions maintain atomicity."""
    # Create securities first (required for trade history JOIN)
    security_repo = SecurityRepository(db=db)
    for symbol in ["AAPL", "MSFT", "GOOGL"]:
        security = Security(
            symbol=symbol,
            yahoo_symbol=symbol,
            name=f"{symbol} Inc.",
            industry="Consumer Electronics",
            country="United States",
            priority_multiplier=1.0,
            min_lot=1,
            active=True,
        )
        await security_repo.create(security)

    trade_repo = TradeRepository(db=db)
    trades_created = []

    async def create_trade(symbol, side, quantity):
        async with file_lock("rebalance", timeout=5.0):
            trade = Trade(
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=150.0,
                executed_at=datetime.now(),
                order_id=f"order_{symbol}",
            )
            await trade_repo.create(trade)
            await asyncio.sleep(0.05)  # Simulate processing time
            trades_created.append(symbol)

    # Create multiple trades concurrently
    await asyncio.gather(
        create_trade("AAPL", "BUY", 10.0),
        create_trade("MSFT", "BUY", 5.0),
        create_trade("GOOGL", "SELL", 3.0),
    )

    # All trades should be created
    assert len(trades_created) == 3

    # Verify all trades were saved
    history = await trade_repo.get_history(limit=10)
    assert len(history) == 3

    symbols = {t.symbol for t in history}
    assert "AAPL" in symbols
    assert "MSFT" in symbols
    assert "GOOGL" in symbols


# Lock directory setup is handled in conftest.py
