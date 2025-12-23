"""Stock scoring engine for long-term value investing.

Scoring weights:
- Quality: 35% (total return, consistency, financial strength, dividend bonus)
- Opportunity: 35% (buy-the-dip signals)
- Analyst: 15% (recommendations, price targets)
- Allocation Fit: 15% (portfolio awareness)

This scoring system is optimized for a 10-20 year retirement portfolio,
prioritizing steady growers bought at discount over momentum plays.

Price data strategy:
- Monthly prices (stock_price_monthly table): Used for 5y/10y CAGR calculations
- Daily prices (stock_price_history table): Used for 52-week high, 200-day MA, volatility
- Falls back to Yahoo API if local data is insufficient, then stores for future use
"""

import math
import logging
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass

import aiosqlite
import numpy as np
import pandas as pd
import empyrical
import pandas_ta as ta

from app.services import yahoo
from app.config import settings

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Scoring thresholds
OPTIMAL_CAGR = 0.11  # 11% target annual return (bell curve peak)
HIGH_DIVIDEND_THRESHOLD = 0.06  # 6%+ yield gets max dividend bonus
MID_DIVIDEND_THRESHOLD = 0.03  # 3%+ yield gets mid dividend bonus
MARKET_AVG_PE = 22  # Market average P/E ratio for comparison

# Technical indicator parameters
TRADING_DAYS_PER_YEAR = 252
EMA_LENGTH = 200
RSI_LENGTH = 14
BOLLINGER_LENGTH = 20

# Minimum data requirements
MIN_DAYS_FOR_OPPORTUNITY = 50
MIN_MONTHS_FOR_CAGR = 12


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class QualityScore:
    """Long-term quality score components."""
    total_return_score: float  # 0-1, bell curve for CAGR + dividend
    consistency_score: float  # 0-1, 5y vs 10y CAGR similarity
    financial_strength_score: float  # 0-1, margins, debt, liquidity
    dividend_bonus: float  # 0-0.10, extra for high dividend stocks
    sharpe_ratio_score: float  # 0-1, risk-adjusted return quality
    max_drawdown_score: float  # 0-1, resilience to losses
    total: float
    # Metadata
    cagr_5y: Optional[float]  # 5-year CAGR
    cagr_10y: Optional[float]  # 10-year CAGR (if available)
    total_return: Optional[float]  # CAGR + dividend yield
    dividend_yield: Optional[float]
    sharpe_ratio: Optional[float]  # Actual Sharpe ratio value
    max_drawdown: Optional[float]  # Actual max drawdown value (negative)
    history_years: float  # Years of price data available


@dataclass
class OpportunityScore:
    """Buy-the-dip opportunity score components."""
    below_52w_high: float  # 0-1, further below = higher (BUY signal)
    ema_distance: float  # 0-1, below 200-EMA = higher (BUY signal)
    pe_vs_historical: float  # 0-1, below avg P/E = higher (BUY signal)
    rsi_score: float  # 0-1, RSI < 30 = 1.0, RSI > 70 = 0.0
    bollinger_score: float  # 0-1, near lower band = higher
    total: float


@dataclass
class AnalystScore:
    """Analyst recommendation score components."""
    recommendation_score: float  # 0-1, based on buy/hold/sell
    target_score: float  # 0-1, based on upside potential
    total: float


@dataclass
class AllocationFitScore:
    """Allocation fit score components (portfolio awareness)."""
    geo_gap_score: float  # 0-1, boost for underweight geographies
    industry_gap_score: float  # 0-1, boost for underweight industries
    averaging_down_score: float  # 0-1, bonus for quality dips we own
    total: float


@dataclass
class PortfolioContext:
    """Portfolio context for allocation fit calculations."""
    geo_weights: dict  # name -> weight (-1 to +1)
    industry_weights: dict  # name -> weight (-1 to +1)
    positions: dict  # symbol -> position_value
    total_value: float
    # Additional data for portfolio scoring
    stock_geographies: dict = None  # symbol -> geography
    stock_industries: dict = None  # symbol -> industry
    stock_scores: dict = None  # symbol -> quality_score
    stock_dividends: dict = None  # symbol -> dividend_yield
    # Cost basis data for averaging down
    position_avg_prices: dict = None  # symbol -> avg_purchase_price
    current_prices: dict = None  # symbol -> current_market_price


@dataclass
class PortfolioScore:
    """Overall portfolio health score."""
    diversification_score: float  # Geographic + industry balance (0-100)
    dividend_score: float  # Weighted average dividend yield score (0-100)
    quality_score: float  # Weighted average stock quality (0-100)
    total: float  # Combined score (0-100)


@dataclass
class CalculatedStockScore:
    """Complete stock score with all components.

    Named CalculatedStockScore to distinguish from the domain model StockScore
    in app.domain.repositories.score_repository which is a flat DB model.
    """
    symbol: str
    quality: QualityScore
    opportunity: OpportunityScore
    analyst: AnalystScore
    allocation_fit: Optional[AllocationFitScore]  # None if no portfolio context
    total_score: float  # Final weighted score
    volatility: Optional[float]  # Raw annualized volatility
    calculated_at: datetime


@dataclass
class PrefetchedStockData:
    """Pre-fetched data to avoid duplicate API calls.

    Used to share data between calculate_quality_score and
    calculate_opportunity_score when called together.
    """
    daily_prices: list  # List of dicts with date, close, high, low, open, volume
    monthly_prices: list  # List of dicts with month, avg_adj_close
    fundamentals: Optional[object]  # Yahoo fundamentals data


# =============================================================================
# Bell Curve Scoring for Total Return
# =============================================================================

def score_total_return(total_return: float) -> float:
    """
    Bell curve scoring for total return (CAGR + dividend yield).

    Peak at 11% (target for ~€1M retirement goal with €20K + €1K/month over 20 years).
    Uses asymmetric Gaussian: steeper rise, gentler fall for high growth.

    Args:
        total_return: Combined CAGR + dividend yield as decimal (e.g., 0.11 for 11%)

    Returns:
        Score from 0.15 (floor) to 1.0 (peak at 11%)
    """
    peak = 0.11  # 11% optimal
    sigma_left = 0.06  # Steeper rise (0% to peak)
    sigma_right = 0.10  # Gentler fall (peak to high growth)
    floor = 0.15  # Minimum score

    if total_return <= 0:
        return floor

    sigma = sigma_left if total_return < peak else sigma_right

    # Gaussian formula
    raw_score = math.exp(-((total_return - peak) ** 2) / (2 * sigma ** 2))

    return floor + raw_score * (1 - floor)


