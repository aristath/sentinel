"""Database maintenance jobs for long-term reliability.

These jobs ensure the databases stay healthy and disk usage is controlled:
- Daily backup of all databases
- WAL checkpoint to prevent file growth
- Weekly integrity check
- Cleanup of old daily prices (keep 1 year)
- Cleanup of old portfolio snapshots (keep 90 days)
"""

import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from app.config import settings
from app.core.database.manager import get_db_manager
from app.core.events import SystemEvent, emit
from app.infrastructure.locking import file_lock
from app.modules.display.services.display_service import set_led4, set_text

logger = logging.getLogger(__name__)


async def create_backup():
    """
    Create a backup of all databases using SQLite's backup API.

    Runs daily, keeps the last 7 backups.
    """
    async with file_lock("db_backup", timeout=300.0):
        await _create_backup_internal()


async def _create_backup_internal():
    """Internal backup implementation."""
    logger.info("Starting database backup")

    emit(SystemEvent.BACKUP_START)
    set_text("BACKING UP DATABASE...")
    set_led4(0, 255, 0)  # Green for processing

    try:
        # Ensure backup directory exists
        backup_dir = settings.data_dir / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Backup core databases
        core_dbs = ["config.db", "ledger.db", "state.db", "cache.db", "calculations.db"]
        for db_name in core_dbs:
            db_path = settings.data_dir / db_name
            if db_path.exists():
                backup_path = (
                    backup_dir / f"{db_name.replace('.db', '')}_{timestamp}.db"
                )
                _backup_database(db_path, backup_path)

        # Backup history databases
        history_dir = settings.data_dir / "history"
        if history_dir.exists():
            history_backup_dir = backup_dir / f"history_{timestamp}"
            history_backup_dir.mkdir(parents=True, exist_ok=True)
            for db_file in history_dir.glob("*.db"):
                backup_path = history_backup_dir / db_file.name
                _backup_database(db_file, backup_path)

        logger.info(f"Database backups created in {backup_dir}")

        # Clean up old backups
        await _cleanup_old_backups(backup_dir)

        emit(SystemEvent.BACKUP_COMPLETE)

    except Exception as e:
        logger.error(f"Database backup failed: {e}")
        error_msg = "BACKUP FAILED"
        emit(SystemEvent.ERROR_OCCURRED, message=error_msg)
        set_text(error_msg)
        raise
    finally:
        set_led4(0, 0, 0)  # Clear LED when done


def _backup_database(source_path: Path, dest_path: Path):
    """Backup a single database file."""
    source = sqlite3.connect(str(source_path))
    dest = sqlite3.connect(str(dest_path))
    source.backup(dest)
    source.close()
    dest.close()


async def _cleanup_old_backups(backup_dir: Path):
    """Remove old backup files, keeping only the most recent ones."""
    import os

    # Clean core database backups
    for prefix in ["config_", "ledger_", "state_", "cache_"]:
        backups = sorted(
            backup_dir.glob(f"{prefix}*.db"), key=os.path.getmtime, reverse=True
        )
        for old_backup in backups[settings.backup_retention_count :]:
            try:
                old_backup.unlink()
                logger.info(f"Removed old backup: {old_backup.name}")
            except Exception as e:
                logger.warning(f"Failed to remove old backup {old_backup.name}: {e}")

    # Clean history backup directories
    history_dirs = sorted(
        [
            d
            for d in backup_dir.iterdir()
            if d.is_dir() and d.name.startswith("history_")
        ],
        key=os.path.getmtime,
        reverse=True,
    )
    for old_dir in history_dirs[settings.backup_retention_count :]:
        try:
            import shutil

            shutil.rmtree(old_dir)
            logger.info(f"Removed old history backup: {old_dir.name}")
        except Exception as e:
            logger.warning(f"Failed to remove old backup {old_dir.name}: {e}")


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
    logger.info("Running WAL checkpoint on all databases")

    set_text("CHECKPOINTING DATABASE...")
    set_led4(0, 255, 0)  # Green for processing

    try:
        db_manager = get_db_manager()

        # Checkpoint core databases
        for db_name, db in [
            ("config", db_manager.config),
            ("ledger", db_manager.ledger),
            ("state", db_manager.state),
            ("cache", db_manager.cache),
            ("calculations", db_manager.calculations),
        ]:
            try:
                result = await db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                row = await result.fetchone()
                if row:
                    logger.info(
                        f"{db_name}: checkpoint complete - busy={row[0]}, log={row[1]}, checkpointed={row[2]}"
                    )
            except Exception as e:
                logger.warning(f"Checkpoint failed for {db_name}: {e}")

        logger.info("WAL checkpoint complete")

    except Exception as e:
        logger.error(f"WAL checkpoint failed: {e}")
        raise


async def integrity_check():
    """
    Run database integrity check.

    Runs weekly to ensure databases are not corrupted.
    """
    async with file_lock("integrity_check", timeout=600.0):
        await _integrity_check_internal()


