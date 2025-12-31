#!/usr/bin/env python3
"""Script to fix missing country data for securities based on exchange names.

This script uses the exchange-to-country mapping to populate missing country fields.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database.manager import get_db_manager
from app.modules.universe.database.security_repository import SecurityRepository


async def fix_missing_countries():
    """Fix missing country data by inferring from exchange names."""
    db_manager = get_db_manager()
    security_repo = SecurityRepository()

    # Exchange to country mapping (from stocks_data_sync.py)
    exchange_to_country = {
        "Amsterdam": "Netherlands",
        "Athens": "Greece",
        "Brussels": "Belgium",
        "Copenhagen": "Denmark",
        "Frankfurt": "Germany",
        "Helsinki": "Finland",
        "Hong Kong": "Hong Kong",
        "Lisbon": "Portugal",
        "London": "United Kingdom",
        "LSE": "United Kingdom",
        "Madrid": "Spain",
        "Milan": "Italy",
        "NASDAQ": "United States",
        "NYSE": "United States",
        "NasdaqGS": "United States",
        "NasdaqGM": "United States",
        "Oslo": "Norway",
        "Paris": "France",
        "Stockholm": "Sweden",
        "Swiss": "Switzerland",
        "Tokyo": "Japan",
        "Toronto": "Canada",
        "Vienna": "Austria",
        "XETRA": "Germany",
        "Stuttgart": "Germany",  # Additional mapping
    }

    # Get securities missing country but with exchange name
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
            print(
                f"Updating {symbol}: setting country = {country} (from exchange {exchange})"
            )
            await security_repo.update(symbol, country=country)
            updated += 1
        else:
            print(f"Warning: {symbol} has exchange '{exchange}' not in mapping")

    print(f"\nUpdated {updated} securities with country data")
    return updated


async def check_missing_data():
    """Check which securities are still missing data."""
    db_manager = get_db_manager()

    cursor = await db_manager.config.execute(
        """SELECT symbol, name, country, industry, fullExchangeName, yahoo_symbol, currency
        FROM securities
        WHERE active = 1 AND (country IS NULL OR industry IS NULL OR currency IS NULL)
        ORDER BY symbol"""
    )
    rows = await cursor.fetchall()

    if rows:
        print("\nStocks still missing data:")
        print("Symbol | Country | Industry | Currency | Exchange | Yahoo Symbol")
        print("-" * 80)
        for row in rows:
            symbol, name, country, industry, exchange, yahoo, currency = row
            print(
                f"{symbol:10} | {country or 'NULL':15} | {industry or 'NULL':20} | "
                f"{currency or 'NULL':8} | {exchange or 'NULL':15} | {yahoo or 'NULL'}"
            )
        return len(rows)
    else:
        print("\n✓ All securities have complete data!")
        return 0


async def main():
    """Main function."""
    print("Fixing missing country data...")
    await fix_missing_countries()

    print("\nChecking for remaining missing data...")
    missing = await check_missing_data()

    if missing == 0:
        print("\n✓ All securities now have complete data!")
        return 0
    else:
        print(f"\n⚠ {missing} securities still have missing data")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
