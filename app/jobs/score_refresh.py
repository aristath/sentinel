"""Periodic stock score refresh job.

Uses the new scoring domain to calculate scores for all active stocks.
"""

import logging
from datetime import datetime
from typing import Optional

from app.domain.scoring import (
    PortfolioContext,
    calculate_stock_score,
)
from app.infrastructure.database.manager import get_db_manager
from app.infrastructure.events import SystemEvent, emit
from app.infrastructure.external import yahoo_finance as yahoo
from app.infrastructure.hardware.display_service import (
    clear_processing,
    set_error,
    set_processing,
)
from app.infrastructure.locking import file_lock

logger = logging.getLogger(__name__)


async def refresh_all_scores():
    """Refresh scores for all active stocks in the universe."""
    async with file_lock("score_refresh", timeout=300.0):
        await _refresh_all_scores_internal()


async def _refresh_all_scores_internal():
    """Internal score refresh implementation."""
    logger.info("Starting periodic score refresh...")

    emit(SystemEvent.SCORE_REFRESH_START)
    emit(SystemEvent.PROCESSING_START)
    set_processing("REFRESHING STOCK SCORES...")

    try:
        db_manager = get_db_manager()

        # Get all active stocks
        cursor = await db_manager.config.execute(
            "SELECT symbol, yahoo_symbol, geography, industry FROM stocks WHERE active = 1"
        )
        stocks = await cursor.fetchall()

        if not stocks:
            logger.info("No active stocks to score")
            emit(SystemEvent.PROCESSING_END)
            emit(SystemEvent.SCORE_REFRESH_COMPLETE)
            return

        # Build portfolio context for diversification scoring
        portfolio_context = await _build_portfolio_context(db_manager)

        scores_updated = 0
        for row in stocks:
            symbol, yahoo_symbol, geography, industry = row
            logger.info(f"Scoring {symbol}...")

            try:
                # Get price data
                daily_prices = await _get_daily_prices(db_manager, symbol, yahoo_symbol)
                monthly_prices = await _get_monthly_prices(
                    db_manager, symbol, yahoo_symbol
                )
                fundamentals = yahoo.get_fundamentals(symbol, yahoo_symbol=yahoo_symbol)

                if not daily_prices or len(daily_prices) < 50:
                    logger.warning(f"Insufficient daily data for {symbol}")
                    continue

                if not monthly_prices or len(monthly_prices) < 12:
                    logger.warning(f"Insufficient monthly data for {symbol}")
                    continue

                # Calculate score using 8-group scoring system
                # Weights are fixed (no longer configurable via settings)
                score = await calculate_stock_score(
                    symbol=symbol,
                    daily_prices=daily_prices,
                    monthly_prices=monthly_prices,
                    fundamentals=fundamentals,
                    geography=geography,
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
                            # Map new groups to old columns for compatibility
                            (gs.get("long_term", 0) + gs.get("fundamentals", 0)) / 2,
                            gs.get("opportunity", 0),
                            gs.get("opinion", 0),
                            gs.get("diversification", 0),
                            score.total_score,
                            datetime.now().isoformat(),
                        ),
                    )
                    scores_updated += 1

            except Exception as e:
                logger.error(f"Failed to score {symbol}: {e}")
                continue

        await db_manager.state.commit()
        logger.info(f"Refreshed scores for {scores_updated} stocks")

        emit(SystemEvent.PROCESSING_END)
        emit(SystemEvent.SCORE_REFRESH_COMPLETE)

    except Exception as e:
        logger.error(f"Score refresh failed: {e}")
        emit(SystemEvent.PROCESSING_END)
        error_msg = "SCORE REFRESH FAILED"
        emit(SystemEvent.ERROR_OCCURRED, message=error_msg)
        set_error(error_msg)
    finally:
        clear_processing()


