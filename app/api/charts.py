"""Chart data API endpoints."""

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.infrastructure.cache import cache
from app.infrastructure.database.manager import DatabaseManager
from app.infrastructure.dependencies import DatabaseManagerDep
from app.infrastructure.external import yahoo_finance as yahoo
from app.infrastructure.external.tradernet_connection import ensure_tradernet_connected

logger = logging.getLogger(__name__)

router = APIRouter()


def _parse_date_range(range_str: str) -> Optional[datetime]:
    """Convert range string to start date."""
    if range_str == "all":
        return None

    now = datetime.now()
    if range_str == "1M":
        return now - timedelta(days=30)
    elif range_str == "3M":
        return now - timedelta(days=90)
    elif range_str == "6M":
        return now - timedelta(days=180)
    elif range_str == "1Y":
        return now - timedelta(days=365)
    elif range_str == "5Y":
        return now - timedelta(days=365 * 5)
    elif range_str == "10Y":
        return now - timedelta(days=365 * 10)
    else:
        return None


async def _get_cached_stock_prices(
    symbol: str, start_date: Optional[datetime], db_manager: DatabaseManager
) -> list[dict]:
    """Get cached stock prices from per-symbol database."""

    if start_date:
        start_date_str = start_date.strftime("%Y-%m-%d")
        history_db = await db_manager.history(symbol)
        rows = await history_db.fetchall(
            """
            SELECT date, close_price
            FROM daily_prices
            WHERE date >= ?
            ORDER BY date ASC
            """,
            (start_date_str,),
        )
    else:
        history_db = await db_manager.history(symbol)
        rows = await history_db.fetchall(
            """
            SELECT date, close_price
            FROM daily_prices
            ORDER BY date ASC
            """
        )

    return [{"time": row["date"], "value": row["close_price"]} for row in rows]


