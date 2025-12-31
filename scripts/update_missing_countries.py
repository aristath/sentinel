#!/usr/bin/env python3
"""Update missing country data for stocks based on exchange names."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database.manager import get_db_manager
from app.modules.universe.database.security_repository import SecurityRepository


async def update_missing_countries():
    """Update missing country data using exchange-to-country mapping."""
    db_manager = get_db_manager()
    stock_repo = SecurityRepository()

    # Exchange to country mapping
    exchange_to_country = {
        "Athens": "Greece",
        "LSE": "United Kingdom",
        "Stuttgart": "Germany",
    }

    # Get stocks missing country but with exchange name
    cursor = await db_manager.config.execute(
        """SELECT symbol, fullExchangeName FROM securities
        WHERE active = 1 AND country IS NULL AND fullExchangeName IS NOT NULL
        ORDER BY symbol"""
    )
    rows = await cursor.fetchall()

    updated = 0
    for symbol, exchange in rows:
        if exchange in exchange_to_country:
            country = exchange_to_country[exchange]
            print(f"Updating {symbol}: setting country = {country} (from exchange {exchange})")
            await stock_repo.update(symbol, country=country)
            updated += 1
        else:
            print(f"Warning: {symbol} has exchange '{exchange}' not in mapping")

    print(f"\nUpdated {updated} stocks with country data")
    return updated


async def main():
    """Main function."""
    await update_missing_countries()


if __name__ == "__main__":
    asyncio.run(main())