def calculate_dividend_bonus(dividend_yield: Optional[float]) -> float:
    """
    Calculate bonus for high-dividend stocks (DRIP priority).

    Args:
        dividend_yield: Current dividend yield as decimal (e.g., 0.09 for 9%)

    Returns:
        Bonus from 0 to 0.10
    """
    if not dividend_yield or dividend_yield <= 0:
        return 0.0

    if dividend_yield >= 0.06:  # 6%+ yield
        return 0.10
    elif dividend_yield >= 0.03:  # 3-6% yield
        return 0.07
    else:  # Any dividend
        return 0.03


# =============================================================================
# Local Database Price Helpers
# =============================================================================

async def _get_monthly_prices_from_db(
    db: aiosqlite.Connection,
    symbol: str,
    years: int
) -> list[dict]:
    """
    Get monthly prices from local database.

    Args:
        db: Database connection
        symbol: Stock symbol
        years: Number of years of data to fetch

    Returns:
        List of dicts with year_month and avg_adj_close
    """
    cutoff = (datetime.now() - timedelta(days=years * 365)).strftime("%Y-%m")
    cursor = await db.execute("""
        SELECT year_month, avg_adj_close, avg_close
        FROM stock_price_monthly
        WHERE symbol = ? AND year_month >= ?
        ORDER BY year_month ASC
    """, (symbol, cutoff))
    rows = await cursor.fetchall()
    return [
        {
            "year_month": row[0],
            "avg_adj_close": row[1] if row[1] else row[2],  # Fallback to avg_close
        }
        for row in rows
    ]


async def _get_daily_prices_from_db(
    db: aiosqlite.Connection,
    symbol: str,
    days: int
) -> list[dict]:
    """
    Get daily prices from local database.

    Args:
        db: Database connection
        symbol: Stock symbol
        days: Number of days of data to fetch

    Returns:
        List of dicts with date, close, high, low, open, volume
    """
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    cursor = await db.execute("""
        SELECT date, close_price, high_price, low_price, open_price, volume
        FROM stock_price_history
        WHERE symbol = ? AND date >= ?
        ORDER BY date ASC
    """, (symbol, cutoff))
    rows = await cursor.fetchall()
    return [
        {
            "date": row[0],
            "close": row[1],
            "high": row[2],
            "low": row[3],
            "open": row[4],
            "volume": row[5],
        }
        for row in rows
    ]


def _aggregate_to_monthly(daily_prices: list) -> list[dict]:
    """
    Convert daily prices to monthly averages.

    Args:
        daily_prices: List of HistoricalPrice objects from Yahoo

    Returns:
        List of dicts with year_month and avg_adj_close
    """
    from collections import defaultdict
    monthly = defaultdict(list)

    for price in daily_prices:
        ym = price.date.strftime("%Y-%m")
        monthly[ym].append(price.adj_close)

    return [
        {"year_month": ym, "avg_adj_close": sum(prices) / len(prices)}
        for ym, prices in sorted(monthly.items())
    ]


async def _store_monthly_prices(
    db: aiosqlite.Connection,
    symbol: str,
    monthly_data: list[dict]
):
    """
    Store monthly prices in database.

    Args:
        db: Database connection
        symbol: Stock symbol
        monthly_data: List of dicts with year_month and avg_adj_close
    """
    now = datetime.now().isoformat()
    for m in monthly_data:
        await db.execute("""
            INSERT OR REPLACE INTO stock_price_monthly
            (symbol, year_month, avg_close, avg_adj_close, source, created_at)
            VALUES (?, ?, ?, ?, 'yahoo', ?)
        """, (symbol, m["year_month"], m["avg_adj_close"], m["avg_adj_close"], now))
    await db.commit()


async def _store_daily_prices(
    db: aiosqlite.Connection,
    symbol: str,
    daily_prices: list
):
    """
    Store daily prices in database.

    Args:
        db: Database connection
        symbol: Stock symbol
        daily_prices: List of HistoricalPrice objects from Yahoo
    """
    now = datetime.now().isoformat()
    for price in daily_prices:
        date_str = price.date.strftime("%Y-%m-%d")
        await db.execute("""
            INSERT OR REPLACE INTO stock_price_history
            (symbol, date, close_price, open_price, high_price, low_price, volume, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'yahoo', ?)
        """, (symbol, date_str, price.close, price.open, price.high, price.low, price.volume, now))
    await db.commit()


# =============================================================================
# Data Prefetching (Performance Optimization)
# =============================================================================

async def prefetch_stock_data(
    db: aiosqlite.Connection,
    symbol: str,
    yahoo_symbol: str = None
) -> PrefetchedStockData:
    """
    Prefetch all data needed for scoring to avoid duplicate API calls.

    This function fetches daily prices, monthly prices, and fundamentals
    once, so they can be shared between calculate_quality_score and
    calculate_opportunity_score.

    Args:
        db: Database connection
        symbol: Tradernet symbol
        yahoo_symbol: Optional explicit Yahoo symbol override

    Returns:
        PrefetchedStockData with all fetched data
    """
    # Fetch daily prices (needed by both quality and opportunity)
    daily_prices = await _get_daily_prices_from_db(db, symbol, days=365)
    if len(daily_prices) < 50:
        logger.info(f"Insufficient local daily data for {symbol}, fetching from Yahoo")
        yahoo_prices = yahoo.get_historical_prices(symbol, yahoo_symbol=yahoo_symbol, period="1y")
        if len(yahoo_prices) >= 50:
            await _store_daily_prices(db, symbol, yahoo_prices)
            daily_prices = [
                {
                    "date": p.date.strftime("%Y-%m-%d"),
                    "close": p.close,
                    "high": p.high,
                    "low": p.low,
                    "open": p.open,
                    "volume": p.volume,
                }
                for p in yahoo_prices
            ]

    # Fetch monthly prices (needed by quality)
    monthly_prices = await _get_monthly_prices_from_db(db, symbol, years=10)
    if len(monthly_prices) < MIN_MONTHS_FOR_CAGR:
        logger.info(f"Insufficient local monthly data for {symbol}, fetching from Yahoo")
        prices_10y = yahoo.get_historical_prices(symbol, yahoo_symbol=yahoo_symbol, period="10y")
        if len(prices_10y) >= 252:  # At least 1 year
            monthly_prices = _aggregate_to_monthly(prices_10y)
            await _store_monthly_prices(db, symbol, monthly_prices)

    # Fetch fundamentals (needed by both quality and opportunity)
    fundamentals = yahoo.get_fundamental_data(symbol, yahoo_symbol=yahoo_symbol)

    return PrefetchedStockData(
        daily_prices=daily_prices,
        monthly_prices=monthly_prices,
        fundamentals=fundamentals
    )


