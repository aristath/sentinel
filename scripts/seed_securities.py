#!/usr/bin/env python3
"""Seed the database with security universe from JSON."""

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
STOCKS_JSON = DATA_DIR / "securities.json"


async def seed_stocks():
    """Load securities from JSON and insert into database."""
    # Ensure data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with open(STOCKS_JSON) as f:
        data = json.load(f)

    async with aiosqlite.connect(DB_PATH) as db:
        # Initialize schema
        await db.executescript(SCHEMA)
        await db.commit()
        print("Database schema initialized")
        for security in data["securities"]:
            await db.execute(
                """
                INSERT OR REPLACE INTO securities (symbol, yahoo_symbol, name, industry, geography, active)
                VALUES (?, ?, ?, ?, ?, 1)
                """,
                (
                    security["symbol"],
                    security.get("yahoo_symbol"),
                    security["name"],
                    security.get("industry"),
                    security["geography"],
                ),
            )
        await db.commit()
        print(f"Seeded {len(data['securities'])} securities")


if __name__ == "__main__":
    asyncio.run(seed_stocks())
