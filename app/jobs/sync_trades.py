"""Sync trades from Tradernet API.

Fetches executed trades from broker and syncs to local database.
This ensures our trades table reflects actual executed trades,
not just placed orders (which may be cancelled externally).
"""

import logging
from datetime import datetime

from app.infrastructure.database.manager import get_db_manager
from app.infrastructure.events import SystemEvent, emit
from app.infrastructure.external.tradernet import get_tradernet_client
from app.infrastructure.hardware.display_service import set_led4, set_text
from app.infrastructure.locking import file_lock

logger = logging.getLogger(__name__)


async def _get_existing_order_ids(db_manager) -> set:
    """Get set of existing order IDs from database."""
    cursor = await db_manager.ledger.execute(
        "SELECT order_id FROM trades WHERE order_id IS NOT NULL"
    )
    return {row[0] for row in await cursor.fetchall()}


async def _get_valid_symbols(db_manager) -> set:
    """Get set of valid stock symbols from database."""
    cursor = await db_manager.config.execute("SELECT symbol FROM stocks")
    return {row[0] for row in await cursor.fetchall()}


def _is_currency_conversion(symbol: str) -> bool:
    """Check if symbol is a currency conversion pair (e.g., USD/EUR, HKD/EUR)."""
    return "/" in symbol and len(symbol.split("/")) == 2


def _validate_trade(
    trade: dict, existing_order_ids: set, valid_symbols: set
) -> tuple[bool, str]:
    """Validate a trade and return (is_valid, reason)."""
    order_id = trade.get("order_id")
    if not order_id:
        return False, "missing order_id"

    if order_id in existing_order_ids:
        return False, "duplicate"

    symbol = trade.get("symbol", "")

    # Allow currency conversions (e.g., USD/EUR, HKD/EUR, GBP/EUR)
    if _is_currency_conversion(symbol):
        # Currency conversions are valid
        pass
    elif symbol not in valid_symbols:
        return False, f"symbol {symbol} not in stocks table"

    side = trade.get("side", "").upper()
    if side not in ("BUY", "SELL"):
        return False, f"invalid side '{side}'"

    return True, ""


async def _insert_trade(db_manager, trade: dict, order_id: str) -> bool:
    """Insert a trade into the database."""
    try:
        symbol = trade.get("symbol", "")
        side = trade.get("side", "").upper()
        quantity = trade.get("quantity", 0)
        price = trade.get("price", 0)
        executed_at = trade.get("executed_at", "")
        if not executed_at:
            executed_at = datetime.now().isoformat()

        created_at = datetime.now().isoformat()

        await db_manager.ledger.execute(
            """
            INSERT INTO trades (symbol, side, quantity, price, executed_at, order_id, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'tradernet', ?)
            """,
            (symbol, side, quantity, price, executed_at, order_id, created_at),
        )
        return True
    except Exception as e:
        logger.error(f"Failed to insert trade {order_id}: {e}")
        return False


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
    set_text("SYNCING TRADES...")
    set_led4(0, 255, 0)  # Green for processing

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
                valid, reason = _validate_trade(
                    trade, existing_order_ids, valid_symbols
                )

                if not valid:
                    if reason != "duplicate":
                        logger.warning(
                            f"Trade {order_id or 'unknown'} invalid: {reason}"
                        )
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
        error_msg = "TRADE SYNC CRASHES"
        emit(SystemEvent.ERROR_OCCURRED, message=error_msg)
        set_text(error_msg)
    finally:
        set_led4(0, 0, 0)  # Clear LED when done


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
