"""Pytest configuration and fixtures."""

import pytest
import aiosqlite
import tempfile
import os
from pathlib import Path

from datetime import datetime
from app.database import SCHEMA, apply_migrations
from app.infrastructure.database.repositories import (
    SQLiteStockRepository,
    SQLitePositionRepository,
    SQLitePortfolioRepository,
    SQLiteAllocationRepository,
    SQLiteScoreRepository,
    SQLiteTradeRepository,
)


@pytest.fixture
async def db():
    """Create a temporary in-memory database for testing."""
    # Create temporary database file
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    try:
        # Initialize database with schema and migrations (matching production init_db)
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row

            # Create schema version table first (as init_db does)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL,
                    description TEXT
                )
            """)

            # Apply base schema
            await db.executescript(SCHEMA)

            # Record version 1 for initial schema
            await db.execute(
                "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
                (1, datetime.now().isoformat(), "Initial schema")
            )

            # Apply migrations to add columns added after initial schema
            await apply_migrations(db, current_version=1)
            await db.commit()
            yield db
    finally:
        # Clean up
        if os.path.exists(db_path):
            os.unlink(db_path)


@pytest.fixture
async def stock_repo(db):
    """Create a stock repository instance."""
    return SQLiteStockRepository(db)


@pytest.fixture
async def position_repo(db):
    """Create a position repository instance."""
    return SQLitePositionRepository(db)


@pytest.fixture
async def portfolio_repo(db):
    """Create a portfolio repository instance."""
    return SQLitePortfolioRepository(db)


@pytest.fixture
async def allocation_repo(db):
    """Create an allocation repository instance."""
    return SQLiteAllocationRepository(db)


@pytest.fixture
async def score_repo(db):
    """Create a score repository instance."""
    return SQLiteScoreRepository(db)


@pytest.fixture
async def trade_repo(db):
    """Create a trade repository instance."""
    return SQLiteTradeRepository(db)


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