# =============================================================================
# Quality Score Calculation
# =============================================================================

async def calculate_quality_score(
    db: aiosqlite.Connection,
    symbol: str,
    yahoo_symbol: str = None,
    prefetched: PrefetchedStockData = None
) -> Optional[QualityScore]:
    """
    Calculate quality score based on long-term track record.

    Uses local monthly price data when available, falls back to Yahoo API.

    Components:
    - Total Return (40%): CAGR + Dividend Yield, bell curve with 11% peak
    - Consistency (20%): 5-year vs 10-year CAGR similarity
    - Financial Strength (20%): Profit margin, debt/equity, current ratio
    - Sharpe Ratio (10%): Risk-adjusted return quality (empyrical)
    - Max Drawdown (10%): Resilience to losses (empyrical)
    - Dividend Bonus: +0.10 max for high-yield stocks (DRIP priority)

    Args:
        db: Database connection
        symbol: Tradernet symbol
        yahoo_symbol: Optional explicit Yahoo symbol override
        prefetched: Optional pre-fetched data to avoid duplicate API calls
    """
    try:
        # Use prefetched data if available, otherwise fetch
        if prefetched:
            monthly_prices = prefetched.monthly_prices
            daily_prices = prefetched.daily_prices
            fundamentals = prefetched.fundamentals
        else:
            # Try local monthly data first (10 years)
            monthly_prices = await _get_monthly_prices_from_db(db, symbol, years=10)

            # Need at least 12 months of data for meaningful CAGR
            if len(monthly_prices) < 12:
                logger.info(f"Insufficient local monthly data for {symbol} ({len(monthly_prices)} months), fetching from Yahoo")
                # Fetch from Yahoo and store
                prices_10y = yahoo.get_historical_prices(symbol, yahoo_symbol=yahoo_symbol, period="10y")
                if len(prices_10y) >= 252:  # At least 1 year
                    monthly_prices = _aggregate_to_monthly(prices_10y)
                    await _store_monthly_prices(db, symbol, monthly_prices)
                else:
                    logger.warning(f"Insufficient Yahoo price data for {symbol}")
                    return None

            # Get fundamentals (always from Yahoo - no local cache)
            fundamentals = yahoo.get_fundamental_data(symbol, yahoo_symbol=yahoo_symbol)

            # Fetch daily prices for Sharpe ratio and max drawdown (need 1 year minimum)
            daily_prices = await _get_daily_prices_from_db(db, symbol, days=365)
            if len(daily_prices) < 50:
                # Fetch from Yahoo if insufficient local data
                yahoo_prices = yahoo.get_historical_prices(symbol, yahoo_symbol=yahoo_symbol, period="1y")
                if len(yahoo_prices) >= 50:
                    await _store_daily_prices(db, symbol, yahoo_prices)
                    daily_prices = [
                        {
                            "date": p.date.strftime("%Y-%m-%d"),
                            "close": p.close,
                        }
                        for p in yahoo_prices
                    ]

        # Validate we have enough data
        if len(monthly_prices) < MIN_MONTHS_FOR_CAGR:
            logger.warning(f"Insufficient monthly price data for {symbol}")
            return None

        # Calculate history in years (12 months = 1 year)
        history_years = len(monthly_prices) / 12.0

        # Calculate daily returns for risk metrics
        sharpe_ratio = None
        max_drawdown = None
        if len(daily_prices) >= 50:
            closes = np.array([p["close"] for p in daily_prices])
            # Validate no zero/negative prices
            if np.any(closes[:-1] <= 0):
                logger.debug(f"Zero/negative prices detected for {symbol}, skipping risk metrics")
            else:
                returns = np.diff(closes) / closes[:-1]
                try:
                    sharpe_ratio = float(empyrical.sharpe_ratio(returns, annualization=252))
                    max_drawdown = float(empyrical.max_drawdown(returns))
                    # Validate empyrical outputs
                    if not np.isfinite(sharpe_ratio):
                        sharpe_ratio = None
                    if not np.isfinite(max_drawdown):
                        max_drawdown = None
                except Exception as e:
                    logger.debug(f"Could not calculate risk metrics for {symbol}: {e}")

        # Calculate CAGRs from monthly data
        # 5-year CAGR: use last 60 months or all available
        months_5y = min(60, len(monthly_prices))
        if months_5y >= 12:
            prices_5y = monthly_prices[-months_5y:]
            start_price_5y = prices_5y[0]["avg_adj_close"]
            end_price_5y = prices_5y[-1]["avg_adj_close"]
            years_5y = months_5y / 12.0
            cagr_5y = (end_price_5y / start_price_5y) ** (1 / years_5y) - 1 if start_price_5y > 0 else 0
        else:
            cagr_5y = 0

        # 10-year CAGR: use all available data if > 5 years
        cagr_10y = None
        if len(monthly_prices) > 60:  # More than 5 years
            start_price_10y = monthly_prices[0]["avg_adj_close"]
            end_price_10y = monthly_prices[-1]["avg_adj_close"]
            years_10y = len(monthly_prices) / 12.0
            if start_price_10y > 0:
                cagr_10y = (end_price_10y / start_price_10y) ** (1 / years_10y) - 1

        # Get dividend yield
        dividend_yield = fundamentals.dividend_yield if fundamentals else None

        # Total Return = Price CAGR + Dividend Yield
        total_return = cagr_5y + (dividend_yield or 0)

        # 1. Total Return Score (50%)
        total_return_score = score_total_return(total_return)

        # 2. Consistency Score (25%): 5-year vs 10-year CAGR similarity
        if cagr_10y is not None:
            diff = abs(cagr_5y - cagr_10y)
            if diff < 0.02:  # Within 2%
                consistency_score = 1.0
            elif diff < 0.05:  # Within 5%
                consistency_score = 0.8
            else:
                consistency_score = max(0.4, 1.0 - diff * 4)
        else:
            consistency_score = 0.6  # Neutral for newer stocks

        # 3. Financial Strength Score (25%)
        if fundamentals:
            # Profit margin (40%): Higher = better
            margin = fundamentals.profit_margin or 0
            margin_score = min(1.0, 0.5 + margin * 2.5) if margin >= 0 else max(0, 0.5 + margin * 2)

            # Debt/Equity (30%): Lower = better (cap at 200)
            de = min(200, fundamentals.debt_to_equity or 50)
            de_score = max(0, 1 - de / 200)

            # Current ratio (30%): Higher = better (cap at 3)
            cr = min(3, fundamentals.current_ratio or 1)
            cr_score = min(1.0, cr / 2)

            financial_strength_score = (
                margin_score * 0.40 +
                de_score * 0.30 +
                cr_score * 0.30
            )
        else:
            financial_strength_score = 0.5  # Neutral

        # 4. Dividend Bonus (DRIP priority) - reduced from 0.15 to 0.10 max
        dividend_bonus = calculate_dividend_bonus(dividend_yield)

        # 5. Sharpe Ratio Score (10%): Risk-adjusted returns
        # Sharpe > 1.0 is good, > 2.0 is excellent
        if sharpe_ratio is not None:
            if sharpe_ratio >= 2.0:
                sharpe_ratio_score = 1.0
            elif sharpe_ratio >= 1.0:
                sharpe_ratio_score = 0.7 + (sharpe_ratio - 1.0) * 0.3  # 0.7-1.0
            elif sharpe_ratio >= 0.5:
                sharpe_ratio_score = 0.4 + (sharpe_ratio - 0.5) * 0.6  # 0.4-0.7
            elif sharpe_ratio >= 0:
                sharpe_ratio_score = sharpe_ratio * 0.8  # 0.0-0.4
            else:
                sharpe_ratio_score = 0.0  # Negative Sharpe = poor
        else:
            sharpe_ratio_score = 0.5  # Neutral if no data

        # 6. Max Drawdown Score (10%): Resilience to losses
        # Drawdown is negative, so -0.10 = 10% drawdown
        # < 10% drawdown is excellent, > 50% is very bad
        if max_drawdown is not None:
            dd_pct = abs(max_drawdown)  # Convert to positive percentage
            if dd_pct <= 0.10:
                max_drawdown_score = 1.0  # < 10% drawdown
            elif dd_pct <= 0.20:
                max_drawdown_score = 0.8 + (0.20 - dd_pct) * 2  # 0.8-1.0
            elif dd_pct <= 0.30:
                max_drawdown_score = 0.6 + (0.30 - dd_pct) * 2  # 0.6-0.8
            elif dd_pct <= 0.50:
                max_drawdown_score = 0.2 + (0.50 - dd_pct) * 2  # 0.2-0.6
            else:
                max_drawdown_score = max(0.0, 0.2 - (dd_pct - 0.50))  # 0.0-0.2
        else:
            max_drawdown_score = 0.5  # Neutral if no data

        # Combined Quality Score (capped at 1.0)
        # Weights: Total Return 40%, Consistency 20%, Financial 20%, Sharpe 10%, Max DD 10%
        total = min(1.0, (
            total_return_score * 0.40 +
            consistency_score * 0.20 +
            financial_strength_score * 0.20 +
            sharpe_ratio_score * 0.10 +
            max_drawdown_score * 0.10 +
            dividend_bonus
        ))

        return QualityScore(
            total_return_score=round(total_return_score, 3),
            consistency_score=round(consistency_score, 3),
            financial_strength_score=round(financial_strength_score, 3),
            dividend_bonus=round(dividend_bonus, 3),
            sharpe_ratio_score=round(sharpe_ratio_score, 3),
            max_drawdown_score=round(max_drawdown_score, 3),
            total=round(total, 3),
            cagr_5y=round(cagr_5y, 4) if cagr_5y else None,
            cagr_10y=round(cagr_10y, 4) if cagr_10y else None,
            total_return=round(total_return, 4) if total_return else None,
            dividend_yield=round(dividend_yield, 4) if dividend_yield else None,
            sharpe_ratio=round(sharpe_ratio, 4) if sharpe_ratio else None,
            max_drawdown=round(max_drawdown, 4) if max_drawdown else None,
            history_years=round(history_years, 1),
        )

    except Exception as e:
        logger.error(f"Failed to calculate quality score for {symbol}: {e}")
        return None


