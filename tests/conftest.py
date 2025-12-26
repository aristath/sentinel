"""Pytest configuration and fixtures."""

import os
import tempfile
from datetime import datetime
from pathlib import Path

import aiosqlite
import pytest

from app.infrastructure.database.schemas import (
    CACHE_SCHEMA,
    CALCULATIONS_SCHEMA,
    CONFIG_SCHEMA,
    HISTORY_SCHEMA,
    LEDGER_SCHEMA,
    STATE_SCHEMA,
)
from app.repositories import (
    AllocationRepository,
    PortfolioRepository,
    PositionRepository,
    ScoreRepository,
    StockRepository,
    TradeRepository,
)


@pytest.fixture
async def db():
    """Create a temporary in-memory database for testing.

    For test purposes, we create a single database with all schemas combined
    to simplify fixture management.
    """
    # Create temporary database file
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    try:
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row

            # Apply all schemas to create a unified test database
            await db.executescript(CONFIG_SCHEMA)
            await db.executescript(LEDGER_SCHEMA)
            await db.executescript(STATE_SCHEMA)
            await db.executescript(CACHE_SCHEMA)
            await db.executescript(CALCULATIONS_SCHEMA)
            await db.executescript(HISTORY_SCHEMA)

            await db.commit()
            yield db
    finally:
        # Clean up
        if os.path.exists(db_path):
            os.unlink(db_path)


@pytest.fixture
async def stock_repo(db):
    """Create a stock repository instance."""
    return StockRepository(db=db)


@pytest.fixture
async def position_repo(db):
    """Create a position repository instance."""
    return PositionRepository(db=db)


@pytest.fixture
async def portfolio_repo(db):
    """Create a portfolio repository instance."""
    return PortfolioRepository(db=db)


@pytest.fixture
async def allocation_repo(db):
    """Create an allocation repository instance."""
    return AllocationRepository(db=db)


@pytest.fixture
async def score_repo(db):
    """Create a score repository instance."""
    return ScoreRepository(db=db)


@pytest.fixture
async def trade_repo(db):
    """Create a trade repository instance."""
    return TradeRepository(db=db)


@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch, tmp_path):
    """Setup test environment variables and directories."""
    # Set lock directory to temporary path for tests
    lock_dir = tmp_path / "locks"
    lock_dir.mkdir()
    monkeypatch.setenv("LOCK_DIR", str(lock_dir))

    # Ensure LOCK_DIR is updated in the module
    from app.infrastructure import locking

    locking.LOCK_DIR = lock_dir
    locking.LOCK_DIR.mkdir(parents=True, exist_ok=True)
