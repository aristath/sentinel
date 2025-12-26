"""Sync trades from Tradernet API.

Fetches executed trades from broker and syncs to local database.
This ensures our trades table reflects actual executed trades,
not just placed orders (which may be cancelled externally).
"""

import logging
from datetime import datetime
from typing import Optional

from app.infrastructure.database.manager import get_db_manager
from app.infrastructure.events import SystemEvent, emit
from app.infrastructure.external.tradernet import get_tradernet_client
from app.infrastructure.hardware.display_service import (
    clear_processing,
    set_error,
    set_processing,
)
from app.infrastructure.locking import file_lock

logger = logging.getLogger(__name__)


async def sync_trades():
    """
    Sync executed trades from Tradernet API to local database.

    Uses order_id as the unique key to avoid duplicates.
    New trades are inserted, existing ones are skipped.
    """
    async with file_lock("sync_trades", timeout=60.0):
        await _sync_trades_internal()


async def _sync_trades_internal():
    """Internal implementation of trade sync."""
    logger.info("Starting trade sync from Tradernet...")

    emit(SystemEvent.TRADE_SYNC_START)
    set_processing("SYNCING TRADES...")

    try:
        # Connect to broker
        client = get_tradernet_client()
        if not client.is_connected:
            if not client.connect():
                logger.warning("Cannot connect to Tradernet, skipping trade sync")
                return

        # Fetch executed trades from API
        executed_trades = client.get_executed_trades(limit=500)

        if not executed_trades:
            logger.info("No executed trades returned from Tradernet")
            return

        logger.info(f"Fetched {len(executed_trades)} trades from Tradernet")

        db_manager = get_db_manager()
        existing_order_ids = await _get_existing_order_ids(db_manager)
        valid_symbols = await _get_valid_symbols(db_manager)

        inserted = 0
        skipped = 0

        async with db_manager.ledger.transaction():
            for trade in executed_trades:
                order_id = trade.get("order_id")
                valid, reason = _validate_trade(trade, existing_order_ids, valid_symbols)

                if not valid:
                    if reason != "duplicate":
                        logger.warning(f"Trade {order_id or 'unknown'} invalid: {reason}")
                    skipped += 1
                    continue

                if await _insert_trade(db_manager, trade, order_id):
                    inserted += 1
                else:
                    skipped += 1

        logger.info(f"Trade sync complete: {inserted} inserted, {skipped} skipped")

        emit(SystemEvent.TRADE_SYNC_COMPLETE)

    except Exception as e:
        logger.error(f"Trade sync failed: {e}", exc_info=True)
        error_msg = "TRADE SYNC FAILED"
        emit(SystemEvent.ERROR_OCCURRED, message=error_msg)
        set_error(error_msg)
    finally:
        clear_processing()


async def clear_and_resync_trades():
    """
    Clear all trades and resync from Tradernet.

    Use this for initial migration or to fix sync issues.
    WARNING: This deletes all existing trade records!
    """
    logger.warning("Clearing all trades and resyncing from Tradernet...")

    db_manager = get_db_manager()

    # Count existing trades
    cursor = await db_manager.ledger.execute("SELECT COUNT(*) as count FROM trades")
    count = (await cursor.fetchone())[0]
    logger.info(f"Deleting {count} existing trades...")

    # Clear trades table
    async with db_manager.ledger.transaction():
        await db_manager.ledger.execute("DELETE FROM trades")

    logger.info("Trades table cleared")

    # Now sync fresh data
    await _sync_trades_internal()
