"""Stock scoring engine for long-term value investing.

Scoring weights:
- Quality: 35% (total return, consistency, financial strength, dividend bonus)
- Opportunity: 35% (buy-the-dip signals)
- Analyst: 15% (recommendations, price targets)
- Allocation Fit: 15% (portfolio awareness)

This scoring system is optimized for a 10-20 year retirement portfolio,
prioritizing steady growers bought at discount over momentum plays.
"""

import math
import logging
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

import numpy as np

from app.services import yahoo

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class QualityScore:
    """Long-term quality score components."""
    total_return_score: float  # 0-1, bell curve for CAGR + dividend
    consistency_score: float  # 0-1, 5y vs 10y CAGR similarity
    financial_strength_score: float  # 0-1, margins, debt, liquidity
    dividend_bonus: float  # 0-0.15, extra for high dividend stocks
    total: float
    # Metadata
    cagr_5y: Optional[float]  # 5-year CAGR
    cagr_10y: Optional[float]  # 10-year CAGR (if available)
    total_return: Optional[float]  # CAGR + dividend yield
    dividend_yield: Optional[float]
    history_years: float  # Years of price data available


@dataclass
class OpportunityScore:
    """Buy-the-dip opportunity score components."""
    below_52w_high: float  # 0-1, further below = higher (BUY signal)
    ma_distance: float  # 0-1, below 200-MA = higher (BUY signal)
    pe_vs_historical: float  # 0-1, below avg P/E = higher (BUY signal)
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


