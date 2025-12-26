#!/usr/bin/env python3
"""Seed the database with stock universe from JSON."""

import asyncio
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import aiosqlite  # noqa: E402

from app.database import SCHEMA  # noqa: E402

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "trader.db"
STOCKS_JSON = DATA_DIR / "stocks.json"


async def seed_stocks():
    """Load stocks from JSON and insert into database."""
    # Ensure data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with open(STOCKS_JSON) as f:
        data = json.load(f)

    async with aiosqlite.connect(DB_PATH) as db:
        # Initialize schema
        await db.executescript(SCHEMA)
        await db.commit()
        print("Database schema initialized")
        for stock in data["stocks"]:
            await db.execute(
                """
                INSERT OR REPLACE INTO stocks (symbol, yahoo_symbol, name, industry, geography, active)
                VALUES (?, ?, ?, ?, ?, 1)
                """,
                (
                    stock["symbol"],
                    stock.get("yahoo_symbol"),
                    stock["name"],
                    stock.get("industry"),
                    stock["geography"],
                ),
            )
        await db.commit()
        print(f"Seeded {len(data['stocks'])} stocks")


if __name__ == "__main__":
    asyncio.run(seed_stocks())
