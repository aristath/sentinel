"""Database maintenance jobs for long-term reliability.

These jobs ensure the database stays healthy and disk usage is controlled:
- Daily backup of the database
- WAL checkpoint to prevent file growth
- Weekly integrity check
- Cleanup of old daily prices (keep 1 year)
- Cleanup of old portfolio snapshots (keep 90 days)
"""

import logging
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from app.config import settings
from app.database import get_db_connection
from app.infrastructure.locking import file_lock

logger = logging.getLogger(__name__)


async def create_backup():
    """
    Create a backup of the database using SQLite's backup API.

    Runs daily, keeps the last 7 backups.
    """
    async with file_lock("db_backup", timeout=300.0):
        await _create_backup_internal()


async def _create_backup_internal():
    """Internal backup implementation."""
    logger.info("Starting database backup")

    try:
        # Ensure backup directory exists
        backup_dir = Path(settings.database_path).parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)

        # Create timestamped backup filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"trader_{timestamp}.db"

        # Use SQLite backup API (synchronous, but safe)
        source = sqlite3.connect(settings.database_path)
        dest = sqlite3.connect(backup_path)
        source.backup(dest)
        source.close()
        dest.close()

        logger.info(f"Database backup created: {backup_path}")

        # Clean up old backups (keep last N)
        await _cleanup_old_backups(backup_dir)

    except Exception as e:
        logger.error(f"Database backup failed: {e}")
        raise


async def _cleanup_old_backups(backup_dir: Path):
    """Remove old backup files, keeping only the most recent ones."""
    backups = sorted(backup_dir.glob("trader_*.db"), key=os.path.getmtime, reverse=True)

    for old_backup in backups[settings.backup_retention_count:]:
        try:
            old_backup.unlink()
            logger.info(f"Removed old backup: {old_backup.name}")
        except Exception as e:
            logger.warning(f"Failed to remove old backup {old_backup.name}: {e}")


async def checkpoint_wal():
    """
    Run WAL checkpoint to prevent the WAL file from growing unbounded.

    Uses TRUNCATE mode to reset the WAL file completely.
    Runs daily after backup.
    """
    async with file_lock("wal_checkpoint", timeout=60.0):
        await _checkpoint_wal_internal()


async def _checkpoint_wal_internal():
    """Internal WAL checkpoint implementation."""
    logger.info("Running WAL checkpoint")

    try:
        async with get_db_connection() as db:
            # Run checkpoint with TRUNCATE mode
            result = await db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            row = await result.fetchone()
            if row:
                # Returns (busy, log, checkpointed)
                logger.info(f"WAL checkpoint complete: busy={row[0]}, log={row[1]}, checkpointed={row[2]}")
            else:
                logger.info("WAL checkpoint complete")

    except Exception as e:
        logger.error(f"WAL checkpoint failed: {e}")
        raise


async def integrity_check():
    """
    Run database integrity check.

    Runs weekly to ensure database is not corrupted.
    """
    async with file_lock("integrity_check", timeout=600.0):
        await _integrity_check_internal()


async def _integrity_check_internal():
    """Internal integrity check implementation."""
    logger.info("Running database integrity check")

    try:
        async with get_db_connection() as db:
            result = await db.execute("PRAGMA integrity_check")
            row = await result.fetchone()

            if row and row[0] == "ok":
                logger.info("Database integrity check passed")
            else:
                error_msg = row[0] if row else "Unknown error"
                logger.error(f"Database integrity check FAILED: {error_msg}")
                # Could add alerting here

    except Exception as e:
        logger.error(f"Database integrity check failed: {e}")
        raise


async def cleanup_old_daily_prices():
    """
    Remove daily prices older than retention period.

    Keeps 1 year of daily data for sparklines and opportunity scoring.
    Monthly averages are retained indefinitely for CAGR calculations.
    """
    async with file_lock("cleanup_prices", timeout=300.0):
        await _cleanup_old_daily_prices_internal()


async def _cleanup_old_daily_prices_internal():
    """Internal daily price cleanup implementation."""
    logger.info("Cleaning up old daily prices")

    try:
        async with get_db_connection() as db:
            cutoff = (datetime.now() - timedelta(days=settings.daily_price_retention_days)).strftime("%Y-%m-%d")

            # Count records to be deleted
            cursor = await db.execute(
                "SELECT COUNT(*) FROM stock_price_history WHERE date < ?",
                (cutoff,)
            )
            row = await cursor.fetchone()
            delete_count = row[0] if row else 0

            if delete_count > 0:
                # Delete old records
                await db.execute(
                    "DELETE FROM stock_price_history WHERE date < ?",
                    (cutoff,)
                )
                await db.commit()
                logger.info(f"Deleted {delete_count} old daily price records (before {cutoff})")
            else:
                logger.info("No old daily price records to clean up")

    except Exception as e:
        logger.error(f"Daily price cleanup failed: {e}")
        raise


async def cleanup_old_snapshots():
    """
    Remove portfolio snapshots older than retention period.

    Keeps 90 days of daily snapshots for basic tracking.
    """
    async with file_lock("cleanup_snapshots", timeout=60.0):
        await _cleanup_old_snapshots_internal()


async def _cleanup_old_snapshots_internal():
    """Internal snapshot cleanup implementation."""
    logger.info("Cleaning up old portfolio snapshots")

    try:
        async with get_db_connection() as db:
            cutoff = (datetime.now() - timedelta(days=settings.snapshot_retention_days)).strftime("%Y-%m-%d")

            # Count records to be deleted
            cursor = await db.execute(
                "SELECT COUNT(*) FROM portfolio_snapshots WHERE date < ?",
                (cutoff,)
            )
            row = await cursor.fetchone()
            delete_count = row[0] if row else 0

            if delete_count > 0:
                # Delete old records
                await db.execute(
                    "DELETE FROM portfolio_snapshots WHERE date < ?",
                    (cutoff,)
                )
                await db.commit()
                logger.info(f"Deleted {delete_count} old portfolio snapshots (before {cutoff})")
            else:
                logger.info("No old portfolio snapshots to clean up")

    except Exception as e:
        logger.error(f"Snapshot cleanup failed: {e}")
        raise


async def run_daily_maintenance():
    """
    Run all daily maintenance tasks.

    This is the main entry point called by the scheduler.
    Order: backup -> cleanup -> checkpoint
    """
    logger.info("Starting daily maintenance")

    try:
        # 1. Create backup first (before any cleanup)
        await create_backup()

        # 2. Clean up old data
        await cleanup_old_daily_prices()
        await cleanup_old_snapshots()

        # 3. Checkpoint WAL (after cleanup for smaller file)
        await checkpoint_wal()

        logger.info("Daily maintenance complete")

    except Exception as e:
        logger.error(f"Daily maintenance failed: {e}")
        raise


async def run_weekly_maintenance():
    """
    Run weekly maintenance tasks.

    This includes the integrity check which is slower.
    """
    logger.info("Starting weekly maintenance")

    try:
        await integrity_check()
        logger.info("Weekly maintenance complete")

    except Exception as e:
        logger.error(f"Weekly maintenance failed: {e}")
        raise
