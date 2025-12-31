"""Chart data API endpoints."""

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.core.cache.cache import cache
from app.core.database.manager import DatabaseManager
from app.infrastructure.dependencies import DatabaseManagerDep, SecurityRepositoryDep
from app.infrastructure.external import yahoo_finance as yahoo
from app.infrastructure.external.tradernet_connection import ensure_tradernet_connected
from app.modules.universe.domain.symbol_resolver import is_isin

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


async def _get_cached_security_prices(
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


async def _store_security_prices(
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
    Per-stock caching for 12 hours - new stocks are fetched immediately.
    """
    try:
        start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

        # Get all active stocks
        stocks = await db_manager.config.fetchall(
            "SELECT symbol FROM securities WHERE active = 1"
        )

        result = {}
        for stock in stocks:
            symbol = stock["symbol"]
            cache_key = f"sparkline:{symbol}"

            # Check per-stock cache first
            cached = cache.get(cache_key)
            if cached is not None:
                result[symbol] = cached
                continue

            # Fetch from database for this stock
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
                sparkline_data = [
                    {"time": row["date"], "value": row["close_price"]}
                    for row in prices
                    if row["date"] and row["close_price"]
                ]
                result[symbol] = sparkline_data
                # Cache this stock's sparkline for 12 hours
                cache.set(cache_key, sparkline_data, ttl_seconds=43200)

        return result
    except Exception as e:
        logger.error(f"Failed to get sparklines data: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get sparklines data: {str(e)}"
        )


async def _should_fetch_data(
    cached_data: list[dict], start_date: Optional[datetime]
) -> bool:
    """Determine if we need to fetch more data from API."""
    if not cached_data:
        return True
    if start_date:
        first_cached_date = datetime.strptime(cached_data[0]["time"], "%Y-%m-%d")
        return first_cached_date > start_date
    return False


async def _fetch_from_tradernet(
    symbol: str, fetch_start: datetime, fetch_end: datetime, db_manager: DatabaseManager
) -> list[dict]:
    """Fetch stock prices from Tradernet API."""
    try:
        tradernet_client = await ensure_tradernet_connected(raise_on_error=False)
        if not tradernet_client:
            return []

        ohlc_data = tradernet_client.get_historical_prices(
            symbol, start=fetch_start, end=fetch_end
        )
        if not ohlc_data:
            return []

        fetched_data = [
            {"time": ohlc.timestamp.strftime("%Y-%m-%d"), "value": ohlc.close}
            for ohlc in ohlc_data
        ]
        await _store_security_prices(symbol, ohlc_data, "tradernet", db_manager)
        return fetched_data
    except Exception as e:
        logger.warning(f"Failed to fetch from Tradernet for {symbol}: {e}")
        return []


async def _fetch_from_yahoo(
    symbol: str, range_str: str, db_manager: DatabaseManager
) -> list[dict]:
    """Fetch stock prices from Yahoo Finance API."""
    try:
        period_map = {
            "1M": "1mo",
            "3M": "3mo",
            "6M": "6mo",
            "1Y": "1y",
            "5Y": "5y",
            "10Y": "10y",
            "all": "max",
        }
        yahoo_period = period_map.get(range_str, "10y")

        historical_prices = yahoo.get_historical_prices(symbol, period=yahoo_period)
        if not historical_prices:
            return []

        fetched_data = [
            {"time": hp.date.strftime("%Y-%m-%d"), "value": hp.close}
            for hp in historical_prices
        ]
        await _store_security_prices(symbol, historical_prices, "yahoo", db_manager)
        return fetched_data
    except Exception as e:
        logger.error(f"Failed to fetch from Yahoo for {symbol}: {e}")
        return []


def _combine_and_filter_data(
    cached_data: list[dict], fetched_data: list[dict], start_date: Optional[datetime]
) -> list[dict]:
    """Combine cached and fetched data, remove duplicates, and filter by date."""
    # Combine data, removing duplicates (later entries override earlier)
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


@router.get("/stocks/{isin}")
async def get_stock_chart(
    isin: str,
    db_manager: DatabaseManagerDep,
    security_repo: SecurityRepositoryDep,
    range: str = Query("1Y", description="Time range: 1M, 3M, 6M, 1Y, all"),
    source: str = Query("tradernet", description="Data source: tradernet or yahoo"),
):
    """
    Get stock price history for charting.

    Returns array of {time: 'YYYY-MM-DD', value: number} using close prices.
    Checks cache first, then fetches from API if missing.

    Args:
        isin: Stock ISIN (e.g., US0378331005)
    """
    try:
        # Validate ISIN format
        isin = isin.strip().upper()
        if not is_isin(isin):
            raise HTTPException(status_code=400, detail="Invalid ISIN format")

        # Look up stock by ISIN to get tradernet symbol
        stock = await security_repo.get_by_isin(isin)
        if not stock:
            raise HTTPException(status_code=404, detail="Stock not found")

        # Use the tradernet symbol for history database lookup
        symbol = stock.symbol
        start_date = _parse_date_range(range)
        cached_data = await _get_cached_security_prices(symbol, start_date, db_manager)

        need_fetch = await _should_fetch_data(cached_data, start_date)
        fetched_data = []

        if need_fetch:
            fetch_start = start_date if start_date else datetime(2010, 1, 1)
            fetch_end = datetime.now()

            if source == "tradernet":
                fetched_data = await _fetch_from_tradernet(
                    symbol, fetch_start, fetch_end, db_manager
                )
                if not fetched_data:
                    source = "yahoo"

            if source == "yahoo" and not fetched_data:
                fetched_data = await _fetch_from_yahoo(symbol, range, db_manager)

        return _combine_and_filter_data(cached_data, fetched_data, start_date)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get stock chart data for ISIN {isin}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get stock chart data: {str(e)}"
        )