# =============================================================================
# Opportunity Score Calculation (Buy the Dip)
# =============================================================================

async def calculate_opportunity_score(
    db: aiosqlite.Connection,
    symbol: str,
    yahoo_symbol: str = None,
    prefetched: PrefetchedStockData = None
) -> Optional[OpportunityScore]:
    """
    Calculate opportunity score based on buy-the-dip signals.

    Uses local daily price data when available, falls back to Yahoo API.

    INVERTED from typical momentum scoring - we WANT stocks that are:
    - Below their 52-week high (temporary dip)
    - Below their 200-day EMA (undervalued)
    - Trading at low P/E vs historical (cheap)
    - RSI indicates oversold (< 30 is ideal)
    - Near lower Bollinger Band (buy opportunity)

    Components:
    - Below 52-week High (30%): Distance from peak
    - EMA Distance (25%): Below 200-EMA = opportunity (pandas-ta)
    - P/E vs Historical (25%): Below average = opportunity
    - RSI Position (10%): Oversold = opportunity (pandas-ta)
    - Bollinger Position (10%): Near lower band = opportunity (pandas-ta)

    Args:
        db: Database connection
        symbol: Tradernet symbol
        yahoo_symbol: Optional explicit Yahoo symbol override
        prefetched: Optional pre-fetched data to avoid duplicate API calls
    """
    try:
        # Use prefetched data if available, otherwise fetch
        if prefetched:
            daily_prices = prefetched.daily_prices
            fundamentals = prefetched.fundamentals
        else:
            # Try local daily data first (1 year = 365 days)
            daily_prices = await _get_daily_prices_from_db(db, symbol, days=365)

            # Need at least 50 days for meaningful calculations
            if len(daily_prices) < 50:
                logger.info(f"Insufficient local daily data for {symbol} ({len(daily_prices)} days), fetching from Yahoo")
                # Fetch from Yahoo and store
                yahoo_prices = yahoo.get_historical_prices(symbol, yahoo_symbol=yahoo_symbol, period="1y")
                if len(yahoo_prices) >= 50:
                    await _store_daily_prices(db, symbol, yahoo_prices)
                    # Convert to our dict format
                    daily_prices = [
                        {
                            "date": p.date.strftime("%Y-%m-%d"),
                            "close": p.close,
                            "high": p.high,
                            "low": p.low,
                            "open": p.open,
                            "volume": p.volume,
                        }
                        for p in yahoo_prices
                    ]
                else:
                    logger.warning(f"Insufficient Yahoo price data for opportunity score: {symbol}")
                    return None

            # Get fundamentals (always from Yahoo - no local cache)
            fundamentals = yahoo.get_fundamental_data(symbol, yahoo_symbol=yahoo_symbol)

        # Validate we have enough data
        if len(daily_prices) < MIN_DAYS_FOR_OPPORTUNITY:
            logger.warning(f"Insufficient daily price data for {symbol}")
            return None

        closes = np.array([p["close"] for p in daily_prices])
        highs = np.array([p["high"] for p in daily_prices if p["high"]])
        if len(highs) == 0:
            highs = closes  # Fallback to close prices
        current_price = closes[-1]

        # Convert to pandas Series for pandas-ta indicators
        closes_series = pd.Series(closes)

        # 1. Below 52-week High Score (30%)
        # Further below = HIGHER score (buying opportunity)
        high_52w = max(highs[-252:]) if len(highs) >= 252 else max(highs)
        pct_below_high = (high_52w - current_price) / high_52w if high_52w > 0 else 0

        if pct_below_high <= 0:
            below_52w_score = 0.2  # At or above high = expensive
        elif pct_below_high < 0.10:
            below_52w_score = 0.2 + (pct_below_high / 0.10) * 0.3  # 0-10% below -> 0.2-0.5
        elif pct_below_high < 0.20:
            below_52w_score = 0.5 + ((pct_below_high - 0.10) / 0.10) * 0.3  # 10-20% below -> 0.5-0.8
        elif pct_below_high < 0.30:
            below_52w_score = 0.8 + ((pct_below_high - 0.20) / 0.10) * 0.2  # 20-30% below -> 0.8-1.0
        else:
            below_52w_score = 1.0  # 30%+ below

        # 2. Distance from 200-day EMA Score (25%)
        # Using EMA instead of SMA - more responsive to recent price action
        # Below EMA = HIGHER score (INVERTED from typical momentum)
        ema_200 = ta.ema(closes_series, length=200)
        if ema_200 is not None and len(ema_200) > 0 and not pd.isna(ema_200.iloc[-1]):
            ema_value = float(ema_200.iloc[-1])
        else:
            # Fallback to SMA if EMA not available (not enough data)
            logger.debug(f"EMA unavailable for {symbol}, using SMA fallback")
            ema_value = float(np.mean(closes[-200:])) if len(closes) >= 200 else float(np.mean(closes))

        pct_from_ema = (current_price - ema_value) / ema_value if ema_value > 0 else 0

        if pct_from_ema >= 0.10:
            ema_score = 0.2  # 10%+ above EMA = expensive
        elif pct_from_ema >= 0:
            ema_score = 0.5 - (pct_from_ema / 0.10) * 0.3  # 0-10% above -> 0.5-0.2
        elif pct_from_ema >= -0.05:
            ema_score = 0.5 + (abs(pct_from_ema) / 0.05) * 0.2  # 0-5% below -> 0.5-0.7
        elif pct_from_ema >= -0.10:
            ema_score = 0.7 + ((abs(pct_from_ema) - 0.05) / 0.05) * 0.3  # 5-10% below -> 0.7-1.0
        else:
            ema_score = 1.0  # 10%+ below EMA

        # 3. P/E vs Historical Score (25%)
        # Below average P/E = HIGHER score (cheap)
        if fundamentals and fundamentals.pe_ratio and fundamentals.pe_ratio > 0:
            current_pe = fundamentals.pe_ratio
            # Use sector average P/E as proxy (could be enhanced with historical tracking)
            avg_pe = 22  # Market average

            # Also consider forward P/E for growth adjustment
            if fundamentals.forward_pe and fundamentals.forward_pe > 0:
                effective_pe = (current_pe + fundamentals.forward_pe) / 2
            else:
                effective_pe = current_pe

            pct_diff = (effective_pe - avg_pe) / avg_pe

            if pct_diff >= 0.20:
                pe_score = 0.2  # 20%+ above average = expensive
            elif pct_diff >= 0:
                pe_score = 0.5 - (pct_diff / 0.20) * 0.3  # 0-20% above -> 0.5-0.2
            elif pct_diff >= -0.10:
                pe_score = 0.5 + (abs(pct_diff) / 0.10) * 0.2  # 0-10% below -> 0.5-0.7
            elif pct_diff >= -0.20:
                pe_score = 0.7 + ((abs(pct_diff) - 0.10) / 0.10) * 0.3  # 10-20% below -> 0.7-1.0
            else:
                pe_score = 1.0  # 20%+ below average
        else:
            pe_score = 0.5  # Neutral if no P/E available

        # 4. RSI Score (10%): Oversold = buying opportunity
        # RSI < 30 = oversold (1.0), RSI > 70 = overbought (0.0)
        rsi = ta.rsi(closes_series, length=14)
        if rsi is not None and len(rsi) > 0 and not pd.isna(rsi.iloc[-1]):
            rsi_value = float(rsi.iloc[-1])
            if rsi_value < 30:
                rsi_score = 1.0  # Oversold - good buying opportunity
            elif rsi_value > 70:
                rsi_score = 0.0  # Overbought - poor time to buy
            else:
                # Linear scale between 30-70: RSI 30 -> 1.0, RSI 70 -> 0.0
                rsi_score = 1.0 - ((rsi_value - 30) / 40)
        else:
            rsi_score = 0.5  # Neutral if no RSI data

        # 5. Bollinger Band Score (10%): Near lower band = opportunity
        # Position within bands: 0=lower band, 1=upper band
        bbands = ta.bbands(closes_series, length=20, std=2)
        bollinger_score = 0.5  # Default neutral
        if bbands is not None:
            # Dynamic column detection for version compatibility
            bb_lower_cols = [c for c in bbands.columns if c.startswith('BBL_')]
            bb_upper_cols = [c for c in bbands.columns if c.startswith('BBU_')]
            if bb_lower_cols and bb_upper_cols:
                bb_lower = bbands[bb_lower_cols[0]].iloc[-1]
                bb_upper = bbands[bb_upper_cols[0]].iloc[-1]
                if not pd.isna(bb_lower) and not pd.isna(bb_upper) and bb_upper > bb_lower:
                    # Where is price within the bands? (0=lower, 1=upper)
                    bb_position = (current_price - bb_lower) / (bb_upper - bb_lower)
                    # Lower position = better score (buying opportunity)
                    bollinger_score = 1.0 - bb_position
                    bollinger_score = max(0.0, min(1.0, bollinger_score))  # Clamp to 0-1

        # Combined Opportunity Score
        # Weights: 52w High 30%, EMA 25%, P/E 25%, RSI 10%, Bollinger 10%
        total = (
            below_52w_score * 0.30 +
            ema_score * 0.25 +
            pe_score * 0.25 +
            rsi_score * 0.10 +
            bollinger_score * 0.10
        )

        return OpportunityScore(
            below_52w_high=round(below_52w_score, 3),
            ema_distance=round(ema_score, 3),
            pe_vs_historical=round(pe_score, 3),
            rsi_score=round(rsi_score, 3),
            bollinger_score=round(bollinger_score, 3),
            total=round(total, 3),
        )

    except Exception as e:
        logger.error(f"Failed to calculate opportunity score for {symbol}: {e}")
        return None


