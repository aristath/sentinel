"""Daily pipeline job for per-symbol data processing.

This job runs hourly and processes stocks sequentially:
1. Gets stocks that haven't been synced in 24 hours (last_synced)
2. For each stock, runs the data pipeline:
   - Sync historical prices from Yahoo
   - Calculate technical metrics
   - Refresh stock score
3. Updates LED display to show progress
4. Updates last_synced timestamp after successful processing

Stocks are processed one at a time to avoid overwhelming external APIs
and to provide clear progress feedback on the LED display.
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from app.infrastructure.events import SystemEvent, emit
from app.infrastructure.hardware.display_service import (
    clear_processing,
    set_error,
    set_processing,
)
from app.infrastructure.locking import file_lock

logger = logging.getLogger(__name__)

# How old last_synced must be to require processing (24 hours)
SYNC_THRESHOLD_HOURS = 24


async def run_daily_pipeline():
    """
    Run the daily pipeline for all stocks needing sync.

    This is the main entry point called by the scheduler every hour.
    """
    async with file_lock("daily_pipeline", timeout=3600.0):
        await _run_daily_pipeline_internal()


async def _run_daily_pipeline_internal():
    """Internal daily pipeline implementation."""
    logger.info("Starting daily pipeline...")

    emit(SystemEvent.SYNC_START)

    try:
        stocks = await _get_stocks_needing_sync()

        if not stocks:
            logger.info("All stocks are up to date, no processing needed")
            emit(SystemEvent.SYNC_COMPLETE)
            return

        logger.info(f"Processing {len(stocks)} stocks needing sync")

        processed = 0
        errors = 0

        for stock in stocks:
            try:
                await _process_single_stock(stock.symbol)
                processed += 1
            except Exception as e:
                logger.error(f"Pipeline failed for {stock.symbol}: {e}")
                errors += 1

        logger.info(f"Daily pipeline complete: {processed} processed, {errors} errors")
        emit(SystemEvent.SYNC_COMPLETE)

    except Exception as e:
        logger.error(f"Daily pipeline failed: {e}", exc_info=True)
        error_msg = "DAILY PIPELINE CRASHES"
        emit(SystemEvent.ERROR_OCCURRED, message=error_msg)
        set_error(error_msg)
    finally:
        clear_processing()


async def refresh_single_stock(symbol: str) -> dict[str, Any]:
    """
    Force refresh a single stock's data.

    This bypasses the last_synced check and immediately processes the stock.
    Used by the API endpoint for manual refreshes.

    Args:
        symbol: The stock symbol to refresh

    Returns:
        Dict with status and details
    """
    logger.info(f"Force refreshing data for {symbol}")

    try:
        set_processing(f"PROCESSING SINGLE STOCK ({symbol})")

        # Run the full pipeline for this stock
        await _sync_historical_for_symbol(symbol)
        await _detect_and_update_country_and_exchange(symbol)
        await _detect_and_update_industry(symbol)
        await _calculate_metrics_for_symbol(symbol)
        await _refresh_score_for_symbol(symbol)
        await _update_last_synced(symbol)

        logger.info(f"Force refresh complete for {symbol}")
        return {"status": "success", "symbol": symbol}

    except Exception as e:
        logger.error(f"Force refresh failed for {symbol}: {e}")
        set_error(f"STOCK REFRESH FAILED ({symbol})")
        return {"status": "error", "symbol": symbol, "reason": str(e)}
    finally:
        clear_processing()


async def _get_stocks_needing_sync() -> list:
    """
    Get all active stocks that need to be synced.

    A stock needs sync if:
    - last_synced is NULL (never synced)
    - last_synced is older than SYNC_THRESHOLD_HOURS

    Returns:
        List of stock objects needing sync
    """
    all_stocks = await _get_all_active_stocks()
    threshold = datetime.now() - timedelta(hours=SYNC_THRESHOLD_HOURS)

    stocks_needing_sync = []
    for stock in all_stocks:
        if stock.last_synced is None:
            stocks_needing_sync.append(stock)
        else:
            try:
                last_synced = datetime.fromisoformat(stock.last_synced)
                if last_synced < threshold:
                    stocks_needing_sync.append(stock)
            except (ValueError, TypeError):
                # Invalid date format, treat as needing sync
                stocks_needing_sync.append(stock)

    return stocks_needing_sync


async def _get_all_active_stocks() -> list:
    """Get all active stocks from the database."""
    from app.repositories import StockRepository

    stock_repo = StockRepository()
    return await stock_repo.get_all_active()


async def _process_single_stock(symbol: str):
    """
    Process a single stock through the full data pipeline.

    Steps:
    1. Sync historical prices from Yahoo
    2. Detect and update industry from Yahoo Finance
    3. Calculate technical metrics (RSI, EMA, CAGR, etc.)
    4. Refresh stock score

    Args:
        symbol: The stock symbol to process
    """
    logger.info(f"Processing {symbol}...")
    set_processing(f"PROCESSING SINGLE STOCK ({symbol})")

    try:
        # Step 1: Sync historical prices
        await _sync_historical_for_symbol(symbol)

        # Step 2: Detect and update country/exchange from Yahoo Finance
        await _detect_and_update_country_and_exchange(symbol)

        # Step 3: Detect and update industry from Yahoo Finance
        await _detect_and_update_industry(symbol)

        # Step 4: Calculate metrics
        metrics_count = await _calculate_metrics_for_symbol(symbol)
        logger.debug(f"Calculated {metrics_count} metrics for {symbol}")

        # Step 5: Refresh score
        await _refresh_score_for_symbol(symbol)

        # Mark as synced
        await _update_last_synced(symbol)

        logger.info(f"Pipeline complete for {symbol}")

    except Exception as e:
        logger.error(f"Pipeline error for {symbol}: {e}", exc_info=True)
        set_error(f"STOCK REFRESH FAILED ({symbol})")
        # Don't update last_synced on error - will retry next hour
        raise
    finally:
        clear_processing()


async def _sync_historical_for_symbol(symbol: str):
    """
    Sync historical prices for a single symbol.

    Fetches daily and monthly prices from Yahoo Finance.
    """
    from app.config import settings
    from app.infrastructure.database.manager import get_db_manager
    from app.infrastructure.external import yahoo_finance as yahoo

    db_manager = get_db_manager()

    # Get the stock's yahoo_symbol
    cursor = await db_manager.config.execute(
        "SELECT yahoo_symbol FROM stocks WHERE symbol = ?", (symbol,)
    )
    row = await cursor.fetchone()
    yahoo_symbol = row[0] if row else None

    # Get history database for this symbol
    history_db = await db_manager.history(symbol)

    # Check if we have monthly data (indicates initial seeding was done)
    cursor = await history_db.execute("SELECT COUNT(*) FROM monthly_prices")
    row = await cursor.fetchone()
    has_monthly = row[0] > 0 if row else False

    # Initial seed: 10 years for CAGR calculations
    # Ongoing updates: 1 year for daily charts
    period = "1y" if has_monthly else "10y"

    ohlc_data = yahoo.get_historical_prices(symbol, yahoo_symbol, period=period)

    if not ohlc_data:
        logger.warning(f"No price data from Yahoo for {symbol}")
        return

    logger.info(f"Fetched {len(ohlc_data)} price records for {symbol} ({period})")

    async with history_db.transaction():
        for ohlc in ohlc_data:
            date = ohlc.date.strftime("%Y-%m-%d")
            await history_db.execute(
                """
                INSERT OR REPLACE INTO daily_prices
                (date, open_price, high_price, low_price, close_price, volume,
                 source, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'yahoo', datetime('now'))
                """,
                (date, ohlc.open, ohlc.high, ohlc.low, ohlc.close, ohlc.volume),
            )

        # Aggregate to monthly
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

    # Rate limit delay
    import asyncio

    await asyncio.sleep(settings.external_api_rate_limit_delay)


async def _detect_and_update_industry(symbol: str):
    """
    Detect and update industry from Yahoo Finance for a stock.

    This runs automatically during the daily pipeline to keep industry
    data up to date from Yahoo Finance.

    Args:
        symbol: The stock symbol to update
    """
    from app.infrastructure.database.manager import get_db_manager
    from app.infrastructure.external import yahoo_finance as yahoo
    from app.repositories import StockRepository

    db_manager = get_db_manager()

    # Get the stock's yahoo_symbol
    cursor = await db_manager.config.execute(
        "SELECT yahoo_symbol FROM stocks WHERE symbol = ?", (symbol,)
    )
    row = await cursor.fetchone()
    if not row:
        logger.warning(f"Stock {symbol} not found for industry detection")
        return

    yahoo_symbol = row[0]

    # Detect industry from Yahoo Finance
    try:
        detected_industry = yahoo.get_stock_industry(symbol, yahoo_symbol)
        if detected_industry:
            # Update the stock's industry in the database
            stock_repo = StockRepository()
            await stock_repo.update(symbol, industry=detected_industry)
            logger.info(f"Updated industry for {symbol}: {detected_industry}")
        else:
            logger.debug(f"No industry detected for {symbol} from Yahoo Finance")
    except Exception as e:
        # Don't fail the entire pipeline if industry detection fails
        logger.warning(f"Failed to detect industry for {symbol}: {e}")


# Fallback mapping: exchange name -> country (used only when Yahoo doesn't provide country)
EXCHANGE_TO_COUNTRY = {
    "Amsterdam": "Netherlands",
    "Athens": "Greece",
    "Brussels": "Belgium",
    "Copenhagen": "Denmark",
    "Frankfurt": "Germany",
    "Helsinki": "Finland",
    "Hong Kong": "Hong Kong",
    "Lisbon": "Portugal",
    "London": "United Kingdom",
    "LSE": "United Kingdom",
    "Madrid": "Spain",
    "Milan": "Italy",
    "NASDAQ": "United States",
    "NYSE": "United States",
    "NasdaqGS": "United States",
    "NasdaqGM": "United States",
    "Oslo": "Norway",
    "Paris": "France",
    "Stockholm": "Sweden",
    "Swiss": "Switzerland",
    "Tokyo": "Japan",
    "Toronto": "Canada",
    "Vienna": "Austria",
    "XETRA": "Germany",
}


async def _detect_and_update_country_and_exchange(symbol: str):
    """
    Detect and update country and exchange from Yahoo Finance for a stock.

    This runs automatically during the daily pipeline to keep country
    and exchange data up to date from Yahoo Finance.

    Args:
        symbol: The stock symbol to update
    """
    from app.infrastructure.database.manager import get_db_manager
    from app.infrastructure.external import yahoo_finance as yahoo
    from app.repositories import StockRepository

    db_manager = get_db_manager()

    # Get the stock's yahoo_symbol
    cursor = await db_manager.config.execute(
        "SELECT yahoo_symbol FROM stocks WHERE symbol = ?", (symbol,)
    )
    row = await cursor.fetchone()
    if not row:
        logger.warning(f"Stock {symbol} not found for country/exchange detection")
        return

    yahoo_symbol = row[0]

    # Detect country and exchange from Yahoo Finance
    try:
        detected_country, detected_exchange = yahoo.get_stock_country_and_exchange(
            symbol, yahoo_symbol
        )

        # Fallback: infer country from exchange if Yahoo didn't provide it
        if not detected_country and detected_exchange:
            detected_country = EXCHANGE_TO_COUNTRY.get(detected_exchange)
            if detected_country:
                logger.debug(
                    f"Inferred country for {symbol} from exchange {detected_exchange}: {detected_country}"
                )

        if detected_country or detected_exchange:
            # Update the stock's country and fullExchangeName in the database
            stock_repo = StockRepository()
            updates = {}
            if detected_country:
                updates["country"] = detected_country
            if detected_exchange:
                updates["fullExchangeName"] = detected_exchange
            if updates:
                await stock_repo.update(symbol, **updates)
                logger.info(
                    f"Updated country/exchange for {symbol}: country={detected_country}, exchange={detected_exchange}"
                )
        else:
            logger.debug(
                f"No country/exchange detected for {symbol} from Yahoo Finance"
            )
    except Exception as e:
        # Don't fail the entire pipeline if country/exchange detection fails
        logger.warning(f"Failed to detect country/exchange for {symbol}: {e}")


async def _calculate_metrics_for_symbol(symbol: str) -> int:
    """
    Calculate and store all metrics for a single symbol.

    Returns:
        Number of metrics calculated
    """
    from app.jobs.metrics_calculation import calculate_all_metrics_for_symbol

    return await calculate_all_metrics_for_symbol(symbol)


async def _refresh_score_for_symbol(symbol: str):
    """
    Refresh the score for a single symbol.

    Uses the scoring domain to calculate the stock's score based on
    historical data, fundamentals, and portfolio context.
    """
    from datetime import datetime

    from app.domain.scoring import calculate_stock_score
    from app.infrastructure.database.manager import get_db_manager
    from app.infrastructure.external import yahoo_finance as yahoo

    db_manager = get_db_manager()

    # Get stock metadata
    cursor = await db_manager.config.execute(
        "SELECT yahoo_symbol, country, industry FROM stocks WHERE symbol = ?",
        (symbol,),
    )
    row = await cursor.fetchone()
    if not row:
        logger.warning(f"Stock {symbol} not found in config")
        return

    yahoo_symbol, country, industry = row

    # Get price data from history database
    history_db = await db_manager.history(symbol)

    cursor = await history_db.execute(
        """
        SELECT date, open_price, high_price, low_price, close_price, volume
        FROM daily_prices
        ORDER BY date DESC
        LIMIT 365
        """
    )
    rows = await cursor.fetchall()
    daily_prices = [
        {
            "date": r[0],
            "open": r[1],
            "high": r[2],
            "low": r[3],
            "close": r[4],
            "volume": r[5],
        }
        for r in list(reversed(list(rows)))
    ]

    cursor = await history_db.execute(
        """
        SELECT year_month, avg_adj_close
        FROM monthly_prices
        ORDER BY year_month DESC
        LIMIT 120
        """
    )
    rows = await cursor.fetchall()
    monthly_prices = [
        {"year_month": r[0], "avg_adj_close": r[1]} for r in list(reversed(list(rows)))
    ]

    if not daily_prices or len(daily_prices) < 50:
        logger.warning(f"Insufficient daily data for {symbol}")
        return

    if not monthly_prices or len(monthly_prices) < 12:
        logger.warning(f"Insufficient monthly data for {symbol}")
        return

    # Get fundamentals from Yahoo
    fundamentals = yahoo.get_fundamental_data(symbol, yahoo_symbol=yahoo_symbol)

    # Build portfolio context
    portfolio_context = await _build_portfolio_context(db_manager)

    # Calculate score
    score = await calculate_stock_score(
        symbol=symbol,
        daily_prices=daily_prices,
        monthly_prices=monthly_prices,
        fundamentals=fundamentals,
        country=country,
        industry=industry,
        portfolio_context=portfolio_context,
        yahoo_symbol=yahoo_symbol,
    )

    if score and score.group_scores:
        gs = score.group_scores

        await db_manager.state.execute(
            """
            INSERT OR REPLACE INTO scores
            (symbol, quality_score, opportunity_score, analyst_score,
             allocation_fit_score, total_score, calculated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                symbol,
                (gs.get("long_term", 0) + gs.get("fundamentals", 0)) / 2,
                gs.get("opportunity", 0),
                gs.get("opinion", 0),
                gs.get("diversification", 0),
                score.total_score,
                datetime.now().isoformat(),
            ),
        )
        await db_manager.state.commit()


