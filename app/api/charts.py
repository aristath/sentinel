"""Chart data API endpoints."""

import logging
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from app.infrastructure.dependencies import get_db
from app.services.tradernet import get_tradernet_client
from app.services import yahoo
import aiosqlite

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
    else:
        return None


@router.get("/portfolio")
async def get_portfolio_chart(
    range: str = Query("all", description="Time range: 1M, 3M, 6M, 1Y, all"),
    db: aiosqlite.Connection = Depends(get_db),
):
    """
    Get portfolio value history for charting.
    
    Returns array of {time: 'YYYY-MM-DD', value: number} for portfolio total_value.
    If data is missing, attempts to fetch from Tradernet API (if available).
    """
    try:
        start_date = _parse_date_range(range)
        
        # Query portfolio_snapshots
        if start_date:
            start_date_str = start_date.strftime("%Y-%m-%d")
            cursor = await db.execute("""
                SELECT date, total_value 
                FROM portfolio_snapshots 
                WHERE date >= ?
                ORDER BY date ASC
            """, (start_date_str,))
        else:
            cursor = await db.execute("""
                SELECT date, total_value 
                FROM portfolio_snapshots 
                ORDER BY date ASC
            """)
        
        rows = await cursor.fetchall()
        result = [{"time": row["date"], "value": row["total_value"]} for row in rows]
        
        # Note: Tradernet API doesn't provide historical portfolio snapshots directly
        # We can only return what's in the database (from daily sync job)
        # Historical data will accumulate over time as the sync job continues
        
        return result
    except Exception as e:
        logger.error(f"Failed to get portfolio chart data: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get portfolio chart data: {str(e)}")


async def _get_cached_stock_prices(
    db: aiosqlite.Connection,
    symbol: str,
    start_date: Optional[datetime]
) -> list[dict]:
    """Get cached stock prices from database."""
    if start_date:
        start_date_str = start_date.strftime("%Y-%m-%d")
        cursor = await db.execute("""
            SELECT date, close_price 
            FROM stock_price_history 
            WHERE symbol = ? AND date >= ?
            ORDER BY date ASC
        """, (symbol, start_date_str))
    else:
        cursor = await db.execute("""
            SELECT date, close_price 
            FROM stock_price_history 
            WHERE symbol = ?
            ORDER BY date ASC
        """, (symbol,))
    
    rows = await cursor.fetchall()
    return [{"time": row["date"], "value": row["close_price"]} for row in rows]


async def _store_stock_prices(
    db: aiosqlite.Connection,
    symbol: str,
    prices: list,
    source: str
):
    """Store stock prices in cache table."""
    from datetime import datetime
    
    now = datetime.now().isoformat()
    for price_data in prices:
        # price_data can be OHLC from Tradernet or HistoricalPrice from Yahoo
        if hasattr(price_data, 'timestamp'):
            # Tradernet OHLC
            date = price_data.timestamp.strftime("%Y-%m-%d")
            close_price = price_data.close
            open_price = price_data.open
            high_price = price_data.high
            low_price = price_data.low
            volume = price_data.volume
        elif hasattr(price_data, 'date'):
            # Yahoo HistoricalPrice
            date = price_data.date.strftime("%Y-%m-%d")
            close_price = price_data.close
            open_price = price_data.open
            high_price = price_data.high
            low_price = price_data.low
            volume = price_data.volume
        else:
            continue
        
        await db.execute("""
            INSERT OR REPLACE INTO stock_price_history 
            (symbol, date, close_price, open_price, high_price, low_price, volume, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (symbol, date, close_price, open_price, high_price, low_price, volume, source, now))
    
    await db.commit()


@router.get("/sparklines")
async def get_all_stock_sparklines(
    db: aiosqlite.Connection = Depends(get_db),
):
    """
    Get 1-year sparkline data for all active stocks.
    Returns dict: {symbol: [{time, value}, ...]}
    """
    try:
        start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

        cursor = await db.execute("""
            SELECT s.symbol, sph.date, sph.close_price
            FROM stocks s
            LEFT JOIN stock_price_history sph ON s.symbol = sph.symbol
                AND sph.date >= ?
            WHERE s.active = 1
            ORDER BY s.symbol, sph.date ASC
        """, (start_date,))

        rows = await cursor.fetchall()

        # Group by symbol
        result = {}
        for row in rows:
            symbol = row["symbol"]
            if symbol not in result:
                result[symbol] = []
            if row["date"] and row["close_price"]:
                result[symbol].append({
                    "time": row["date"],
                    "value": row["close_price"]
                })

        return result
    except Exception as e:
        logger.error(f"Failed to get sparklines data: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get sparklines data: {str(e)}")


@router.get("/stocks/{symbol}")
async def get_stock_chart(
    symbol: str,
    range: str = Query("1Y", description="Time range: 1M, 3M, 6M, 1Y, all"),
    source: str = Query("tradernet", description="Data source: tradernet or yahoo"),
    db: aiosqlite.Connection = Depends(get_db),
):
    """
    Get stock price history for charting.
    
    Returns array of {time: 'YYYY-MM-DD', value: number} using close prices.
    Checks cache first, then fetches from API if missing.
    """
    try:
        start_date = _parse_date_range(range)
        
        # Check cache first
        cached_data = await _get_cached_stock_prices(db, symbol, start_date)
        
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
                    tradernet_client = get_tradernet_client()
                    if not tradernet_client.is_connected:
                        tradernet_client.connect()
                    
                    if tradernet_client.is_connected:
                        ohlc_data = tradernet_client.get_historical_prices(
                            symbol,
                            start=fetch_start,
                            end=fetch_end
                        )
                        if ohlc_data:
                            fetched_data = [
                                {"time": ohlc.timestamp.strftime("%Y-%m-%d"), "value": ohlc.close}
                                for ohlc in ohlc_data
                            ]
                            # Store in cache
                            await _store_stock_prices(db, symbol, ohlc_data, "tradernet")
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
                        "all": "max"
                    }
                    yahoo_period = period_map.get(range, "1y")
                    
                    historical_prices = yahoo.get_historical_prices(symbol, period=yahoo_period)
                    if historical_prices:
                        fetched_data = [
                            {"time": hp.date.strftime("%Y-%m-%d"), "value": hp.close}
                            for hp in historical_prices
                        ]
                        # Store in cache
                        await _store_stock_prices(db, symbol, historical_prices, "yahoo")
                except Exception as e:
                    logger.error(f"Failed to fetch from Yahoo for {symbol}: {e}")
        
        # Combine cached and fetched data, removing duplicates
        all_data = {}
        for item in cached_data:
            all_data[item["time"]] = item["value"]
        for item in fetched_data:
            all_data[item["time"]] = item["value"]
        
        # Convert to list and sort by date
        result = [{"time": date, "value": value} for date, value in sorted(all_data.items())]
        
        # Filter by date range if specified
        if start_date:
            result = [
                item for item in result
                if datetime.strptime(item["time"], "%Y-%m-%d") >= start_date
            ]
        
        return result
    except Exception as e:
        logger.error(f"Failed to get stock chart data for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stock chart data: {str(e)}")