# =============================================================================
# Analyst Score Calculation (kept from original, reduced weight)
# =============================================================================

def calculate_analyst_score(symbol: str, yahoo_symbol: str = None) -> Optional[AnalystScore]:
    """
    Calculate analyst score from recommendations and price targets.

    Components:
    - Recommendation (60%): Buy/Hold/Sell consensus
    - Price Target (40%): Upside potential

    Args:
        symbol: Tradernet symbol
        yahoo_symbol: Optional explicit Yahoo symbol override
    """
    try:
        data = yahoo.get_analyst_data(symbol, yahoo_symbol=yahoo_symbol)

        if not data:
            return None

        # Recommendation score (already 0-1 from yahoo service)
        recommendation_score = data.recommendation_score

        # Target score: based on upside potential
        # 0% upside = 0.5, 20%+ upside = 1.0, -20% = 0.0
        upside = data.upside_pct / 100  # Convert to decimal
        target_score = 0.5 + (upside * 2.5)  # Scale
        target_score = max(0, min(1, target_score))

        # Combined analyst score
        total = (
            recommendation_score * 0.60 +
            target_score * 0.40
        )

        return AnalystScore(
            recommendation_score=round(recommendation_score, 3),
            target_score=round(target_score, 3),
            total=round(total, 3),
        )

    except Exception as e:
        logger.error(f"Failed to calculate analyst score for {symbol}: {e}")
        return None