async def _build_portfolio_context(db_manager):
    """Build portfolio context for allocation fit calculations."""
    from app.domain.scoring import PortfolioContext

    # Get current positions
    cursor = await db_manager.state.execute(
        "SELECT symbol, market_value_eur FROM positions"
    )
    positions = {row[0]: row[1] or 0 for row in await cursor.fetchall()}
    total_value = sum(positions.values())

    # Get group targets (use repository for consistency)
    from app.repositories import AllocationRepository, GroupingRepository

    allocation_repo = AllocationRepository(db=db_manager.config)
    country_weights = await allocation_repo.get_country_group_targets()
    industry_weights = await allocation_repo.get_industry_group_targets()

    # Build group mappings (country -> group, industry -> group)
    grouping_repo = GroupingRepository(db=db_manager.config)
    country_groups = await grouping_repo.get_country_groups()
    industry_groups = await grouping_repo.get_industry_groups()

    # Build reverse mappings: country -> group, industry -> group
    country_to_group = {}
    for group_name, country_names in country_groups.items():
        for country_name in country_names:
            country_to_group[country_name] = group_name

    industry_to_group = {}
    for group_name, industry_names in industry_groups.items():
        for industry_name in industry_names:
            industry_to_group[industry_name] = group_name

    # Get stock metadata for scoring
    cursor = await db_manager.config.execute(
        "SELECT symbol, country, industry FROM stocks WHERE active = 1"
    )
    stock_data = await cursor.fetchall()

    stock_countries = {row[0]: row[1] for row in stock_data if row[1]}
    stock_industries = {row[0]: row[2] for row in stock_data if row[2]}

    # Get scores for quality weighting (from calculations.db)
    cursor = await db_manager.calculations.execute(
        "SELECT symbol, quality_score FROM scores"
    )
    stock_scores = {row[0]: row[1] for row in await cursor.fetchall() if row[1]}

    return PortfolioContext(
        country_weights=country_weights,
        industry_weights=industry_weights,
        positions=positions,
        total_value=total_value,
        stock_countries=stock_countries,
        stock_industries=stock_industries,
        stock_scores=stock_scores,
        country_to_group=country_to_group,
        industry_to_group=industry_to_group,
    )


async def _update_last_synced(symbol: str):
    """Update the last_synced timestamp for a stock."""
    from app.infrastructure.database.manager import get_db_manager

    db_manager = get_db_manager()
    now = datetime.now().isoformat()

    await db_manager.config.execute(
        "UPDATE stocks SET last_synced = ?, updated_at = ? WHERE symbol = ?",
        (now, now, symbol),
    )
    await db_manager.config.commit()
