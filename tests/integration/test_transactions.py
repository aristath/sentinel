"""Integration tests for transaction management and rollback scenarios."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.domain.models import Position, Stock, Trade
from app.repositories import (
    PositionRepository,
    StockRepository,
    TradeRepository,
)
from app.repositories.base import transaction_context


@pytest.mark.asyncio
async def test_trade_creation_and_retrieval(db, trade_repo):
    """Test that trades can be created and retrieved."""
    # Create a trade
    trade1 = Trade(
        symbol="AAPL",
        side="BUY",
        quantity=10.0,
        price=150.0,
        executed_at=datetime.now(),
        order_id="order1",
    )

    await trade_repo.create(trade1)

    # Verify trade was committed
    history = await trade_repo.get_history(limit=10)
    assert len(history) == 1
    assert history[0].symbol == "AAPL"
    assert history[0].quantity == 10.0


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

    async with transaction_context(db):
        await trade_repo.create(trade1)
        await trade_repo.create(trade2)

    # Both trades should be committed
    history = await trade_repo.get_history(limit=10)
    assert len(history) == 2
    symbols = {t.symbol for t in history}
    assert "AAPL" in symbols
    assert "MSFT" in symbols


@pytest.mark.asyncio
async def test_multiple_repository_operations_in_transaction(db):
    """Test multiple repository operations within a single transaction."""
    stock_repo = StockRepository(db=db)
    position_repo = PositionRepository(db=db)

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

    async with transaction_context(db):
        await stock_repo.create(stock)
        await position_repo.upsert(position)

    # Both should be committed
    retrieved_stock = await stock_repo.get_by_symbol("AAPL")
    retrieved_position = await position_repo.get_by_symbol("AAPL")

    assert retrieved_stock is not None
    assert retrieved_position is not None
    assert retrieved_stock.symbol == "AAPL"
    assert retrieved_position.symbol == "AAPL"


@pytest.mark.asyncio
async def test_auto_commit_behavior(db, stock_repo, trade_repo):
    """Test that auto_commit=True commits immediately."""
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

    # Trade should commit after create
    await trade_repo.create(trade)

    history = await trade_repo.get_history(limit=10)
    assert len(history) == 1

    # Inside a transaction, changes are committed at the end
    trade2 = Trade(
        symbol="MSFT",
        side="BUY",
        quantity=5.0,
        price=300.0,
        executed_at=datetime.now(),
        order_id="order2",
    )

    async with transaction_context(db):
        await trade_repo.create(trade2)

    # After transaction commits, should have 2 trades
    history = await trade_repo.get_history(limit=10)
    assert len(history) == 2