# =============================================================================
# Allocation Fit Score Calculation (Portfolio Awareness)
# =============================================================================

def calculate_allocation_fit_score(
    symbol: str,
    geography: str,
    industry: Optional[str],
    quality_score: float,
    opportunity_score: float,
    portfolio_context: PortfolioContext,
) -> AllocationFitScore:
    """
    Calculate allocation fit score based on portfolio awareness.

    This enables:
    - Prioritizing stocks in underweight geographies/industries
    - Averaging down on quality stocks at discounts that we already own
    - Avoiding excessive concentration

    Components:
    - Geography Gap (40%): Boost underweight regions
    - Industry Gap (30%): Boost underweight sectors
    - Averaging Down (30%): Bonus for quality+opportunity stocks we own

    Args:
        symbol: Stock symbol
        geography: Stock geography (EU, ASIA, US)
        industry: Stock industry (comma-separated if multiple)
        quality_score: Pre-calculated quality score (0-1)
        opportunity_score: Pre-calculated opportunity score (0-1)
        portfolio_context: Portfolio weights and positions
    """
    # 1. Geography Gap Score (40%)
    # Higher weight = higher priority, weight ranges from -1 to +1
    geo_weight = portfolio_context.geo_weights.get(geography, 0)
    # Convert weight to score: -1 -> 0.2, 0 -> 0.5, +1 -> 1.0
    geo_gap_score = 0.5 + (geo_weight * 0.4)  # Range: 0.1 to 0.9
    geo_gap_score = max(0.1, min(0.9, geo_gap_score))

    # 2. Industry Gap Score (30%)
    if industry:
        industries = [ind.strip() for ind in industry.split(",") if ind.strip()]
        if industries:
            ind_scores = []
            for ind in industries:
                ind_weight = portfolio_context.industry_weights.get(ind, 0)
                ind_score = 0.5 + (ind_weight * 0.4)
                ind_scores.append(max(0.1, min(0.9, ind_score)))
            industry_gap_score = sum(ind_scores) / len(ind_scores)
        else:
            industry_gap_score = 0.5  # Neutral
    else:
        industry_gap_score = 0.5  # Neutral

    # 3. Averaging Down Score (30%)
    # Bonus for stocks we own that have high quality + high opportunity (buying the dip)
    # PLUS extra bonus when current price is below our average purchase price
    position_value = portfolio_context.positions.get(symbol, 0)

    if position_value > 0:
        # We own this stock - check if it's a good averaging down opportunity
        # High quality + high opportunity = good candidate for averaging down
        avg_down_potential = quality_score * opportunity_score

        # Scale: if quality=0.8 and opportunity=0.8, potential = 0.64
        # Give bonus for high potential
        if avg_down_potential >= 0.5:
            averaging_down_score = 0.7 + (avg_down_potential - 0.5) * 0.6  # 0.7-1.0
        elif avg_down_potential >= 0.3:
            averaging_down_score = 0.5 + (avg_down_potential - 0.3) * 1.0  # 0.5-0.7
        else:
            averaging_down_score = 0.3  # Low potential, slight penalty

        # COST BASIS BONUS: If current price < avg purchase price, boost priority
        # This helps improve our average cost on positions we're underwater on
        if (portfolio_context.position_avg_prices and
            portfolio_context.current_prices):
            avg_price = portfolio_context.position_avg_prices.get(symbol)
            current_price = portfolio_context.current_prices.get(symbol)

            if avg_price and current_price and avg_price > 0:
                price_vs_avg = (current_price - avg_price) / avg_price

                if price_vs_avg < 0:
                    # We're underwater - buying more will lower our average cost
                    # The deeper underwater, the bigger the boost (up to 20% loss)
                    loss_pct = abs(price_vs_avg)
                    if loss_pct <= 0.20:
                        # Linear boost: 5% loss = +0.1, 10% loss = +0.2, 20% loss = +0.4
                        cost_basis_boost = min(0.4, loss_pct * 2)
                        averaging_down_score = min(1.0, averaging_down_score + cost_basis_boost)
                        logger.debug(
                            f"{symbol}: price {price_vs_avg*100:.1f}% below avg, "
                            f"cost basis boost +{cost_basis_boost:.2f}"
                        )
                    # Note: if loss > 20%, no boost (might be a falling knife)

        # Also consider position size - avoid over-concentration
        total_value = portfolio_context.total_value
        if total_value > 0:
            position_pct = position_value / total_value
            if position_pct > 0.10:  # Already >10% of portfolio
                averaging_down_score *= 0.7  # Reduce enthusiasm
            elif position_pct > 0.05:  # 5-10% of portfolio
                averaging_down_score *= 0.9  # Slight reduction
    else:
        # Don't own this stock - neutral averaging down score
        averaging_down_score = 0.5

    # Combined Allocation Fit Score
    total = (
        geo_gap_score * 0.40 +
        industry_gap_score * 0.30 +
        averaging_down_score * 0.30
    )

    return AllocationFitScore(
        geo_gap_score=round(geo_gap_score, 3),
        industry_gap_score=round(industry_gap_score, 3),
        averaging_down_score=round(averaging_down_score, 3),
        total=round(total, 3),
    )


