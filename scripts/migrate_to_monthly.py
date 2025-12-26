#!/usr/bin/env python3
"""
One-time migration script to:
1. Aggregate existing daily prices into monthly averages
2. Clean up old daily prices (keep 1 year)
3. Clean up old portfolio snapshots (keep 90 days)

Run this script once after deploying the new database structure.

Usage:
    python scripts/migrate_to_monthly.py
"""

import asyncio
import logging
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def migrate_prices_to_monthly(db_path: Path):
    """Aggregate existing daily prices into monthly averages."""
    logger.info("Starting migration: aggregating daily prices to monthly...")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Count existing daily prices
        cursor.execute("SELECT COUNT(*) as count FROM stock_price_history")
        daily_count = cursor.fetchone()["count"]
        logger.info(f"Found {daily_count} daily price records")

        if daily_count == 0:
            logger.info("No daily prices to migrate")
            return

        # Get unique symbols
        cursor.execute("SELECT DISTINCT symbol FROM stock_price_history")
        symbols = [row["symbol"] for row in cursor.fetchall()]
        logger.info(f"Processing {len(symbols)} symbols")

        migrated_count = 0
        for symbol in symbols:
            # Aggregate daily to monthly for this symbol
            cursor.execute(
                """
                INSERT OR REPLACE INTO stock_price_monthly
                (symbol, year_month, avg_close, avg_adj_close, min_price, max_price, source, created_at)
                SELECT
                    symbol,
                    strftime('%Y-%m', date) as year_month,
                    AVG(close_price) as avg_close,
                    AVG(close_price) as avg_adj_close,
                    MIN(low_price) as min_price,
                    MAX(high_price) as max_price,
                    'migrated' as source,
                    datetime('now') as created_at
                FROM stock_price_history
                WHERE symbol = ?
                GROUP BY symbol, strftime('%Y-%m', date)
            """,
                (symbol,),
            )
            migrated_count += cursor.rowcount

        conn.commit()
        logger.info(f"Created {migrated_count} monthly price records")

        # Verify
        cursor.execute("SELECT COUNT(*) as count FROM stock_price_monthly")
        monthly_count = cursor.fetchone()["count"]
        logger.info(f"Total monthly price records: {monthly_count}")

    finally:
        conn.close()


def cleanup_old_daily_prices(db_path: Path, retention_days: int = 365):
    """Remove daily prices older than retention period."""
    logger.info(f"Cleaning up daily prices older than {retention_days} days...")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cutoff = (datetime.now() - timedelta(days=retention_days)).strftime("%Y-%m-%d")

        # Count records to be deleted
        cursor.execute(
            "SELECT COUNT(*) FROM stock_price_history WHERE date < ?", (cutoff,)
        )
        delete_count = cursor.fetchone()[0]

        if delete_count > 0:
            cursor.execute("DELETE FROM stock_price_history WHERE date < ?", (cutoff,))
            conn.commit()
            logger.info(
                f"Deleted {delete_count} old daily price records (before {cutoff})"
            )
        else:
            logger.info("No old daily prices to delete")

    finally:
        conn.close()


def cleanup_old_snapshots(db_path: Path, retention_days: int = 90):
    """Remove portfolio snapshots older than retention period."""
    logger.info(f"Cleaning up snapshots older than {retention_days} days...")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cutoff = (datetime.now() - timedelta(days=retention_days)).strftime("%Y-%m-%d")

        # Count records to be deleted
        cursor.execute(
            "SELECT COUNT(*) FROM portfolio_snapshots WHERE date < ?", (cutoff,)
        )
        delete_count = cursor.fetchone()[0]

        if delete_count > 0:
            cursor.execute("DELETE FROM portfolio_snapshots WHERE date < ?", (cutoff,))
            conn.commit()
            logger.info(
                f"Deleted {delete_count} old snapshot records (before {cutoff})"
            )
        else:
            logger.info("No old snapshots to delete")

    finally:
        conn.close()


def vacuum_database(db_path: Path):
    """Reclaim disk space after deletions."""
    logger.info("Running VACUUM to reclaim disk space...")

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("VACUUM")
        logger.info("VACUUM complete")
    finally:
        conn.close()


def show_stats(db_path: Path):
    """Show database statistics after migration."""
    logger.info("=== Database Statistics ===")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Daily prices
        cursor.execute("SELECT COUNT(*) as count FROM stock_price_history")
        daily_count = cursor.fetchone()["count"]

        cursor.execute(
            "SELECT COUNT(DISTINCT symbol) as count FROM stock_price_history"
        )
        daily_symbols = cursor.fetchone()["count"]

        cursor.execute(
            "SELECT MIN(date) as min, MAX(date) as max FROM stock_price_history"
        )
        daily_range = cursor.fetchone()

        # Monthly prices
        cursor.execute("SELECT COUNT(*) as count FROM stock_price_monthly")
        monthly_count = cursor.fetchone()["count"]

        cursor.execute(
            "SELECT COUNT(DISTINCT symbol) as count FROM stock_price_monthly"
        )
        monthly_symbols = cursor.fetchone()["count"]

        cursor.execute(
            "SELECT MIN(year_month) as min, MAX(year_month) as max FROM stock_price_monthly"
        )
        monthly_range = cursor.fetchone()

        # Snapshots
        cursor.execute("SELECT COUNT(*) as count FROM portfolio_snapshots")
        snapshot_count = cursor.fetchone()["count"]

        logger.info(f"Daily prices: {daily_count} records, {daily_symbols} symbols")
        if daily_range["min"]:
            logger.info(f"  Range: {daily_range['min']} to {daily_range['max']}")

        logger.info(
            f"Monthly prices: {monthly_count} records, {monthly_symbols} symbols"
        )
        if monthly_range["min"]:
            logger.info(f"  Range: {monthly_range['min']} to {monthly_range['max']}")

        logger.info(f"Portfolio snapshots: {snapshot_count} records")

        # File size
        import os

        db_size = os.path.getsize(db_path) / (1024 * 1024)
        logger.info(f"Database size: {db_size:.2f} MB")

    finally:
        conn.close()


def main():
    """Run the migration."""
    db_path = settings.database_path
    logger.info(f"Database path: {db_path}")

    if not Path(db_path).exists():
        logger.error(f"Database not found: {db_path}")
        return 1

    # Show stats before
    logger.info("\n=== BEFORE MIGRATION ===")
    show_stats(db_path)

    # Run migration steps
    logger.info("\n=== RUNNING MIGRATION ===")
    migrate_prices_to_monthly(db_path)
    cleanup_old_daily_prices(db_path, retention_days=365)
    cleanup_old_snapshots(db_path, retention_days=90)
    vacuum_database(db_path)

    # Show stats after
    logger.info("\n=== AFTER MIGRATION ===")
    show_stats(db_path)

    logger.info("\nMigration complete!")
    return 0


if __name__ == "__main__":
    exit(main())
