#!/usr/bin/env python3
"""
Migration script v4: Add min_lot column to stocks table.

This column specifies the minimum number of shares that must be
purchased for a stock (e.g., 100 for Japanese stocks).

Usage:
    python scripts/migrate_v4.py
"""

import asyncio
from pathlib import Path

import aiosqlite

# Known minimum lot sizes for Asian stocks
KNOWN_LOT_SIZES = {
    # Japanese stocks trade in 100-share lots
    "7203.T": 100,  # Toyota
    "6758.T": 100,  # Sony
    "9984.T": 100,  # SoftBank
    # Korean stocks typically trade in single shares
    "005930.KS": 1,  # Samsung
    # European and US stocks typically trade in single shares
}


async def migrate():
    """Add min_lot column to stocks table."""
    db_path = Path("data/trader.db")

    if not db_path.exists():
        print(f"Database not found at {db_path}")
        return False

    async with aiosqlite.connect(db_path) as db:
        # Check stocks table for min_lot column
        cursor = await db.execute("PRAGMA table_info(securities)")
        stock_columns = [row[1] for row in await cursor.fetchall()]

        if "min_lot" not in stock_columns:
            await db.execute("ALTER TABLE stocks ADD COLUMN min_lot INTEGER DEFAULT 1")
            print("Added min_lot column to stocks table")

            # Update known lot sizes
            for symbol, lot_size in KNOWN_LOT_SIZES.items():
                await db.execute(
                    "UPDATE securities SET min_lot = ? WHERE symbol = ?", (lot_size, symbol)
                )
            print(f"Updated {len(KNOWN_LOT_SIZES)} stocks with known lot sizes")
        else:
            print("min_lot column already exists in stocks table")

        await db.commit()

    return True


if __name__ == "__main__":
    success = asyncio.run(migrate())
    exit(0 if success else 1)