def calculate_portfolio_score(portfolio_context: PortfolioContext) -> PortfolioScore:
    """
    Calculate overall portfolio health score.

    Components:
    - Diversification (40%): How close to target geo/industry allocations
    - Dividend (30%): Weighted average dividend yield across positions
    - Quality (30%): Weighted average stock quality scores

    Returns:
        PortfolioScore with component scores and total (0-100 scale)
    """
    total_value = portfolio_context.total_value
    if total_value <= 0:
        return PortfolioScore(
            diversification_score=50.0,
            dividend_score=50.0,
            quality_score=50.0,
            total=50.0,
        )

    # 1. Diversification Score (40%)
    # Calculate how close current allocations are to targets
    geo_deviations = []
    if portfolio_context.stock_geographies:
        # Calculate current geo allocations
        geo_values = {}
        for symbol, value in portfolio_context.positions.items():
            geo = portfolio_context.stock_geographies.get(symbol, "OTHER")
            geo_values[geo] = geo_values.get(geo, 0) + value

        # Compare to targets (weights are -1 to +1, convert to percentages)
        for geo, weight in portfolio_context.geo_weights.items():
            target_pct = 0.33 + (weight * 0.15)  # Base 33% +/- 15%
            current_pct = geo_values.get(geo, 0) / total_value if total_value > 0 else 0
            deviation = abs(current_pct - target_pct)
            geo_deviations.append(deviation)

    avg_geo_deviation = sum(geo_deviations) / len(geo_deviations) if geo_deviations else 0.2
    # Convert deviation to score: 0 deviation = 100, 0.3+ deviation = 0
    diversification_score = max(0, 100 * (1 - avg_geo_deviation / 0.3))

    # 2. Dividend Score (30%)
    # Weighted average dividend yield
    if portfolio_context.stock_dividends:
        weighted_dividend = 0.0
        for symbol, value in portfolio_context.positions.items():
            div_yield = portfolio_context.stock_dividends.get(symbol, 0) or 0
            weighted_dividend += div_yield * (value / total_value)
        # Score: 0% yield = 30, 3% = 60, 6%+ = 100
        dividend_score = min(100, 30 + weighted_dividend * 1000)
    else:
        dividend_score = 50.0

    # 3. Quality Score (30%)
    # Weighted average stock quality
    if portfolio_context.stock_scores:
        weighted_quality = 0.0
        for symbol, value in portfolio_context.positions.items():
            quality = portfolio_context.stock_scores.get(symbol, 0.5) or 0.5
            weighted_quality += quality * (value / total_value)
        # Convert 0-1 to 0-100
        quality_score = weighted_quality * 100
    else:
        quality_score = 50.0

    # Combined score
    total = (
        diversification_score * 0.40 +
        dividend_score * 0.30 +
        quality_score * 0.30
    )

    return PortfolioScore(
        diversification_score=round(diversification_score, 1),
        dividend_score=round(dividend_score, 1),
        quality_score=round(quality_score, 1),
        total=round(total, 1),
    )


def calculate_post_transaction_score(
    symbol: str,
    geography: str,
    industry: Optional[str],
    proposed_value: float,
    stock_quality: float,
    stock_dividend: float,
    portfolio_context: PortfolioContext,
) -> tuple[PortfolioScore, float]:
    """
    Calculate portfolio score AFTER a proposed transaction.

    Args:
        symbol: Stock symbol to buy
        geography: Stock geography (EU, ASIA, US)
        industry: Stock industry
        proposed_value: Transaction value (min_lot * price)
        stock_quality: Quality score of the stock (0-1)
        stock_dividend: Dividend yield of the stock (0-1)
        portfolio_context: Current portfolio context

    Returns:
        Tuple of (new_portfolio_score, score_change)
    """
    # Calculate current portfolio score
    current_score = calculate_portfolio_score(portfolio_context)

    # Create a modified context with the proposed transaction
    new_positions = dict(portfolio_context.positions)
    new_positions[symbol] = new_positions.get(symbol, 0) + proposed_value

    new_geographies = dict(portfolio_context.stock_geographies or {})
    new_geographies[symbol] = geography

    new_industries = dict(portfolio_context.stock_industries or {})
    if industry:
        new_industries[symbol] = industry

    new_scores = dict(portfolio_context.stock_scores or {})
    new_scores[symbol] = stock_quality

    new_dividends = dict(portfolio_context.stock_dividends or {})
    new_dividends[symbol] = stock_dividend

    new_context = PortfolioContext(
        geo_weights=portfolio_context.geo_weights,
        industry_weights=portfolio_context.industry_weights,
        positions=new_positions,
        total_value=portfolio_context.total_value + proposed_value,
        stock_geographies=new_geographies,
        stock_industries=new_industries,
        stock_scores=new_scores,
        stock_dividends=new_dividends,
    )

    # Calculate new portfolio score
    new_score = calculate_portfolio_score(new_context)
    score_change = new_score.total - current_score.total

    return new_score, score_change


# =============================================================================
# Combined Stock Score
# =============================================================================

