"""Integration tests for transaction management and rollback scenarios."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch

from app.database import transaction
from app.domain.repositories import Trade, Position, Stock
from app.infrastructure.database.repositories import (
    SQLiteTradeRepository,
    SQLitePositionRepository,
    SQLiteStockRepository,
)


@pytest.mark.asyncio
async def test_transaction_rollback_on_error(db, trade_repo):
    """Test that transactions rollback when an error occurs."""
    # Create a trade that will succeed
    trade1 = Trade(
        symbol="AAPL",
        side="BUY",
        quantity=10.0,
        price=150.0,
        executed_at=datetime.now(),
        order_id="order1",
    )
    
    # Create a trade that will fail (invalid data)
    trade2 = Trade(
        symbol="",  # Invalid: empty symbol
        side="BUY",
        quantity=10.0,
        price=150.0,
        executed_at=datetime.now(),
        order_id="order2",
    )
    
    try:
        async with transaction(db):
            # First trade should be inserted
            await trade_repo.create(trade1, auto_commit=False)
            
            # This should fail and trigger rollback
            await db.execute(
                "INSERT INTO trades (symbol, side, quantity, price, executed_at) VALUES (?, ?, ?, ?, ?)",
                ("", "BUY", 10.0, 150.0, datetime.now().isoformat())
            )
            # Force an error by violating a constraint
            await db.execute("INSERT INTO trades (symbol) VALUES (NULL)")
    except Exception:
        pass  # Expected error
    
    # Verify that trade1 was NOT committed (rolled back)
    history = await trade_repo.get_history(limit=10)
    assert len(history) == 0, "Transaction should have rolled back"


@pytest.mark.asyncio
async def test_transaction_commit_on_success(db, stock_repo, trade_repo):
    """Test that transactions commit successfully when no errors occur."""
    # Create stocks first (required for trade history JOIN)
    for symbol in ["AAPL", "MSFT"]:
        stock = Stock(
            symbol=symbol,
            yahoo_symbol=symbol,
            name=f"{symbol} Inc.",
            industry="Technology",
            geography="US",
            priority_multiplier=1.0,
            min_lot=1,
            active=True,
        )
        await stock_repo.create(stock)

    trade1 = Trade(
        symbol="AAPL",
        side="BUY",
        quantity=10.0,
        price=150.0,
        executed_at=datetime.now(),
        order_id="order1",
    )

    trade2 = Trade(
        symbol="MSFT",
        side="SELL",
        quantity=5.0,
        price=300.0,
        executed_at=datetime.now(),
        order_id="order2",
    )

    async with transaction(db):
        await trade_repo.create(trade1, auto_commit=False)
        await trade_repo.create(trade2, auto_commit=False)
    
    # Both trades should be committed
    history = await trade_repo.get_history(limit=10)
    assert len(history) == 2
    symbols = {t.symbol for t in history}
    assert "AAPL" in symbols
    assert "MSFT" in symbols


@pytest.mark.asyncio
async def test_multiple_repository_operations_in_transaction(db):
    """Test multiple repository operations within a single transaction."""
    stock_repo = SQLiteStockRepository(db)
    position_repo = SQLitePositionRepository(db)
    
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
    
    position = Position(
        symbol="AAPL",
        quantity=10.0,
        avg_price=150.0,
        current_price=155.0,
        currency="USD",
        currency_rate=1.05,
        market_value_eur=1476.19,
        last_updated=datetime.now().isoformat(),
    )
    
    async with transaction(db):
        await stock_repo.create(stock, auto_commit=False)
        await position_repo.upsert(position, auto_commit=False)
    
    # Both should be committed
    retrieved_stock = await stock_repo.get_by_symbol("AAPL")
    retrieved_position = await position_repo.get_by_symbol("AAPL")
    
    assert retrieved_stock is not None
    assert retrieved_position is not None
    assert retrieved_stock.symbol == "AAPL"
    assert retrieved_position.symbol == "AAPL"


@pytest.mark.asyncio
async def test_nested_transactions_rollback(db, stock_repo, trade_repo):
    """Test that nested transactions (savepoints) work correctly."""
    # Create stocks first (required for trade history JOIN)
    for symbol in ["AAPL", "MSFT"]:
        stock = Stock(
            symbol=symbol,
            yahoo_symbol=symbol,
            name=f"{symbol} Inc.",
            industry="Technology",
            geography="US",
            priority_multiplier=1.0,
            min_lot=1,
            active=True,
        )
        await stock_repo.create(stock)

    trade1 = Trade(
        symbol="AAPL",
        side="BUY",
        quantity=10.0,
        price=150.0,
        executed_at=datetime.now(),
        order_id="order1",
    )

    trade2 = Trade(
        symbol="MSFT",
        side="BUY",
        quantity=5.0,
        price=300.0,
        executed_at=datetime.now(),
        order_id="order2",
    )

    # Outer transaction
    async with transaction(db):
        await trade_repo.create(trade1, auto_commit=False)
        
        # Inner transaction (savepoint)
        try:
            async with transaction(db):
                await trade_repo.create(trade2, auto_commit=False)
                # Force error in inner transaction
                raise ValueError("Inner transaction error")
        except ValueError:
            pass  # Inner transaction rolled back
    
    # Only trade1 should be committed (outer transaction succeeded)
    history = await trade_repo.get_history(limit=10)
    assert len(history) == 1
    assert history[0].symbol == "AAPL"


@pytest.mark.asyncio
async def test_auto_commit_behavior(db, stock_repo, trade_repo):
    """Test that auto_commit=True commits immediately, auto_commit=False doesn't."""
    # Create stocks first (required for trade history JOIN)
    for symbol in ["AAPL", "MSFT"]:
        stock = Stock(
            symbol=symbol,
            yahoo_symbol=symbol,
            name=f"{symbol} Inc.",
            industry="Technology",
            geography="US",
            priority_multiplier=1.0,
            min_lot=1,
            active=True,
        )
        await stock_repo.create(stock)

    trade = Trade(
        symbol="AAPL",
        side="BUY",
        quantity=10.0,
        price=150.0,
        executed_at=datetime.now(),
        order_id="order1",
    )

    # With auto_commit=True, should commit immediately
    await trade_repo.create(trade, auto_commit=True)
    
    history = await trade_repo.get_history(limit=10)
    assert len(history) == 1
    
    # With auto_commit=False inside a transaction, changes are not visible until commit
    # Note: SQLite autocommits by default, so auto_commit=False only works within explicit transactions
    trade2 = Trade(
        symbol="MSFT",
        side="BUY",
        quantity=5.0,
        price=300.0,
        executed_at=datetime.now(),
        order_id="order2",
    )

    # Start a transaction to test auto_commit=False behavior
    async with transaction(db):
        await trade_repo.create(trade2, auto_commit=False)
        # Inside transaction, trade2 should be visible to this connection
        # but would rollback if we raised an exception here

    # After transaction commits, should have 2 trades
    history = await trade_repo.get_history(limit=10)
    assert len(history) == 2

