"""Cash flow sync job for periodic updates from Tradernet API."""

import logging
import aiosqlite
from app.services.tradernet import get_tradernet_client
from app.infrastructure.database.repositories import SQLiteCashFlowRepository
from app.infrastructure.locking import file_lock
from app.config import settings

logger = logging.getLogger(__name__)


async def sync_cash_flows():
    """
    Sync cash flow transactions from Tradernet API to local database.
    
    This job:
    1. Fetches all cash flow transactions from Tradernet API
    2. Upserts them into the local database
    3. Handles errors gracefully with logging
    
    Uses file locking to prevent concurrent syncs.
    """
    async with file_lock("cash_flow_sync", timeout=120.0):
        await _sync_cash_flows_internal()


async def _sync_cash_flows_internal():
    """Internal cash flow sync implementation."""
    logger.info("Starting cash flow sync")
    
    client = get_tradernet_client()
    
    if not client.is_connected:
        if not client.connect():
            logger.warning("Failed to connect to Tradernet, skipping cash flow sync")
            return
    
    try:
        # Fetch all cash flows from API
        transactions = client.get_all_cash_flows(limit=1000)
        
        if not transactions:
            logger.info("No cash flow transactions found in API")
            return
        
        logger.info(f"Fetched {len(transactions)} transactions from API")
        
        # Sync to database
        async with aiosqlite.connect(settings.database_path) as db:
            db.row_factory = aiosqlite.Row
            cash_flow_repo = SQLiteCashFlowRepository(db)
            synced_count = await cash_flow_repo.sync_from_api(transactions)
        
        logger.info(
            f"Cash flow sync complete: {synced_count}/{len(transactions)} transactions synced"
        )
        
    except Exception as e:
        logger.error(f"Cash flow sync failed: {e}", exc_info=True)
        # Don't raise - allow other jobs to continue
        return