async def calculate_stock_score(
    db: aiosqlite.Connection,
    symbol: str,
    yahoo_symbol: str = None,
    geography: str = None,
    industry: str = None,
    portfolio_context: PortfolioContext = None,
) -> Optional[CalculatedStockScore]:
    """
    Calculate complete stock score with all components.

    Uses local database for price data, falling back to Yahoo API when needed.

    Final weights (optimized for long-term value investing):
    - Quality: 35% (total return, consistency, financial strength, dividend bonus)
    - Opportunity: 35% (buy-the-dip signals)
    - Analyst: 15% (reduced from 30%)
    - Allocation Fit: 15% (portfolio awareness - geo gaps, industry gaps, averaging down)

    When portfolio_context is provided, allocation fit is calculated and included.
    Without portfolio_context, a normalized base score (85% -> 100%) is returned.

    Args:
        db: Database connection
        symbol: Tradernet symbol
        yahoo_symbol: Optional explicit Yahoo symbol override
        geography: Stock geography (EU, ASIA, US) - required for allocation fit
        industry: Stock industry - required for allocation fit
        portfolio_context: Portfolio weights and positions for allocation fit
    """
    # Prefetch data once for both quality and opportunity scoring (avoids duplicate API calls)
    prefetched = await prefetch_stock_data(db, symbol, yahoo_symbol)

    quality = await calculate_quality_score(db, symbol, yahoo_symbol, prefetched=prefetched)
    opportunity = await calculate_opportunity_score(db, symbol, yahoo_symbol, prefetched=prefetched)
    analyst = calculate_analyst_score(symbol, yahoo_symbol)  # Still sync, uses Yahoo directly

    # Handle missing scores with defaults
    quality_score = quality.total if quality else 0.5
    opportunity_score = opportunity.total if opportunity else 0.5
    analyst_score = analyst.total if analyst else 0.5

    # Calculate allocation fit if portfolio context provided
    allocation_fit = None
    if portfolio_context and geography:
        allocation_fit = calculate_allocation_fit_score(
            symbol=symbol,
            geography=geography,
            industry=industry,
            quality_score=quality_score,
            opportunity_score=opportunity_score,
            portfolio_context=portfolio_context,
        )
        allocation_fit_score = allocation_fit.total
    else:
        allocation_fit_score = None

    # Calculate weighted total score
    if allocation_fit_score is not None:
        # Full calculation with all 4 components
        total_score = (
            quality_score * 0.35 +
            opportunity_score * 0.35 +
            analyst_score * 0.15 +
            allocation_fit_score * 0.15
        )
    else:
        # Without allocation fit, normalize base score
        # (35% + 35% + 15%) / 85% = normalize to full scale
        base_score = (
            quality_score * 0.35 +
            opportunity_score * 0.35 +
            analyst_score * 0.15
        )
        total_score = base_score / 0.85

    # Get volatility from local daily price data using empyrical
    volatility = None
    try:
        daily_prices = await _get_daily_prices_from_db(db, symbol, days=365)
        if len(daily_prices) >= 30:
            closes = np.array([p["close"] for p in daily_prices])
            # Validate no zero/negative prices
            if not np.any(closes[:-1] <= 0):
                returns = np.diff(closes) / closes[:-1]
                volatility = float(empyrical.annual_volatility(returns))
                # Validate empyrical output
                if not np.isfinite(volatility) or volatility < 0:
                    volatility = None
    except Exception:
        pass

    # Create default scores if missing
    if not quality:
        quality = QualityScore(
            total_return_score=0.5,
            consistency_score=0.5,
            financial_strength_score=0.5,
            dividend_bonus=0.0,
            sharpe_ratio_score=0.5,
            max_drawdown_score=0.5,
            total=0.5,
            cagr_5y=None,
            cagr_10y=None,
            total_return=None,
            dividend_yield=None,
            sharpe_ratio=None,
            max_drawdown=None,
            history_years=0
        )
    if not opportunity:
        opportunity = OpportunityScore(
            below_52w_high=0.5,
            ema_distance=0.5,
            pe_vs_historical=0.5,
            rsi_score=0.5,
            bollinger_score=0.5,
            total=0.5
        )
    if not analyst:
        analyst = AnalystScore(
            recommendation_score=0.5,
            target_score=0.5,
            total=0.5
        )

    return CalculatedStockScore(
        symbol=symbol,
        quality=quality,
        opportunity=opportunity,
        analyst=analyst,
        allocation_fit=allocation_fit,
        total_score=round(total_score, 3),
        volatility=round(volatility, 4) if volatility else None,
        calculated_at=datetime.now(),
    )


# =============================================================================
# Batch Scoring
# =============================================================================

async def score_all_stocks(db, portfolio_context: PortfolioContext = None) -> list[CalculatedStockScore]:
    """
    Score all active stocks in the universe and update database.

    Args:
        db: Database connection
        portfolio_context: Optional portfolio context for allocation fit calculation

    Returns:
        List of calculated scores
    """
    # Get all active stocks with their Yahoo symbol overrides, geography, and industry
    cursor = await db.execute(
        "SELECT symbol, yahoo_symbol, geography, industry FROM stocks WHERE active = 1"
    )
    rows = await cursor.fetchall()

    scores = []
    for row in rows:
        symbol = row[0]
        yahoo_symbol = row[1]  # May be None
        geography = row[2]
        industry = row[3]
        logger.info(f"Scoring {symbol}...")
        score = await calculate_stock_score(
            db,
            symbol,
            yahoo_symbol=yahoo_symbol,
            geography=geography,
            industry=industry,
            portfolio_context=portfolio_context,
        )

        if score:
            scores.append(score)

            # Get allocation fit score if available
            alloc_fit_score = score.allocation_fit.total if score.allocation_fit else None

            # Update database with new scoring columns
            await db.execute(
                """
                INSERT OR REPLACE INTO scores
                (symbol, technical_score, analyst_score, fundamental_score,
                 total_score, volatility, calculated_at,
                 quality_score, opportunity_score, allocation_fit_score,
                 cagr_score, consistency_score, history_years)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    symbol,
                    # Legacy columns (for backwards compatibility)
                    score.quality.total,  # technical_score -> quality
                    score.analyst.total,
                    score.opportunity.total,  # fundamental_score -> opportunity
                    score.total_score,
                    score.volatility,
                    score.calculated_at.isoformat(),
                    # New columns
                    score.quality.total,
                    score.opportunity.total,
                    alloc_fit_score,  # May be None if no portfolio context
                    score.quality.total_return_score,  # CAGR component
                    score.quality.consistency_score,
                    score.quality.history_years,
                ),
            )

    await db.commit()
    logger.info(f"Scored {len(scores)} stocks")

    return scores
