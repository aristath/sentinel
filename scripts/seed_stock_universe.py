#!/usr/bin/env python3
"""
Seed stock universe from JSON export.

Usage:
    python scripts/seed_stock_universe.py ~/STOCKS-UNIVERSE.json

This imports the curated stock universe into config.db.
All other data (trades, positions, prices) will be fetched
from external APIs by the normal sync jobs.
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database.manager import (  # noqa: E402
    get_db_manager,
    init_databases,
    shutdown_databases,
)


async def seed_stocks(json_path: Path):
    """Import stocks from JSON into config.db."""

    # Load JSON
    print(f"Loading stock universe from: {json_path}")
    with open(json_path) as f:
        stocks = json.load(f)

    print(f"Found {len(stocks)} stocks")

    # Initialize database
    data_dir = Path(__file__).parent.parent / "data"
    await init_databases(data_dir)

    db_manager = get_db_manager()
    now = datetime.now().isoformat()

    # Insert stocks
    inserted = 0
    skipped = 0

    async with db_manager.config.transaction() as conn:
        for stock in stocks:
            try:
                await conn.execute(
                    """
                    INSERT OR REPLACE INTO stocks
                    (symbol, yahoo_symbol, name, industry, geography,
                     priority_multiplier, min_lot, active, allow_buy, allow_sell,
                     currency, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        stock["symbol"],
                        stock.get("yahoo_symbol"),
                        stock["name"],
                        stock.get("industry"),
                        stock["geography"],
                        stock.get("priority_multiplier", 1.0),
                        stock.get("min_lot", 1),
                        stock.get("active", 1),
                        stock.get("allow_buy", 1),
                        stock.get("allow_sell", 0),
                        stock.get("currency"),
                        now,
                        now,
                    ),
                )
                inserted += 1
            except Exception as e:
                print(f"  Error inserting {stock['symbol']}: {e}")
                skipped += 1

    print("\nSeeding complete:")
    print(f"  Inserted: {inserted}")
    print(f"  Skipped:  {skipped}")

    # Show summary by geography
    result = await db_manager.config.fetchall(
        "SELECT geography, COUNT(*) as cnt, SUM(active) as active FROM stocks GROUP BY geography"
    )
    print("\nBy geography:")
    for row in result:
        print(f"  {row['geography']}: {row['cnt']} total, {row['active']} active")

    await shutdown_databases()
    print("\nDone. Run the sync jobs to populate trades, positions, and prices.")


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/seed_stock_universe.py <path-to-json>")
        print("Example: python scripts/seed_stock_universe.py ~/STOCKS-UNIVERSE.json")
        sys.exit(1)

    json_path = Path(sys.argv[1]).expanduser()

    if not json_path.exists():
        print(f"Error: File not found: {json_path}")
        sys.exit(1)

    asyncio.run(seed_stocks(json_path))


if __name__ == "__main__":
    main()
