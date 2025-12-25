"""
Migration v5: Remove ScoreCache entries from cache.db

After refactoring to use calculations.db for raw metrics, ScoreCache is no longer
needed. This migration removes all ScoreCache entries from cache.db to free up space.

Run this migration once after deploying the calculations.db refactor.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config import settings
from app.infrastructure.database.manager import init_databases, DatabaseManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate():
    """Remove all ScoreCache entries from cache.db."""
    logger.info("Starting migration v5: Remove ScoreCache entries")

    # Initialize database manager
    db_manager = await init_databases(settings.data_dir)

    try:
        # Count existing ScoreCache entries
        cursor = await db_manager.cache.execute(
            "SELECT COUNT(*) as cnt FROM cache_entries WHERE key LIKE 'score:%'"
        )
        row = await cursor.fetchone()
        count_before = row["cnt"] if row else 0

        logger.info(f"Found {count_before} ScoreCache entries to remove")

        if count_before == 0:
            logger.info("No ScoreCache entries found, migration complete")
            return

        # Delete all ScoreCache entries
        cursor = await db_manager.cache.execute(
            "DELETE FROM cache_entries WHERE key LIKE 'score:%'"
        )
        await db_manager.cache.commit()

        deleted_count = cursor.rowcount
        logger.info(f"Deleted {deleted_count} ScoreCache entries from cache.db")

        # Verify deletion
        cursor = await db_manager.cache.execute(
            "SELECT COUNT(*) as cnt FROM cache_entries WHERE key LIKE 'score:%'"
        )
        row = await cursor.fetchone()
        count_after = row["cnt"] if row else 0

        if count_after == 0:
            logger.info("Migration v5 complete: All ScoreCache entries removed")
        else:
            logger.warning(f"Migration incomplete: {count_after} entries still remain")

    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        raise
    finally:
        await db_manager.close_all()


if __name__ == "__main__":
    asyncio.run(migrate())

