"""Periodic stock score refresh job."""

import logging
import aiosqlite
from app.config import settings
from app.services.scorer import score_all_stocks

logger = logging.getLogger(__name__)


async def refresh_all_scores():
    """Refresh scores for all active stocks in the universe."""
    logger.info("Starting periodic score refresh...")

    try:
        async with aiosqlite.connect(settings.database_path) as db:
            db.row_factory = aiosqlite.Row
            scores = await score_all_stocks(db)
            logger.info(f"Refreshed scores for {len(scores)} stocks")
    except Exception as e:
        logger.error(f"Score refresh failed: {e}")
