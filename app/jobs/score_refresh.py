"""Periodic stock score refresh job."""

import logging
import aiosqlite
from app.config import settings
from app.services.scorer import score_all_stocks
from app.infrastructure.hardware.led_display import get_led_display
from app.infrastructure.locking import file_lock

logger = logging.getLogger(__name__)


async def refresh_all_scores():
    """Refresh scores for all active stocks in the universe."""
    async with file_lock("score_refresh", timeout=300.0):
        await _refresh_all_scores_internal()


async def _refresh_all_scores_internal():
    """Internal score refresh implementation."""
    logger.info("Starting periodic score refresh...")

    try:
        async with aiosqlite.connect(settings.database_path) as db:
            db.row_factory = aiosqlite.Row
            # Enable WAL mode and busy timeout
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=30000")
            scores = await score_all_stocks(db)
            logger.info(f"Refreshed scores for {len(scores)} stocks")
    except Exception as e:
        logger.error(f"Score refresh failed: {e}")
        display = get_led_display()
        if display.is_connected:
            display.show_error("SCORE FAIL")
