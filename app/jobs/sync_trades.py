"""Sync trades from Tradernet API.

Fetches executed trades from broker and syncs to local database.
This ensures our trades table reflects actual executed trades,
not just placed orders (which may be cancelled externally).
"""

import logging
from datetime import datetime

from app.infrastructure.external.tradernet import get_tradernet_client
from app.infrastructure.locking import file_lock
from app.infrastructure.hardware.led_display import set_activity
from app.infrastructure.events import emit, SystemEvent
from app.infrastructure.database.manager import get_db_manager

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
    set_activity("SYNCING TRADES...", duration=15.0)

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

        # Get existing order_ids to avoid duplicates
        cursor = await db_manager.ledger.execute(
            "SELECT order_id FROM trades WHERE order_id IS NOT NULL"
        )
        existing_order_ids = {row[0] for row in await cursor.fetchall()}
        logger.info(f"Found {len(existing_order_ids)} existing trades in database")

        # Get valid symbols from stocks table
        cursor = await db_manager.config.execute("SELECT symbol FROM stocks")
        valid_symbols = {row[0] for row in await cursor.fetchall()}

        # Insert new trades
        inserted = 0
        skipped = 0

        async with db_manager.ledger.transaction():
            for trade in executed_trades:
                order_id = trade.get("order_id")
                if not order_id:
                    logger.warning(f"Trade missing order_id, skipping: {trade}")
                    skipped += 1
                    continue

                if order_id in existing_order_ids:
                    skipped += 1
                    continue

                symbol = trade.get("symbol", "")
                if symbol not in valid_symbols:
                    logger.debug(f"Symbol {symbol} not in stocks table, skipping")
                    skipped += 1
                    continue

                side = trade.get("side", "").upper()
                if side not in ("BUY", "SELL"):
                    logger.warning(f"Invalid side '{side}' for trade {order_id}, skipping")
                    skipped += 1
                    continue

                quantity = trade.get("quantity", 0)
                price = trade.get("price", 0)
                executed_at = trade.get("executed_at", "")

                if not executed_at:
                    executed_at = datetime.now().isoformat()

                try:
                    await db_manager.ledger.execute(
                        """
                        INSERT INTO trades (symbol, side, quantity, price, executed_at, order_id, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                        """,
                        (symbol, side, quantity, price, executed_at, order_id)
                    )
                    inserted += 1
                    logger.debug(f"Inserted trade: {side} {quantity} {symbol} @ {price}")
                except Exception as e:
                    logger.error(f"Failed to insert trade {order_id}: {e}")
                    skipped += 1

        logger.info(f"Trade sync complete: {inserted} inserted, {skipped} skipped")

        emit(SystemEvent.TRADE_SYNC_COMPLETE)
        set_activity("TRADE SYNC COMPLETE", duration=5.0)

    except Exception as e:
        logger.error(f"Trade sync failed: {e}", exc_info=True)
        emit(SystemEvent.ERROR_OCCURRED, message="TRADE SYNC FAILED")


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
