"""Periodic stock score refresh job."""

import logging
from app.database import get_db_connection
from app.services.scorer import score_all_stocks
from app.infrastructure.events import emit, SystemEvent
from app.infrastructure.locking import file_lock

logger = logging.getLogger(__name__)


async def refresh_all_scores():
    """Refresh scores for all active stocks in the universe."""
    async with file_lock("score_refresh", timeout=300.0):
        await _refresh_all_scores_internal()


async def _refresh_all_scores_internal():
    """Internal score refresh implementation."""
    logger.info("Starting periodic score refresh...")

    emit(SystemEvent.PROCESSING_START)

    try:
        async with get_db_connection() as db:
            scores = await score_all_stocks(db)
            logger.info(f"Refreshed scores for {len(scores)} stocks")
        emit(SystemEvent.PROCESSING_END)
    except Exception as e:
        logger.error(f"Score refresh failed: {e}")
        emit(SystemEvent.PROCESSING_END)
        emit(SystemEvent.ERROR_OCCURRED, message="SCORE FAIL")
