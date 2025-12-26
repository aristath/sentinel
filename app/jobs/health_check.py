"""Database health check job with auto-recovery.

This job runs periodically to check database integrity and
automatically recover from corruption when possible.

Self-healing capabilities:
- Runs PRAGMA integrity_check on all databases
    - Logs issues found
- Per-symbol databases can be rebuilt from Yahoo API
- Core databases trigger alerts for manual intervention
"""

import logging
from datetime import datetime
from pathlib import Path

from app.config import settings
from app.infrastructure.events import SystemEvent, emit
from app.infrastructure.hardware.display_service import (
    clear_processing,
    set_error,
    set_processing,
)
from app.infrastructure.locking import file_lock

logger = logging.getLogger(__name__)


async def run_health_check():
    """
    Run database health checks on all databases.

    Uses file locking to prevent concurrent checks.
    """
    async with file_lock("health_check", timeout=120.0):
        await _run_health_check_internal()


async def _check_core_databases(issues: list) -> None:
    """Check integrity of core databases."""
    core_dbs = [
        ("config.db", "Configuration database"),
        ("ledger.db", "Ledger database"),
        ("state.db", "State database"),
        ("cache.db", "Cache database"),
    ]

    for db_file, description in core_dbs:
        db_path = Path(settings.data_dir) / db_file
        if db_path.exists():
            result = await _check_database_integrity(db_path)
            if result != "ok":
                issues.append(
                    {
                        "database": db_file,
                        "description": description,
                        "error": result,
                        "recoverable": db_file == "cache.db",
                    }
                )
                logger.error(f"Integrity check failed for {db_file}: {result}")

                if db_file == "cache.db":
                    await _rebuild_cache_db(db_path)
        else:
            logger.warning(f"Database not found: {db_file}")


async def _check_history_databases(issues: list) -> None:
    """Check integrity of per-symbol history databases."""
    history_dir = Path(settings.data_dir) / "history"
    if not history_dir.exists():
        return

    for db_file in history_dir.glob("*.db"):
        result = await _check_database_integrity(db_file)
        if result != "ok":
            symbol = db_file.stem
            issues.append(
                {
                    "database": f"history/{db_file.name}",
                    "description": f"History for {symbol}",
                    "error": result,
                    "recoverable": True,
                }
            )
            logger.error(f"Integrity check failed for {db_file.name}: {result}")
            await _rebuild_symbol_history(db_file, symbol)


async def _check_legacy_database(issues: list) -> None:
    """Check integrity of legacy database if it exists."""
    legacy_db = Path(settings.database_path)
    if not legacy_db.exists():
        return

    result = await _check_database_integrity(legacy_db)
    if result != "ok":
        issues.append(
            {
                "database": "trader.db (legacy)",
                "description": "Legacy database",
                "error": result,
                "recoverable": False,
            }
        )
        logger.error(f"Integrity check failed for legacy database: {result}")


async def _run_health_check_internal():
    """Internal health check implementation."""
    logger.info("Starting database health check...")

    set_processing("CHECKING DATABASE HEALTH...")

    issues = []

    try:
        await _check_core_databases(issues)
        await _check_history_databases(issues)
        await _check_legacy_database(issues)

        if issues:
            await _report_issues(issues)
            error_msg = f"DB HEALTH: {len(issues)} ISSUE(S)"
            emit(SystemEvent.ERROR_OCCURRED, message=error_msg)
            set_error(error_msg)
        else:
            logger.info("Database health check passed: all databases healthy")

    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        error_msg = "HEALTH CHECK FAILED"
        emit(SystemEvent.ERROR_OCCURRED, message=error_msg)
        set_error(error_msg)
    finally:
        clear_processing()


async def _check_database_integrity(db_path: Path) -> str:
    """
    Run PRAGMA integrity_check on a database.

    Returns:
        "ok" if healthy, error message otherwise
    """
    import aiosqlite

    try:
        async with aiosqlite.connect(str(db_path)) as db:
            cursor = await db.execute("PRAGMA integrity_check")
            result = await cursor.fetchone()
            return result[0] if result else "unknown error"
    except Exception as e:
        return str(e)


