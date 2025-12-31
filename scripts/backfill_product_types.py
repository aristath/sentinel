"""Backfill product_type for existing securities in the database.

WHEN TO RUN:
- After deploying migration v9 (adds product_type column)
- For existing installations upgrading from securities-only to multi-product support
- Fresh installations do NOT need this (product_type set on security creation)

WHAT IT DOES:
1. Queries all securities from the database
2. For each security, fetches product type from Yahoo Finance
3. Uses heuristics to classify ETCs vs ETFs (see ProductType.from_yahoo_quote_type)
4. Updates the database with detected types
5. Reports statistics and securities needing manual review

SAFETY:
- Safe to run multiple times (idempotent)
- Does not modify securities that already have product_type set (unless --force flag)
- Makes API calls to Yahoo Finance (rate limiting may apply)
- Database updates are committed per security (partial progress preserved on failure)

USAGE:
    # Dry run (show what would be updated without changing database):
    python scripts/backfill_product_types.py --dry-run

    # Normal run (skip securities with product_type already set):
    python scripts/backfill_product_types.py

    # Force update all securities (re-detect even if product_type set):
    python scripts/backfill_product_types.py --force

MANUAL REVIEW NEEDED:
Some securities may return UNKNOWN or ambiguous types from Yahoo Finance.
The script will list these at the end for manual classification via:
    PUT /api/securities/{symbol} with {"product_type": "ETF"}

See: docs/MIGRATION_GUIDE.md for deployment instructions
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime

from app.core.database.manager import DatabaseManager
from app.domain.value_objects.product_type import ProductType
from app.infrastructure.external import yahoo_finance as yahoo

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def backfill_product_types(dry_run: bool = False, force: bool = False):
    """Backfill product types for all securities in the database.

    Args:
        dry_run: If True, show what would be updated without changing database
        force: If True, re-detect product_type even for securities that already have it set
    """
    db_manager = DatabaseManager()
    await db_manager.init()

    config_db = await db_manager.get_config_db()

    # Get all securities
    securities = await config_db.fetchall(
        """
        SELECT symbol, name, yahoo_symbol, isin, product_type, country, industry
        FROM securities
        ORDER BY symbol
        """
    )

    total_stocks = len(securities)
    logger.info(f"Found {total_stocks} securities in database")
    if dry_run:
        logger.info("DRY RUN MODE - No database changes will be made")

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

    for security in securities:
        symbol = security["symbol"]
        name = security["name"]
        yahoo_symbol = security["yahoo_symbol"]
        isin = security["isin"]
        current_product_type = security["product_type"]
        country = security["country"]
        industry = security["industry"]

        # Skip if already has product_type (unless force mode)
        if current_product_type and not force:
            stats["already_set"] += 1
            logger.info(f"  {symbol}: Already set to {current_product_type}")
            try:
                pt = ProductType.from_string(current_product_type)
                stats[pt] += 1
            except (ValueError, KeyError):
                pass
            continue

        # Detect product type
        action = "Would detect" if dry_run else "Detecting"
        logger.info(f"  {symbol}: {action} product type...")
        try:
            product_type = yahoo.get_product_type(symbol, yahoo_symbol, name)

            # Update database (unless dry run)
            if not dry_run:
                await config_db.execute(
                    "UPDATE securities SET product_type = ?, updated_at = ? WHERE symbol = ?",
                    (product_type.value, datetime.now().isoformat(), symbol),
                )
                await config_db.commit()

            stats[product_type] += 1
            stats["updated"] += 1
            action = "Would set" if dry_run else "Set"
            logger.info(f"  {symbol}: {action} to {product_type.value}")

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
    if dry_run:
        print("BACKFILL SUMMARY (DRY RUN - No Changes Made)")
    else:
        print("BACKFILL SUMMARY")
    print("=" * 80)
    print(f"Total securities: {total_stocks}")
    print(f"Already had product_type: {stats['already_set']}")
    action = "Would update" if dry_run else "Updated"
    print(f"{action}: {stats['updated']}")
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
        print("To manually update a security's product type:")
        print('  curl -X PUT "http://localhost:8000/api/securities/{symbol}" \\')
        print('       -H "Content-Type: application/json" \\')
        print('       -d \'{"product_type": "ETC"}\'')
        print()

    await db_manager.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Backfill product_type for existing securities in the database"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without changing database",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-detect product_type even for securities that already have it set",
    )

    args = parser.parse_args()

    try:
        asyncio.run(backfill_product_types(dry_run=args.dry_run, force=args.force))
    except KeyboardInterrupt:
        print("\n\nBackfill interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Backfill failed: {e}")
        sys.exit(1)
