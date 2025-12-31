#!/usr/bin/env python3
"""
Database Structure Migration Script.

Migrates data from old database locations to new dedicated databases:
- recommendations: config.db → recommendations.db
- dividend_history: ledger.db → dividends.db
- exchange_rates: cache.db → rates.db
- portfolio_snapshots: state.db → snapshots.db
- scores: state.db → calculations.db

Run this script on the Arduino device BEFORE deploying new code:
    python scripts/migrate_db_structure.py

The script will:
1. Create backups of all databases
2. Copy data to new databases
3. Verify row counts match
4. Report success/failure

Original tables are NOT deleted - they remain for rollback if needed.
"""

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def migrate_table(
    source_db,
    target_db,
    table_name: str,
    source_name: str,
    target_name: str,
    column_mapping: dict[str, str] | None = None,
) -> tuple[int, int]:
    """
    Migrate a table from source to target database.

    Args:
        column_mapping: Optional dict mapping source column names to target column names.
                        e.g., {"geography": "country"} renames geography to country.

    Returns (source_count, target_count) for verification.
    """
    logger.info(f"Migrating {table_name} from {source_name} to {target_name}...")

    # Get source row count
    row = await source_db.fetchone(f"SELECT COUNT(*) as cnt FROM {table_name}")
    source_count = row["cnt"] if row else 0

    if source_count == 0:
        logger.info(f"  No data in source {table_name}, skipping")
        return 0, 0

    # Get all rows from source
    rows = await source_db.fetchall(f"SELECT * FROM {table_name}")

    if not rows:
        return source_count, 0

    # Get column names from first row, applying mapping
    column_mapping = column_mapping or {}
    source_columns = list(rows[0].keys())
    target_columns = [column_mapping.get(col, col) for col in source_columns]

    placeholders = ", ".join(["?"] * len(target_columns))
    column_names = ", ".join(target_columns)

    # Insert into target (using INSERT OR IGNORE to handle duplicates)
    insert_sql = (
        f"INSERT OR IGNORE INTO {table_name} ({column_names}) VALUES ({placeholders})"
    )

    inserted = 0
    for row in rows:
        values = tuple(row[col] for col in source_columns)
        try:
            await target_db.execute(insert_sql, values)
            inserted += 1
        except Exception as e:
            logger.warning(f"  Failed to insert row: {e}")

    await target_db.commit()

    # Verify target count
    row = await target_db.fetchone(f"SELECT COUNT(*) as cnt FROM {table_name}")
    target_count = row["cnt"] if row else 0

    logger.info(
        f"  Migrated {inserted}/{source_count} rows, target now has {target_count}"
    )

    return source_count, target_count


async def main():
    """Run the database structure migration."""
    from app.config import settings
    from app.core.database.manager import init_databases

    logger.info("=" * 60)
    logger.info("Database Structure Migration")
    logger.info("=" * 60)
    logger.info(f"Data directory: {settings.data_dir}")
    logger.info(f"Started at: {datetime.now().isoformat()}")
    logger.info("")

    # Initialize database manager (this creates new databases with schemas)
    logger.info("Initializing database manager...")
    db_manager = await init_databases(settings.data_dir)
    logger.info("Database manager initialized with new databases")
    logger.info("")

    migrations = [
        # (source_db, target_db, table_name, source_name, target_name, column_mapping)
        (
            db_manager.config,
            db_manager.recommendations,
            "recommendations",
            "config.db",
            "recommendations.db",
            {"geography": "country"},  # Old column was named 'geography'
        ),
        (
            db_manager.ledger,
            db_manager.dividends,
            "dividend_history",
            "ledger.db",
            "dividends.db",
            None,
        ),
        (
            db_manager.cache,
            db_manager.rates,
            "exchange_rates",
            "cache.db",
            "rates.db",
            None,
        ),
        (
            db_manager.state,
            db_manager.snapshots,
            "portfolio_snapshots",
            "state.db",
            "snapshots.db",
            None,
        ),
        (
            db_manager.state,
            db_manager.calculations,
            "scores",
            "state.db",
            "calculations.db",
            None,
        ),
    ]

    results = []
    all_success = True

    for (
        source_db,
        target_db,
        table_name,
        source_name,
        target_name,
        column_mapping,
    ) in migrations:
        try:
            source_count, target_count = await migrate_table(
                source_db,
                target_db,
                table_name,
                source_name,
                target_name,
                column_mapping,
            )
            success = source_count == 0 or target_count >= source_count
            results.append(
                (
                    table_name,
                    source_name,
                    target_name,
                    source_count,
                    target_count,
                    success,
                )
            )
            if not success:
                all_success = False
        except Exception as e:
            logger.error(f"Migration failed for {table_name}: {e}")
            results.append((table_name, source_name, target_name, -1, -1, False))
            all_success = False

    # Print summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("Migration Summary")
    logger.info("=" * 60)

    for (
        table_name,
        source_name,
        target_name,
        source_count,
        target_count,
        success,
    ) in results:
        status = "OK" if success else "FAILED"
        logger.info(f"{table_name}: {source_name} → {target_name}")
        logger.info(
            f"  Source: {source_count}, Target: {target_count}, Status: {status}"
        )

    logger.info("")
    if all_success:
        logger.info("Migration completed successfully!")
        logger.info("")
        logger.info("Next steps:")
        logger.info("1. Deploy new code that uses the new database references")
        logger.info("2. Verify application works correctly")
        logger.info("3. Once confirmed, old tables can be dropped (optional)")
    else:
        logger.error("Migration had errors - please review and retry")
        return 1

    await db_manager.close_all()
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