async def _store_stock_prices(
    symbol: str, prices: list, source: str, db_manager: DatabaseManager
):
    """Store stock prices in per-symbol database."""
    now = datetime.now().isoformat()

    for price_data in prices:
        # price_data can be OHLC from Tradernet or HistoricalPrice from Yahoo
        if hasattr(price_data, "timestamp"):
            # Tradernet OHLC
            date = price_data.timestamp.strftime("%Y-%m-%d")
            close_price = price_data.close
            open_price = price_data.open
            high_price = price_data.high
            low_price = price_data.low
            volume = price_data.volume
        elif hasattr(price_data, "date"):
            # Yahoo HistoricalPrice
            date = price_data.date.strftime("%Y-%m-%d")
            close_price = price_data.close
            open_price = price_data.open
            high_price = price_data.high
            low_price = price_data.low
            volume = price_data.volume
        else:
            continue

        history_db = await db_manager.history(symbol)
        await history_db.execute(
            """
            INSERT OR REPLACE INTO daily_prices
            (date, close_price, open_price, high_price, low_price, volume, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (date, close_price, open_price, high_price, low_price, volume, source, now),
        )


@router.get("/sparklines")
async def get_all_stock_sparklines(db_manager: DatabaseManagerDep):
    """
    Get 1-year sparkline data for all active stocks.
    Returns dict: {symbol: [{time, value}, ...]}
    Cached for 12 hours.
    """
    # Check cache first
    cached = cache.get("sparklines")
    if cached is not None:
        return cached

    try:
        start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

        # Get all active stocks
        stocks = await db_manager.config.fetchall(
            "SELECT symbol FROM stocks WHERE active = 1"
        )

        result = {}
        for stock in stocks:
            symbol = stock["symbol"]
            # Get prices from per-symbol database
            history_db = await db_manager.history(symbol)
            prices = await history_db.fetchall(
                """
                SELECT date, close_price
                FROM daily_prices
                WHERE date >= ?
                ORDER BY date ASC
                """,
                (start_date,),
            )
            if prices:
                result[symbol] = [
                    {"time": row["date"], "value": row["close_price"]}
                    for row in prices
                    if row["date"] and row["close_price"]
                ]

        # Cache for 12 hours
        cache.set("sparklines", result, ttl_seconds=43200)
        return result
    except Exception as e:
        logger.error(f"Failed to get sparklines data: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get sparklines data: {str(e)}"
        )


@router.get("/stocks/{symbol}")
async def get_stock_chart(
    symbol: str,
    db_manager: DatabaseManagerDep,
    range: str = Query("1Y", description="Time range: 1M, 3M, 6M, 1Y, all"),
    source: str = Query("tradernet", description="Data source: tradernet or yahoo"),
):
    """
    Get stock price history for charting.

    Returns array of {time: 'YYYY-MM-DD', value: number} using close prices.
    Checks cache first, then fetches from API if missing.
    """
    try:
        start_date = _parse_date_range(range)

        # Check cache first
        cached_data = await _get_cached_stock_prices(symbol, start_date, db_manager)

        # Determine if we need to fetch more data
        need_fetch = False
        if not cached_data:
            need_fetch = True
        elif start_date:
            # Check if we have data covering the full range
            first_cached_date = datetime.strptime(cached_data[0]["time"], "%Y-%m-%d")
            if first_cached_date > start_date:
                need_fetch = True

        fetched_data = []
        if need_fetch:
            # Determine date range to fetch
            if start_date:
                fetch_start = start_date
            else:
                # For "all" range, fetch from 2010-01-01
                fetch_start = datetime(2010, 1, 1)

            fetch_end = datetime.now()

            # Try to fetch from API
            if source == "tradernet":
                try:
                    tradernet_client = await ensure_tradernet_connected(
                        raise_on_error=False
                    )
                    if tradernet_client:
                        ohlc_data = tradernet_client.get_historical_prices(
                            symbol, start=fetch_start, end=fetch_end
                        )
                        if ohlc_data:
                            fetched_data = [
                                {
                                    "time": ohlc.timestamp.strftime("%Y-%m-%d"),
                                    "value": ohlc.close,
                                }
                                for ohlc in ohlc_data
                            ]
                            # Store in cache
                            await _store_stock_prices(
                                symbol, ohlc_data, "tradernet", db_manager
                            )
                except Exception as e:
                    logger.warning(f"Failed to fetch from Tradernet for {symbol}: {e}")
                    # Fallback to Yahoo
                    source = "yahoo"

            if source == "yahoo" and not fetched_data:
                try:
                    # Map range to Yahoo period
                    period_map = {
                        "1M": "1mo",
                        "3M": "3mo",
                        "6M": "6mo",
                        "1Y": "1y",
                        "5Y": "5y",
                        "10Y": "10y",
                        "all": "max",
                    }
                    yahoo_period = period_map.get(range, "10y")

                    historical_prices = yahoo.get_historical_prices(
                        symbol, period=yahoo_period
                    )
                    if historical_prices:
                        fetched_data = [
                            {"time": hp.date.strftime("%Y-%m-%d"), "value": hp.close}
                            for hp in historical_prices
                        ]
                        # Store in cache
                        await _store_stock_prices(
                            symbol, historical_prices, "yahoo", db_manager
                        )
                except Exception as e:
                    logger.error(f"Failed to fetch from Yahoo for {symbol}: {e}")

        # Combine cached and fetched data, removing duplicates
        all_data = {}
        for item in cached_data:
            all_data[item["time"]] = item["value"]
        for item in fetched_data:
            all_data[item["time"]] = item["value"]

        # Convert to list and sort by date
        result = [
            {"time": date, "value": value} for date, value in sorted(all_data.items())
        ]

        # Filter by date range if specified
        if start_date:
            result = [
                item
                for item in result
                if datetime.strptime(item["time"], "%Y-%m-%d") >= start_date
            ]

        return result
    except Exception as e:
        logger.error(f"Failed to get stock chart data for {symbol}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get stock chart data: {str(e)}"
        )