async def _rebuild_cache_db(db_path: Path):
    """
    Rebuild the cache database from scratch.

    Cache data is ephemeral and can be regenerated.
    """
    logger.info(f"Rebuilding cache database: {db_path}")

    try:
        # Backup corrupted file
        backup_path = db_path.with_suffix(
            f".corrupted.{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        )
        db_path.rename(backup_path)
        logger.info(f"Backed up corrupted cache to: {backup_path}")

        # Create fresh cache database
        import aiosqlite

        from app.infrastructure.database.schemas import CACHE_SCHEMA

        async with aiosqlite.connect(str(db_path)) as db:
            await db.executescript(CACHE_SCHEMA)
            await db.commit()

        logger.info("Cache database rebuilt successfully")
        emit(SystemEvent.SYNC_COMPLETE)

    except Exception as e:
        logger.error(f"Failed to rebuild cache database: {e}")


async def _rebuild_symbol_history(db_path: Path, symbol: str):
    """
    Rebuild a per-symbol history database from Yahoo API.

    Args:
        db_path: Path to the corrupted database
        symbol: Stock symbol
    """
    logger.info(f"Rebuilding history database for {symbol}")

    try:
        # Backup corrupted file
        backup_path = db_path.with_suffix(
            f".corrupted.{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        )
        db_path.rename(backup_path)
        logger.info(f"Backed up corrupted history to: {backup_path}")

        # Create fresh history database
        import aiosqlite

        from app.infrastructure.database.schemas import HISTORY_SCHEMA

        async with aiosqlite.connect(str(db_path)) as db:
            await db.executescript(HISTORY_SCHEMA)
            await db.commit()

        logger.info(f"History database for {symbol} rebuilt (empty)")

        # Note: Actual data will be refetched by historical_data_sync job
        emit(SystemEvent.SYNC_START)

    except Exception as e:
        logger.error(f"Failed to rebuild history database for {symbol}: {e}")


async def _report_issues(issues: list):
    """
    Report health check issues to logs.

    Args:
        issues: List of issue dicts with database, description, error, recoverable
    """
    # Build message
    lines = ["Database Health Check Issues", ""]

    for issue in issues:
        status = "RECOVERED" if issue["recoverable"] else "CRITICAL"
        lines.append(f"- {issue['database']} ({status})")
        lines.append(f"  {issue['description']}")
        lines.append(f"  Error: {issue['error']}")
        lines.append("")

    if any(not issue["recoverable"] for issue in issues):
        lines.append("Action Required: Non-recoverable issues detected!")

    message = "\n".join(lines)
    logger.error(message)


async def check_wal_status():
    """
    Check WAL file sizes and checkpoint if needed.

    Large WAL files can indicate checkpoint issues.
    """
    import aiosqlite

    logger.info("Checking WAL file status...")

    core_dbs = ["config.db", "ledger.db", "state.db", "cache.db"]

    for db_file in core_dbs:
        db_path = Path(settings.data_dir) / db_file
        wal_path = db_path.with_suffix(".db-wal")

        if wal_path.exists():
            wal_size = wal_path.stat().st_size
            wal_size_mb = wal_size / (1024 * 1024)

            if wal_size_mb > 10:  # WAL > 10MB
                logger.warning(
                    f"{db_file} WAL is {wal_size_mb:.1f}MB, running checkpoint..."
                )
                try:
                    async with aiosqlite.connect(str(db_path)) as db:
                        await db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                    logger.info(f"Checkpoint complete for {db_file}")
                except Exception as e:
                    logger.error(f"Checkpoint failed for {db_file}: {e}")
            else:
                logger.debug(f"{db_file} WAL: {wal_size_mb:.2f}MB (healthy)")


async def get_database_stats() -> dict:
    """
    Get statistics about all databases.

    Returns:
        Dict with size, table counts, etc. for each database
    """
    import aiosqlite

    stats = {}

    # Core databases
    core_dbs = ["config.db", "ledger.db", "state.db", "cache.db"]

    for db_file in core_dbs:
        db_path = Path(settings.data_dir) / db_file
        if db_path.exists():
            try:
                async with aiosqlite.connect(str(db_path)) as db:
                    # Get table count
                    cursor = await db.execute(
                        "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
                    )
                    row = await cursor.fetchone()
                    table_count = row[0] if row else 0

                    # Get page count and size
                    cursor = await db.execute("PRAGMA page_count")
                    row = await cursor.fetchone()
                    page_count = row[0] if row else 0
                    cursor = await db.execute("PRAGMA page_size")
                    row = await cursor.fetchone()
                    page_size = row[0] if row else 0

                stats[db_file] = {
                    "size_bytes": db_path.stat().st_size,
                    "size_mb": db_path.stat().st_size / (1024 * 1024),
                    "table_count": table_count,
                    "page_count": page_count,
                    "page_size": page_size,
                }
            except Exception as e:
                stats[db_file] = {"error": str(e)}
        else:
            stats[db_file] = {"exists": False}

    # History databases
    history_dir = Path(settings.data_dir) / "history"
    if history_dir.exists():
        history_files = list(history_dir.glob("*.db"))
        total_size = sum(f.stat().st_size for f in history_files)
        stats["history"] = {
            "count": len(history_files),
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024),
        }

    return stats