@dataclass
class StockScore:
    """Complete stock score with all components."""
    symbol: str
    quality: QualityScore
    opportunity: OpportunityScore
    analyst: AnalystScore
    allocation_fit: Optional[AllocationFitScore]  # None if no portfolio context
    total_score: float  # Final weighted score
    volatility: Optional[float]  # Raw annualized volatility
    calculated_at: datetime


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
        Bonus from 0 to 0.15
    """
    if not dividend_yield or dividend_yield <= 0:
        return 0.0

    if dividend_yield >= 0.06:  # 6%+ yield
        return 0.15
    elif dividend_yield >= 0.03:  # 3-6% yield
        return 0.10
    else:  # Any dividend
        return 0.05


# =============================================================================
# Quality Score Calculation
# =============================================================================

def calculate_quality_score(symbol: str, yahoo_symbol: str = None) -> Optional[QualityScore]:
    """
    Calculate quality score based on long-term track record.

    Components:
    - Total Return (50%): CAGR + Dividend Yield, bell curve with 11% peak
    - Consistency (25%): 5-year vs 10-year CAGR similarity
    - Financial Strength (25%): Profit margin, debt/equity, current ratio
    - Dividend Bonus: +0.15 max for high-yield stocks (DRIP priority)

    Args:
        symbol: Tradernet symbol
        yahoo_symbol: Optional explicit Yahoo symbol override
    """
    try:
        # Get 5-year and 10-year price history
        prices_5y = yahoo.get_historical_prices(symbol, yahoo_symbol=yahoo_symbol, period="5y")
        prices_10y = yahoo.get_historical_prices(symbol, yahoo_symbol=yahoo_symbol, period="10y")
        fundamentals = yahoo.get_fundamental_data(symbol, yahoo_symbol=yahoo_symbol)

        if len(prices_5y) < 252:  # Need at least 1 year of data
            logger.warning(f"Insufficient price data for {symbol}")
            return None

        # Calculate CAGRs
        history_years = len(prices_5y) / 252  # Trading days per year

        # 5-year CAGR
        start_price_5y = prices_5y[0].adj_close
        end_price_5y = prices_5y[-1].adj_close
        years_5y = min(5.0, history_years)
        cagr_5y = (end_price_5y / start_price_5y) ** (1 / years_5y) - 1 if years_5y > 0 else 0

        # 10-year CAGR (if available)
        cagr_10y = None
        if len(prices_10y) > len(prices_5y) + 252:  # Has more than 5 years of data
            start_price_10y = prices_10y[0].adj_close
            end_price_10y = prices_10y[-1].adj_close
            years_10y = len(prices_10y) / 252
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

        # 4. Dividend Bonus (DRIP priority)
        dividend_bonus = calculate_dividend_bonus(dividend_yield)

        # Combined Quality Score (capped at 1.0)
        total = min(1.0, (
            total_return_score * 0.50 +
            consistency_score * 0.25 +
            financial_strength_score * 0.25 +
            dividend_bonus
        ))

        return QualityScore(
            total_return_score=round(total_return_score, 3),
            consistency_score=round(consistency_score, 3),
            financial_strength_score=round(financial_strength_score, 3),
            dividend_bonus=round(dividend_bonus, 3),
            total=round(total, 3),
            cagr_5y=round(cagr_5y, 4) if cagr_5y else None,
            cagr_10y=round(cagr_10y, 4) if cagr_10y else None,
            total_return=round(total_return, 4) if total_return else None,
            dividend_yield=round(dividend_yield, 4) if dividend_yield else None,
            history_years=round(history_years, 1),
        )

    except Exception as e:
        logger.error(f"Failed to calculate quality score for {symbol}: {e}")
        return None


# =============================================================================
# Opportunity Score Calculation (Buy the Dip)
# =============================================================================

def calculate_opportunity_score(symbol: str, yahoo_symbol: str = None) -> Optional[OpportunityScore]:
    """
    Calculate opportunity score based on buy-the-dip signals.

    INVERTED from typical momentum scoring - we WANT stocks that are:
    - Below their 52-week high (temporary dip)
    - Below their 200-day moving average (undervalued)
    - Trading at low P/E vs historical (cheap)

    Components:
    - Below 52-week High (35%): Distance from peak
    - MA Distance (30%): Below 200-MA = opportunity
    - P/E vs Historical (35%): Below average = opportunity

    Args:
        symbol: Tradernet symbol
        yahoo_symbol: Optional explicit Yahoo symbol override
    """
    try:
        prices = yahoo.get_historical_prices(symbol, yahoo_symbol=yahoo_symbol, period="1y")
        fundamentals = yahoo.get_fundamental_data(symbol, yahoo_symbol=yahoo_symbol)

        if len(prices) < 50:
            logger.warning(f"Insufficient price data for opportunity score: {symbol}")
            return None

        closes = np.array([p.close for p in prices])
        highs = np.array([p.high for p in prices])
        current_price = closes[-1]

        # 1. Below 52-week High Score (35%)
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

        # 2. Distance from 200-day MA Score (30%)
        # Below MA = HIGHER score (INVERTED from typical momentum)
        ma_200 = np.mean(closes[-200:]) if len(closes) >= 200 else np.mean(closes)
        pct_from_ma = (current_price - ma_200) / ma_200 if ma_200 > 0 else 0

        if pct_from_ma >= 0.10:
            ma_score = 0.2  # 10%+ above MA = expensive
        elif pct_from_ma >= 0:
            ma_score = 0.5 - (pct_from_ma / 0.10) * 0.3  # 0-10% above -> 0.5-0.2
        elif pct_from_ma >= -0.05:
            ma_score = 0.5 + (abs(pct_from_ma) / 0.05) * 0.2  # 0-5% below -> 0.5-0.7
        elif pct_from_ma >= -0.10:
            ma_score = 0.7 + ((abs(pct_from_ma) - 0.05) / 0.05) * 0.3  # 5-10% below -> 0.7-1.0
        else:
            ma_score = 1.0  # 10%+ below MA

        # 3. P/E vs Historical Score (35%)
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

        # Combined Opportunity Score
        total = (
            below_52w_score * 0.35 +
            ma_score * 0.30 +
            pe_score * 0.35
        )

        return OpportunityScore(
            below_52w_high=round(below_52w_score, 3),
            ma_distance=round(ma_score, 3),
            pe_vs_historical=round(pe_score, 3),
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


# =============================================================================
# Combined Stock Score
# =============================================================================

def calculate_stock_score(
    symbol: str,
    yahoo_symbol: str = None,
    geography: str = None,
    industry: str = None,
    portfolio_context: PortfolioContext = None,
) -> Optional[StockScore]:
    """
    Calculate complete stock score with all components.

    Final weights (optimized for long-term value investing):
    - Quality: 35% (total return, consistency, financial strength, dividend bonus)
    - Opportunity: 35% (buy-the-dip signals)
    - Analyst: 15% (reduced from 30%)
    - Allocation Fit: 15% (portfolio awareness - geo gaps, industry gaps, averaging down)

    When portfolio_context is provided, allocation fit is calculated and included.
    Without portfolio_context, a normalized base score (85% -> 100%) is returned.

    Args:
        symbol: Tradernet symbol
        yahoo_symbol: Optional explicit Yahoo symbol override
        geography: Stock geography (EU, ASIA, US) - required for allocation fit
        industry: Stock industry - required for allocation fit
        portfolio_context: Portfolio weights and positions for allocation fit
    """
    quality = calculate_quality_score(symbol, yahoo_symbol)
    opportunity = calculate_opportunity_score(symbol, yahoo_symbol)
    analyst = calculate_analyst_score(symbol, yahoo_symbol)

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

    # Get volatility from price data for risk assessment
    volatility = None
    try:
        prices = yahoo.get_historical_prices(symbol, yahoo_symbol=yahoo_symbol, period="1y")
        if len(prices) >= 30:
            closes = np.array([p.close for p in prices])
            returns = np.diff(closes) / closes[:-1]
            volatility = float(np.std(returns) * np.sqrt(252))  # Annualized
    except Exception:
        pass

    # Create default scores if missing
    if not quality:
        quality = QualityScore(0.5, 0.5, 0.5, 0.0, 0.5, None, None, None, None, 0)
    if not opportunity:
        opportunity = OpportunityScore(0.5, 0.5, 0.5, 0.5)
    if not analyst:
        analyst = AnalystScore(0.5, 0.5, 0.5)

    return StockScore(
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

async def score_all_stocks(db, portfolio_context: PortfolioContext = None) -> list[StockScore]:
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
        score = calculate_stock_score(
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
