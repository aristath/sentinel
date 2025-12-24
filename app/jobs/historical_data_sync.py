"""Historical data sync job for stock prices."""

import logging
import asyncio
from datetime import datetime, timedelta

import aiosqlite

from app.config import settings
from app.database import get_db_connection
from app.services import yahoo
from app.infrastructure.locking import file_lock
from app.infrastructure.events import emit, SystemEvent

logger = logging.getLogger(__name__)


async def sync_historical_data():
    """
    Sync historical stock prices.

    This job:
    1. Fetches historical stock prices for all active stocks (1 year)
    2. Aggregates prices into monthly averages for long-term storage

    Uses file locking to prevent concurrent runs.
    """
    async with file_lock("historical_data_sync", timeout=3600.0):
        await _sync_historical_data_internal()


async def _sync_historical_data_internal():
    """Internal historical data sync implementation."""
    logger.info("Starting historical data sync")

    emit(SystemEvent.SYNC_START)

    try:
        await _sync_stock_price_history()
        await _aggregate_to_monthly()
        logger.info("Historical data sync complete")
        emit(SystemEvent.SYNC_COMPLETE)
    except Exception as e:
        logger.error(f"Historical data sync failed: {e}")
        emit(SystemEvent.ERROR_OCCURRED, message="HIST FAIL")
        raise


async def _sync_stock_price_history():
    """Fetch and store historical stock prices for all active stocks (1 year)."""
    logger.info("Starting stock price history sync (using Yahoo Finance)")

    async with get_db_connection() as db:
        cursor = await db.execute(
            "SELECT symbol, yahoo_symbol FROM stocks WHERE active = 1"
        )
        rows = await cursor.fetchall()
        stocks = [(row["symbol"], row["yahoo_symbol"]) for row in rows]

        if not stocks:
            logger.info("No active stocks to sync")
            return

        logger.info(f"Syncing historical prices for {len(stocks)} stocks")

        processed = 0
        errors = 0

        for symbol, yahoo_symbol in stocks:
            try:
                # Check if we already have recent data
                cursor = await db.execute("""
                    SELECT MAX(date) as max_date
                    FROM stock_price_history
                    WHERE symbol = ?
                """, (symbol,))
                row = await cursor.fetchone()

                if row and row["max_date"]:
                    max_date = datetime.strptime(row["max_date"], "%Y-%m-%d")
                    if max_date >= datetime.now() - timedelta(days=1):
                        processed += 1
                        continue

                await _fetch_and_store_prices(db, symbol, yahoo_symbol)

                processed += 1
                if processed % 10 == 0:
                    logger.info(f"Processed {processed}/{len(stocks)} stocks")

                await asyncio.sleep(settings.external_api_rate_limit_delay)

            except Exception as e:
                errors += 1
                logger.error(f"Failed to sync historical prices for {symbol}: {e}")
                continue

        logger.info(f"Stock price history sync complete: {processed} processed, {errors} errors")


async def _fetch_and_store_prices(
    db: aiosqlite.Connection,
    symbol: str,
    yahoo_symbol: str = None
):
    """Fetch historical prices from Yahoo Finance and store in database."""
    try:
        # Fetch 1 year of historical data from Yahoo Finance
        ohlc_data = yahoo.get_historical_prices(symbol, yahoo_symbol, period="1y")

        if not ohlc_data:
            logger.warning(f"No price data from Yahoo for {symbol}")
            return

        logger.info(f"Fetched {len(ohlc_data)} price records for {symbol} from Yahoo")

        now = datetime.now().isoformat()
        for ohlc in ohlc_data:
            date = ohlc.date.strftime("%Y-%m-%d")
            await db.execute("""
                INSERT OR REPLACE INTO stock_price_history
                (symbol, date, close_price, open_price, high_price, low_price, volume, source, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                symbol,
                date,
                ohlc.close,
                ohlc.open,
                ohlc.high,
                ohlc.low,
                ohlc.volume,
                "yahoo",
                now,
            ))

        await db.commit()
        logger.debug(f"Stored {len(ohlc_data)} Yahoo price records for {symbol}")

    except Exception as e:
        logger.error(f"Failed to fetch/store Yahoo prices for {symbol}: {e}")
        raise


async def _aggregate_to_monthly():
    """Aggregate daily prices to monthly averages for all symbols."""
    logger.info("Aggregating daily prices to monthly averages")

    async with get_db_connection() as db:
        cursor = await db.execute("SELECT DISTINCT symbol FROM stock_price_history")
        symbols = [row["symbol"] for row in await cursor.fetchall()]

        for symbol in symbols:
            await db.execute("""
                INSERT OR REPLACE INTO stock_price_monthly
                (symbol, year_month, avg_close, avg_adj_close, min_price, max_price, source, created_at)
                SELECT
                    symbol,
                    strftime('%Y-%m', date) as year_month,
                    AVG(close_price) as avg_close,
                    AVG(close_price) as avg_adj_close,
                    MIN(low_price) as min_price,
                    MAX(high_price) as max_price,
                    'calculated' as source,
                    datetime('now') as created_at
                FROM stock_price_history
                WHERE symbol = ?
                GROUP BY symbol, strftime('%Y-%m', date)
            """, (symbol,))

        await db.commit()
        logger.info(f"Aggregated monthly prices for {len(symbols)} symbols")