async def _integrity_check_internal():
    """Internal integrity check implementation."""
    logger.info("Running database integrity check")

    emit(SystemEvent.INTEGRITY_CHECK_START)
    set_text("CHECKING DATABASE INTEGRITY...")
    set_led4(0, 255, 0)  # Green for processing

    try:
        db_manager = get_db_manager()
        all_ok = True

        # Check core databases
        for db_name, db in [
            ("config", db_manager.config),
            ("ledger", db_manager.ledger),
            ("state", db_manager.state),
            ("cache", db_manager.cache),
            ("calculations", db_manager.calculations),
        ]:
            try:
                result = await db.execute("PRAGMA integrity_check")
                row = await result.fetchone()
                if row and row[0] == "ok":
                    logger.info(f"{db_name}: integrity check passed")
                else:
                    error_msg = row[0] if row else "Unknown error"
                    logger.error(f"{db_name}: integrity check FAILED: {error_msg}")
                    all_ok = False
            except Exception as e:
                logger.error(f"{db_name}: integrity check error: {e}")
                all_ok = False

        if all_ok:
            emit(SystemEvent.INTEGRITY_CHECK_COMPLETE)
        else:
            error_msg = "INTEGRITY CHECK FAILED"
            emit(SystemEvent.ERROR_OCCURRED, message=error_msg)
            set_text(error_msg)

    except Exception as e:
        logger.error(f"Database integrity check failed: {e}")
        error_msg = "INTEGRITY CHECK FAILED"
        emit(SystemEvent.ERROR_OCCURRED, message=error_msg)
        set_text(error_msg)
        raise
    finally:
        set_led4(0, 0, 0)  # Clear LED when done


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

    emit(SystemEvent.CLEANUP_START)
    set_text("CLEANING OLD PRICES...")
    set_led4(0, 255, 0)  # Green for processing

    try:
        db_manager = get_db_manager()
        cutoff = (
            datetime.now() - timedelta(days=settings.daily_price_retention_days)
        ).strftime("%Y-%m-%d")

        # Get all active symbols
        cursor = await db_manager.config.execute(
            "SELECT symbol FROM securities WHERE active = 1"
        )
        symbols = [row[0] for row in await cursor.fetchall()]

        total_deleted = 0
        for symbol in symbols:
            try:
                history_db = await db_manager.history(symbol)

                # Count records to be deleted
                cursor = await history_db.execute(
                    "SELECT COUNT(*) FROM daily_prices WHERE date < ?", (cutoff,)
                )
                row = await cursor.fetchone()
                delete_count = row[0] if row else 0

                if delete_count > 0:
                    await history_db.execute(
                        "DELETE FROM daily_prices WHERE date < ?", (cutoff,)
                    )
                    await history_db.commit()
                    total_deleted += delete_count
            except Exception as e:
                logger.warning(f"Cleanup failed for {symbol}: {e}")

        if total_deleted > 0:
            logger.info(
                f"Deleted {total_deleted} old daily price records (before {cutoff})"
            )
        else:
            logger.info("No old daily price records to clean up")

        emit(SystemEvent.CLEANUP_COMPLETE)

    except Exception as e:
        logger.error(f"Daily price cleanup failed: {e}")
        error_msg = "CLEANUP FAILED"
        emit(SystemEvent.ERROR_OCCURRED, message=error_msg)
        set_text(error_msg)
        raise


async def cleanup_expired_caches():
    """
    Clean up expired recommendation and analytics cache entries.

    These caches have 48h (recommendation) and 4h (symbol data) TTLs.
    Also cleans up expired metrics from calculations.db.
    """
    async with file_lock("cleanup_caches", timeout=60.0):
        await _cleanup_expired_caches_internal()


async def _cleanup_expired_caches_internal():
    """Internal cache cleanup implementation."""
    logger.info("Cleaning up expired caches")

    set_text("CLEANING EXPIRED CACHES...")

    try:
        from app.infrastructure.recommendation_cache import get_recommendation_cache
        from app.repositories.calculations import CalculationsRepository

        # Clean recommendation cache
        rec_cache = get_recommendation_cache()
        removed_count = await rec_cache.cleanup_expired()

        # Clean expired metrics from calculations.db
        calc_repo = CalculationsRepository()
        expired_metrics = await calc_repo.delete_expired()

        total_removed = removed_count + expired_metrics

        if total_removed > 0:
            logger.info(
                f"Cleaned up {total_removed} expired entries "
                f"({removed_count} cache, {expired_metrics} metrics)"
            )
        else:
            logger.info("No expired cache entries to clean up")

    except Exception as e:
        logger.error(f"Cache cleanup failed: {e}")
        # Don't raise - cache cleanup is not critical


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

    set_text("CLEANING OLD SNAPSHOTS...")

    try:
        db_manager = get_db_manager()
        cutoff = (
            datetime.now() - timedelta(days=settings.snapshot_retention_days)
        ).strftime("%Y-%m-%d")

        # Count records to be deleted
        cursor = await db_manager.state.execute(
            "SELECT COUNT(*) FROM portfolio_snapshots WHERE date < ?", (cutoff,)
        )
        row = await cursor.fetchone()
        delete_count = row[0] if row else 0

        if delete_count > 0:
            await db_manager.state.execute(
                "DELETE FROM portfolio_snapshots WHERE date < ?", (cutoff,)
            )
            await db_manager.state.commit()
            logger.info(
                f"Deleted {delete_count} old portfolio snapshots (before {cutoff})"
            )
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

    emit(SystemEvent.MAINTENANCE_START)
    set_text("RUNNING MAINTENANCE...")

    try:
        # 1. Create backup first (before any cleanup)
        await create_backup()

        # 2. Clean up old data
        await cleanup_old_daily_prices()
        await cleanup_old_snapshots()
        await cleanup_expired_caches()

        # 3. Checkpoint WAL (after cleanup for smaller file)
        await checkpoint_wal()

        logger.info("Daily maintenance complete")
        emit(SystemEvent.MAINTENANCE_COMPLETE)

    except Exception as e:
        logger.error(f"Daily maintenance failed: {e}")
        error_msg = "MAINTENANCE FAILED"
        emit(SystemEvent.ERROR_OCCURRED, message=error_msg)
        set_text(error_msg)
        raise
    finally:
        set_led4(0, 0, 0)  # Clear LED when done


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
