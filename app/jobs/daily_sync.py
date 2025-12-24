"""Daily sync jobs for portfolio and prices."""

import logging
from datetime import datetime

import aiosqlite

from app.config import settings
from app.services.tradernet import get_tradernet_client
from app.services import yahoo
from app.infrastructure.events import emit, SystemEvent
from app.infrastructure.dependencies import get_position_repository
from app.infrastructure.locking import file_lock
from app.domain.constants import DEFAULT_CURRENCY
from app.domain.repositories import Position

logger = logging.getLogger(__name__)


async def sync_portfolio():
    """
    Sync portfolio positions from Tradernet to local database.

    This job:
    1. Fetches current positions from Tradernet
    2. Updates local positions table
    3. Creates a daily portfolio snapshot

    Uses file locking to prevent concurrent syncs.
    """
    async with file_lock("portfolio_sync", timeout=60.0):
        await _sync_portfolio_internal()


async def _sync_portfolio_internal():
    """Internal portfolio sync implementation."""
    logger.info("Starting portfolio sync")

    emit(SystemEvent.SYNC_START)

    client = get_tradernet_client()

    if not client.is_connected:
        if not client.connect():
            logger.error("Failed to connect to Tradernet, skipping sync")
            emit(SystemEvent.ERROR_OCCURRED, message="BROKER DOWN")
            return

    try:
        # Get positions from Tradernet
        positions = client.get_portfolio()
        cash_balance = client.get_total_cash_eur()

        async with aiosqlite.connect(settings.database_path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute("BEGIN TRANSACTION")
            try:
                position_repo = get_position_repository(db)

                # Save tracking dates before clearing
                cursor = await db.execute(
                    "SELECT symbol, first_bought_at, last_sold_at FROM positions"
                )
                tracking_dates = {
                    row[0]: (row[1], row[2])
                    for row in await cursor.fetchall()
                }

                await position_repo.delete_all(auto_commit=False)

                # Insert current positions
                total_value = 0.0
                geo_values = {"EU": 0.0, "ASIA": 0.0, "US": 0.0}

                for pos in positions:
                    saved_dates = tracking_dates.get(pos.symbol, (None, None))

                    position = Position(
                        symbol=pos.symbol,
                        quantity=pos.quantity,
                        avg_price=pos.avg_price,
                        current_price=pos.current_price,
                        currency=pos.currency or DEFAULT_CURRENCY,
                        currency_rate=pos.currency_rate,
                        market_value_eur=pos.market_value_eur,
                        last_updated=datetime.now().isoformat(),
                        first_bought_at=saved_dates[0],
                        last_sold_at=saved_dates[1],
                    )
                    await position_repo.upsert(position, auto_commit=False)

                    market_value = pos.market_value_eur
                    total_value += market_value

                    # Determine geography
                    geo = None
                    cursor = await db.execute(
                        "SELECT geography FROM stocks WHERE symbol = ?",
                        (pos.symbol,)
                    )
                    row = await cursor.fetchone()
                    if row:
                        geo = row[0]
                    else:
                        symbol = pos.symbol.upper()
                        if symbol.endswith(".GR") or symbol.endswith(".DE") or symbol.endswith(".PA"):
                            geo = "EU"
                        elif symbol.endswith(".AS") or symbol.endswith(".HK") or symbol.endswith(".T"):
                            geo = "ASIA"
                        elif symbol.endswith(".US"):
                            geo = "US"

                    if geo:
                        geo_values[geo] = geo_values.get(geo, 0) + market_value

                # Create daily snapshot
                today = datetime.now().strftime("%Y-%m-%d")
                await db.execute(
                    """
                    INSERT OR REPLACE INTO portfolio_snapshots
                    (date, total_value, cash_balance, geo_eu_pct, geo_asia_pct, geo_us_pct)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        today,
                        total_value,
                        cash_balance,
                        geo_values["EU"] / total_value if total_value else 0,
                        geo_values["ASIA"] / total_value if total_value else 0,
                        geo_values["US"] / total_value if total_value else 0,
                    ),
                )

                await db.commit()
            except Exception:
                await db.rollback()
                raise

        logger.info(
            f"Portfolio sync complete: {len(positions)} positions, "
            f"total value: {total_value:.2f}, cash: {cash_balance:.2f}"
        )

        # Sync stock currencies (do this during portfolio sync)
        await sync_stock_currencies()

        emit(SystemEvent.SYNC_COMPLETE)

    except Exception as e:
        logger.error(f"Portfolio sync failed: {e}")
        emit(SystemEvent.SYNC_COMPLETE)
        emit(SystemEvent.ERROR_OCCURRED, message="SYNC FAIL")
        raise


async def sync_prices():
    """
    Sync current prices for all stocks in universe.

    Uses file locking to prevent concurrent syncs.
    """
    async with file_lock("price_sync", timeout=120.0):
        await _sync_prices_internal()


async def _sync_prices_internal():
    """Internal price sync implementation."""
    logger.info("Starting price sync")

    emit(SystemEvent.SYNC_START)

    try:
        async with aiosqlite.connect(settings.database_path) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=30000")

            cursor = await db.execute(
                "SELECT symbol, yahoo_symbol FROM stocks WHERE active = 1"
            )
            rows = await cursor.fetchall()

            if not rows:
                logger.info("No stocks to sync")
                emit(SystemEvent.SYNC_COMPLETE)
                return

            symbol_yahoo_map = {row[0]: row[1] for row in rows}

            quotes = yahoo.get_batch_quotes(symbol_yahoo_map)

            updated = 0
            now = datetime.now().isoformat()
            for symbol, price in quotes.items():
                # Update current_price and recalculate market_value_eur from Yahoo price
                # This ensures portfolio value uses fresh Yahoo prices, not stale Tradernet values
                result = await db.execute(
                    """
                    UPDATE positions
                    SET current_price = ?,
                        market_value_eur = quantity * ? / currency_rate,
                        last_updated = ?
                    WHERE symbol = ?
                    """,
                    (price, price, now, symbol),
                )
                if result.rowcount > 0:
                    updated += 1

            await db.commit()

        logger.info(f"Price sync complete: {len(quotes)} quotes, {updated} positions updated")

        emit(SystemEvent.SYNC_COMPLETE)

    except Exception as e:
        logger.error(f"Price sync failed: {e}")
        emit(SystemEvent.SYNC_COMPLETE)
        emit(SystemEvent.ERROR_OCCURRED, message="PRICE FAIL")
        raise


async def sync_stock_currencies():
    """
    Fetch and store trading currency for all stocks from Tradernet.

    Uses the x_curr field from get_quotes() which contains the actual
    trading currency (e.g., BA.EU trades in GBP, not EUR).
    """
    logger.info("Starting stock currency sync")

    client = get_tradernet_client()

    if not client.is_connected:
        if not client.connect():
            logger.error("Failed to connect to Tradernet for currency sync")
            return

    try:
        async with aiosqlite.connect(settings.database_path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=30000")

            # Get all active stock symbols
            cursor = await db.execute("SELECT symbol FROM stocks WHERE active=1")
            symbols = [row[0] for row in await cursor.fetchall()]

            if not symbols:
                logger.info("No stocks to sync currencies for")
                return

            # Fetch quotes to get x_curr
            quotes_response = client.get_quotes_raw(symbols)

            # Handle different response formats
            if isinstance(quotes_response, list):
                q_list = quotes_response
            elif isinstance(quotes_response, dict):
                q_list = quotes_response.get("result", {}).get("q", [])
                if not q_list:
                    q_list = quotes_response.get("q", [])
            else:
                q_list = []

            updated = 0
            for q in q_list:
                if isinstance(q, dict):
                    symbol = q.get("c")
                    currency = q.get("x_curr")
                    if symbol and currency:
                        await db.execute(
                            "UPDATE stocks SET currency = ? WHERE symbol = ?",
                            (currency, symbol)
                        )
                        updated += 1

            await db.commit()
            logger.info(f"Stock currency sync complete: updated {updated} stocks")

    except Exception as e:
        logger.error(f"Stock currency sync failed: {e}")
        raise
