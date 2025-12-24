"""Sync trades from Tradernet API.

Fetches executed trades from broker and syncs to local database.
This ensures our trades table reflects actual executed trades,
not just placed orders (which may be cancelled externally).
"""

import logging
from datetime import datetime

import aiosqlite

from app.config import settings
from app.services.tradernet import get_tradernet_client
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

        async with aiosqlite.connect(settings.database_path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=30000")

            # Get existing order_ids to avoid duplicates
            cursor = await db.execute(
                "SELECT order_id FROM trades WHERE order_id IS NOT NULL"
            )
            existing_order_ids = {row["order_id"] for row in await cursor.fetchall()}
            logger.info(f"Found {len(existing_order_ids)} existing trades in database")

            # Get valid symbols from stocks table
            cursor = await db.execute("SELECT symbol FROM stocks")
            valid_symbols = {row["symbol"] for row in await cursor.fetchall()}

            # Insert new trades
            inserted = 0
            skipped = 0

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
                    await db.execute(
                        """
                        INSERT INTO trades (symbol, side, quantity, price, executed_at, order_id)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (symbol, side, quantity, price, executed_at, order_id)
                    )
                    inserted += 1
                    logger.debug(f"Inserted trade: {side} {quantity} {symbol} @ {price}")
                except Exception as e:
                    logger.error(f"Failed to insert trade {order_id}: {e}")
                    skipped += 1

            await db.commit()
            logger.info(f"Trade sync complete: {inserted} inserted, {skipped} skipped")

    except Exception as e:
        logger.error(f"Trade sync failed: {e}", exc_info=True)


async def clear_and_resync_trades():
    """
    Clear all trades and resync from Tradernet.

    Use this for initial migration or to fix sync issues.
    WARNING: This deletes all existing trade records!
    """
    logger.warning("Clearing all trades and resyncing from Tradernet...")

    async with aiosqlite.connect(settings.database_path) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA busy_timeout=30000")

        # Count existing trades
        cursor = await db.execute("SELECT COUNT(*) as count FROM trades")
        count = (await cursor.fetchone())["count"]
        logger.info(f"Deleting {count} existing trades...")

        # Clear trades table
        await db.execute("DELETE FROM trades")
        await db.commit()
        logger.info("Trades table cleared")

    # Now sync fresh data
    await _sync_trades_internal()
