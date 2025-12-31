"""Historical data sync job for stock prices.

Fetches historical prices from Yahoo and stores in per-symbol databases.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from app.config import settings
from app.core.database.manager import get_db_manager
from app.core.events import SystemEvent, emit
from app.infrastructure.external import yahoo_finance as yahoo
from app.infrastructure.locking import file_lock
from app.modules.display.services.display_service import set_led4, set_text

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
        await _sync_security_price_history()
        logger.info("Historical data sync complete")
        emit(SystemEvent.SYNC_COMPLETE)
    except Exception as e:
        logger.error(f"Historical data sync failed: {e}")
        error_msg = "HISTORICAL DATA SYNC CRASHES"
        emit(SystemEvent.ERROR_OCCURRED, message=error_msg)
        set_text(error_msg)
        raise
    finally:
        set_led4(0, 0, 0)  # Clear LED when done


async def _sync_security_price_history():
    """Fetch and store historical stock prices for all active stocks."""
    logger.info("Starting stock price history sync (using Yahoo Finance)")

    set_text("SYNCING HISTORICAL PRICES...")
    set_led4(0, 255, 0)  # Green for processing

    db_manager = get_db_manager()

    # Get all active stocks from config
    cursor = await db_manager.config.execute(
        "SELECT symbol, yahoo_symbol FROM securities WHERE active = 1"
    )
    rows = await cursor.fetchall()
    stocks = [(row[0], row[1]) for row in rows]

    if not stocks:
        logger.info("No active stocks to sync")
        return

    logger.info(f"Syncing historical prices for {len(stocks)} stocks")

    processed = 0
    errors = 0

    for symbol, yahoo_symbol in stocks:
        try:
            # Get history database for this symbol
            history_db = await db_manager.history(symbol)

            # Check if we already have recent data
            cursor = await history_db.execute(
                "SELECT MAX(date) as max_date FROM daily_prices"
            )
            row = await cursor.fetchone()

            if row and row[0]:
                max_date = datetime.strptime(row[0], "%Y-%m-%d")
                if max_date >= datetime.now() - timedelta(days=1):
                    processed += 1
                    continue

            await _fetch_and_store_prices(history_db, symbol, yahoo_symbol)

            # Metrics in calculations.db will expire naturally via TTL
            # No manual invalidation needed

            processed += 1
            if processed % 10 == 0:
                logger.info(f"Processed {processed}/{len(stocks)} stocks")

            await asyncio.sleep(settings.external_api_rate_limit_delay)

        except Exception as e:
            errors += 1
            logger.error(f"Failed to sync historical prices for {symbol}: {e}")
            continue

    logger.info(
        f"Stock price history sync complete: {processed} processed, {errors} errors"
    )


async def _fetch_and_store_prices(
    history_db, symbol: str, yahoo_symbol: Optional[str] = None
):
    """Fetch historical prices from Yahoo Finance and store in per-symbol database."""
    try:
        # Check if we have monthly data (indicates initial seeding was done)
        cursor = await history_db.execute("SELECT COUNT(*) FROM monthly_prices")
        has_monthly = (await cursor.fetchone())[0] > 0

        # Initial seed: 10 years for CAGR calculations
        # Ongoing updates: 1 year for daily charts
        period = "1y" if has_monthly else "10y"

        ohlc_data = yahoo.get_historical_prices(symbol, yahoo_symbol, period=period)

        if not ohlc_data:
            logger.warning(f"No price data from Yahoo for {symbol}")
            return

        logger.info(
            f"Fetched {len(ohlc_data)} price records for {symbol} ({period}) from Yahoo"
        )

        async with history_db.transaction():
            for ohlc in ohlc_data:
                date = ohlc.date.strftime("%Y-%m-%d")
                close = ohlc.close
                open_price = ohlc.open
                high = ohlc.high
                low = ohlc.low
                volume = ohlc.volume

                await history_db.execute(
                    """
                    INSERT OR REPLACE INTO daily_prices
                    (date, open_price, high_price, low_price, close_price, volume, source, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'yahoo', datetime('now'))
                    """,
                    (date, open_price, high, low, close, volume),
                )

            # Aggregate to monthly
            await _aggregate_to_monthly(history_db)

        logger.debug(f"Stored {len(ohlc_data)} Yahoo price records for {symbol}")

    except Exception as e:
        logger.error(f"Failed to fetch/store Yahoo prices for {symbol}: {e}")
        raise


async def _aggregate_to_monthly(history_db):
    """Aggregate daily prices to monthly averages for this symbol."""
    await history_db.execute(
        """
        INSERT OR REPLACE INTO monthly_prices
        (year_month, avg_close, avg_adj_close, source, created_at)
        SELECT
            strftime('%Y-%m', date) as year_month,
            AVG(close_price) as avg_close,
            AVG(close_price) as avg_adj_close,
            'calculated',
            datetime('now')
        FROM daily_prices
        GROUP BY strftime('%Y-%m', date)
    """
    )