async def _build_portfolio_context(db_manager) -> PortfolioContext:
    """Build portfolio context for allocation fit calculations."""
    # Get current positions
    cursor = await db_manager.state.execute(
        "SELECT symbol, market_value_eur FROM positions"
    )
    positions = {row[0]: row[1] or 0 for row in await cursor.fetchall()}
    total_value = sum(positions.values())

    # Get allocation targets
    cursor = await db_manager.config.execute(
        "SELECT name, target_pct, type FROM allocation_targets"
    )
    targets = await cursor.fetchall()

    geo_weights = {}
    industry_weights = {}
    for name, target_pct, alloc_type in targets:
        if alloc_type == "geography":
            # Convert target_pct to weight: 33% target = 0 weight, higher = positive
            geo_weights[name] = (target_pct - 0.33) / 0.15 if target_pct else 0
        elif alloc_type == "industry":
            industry_weights[name] = (target_pct - 0.10) / 0.10 if target_pct else 0

    # Get stock metadata for scoring
    cursor = await db_manager.config.execute(
        "SELECT symbol, geography, industry FROM stocks WHERE active = 1"
    )
    stock_data = await cursor.fetchall()

    stock_geographies = {row[0]: row[1] for row in stock_data if row[1]}
    stock_industries = {row[0]: row[2] for row in stock_data if row[2]}

    # Get scores for quality weighting
    cursor = await db_manager.state.execute("SELECT symbol, quality_score FROM scores")
    stock_scores = {row[0]: row[1] for row in await cursor.fetchall() if row[1]}

    return PortfolioContext(
        geo_weights=geo_weights,
        industry_weights=industry_weights,
        positions=positions,
        total_value=total_value,
        stock_geographies=stock_geographies,
        stock_industries=stock_industries,
        stock_scores=stock_scores,
    )


async def _get_daily_prices(db_manager, symbol: str, yahoo_symbol: Optional[str] = None) -> list:
    """Get daily price data from history database or Yahoo."""
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

    if len(rows) >= 50:
        # Reverse to chronological order
        return [
            {
                "date": row[0],
                "open": row[1],
                "high": row[2],
                "low": row[3],
                "close": row[4],
                "volume": row[5],
            }
            for row in reversed(rows)
        ]

    # Fetch from Yahoo if not enough local data
    logger.info(f"Fetching daily prices for {symbol} from Yahoo")
    prices = yahoo.get_historical_prices(symbol, yahoo_symbol=yahoo_symbol, period="1y")

    if prices:
        # Store for future use
        async with history_db.transaction():
            for p in prices:
                await history_db.execute(
                    """
                    INSERT OR REPLACE INTO daily_prices
                    (date, open_price, high_price, low_price, close_price, volume, source, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'yahoo', datetime('now'))
                    """,
                    (
                        p.date.strftime("%Y-%m-%d"),
                        p.open,
                        p.high,
                        p.low,
                        p.close,
                        p.volume,
                    ),
                )

    return prices or []


async def _get_monthly_prices(
    db_manager, symbol: str, yahoo_symbol: Optional[str] = None
) -> list:
    """Get monthly price data from history database or Yahoo."""
    history_db = await db_manager.history(symbol)

    cursor = await history_db.execute(
        """
        SELECT year_month, avg_adj_close
        FROM monthly_prices
        ORDER BY year_month DESC
        LIMIT 120
        """
    )
    rows = await cursor.fetchall()

    if len(rows) >= 12:
        return [
            {"year_month": row[0], "avg_adj_close": row[1]} for row in reversed(rows)
        ]

    # Fetch from Yahoo if not enough local data
    logger.info(f"Fetching monthly prices for {symbol} from Yahoo")
    prices = yahoo.get_historical_prices(
        symbol, yahoo_symbol=yahoo_symbol, period="10y"
    )

    if prices:
        # Aggregate to monthly averages
        from collections import defaultdict

        monthly_data = defaultdict(list)
        for p in prices:
            if p.date and p.close:
                month = p.date.strftime("%Y-%m")  # YYYY-MM
                monthly_data[month].append(p.close)

        monthly_prices = []
        async with history_db.transaction():
            for month, closes in sorted(monthly_data.items()):
                avg_close = sum(closes) / len(closes)
                monthly_prices.append({"year_month": month, "avg_adj_close": avg_close})
                await history_db.execute(
                    """
                    INSERT OR REPLACE INTO monthly_prices
                    (year_month, avg_close, avg_adj_close, source, created_at)
                    VALUES (?, ?, ?, 'calculated', datetime('now'))
                    """,
                    (month, avg_close, avg_close),
                )

        return monthly_prices

    return []
