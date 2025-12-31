"""Backfill product_type for existing stocks in the database.

This script:
1. Queries all stocks without product_type set
2. Fetches product type from Yahoo Finance for each
3. Updates the database with detected types
4. Reports statistics and stocks needing manual review

Usage:
    python scripts/backfill_product_types.py
"""

import asyncio
import logging
from datetime import datetime

from app.core.database.manager import DatabaseManager
from app.domain.value_objects.product_type import ProductType
from app.infrastructure.external import yahoo_finance as yahoo

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def backfill_product_types():
    """Backfill product types for all stocks in the database."""
    db_manager = DatabaseManager()
    await db_manager.init()

    config_db = await db_manager.get_config_db()

    # Get all stocks
    stocks = await config_db.fetchall(
        """
        SELECT symbol, name, yahoo_symbol, isin, product_type, country, industry
        FROM securities
        ORDER BY symbol
        """
    )

    total_stocks = len(stocks)
    logger.info(f"Found {total_stocks} stocks in database")

    # Statistics
    stats = {
        ProductType.EQUITY: 0,
        ProductType.ETF: 0,
        ProductType.ETC: 0,
        ProductType.MUTUALFUND: 0,
        ProductType.UNKNOWN: 0,
        "already_set": 0,
        "updated": 0,
        "failed": 0,
    }

    needs_manual_review = []

    for stock in stocks:
        symbol = stock["symbol"]
        name = stock["name"]
        yahoo_symbol = stock["yahoo_symbol"]
        isin = stock["isin"]
        current_product_type = stock["product_type"]
        country = stock["country"]
        industry = stock["industry"]

        # Skip if already has product_type
        if current_product_type:
            stats["already_set"] += 1
            logger.info(f"  {symbol}: Already set to {current_product_type}")
            try:
                pt = ProductType.from_string(current_product_type)
                stats[pt] += 1
            except (ValueError, KeyError):
                pass
            continue

        # Detect product type
        logger.info(f"  {symbol}: Detecting product type...")
        try:
            product_type = yahoo.get_product_type(symbol, yahoo_symbol, name)

            # Update database
            await config_db.execute(
                "UPDATE securities SET product_type = ?, updated_at = ? WHERE symbol = ?",
                (product_type.value, datetime.now().isoformat(), symbol),
            )
            await config_db.commit()

            stats[product_type] += 1
            stats["updated"] += 1
            logger.info(f"  {symbol}: Set to {product_type.value}")

            # Check if needs manual review
            if product_type == ProductType.UNKNOWN:
                needs_manual_review.append(
                    {
                        "symbol": symbol,
                        "name": name,
                        "reason": "Could not detect product type",
                    }
                )
            elif product_type == ProductType.ETC:
                # ETCs detected by heuristics might need verification
                needs_manual_review.append(
                    {
                        "symbol": symbol,
                        "name": name,
                        "reason": "ETC detected by heuristic - verify accuracy",
                    }
                )
            elif product_type == ProductType.EQUITY and not country:
                # Equity without country is suspicious
                needs_manual_review.append(
                    {
                        "symbol": symbol,
                        "name": name,
                        "reason": "EQUITY type but missing country",
                    }
                )

        except Exception as e:
            logger.error(f"  {symbol}: Failed to detect product type: {e}")
            stats["failed"] += 1
            needs_manual_review.append(
                {"symbol": symbol, "name": name, "reason": f"Detection failed: {e}"}
            )

    # Print summary
    print("\n" + "=" * 80)
    print("BACKFILL SUMMARY")
    print("=" * 80)
    print(f"Total stocks: {total_stocks}")
    print(f"Already had product_type: {stats['already_set']}")
    print(f"Updated: {stats['updated']}")
    print(f"Failed: {stats['failed']}")
    print()
    print("Product Type Distribution:")
    print(f"  EQUITY:       {stats[ProductType.EQUITY]}")
    print(f"  ETF:          {stats[ProductType.ETF]}")
    print(f"  ETC:          {stats[ProductType.ETC]}")
    print(f"  MUTUALFUND:   {stats[ProductType.MUTUALFUND]}")
    print(f"  UNKNOWN:      {stats[ProductType.UNKNOWN]}")
    print()

    if needs_manual_review:
        print("=" * 80)
        print(f"STOCKS NEEDING MANUAL REVIEW ({len(needs_manual_review)})")
        print("=" * 80)
        for item in needs_manual_review:
            print(f"  {item['symbol']}: {item['name']}")
            print(f"    Reason: {item['reason']}")
        print()
        print("To manually update a stock's product type:")
        print('  curl -X PUT "http://localhost:8000/api/stocks/{symbol}" \\')
        print('       -H "Content-Type: application/json" \\')
        print('       -d \'{"product_type": "ETC"}\'')
        print()

    await db_manager.close()


if __name__ == "__main__":
    asyncio.run(backfill_product_types())
