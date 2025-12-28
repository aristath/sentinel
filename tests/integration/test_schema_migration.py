"""Integration tests for database schema migrations."""

import aiosqlite
import pytest

from app.infrastructure.database.schemas import init_config_schema


@pytest.mark.asyncio
async def test_schema_migration_v5_to_v6_adds_portfolio_target_columns():
    """Test that migration from version 5 to 6 adds min/max portfolio target columns."""
    # Create a database with version 5 schema
    async with aiosqlite.connect(":memory:") as db:
        db.row_factory = aiosqlite.Row

        # Create stocks table with version 5 schema (without portfolio target columns)
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS stocks (
                symbol TEXT PRIMARY KEY,
                yahoo_symbol TEXT,
                name TEXT NOT NULL,
                industry TEXT,
                country TEXT,
                fullExchangeName TEXT,
                priority_multiplier REAL DEFAULT 1.0,
                min_lot INTEGER DEFAULT 1,
                active INTEGER DEFAULT 1,
                allow_buy INTEGER DEFAULT 1,
                allow_sell INTEGER DEFAULT 0,
                currency TEXT,
                last_synced TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """
        )

        # Create schema_version table and set to version 5
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL,
                description TEXT
            )
        """
        )
        await db.execute(
            "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
            (5, "2024-01-01T00:00:00", "Version 5 schema"),
        )

        # Insert a test stock
        await db.execute(
            """INSERT INTO stocks
               (symbol, name, created_at, updated_at)
               VALUES (?, ?, ?, ?)""",
            ("AAPL", "Apple Inc.", "2024-01-01T00:00:00", "2024-01-01T00:00:00"),
        )

        await db.commit()

        # Run migration
        await init_config_schema(db)

        # Check that columns were added
        cursor = await db.execute("PRAGMA table_info(stocks)")
        columns = {row[1]: row[2] for row in await cursor.fetchall()}

        assert "min_portfolio_target" in columns
        assert "max_portfolio_target" in columns
        assert columns["min_portfolio_target"] == "REAL"
        assert columns["max_portfolio_target"] == "REAL"

        # Check that existing data is preserved
        row = await db.fetchone("SELECT * FROM stocks WHERE symbol = ?", ("AAPL",))
        assert row is not None
        assert row["symbol"] == "AAPL"
        assert row["name"] == "Apple Inc."
        # New columns should be NULL
        assert row["min_portfolio_target"] is None
        assert row["max_portfolio_target"] is None

        # Check that schema version was updated to 6
        version_row = await db.fetchone("SELECT MAX(version) as v FROM schema_version")
        assert version_row["v"] == 6


@pytest.mark.asyncio
async def test_new_installation_includes_portfolio_target_columns():
    """Test that new installations include portfolio target columns in initial schema."""
    async with aiosqlite.connect(":memory:") as db:
        db.row_factory = aiosqlite.Row

        # Run init on fresh database (version 0)
        await init_config_schema(db)

        # Check that columns exist in stocks table
        cursor = await db.execute("PRAGMA table_info(stocks)")
        columns = {row[1]: row[2] for row in await cursor.fetchall()}

        assert "min_portfolio_target" in columns
        assert "max_portfolio_target" in columns
        assert columns["min_portfolio_target"] == "REAL"
        assert columns["max_portfolio_target"] == "REAL"

        # Check that schema version is 6
        version_row = await db.fetchone("SELECT MAX(version) as v FROM schema_version")
        assert version_row["v"] == 6


@pytest.mark.asyncio
async def test_portfolio_target_columns_are_nullable():
    """Test that portfolio target columns allow NULL values."""
    async with aiosqlite.connect(":memory:") as db:
        db.row_factory = aiosqlite.Row

        await init_config_schema(db)

        # Insert stock without portfolio targets (should be NULL)
        await db.execute(
            """INSERT INTO stocks
               (symbol, name, created_at, updated_at)
               VALUES (?, ?, ?, ?)""",
            ("MSFT", "Microsoft Corp.", "2024-01-01T00:00:00", "2024-01-01T00:00:00"),
        )

        # Insert stock with portfolio targets
        await db.execute(
            """INSERT INTO stocks
               (symbol, name, min_portfolio_target, max_portfolio_target, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                "GOOGL",
                "Alphabet Inc.",
                5.0,
                15.0,
                "2024-01-01T00:00:00",
                "2024-01-01T00:00:00",
            ),
        )

        await db.commit()

        # Verify NULL values are allowed
        row1 = await db.fetchone("SELECT * FROM stocks WHERE symbol = ?", ("MSFT",))
        assert row1["min_portfolio_target"] is None
        assert row1["max_portfolio_target"] is None

        # Verify non-NULL values work
        row2 = await db.fetchone("SELECT * FROM stocks WHERE symbol = ?", ("GOOGL",))
        assert row2["min_portfolio_target"] == 5.0
        assert row2["max_portfolio_target"] == 15.0
