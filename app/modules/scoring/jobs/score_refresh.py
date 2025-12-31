"""Periodic stock score refresh job.

Uses the new scoring domain to calculate scores for all active stocks.
"""

import logging
from datetime import datetime
from typing import Optional

from app.core.database.manager import get_db_manager
from app.core.events import SystemEvent, emit
from app.infrastructure.external import yahoo_finance as yahoo
from app.infrastructure.locking import file_lock
from app.modules.display.services.display_service import set_led4, set_text
from app.modules.scoring.domain import PortfolioContext, calculate_security_score

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
    set_text("REFRESHING STOCK SCORES...")
    set_led4(0, 255, 0)  # Green for processing

    try:
        db_manager = get_db_manager()

        # Get all active stocks
        cursor = await db_manager.config.execute(
            "SELECT symbol, yahoo_symbol, country, industry FROM securities WHERE active = 1"
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
            symbol, yahoo_symbol, country, industry = row
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
                score = await calculate_security_score(
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

                    await db_manager.calculations.execute(
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

        await db_manager.calculations.commit()
        logger.info(f"Refreshed scores for {scores_updated} stocks")

        emit(SystemEvent.PROCESSING_END)
        emit(SystemEvent.SCORE_REFRESH_COMPLETE)

    except Exception as e:
        logger.error(f"Score refresh failed: {e}")
        emit(SystemEvent.PROCESSING_END)
        error_msg = "SCORE REFRESH CRASHES"
        emit(SystemEvent.ERROR_OCCURRED, message=error_msg)
        set_text(error_msg)
    finally:
        set_led4(0, 0, 0)  # Clear LED when done


async def _build_portfolio_context(db_manager) -> PortfolioContext:
    """Build portfolio context for allocation fit calculations."""
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
        "SELECT symbol, country, industry FROM securities WHERE active = 1"
    )
    security_data = await cursor.fetchall()

    security_countries = {row[0]: row[1] for row in security_data if row[1]}
    security_industries = {row[0]: row[2] for row in security_data if row[2]}

    # Get scores for quality weighting (from calculations.db)
    cursor = await db_manager.calculations.execute(
        "SELECT symbol, quality_score FROM scores"
    )
    security_scores = {row[0]: row[1] for row in await cursor.fetchall() if row[1]}

    return PortfolioContext(
        country_weights=country_weights,
        industry_weights=industry_weights,
        positions=positions,
        total_value=total_value,
        security_countries=security_countries,
        security_industries=security_industries,
        security_scores=security_scores,
        country_to_group=country_to_group,
        industry_to_group=industry_to_group,
    )


async def _get_daily_prices(
    db_manager, symbol: str, yahoo_symbol: Optional[str] = None
) -> list:
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
