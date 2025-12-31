#!/usr/bin/env python3
"""
Migration script v3: Add volatility column to scores table
                     Add priority_multiplier column to securities table.

Run this once to add columns for the enhanced algorithm.

Usage:
    python scripts/migrate_v3.py
"""

import asyncio
from pathlib import Path

import aiosqlite


async def migrate():
    """Add volatility column to scores, priority_multiplier to securities."""
    db_path = Path("data/trader.db")

    if not db_path.exists():
        print(f"Database not found at {db_path}")
        return False

    async with aiosqlite.connect(db_path) as db:
        # Check scores table for volatility column
        cursor = await db.execute("PRAGMA table_info(scores)")
        score_columns = [row[1] for row in await cursor.fetchall()]

        if "volatility" not in score_columns:
            await db.execute("ALTER TABLE scores ADD COLUMN volatility REAL")
            print("Added volatility column to scores table")
        else:
            print("Volatility column already exists in scores table")

        # Check securities table for priority_multiplier column
        cursor = await db.execute("PRAGMA table_info(securities)")
        stock_columns = [row[1] for row in await cursor.fetchall()]

        if "priority_multiplier" not in stock_columns:
            await db.execute(
                "ALTER TABLE securities ADD COLUMN priority_multiplier REAL DEFAULT 1.0"
            )
            print("Added priority_multiplier column to securities table")
        else:
            print("Priority_multiplier column already exists in securities table")

        await db.commit()

    return True


if __name__ == "__main__":
    success = asyncio.run(migrate())
    exit(0 if success else 1)
