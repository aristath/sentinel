#!/usr/bin/env python3
"""
Migration script for v2 schema changes.

Adds:
- yahoo_symbol column to securities table
- Sets known Asian security Yahoo symbol mappings
"""

import asyncio
from pathlib import Path

import aiosqlite

DB_PATH = Path(__file__).parent.parent / "data" / "trader.db"


async def migrate():
    """Run migration."""
    print(f"Migrating database: {DB_PATH}")

    if not DB_PATH.exists():
        print("Database does not exist. Run seed_stocks.py first.")
        return

    async with aiosqlite.connect(DB_PATH) as db:
        # Check if yahoo_symbol column exists
        cursor = await db.execute("PRAGMA table_info(securities)")
        columns = [row[1] for row in await cursor.fetchall()]

        if "yahoo_symbol" not in columns:
            print("Adding yahoo_symbol column...")
            await db.execute("ALTER TABLE securities ADD COLUMN yahoo_symbol TEXT")
            await db.commit()
            print("Column added.")
        else:
            print("yahoo_symbol column already exists.")

        # Update known Asian security mappings that require explicit Yahoo symbols
        mappings = {
            "XIAO.1810.AS": "1810.HK",
            "BYD.285.AS": "285.HK",
            "CAT.3750.AS": "300750.SZ",
        }

        print("Applying Yahoo symbol mappings...")
        for tradernet, yahoo in mappings.items():
            cursor = await db.execute(
                "UPDATE securities SET yahoo_symbol = ? WHERE symbol = ?",
                (yahoo, tradernet),
            )
            if cursor.rowcount > 0:
                print(f"  {tradernet} -> {yahoo}")

        await db.commit()
        print("Migration complete.")

        # Show current securities
        print("\nCurrent securities:")
        cursor = await db.execute(
            "SELECT symbol, yahoo_symbol, name, industry FROM securities WHERE active = 1"
        )
        for row in await cursor.fetchall():
            yahoo = row[1] or "(convention)"
            industry = row[3] or "(none)"
            print(f"  {row[0]:20} yahoo={yahoo:15} industry={industry}")


if __name__ == "__main__":
    asyncio.run(migrate())
