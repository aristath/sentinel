"""Integration tests for repositories."""

from datetime import datetime

import pytest

from app.domain.models import (
    AllocationTarget,
    PortfolioSnapshot,
    Position,
    Security,
    SecurityScore,
    Trade,
)


@pytest.mark.asyncio
async def test_stock_repository_create_and_get(security_repo):
    """Test creating and retrieving a security."""
    security = Security(
        symbol="AAPL",
        yahoo_symbol="AAPL",
        name="Apple Inc.",
        industry="Consumer Electronics",
        country="United States",
        priority_multiplier=1.0,
        min_lot=1,
        active=True,
    )

    await security_repo.create(security)

    retrieved = await security_repo.get_by_symbol("AAPL")
    assert retrieved is not None
    assert retrieved.symbol == "AAPL"
    assert retrieved.name == "Apple Inc."


@pytest.mark.asyncio
async def test_stock_repository_get_all_active(security_repo):
    """Test getting all active securities."""
    stock1 = Security(
        symbol="AAPL",
        yahoo_symbol="AAPL",
        name="Apple Inc.",
        industry="Consumer Electronics",
        country="United States",
        priority_multiplier=1.0,
        min_lot=1,
        active=True,
    )
    stock2 = Security(
        symbol="MSFT",
        yahoo_symbol="MSFT",
        name="Microsoft Corp.",
        industry="Consumer Electronics",
        country="United States",
        priority_multiplier=1.0,
        min_lot=1,
        active=False,  # Inactive
    )

    await security_repo.create(stock1)
    await security_repo.create(stock2)

    active_stocks = await security_repo.get_all_active()
    assert len(active_stocks) == 1
    assert active_stocks[0].symbol == "AAPL"


@pytest.mark.asyncio
async def test_position_repository_upsert(position_repo):
    """Test upserting a position."""
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

    await position_repo.upsert(position)

    retrieved = await position_repo.get_by_symbol("AAPL")
    assert retrieved is not None
    assert retrieved.quantity == 10.0
    assert retrieved.current_price == 155.0


@pytest.mark.asyncio
async def test_portfolio_repository_create_and_get(portfolio_repo):
    """Test creating and retrieving portfolio snapshots."""
    snapshot = PortfolioSnapshot(
        date="2024-01-01",
        total_value=10000.0,
        cash_balance=1000.0,
        geo_eu_pct=0.5,
        geo_asia_pct=0.3,
        geo_us_pct=0.2,
    )

    await portfolio_repo.upsert(snapshot)

    latest = await portfolio_repo.get_latest()
    assert latest is not None
    assert latest.total_value == 10000.0
    assert latest.cash_balance == 1000.0


@pytest.mark.asyncio
async def test_allocation_repository_upsert_and_get(allocation_repo):
    """Test creating and retrieving allocation targets."""
    # Create allocation targets
    target_de = AllocationTarget(
        type="country",
        name="Germany",
        target_pct=0.33,
    )
    target_us = AllocationTarget(
        type="country",
        name="United States",
        target_pct=0.33,
    )

    await allocation_repo.upsert(target_de)
    await allocation_repo.upsert(target_us)

    targets = await allocation_repo.get_all()
    assert len(targets) >= 2
    assert "country:Germany" in targets
    assert "country:United States" in targets
    assert targets["country:Germany"] == 0.33


@pytest.mark.asyncio
async def test_score_repository_upsert(score_repo):
    """Test upserting a score."""
    score = SecurityScore(
        symbol="AAPL",
        quality_score=0.8,
        opportunity_score=0.7,
        analyst_score=0.6,
        total_score=0.7,
        calculated_at=datetime.now(),
    )

    await score_repo.upsert(score)

    retrieved = await score_repo.get_by_symbol("AAPL")
    assert retrieved is not None
    assert retrieved.total_score == 0.7
    assert retrieved.quality_score == 0.8


@pytest.mark.asyncio
async def test_trade_repository_create(security_repo, trade_repo):
    """Test creating a trade."""
    # Create security first (required for trade history JOIN)
    security = Security(
        symbol="AAPL",
        yahoo_symbol="AAPL",
        name="Apple Inc.",
        industry="Consumer Electronics",
        country="United States",
        priority_multiplier=1.0,
        min_lot=1,
        active=True,
    )
    await security_repo.create(security)

    trade = Trade(
        symbol="AAPL",
        side="BUY",
        quantity=10.0,
        price=150.0,
        executed_at=datetime.now(),
        order_id="12345",
    )

    await trade_repo.create(trade)

    history = await trade_repo.get_history(limit=10)
    assert len(history) == 1
    assert history[0].symbol == "AAPL"
    assert history[0].side == "BUY"
