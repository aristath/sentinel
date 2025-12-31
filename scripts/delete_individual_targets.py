#!/usr/bin/env python3
"""
Delete Individual Allocation Targets Migration Script.

Deletes all individual country and industry targets from allocation_targets table.
Only group targets (type='country_group' or type='industry_group') are kept.

Run this script on the Arduino device AFTER deploying the new code:
    python scripts/delete_individual_targets.py

The script will:
1. Count existing individual targets
2. Delete all targets where type='country' or type='industry'
3. Report how many targets were deleted
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    """Delete individual allocation targets."""
    from app.config import settings
    from app.core.database.manager import init_databases

    logger.info("=" * 60)
    logger.info("Delete Individual Allocation Targets")
    logger.info("=" * 60)
    logger.info(f"Data directory: {settings.data_dir}")
    logger.info("")

    # Initialize database manager
    logger.info("Initializing database manager...")
    db_manager = await init_databases(settings.data_dir)
    logger.info("Database manager initialized")
    logger.info("")

    # Count existing individual targets
    cursor = await db_manager.config.execute(
        "SELECT COUNT(*) as count FROM allocation_targets WHERE type IN ('country', 'industry')"
    )
    row = await cursor.fetchone()
    individual_count = row["count"] if row else 0

    logger.info(f"Found {individual_count} individual targets to delete")
    logger.info("")

    if individual_count == 0:
        logger.info("No individual targets found. Nothing to delete.")
        return

    # Delete individual targets
    logger.info("Deleting individual targets...")
    cursor = await db_manager.config.execute(
        "DELETE FROM allocation_targets WHERE type IN ('country', 'industry')"
    )
    deleted_count = cursor.rowcount
    await db_manager.config.commit()

    logger.info(f"Deleted {deleted_count} individual targets")
    logger.info("")

    # Verify deletion
    cursor = await db_manager.config.execute(
        "SELECT COUNT(*) as count FROM allocation_targets WHERE type IN ('country', 'industry')"
    )
    row = await cursor.fetchone()
    remaining_count = row["count"] if row else 0

    if remaining_count == 0:
        logger.info("✓ Successfully deleted all individual targets")
    else:
        logger.warning(f"⚠ Warning: {remaining_count} individual targets still remain")

    # Show remaining group targets
    cursor = await db_manager.config.execute(
        "SELECT type, COUNT(*) as count FROM allocation_targets GROUP BY type"
    )
    rows = await cursor.fetchall()
    logger.info("")
    logger.info("Remaining allocation targets by type:")
    for row in rows:
        logger.info(f"  {row['type']}: {row['count']} targets")


if __name__ == "__main__":
    asyncio.run(main())
