"""
Diversification Score - Portfolio fit and balance.

Components:
- Geography Gap (40%): Boost underweight regions
- Industry Gap (30%): Boost underweight sectors
- Averaging Down (30%): Bonus for quality dips we own
"""

import logging
from typing import Dict, Optional

from app.domain.responses import ScoreResult
from app.modules.scoring.domain.constants import (
    CONCENTRATION_HIGH,
    CONCENTRATION_MED,
    COST_BASIS_BOOST_THRESHOLD,
    MAX_COST_BASIS_BOOST,
)
from app.modules.scoring.domain.models import PortfolioContext, PortfolioScore

logger = logging.getLogger(__name__)

# Internal weights (hardcoded)
WEIGHT_GEOGRAPHY = 0.40
WEIGHT_INDUSTRY = 0.30
WEIGHT_AVERAGING = 0.30


def _calculate_geo_gap_score(
    country: str, portfolio_context: PortfolioContext
) -> float:
    """Calculate country gap score (40% weight)."""
    # Map individual country to group
    country_to_group = portfolio_context.country_to_group or {}
    group = country_to_group.get(country, "OTHER")

    # Look up weight for the group
    geo_weight = portfolio_context.country_weights.get(group, 0)
    geo_gap_score = 0.5 + (geo_weight * 0.4)
    return max(0.1, min(0.9, geo_gap_score))


def _calculate_industry_gap_score(
    industry: Optional[str], portfolio_context: PortfolioContext
) -> float:
    """Calculate industry gap score (30% weight)."""
    if not industry:
        return 0.5

    industries = [ind.strip() for ind in industry.split(",") if ind.strip()]
    if not industries:
        return 0.5

    ind_scores = []
    industry_to_group = portfolio_context.industry_to_group or {}
    for ind in industries:
        # Map individual industry to group
        group = industry_to_group.get(ind, "OTHER")
        # Look up weight for the group
        ind_weight = portfolio_context.industry_weights.get(group, 0)
        ind_score = 0.5 + (ind_weight * 0.4)
        ind_scores.append(max(0.1, min(0.9, ind_score)))

    return sum(ind_scores) / len(ind_scores)


def _calculate_averaging_down_score(
    symbol: str,
    quality_score: float,
    opportunity_score: float,
    portfolio_context: PortfolioContext,
) -> float:
    """Calculate averaging down score (30% weight)."""
    position_value = portfolio_context.positions.get(symbol, 0)

    if position_value <= 0:
        return 0.5

    avg_down_potential = quality_score * opportunity_score

    if avg_down_potential >= 0.5:
        averaging_down_score = 0.7 + (avg_down_potential - 0.5) * 0.6
    elif avg_down_potential >= 0.3:
        averaging_down_score = 0.5 + (avg_down_potential - 0.3) * 1.0
    else:
        averaging_down_score = 0.3

    # Apply cost basis bonus
    averaging_down_score = _apply_cost_basis_bonus(
        symbol, averaging_down_score, portfolio_context
    )

    # Apply concentration penalty
    averaging_down_score = _apply_concentration_penalty(
        position_value, averaging_down_score, portfolio_context
    )

    return averaging_down_score


def _apply_cost_basis_bonus(
    symbol: str, score: float, portfolio_context: PortfolioContext
) -> float:
    """Apply cost basis bonus if price is below average."""
    if (
        not portfolio_context.position_avg_prices
        or not portfolio_context.current_prices
    ):
        return score

    avg_price = portfolio_context.position_avg_prices.get(symbol)
    current_price = portfolio_context.current_prices.get(symbol)

    if not avg_price or not current_price or avg_price <= 0:
        return score

    price_vs_avg = (current_price - avg_price) / avg_price
    if price_vs_avg >= 0:
        return score

    loss_pct = abs(price_vs_avg)
    if loss_pct <= COST_BASIS_BOOST_THRESHOLD:
        cost_basis_boost = min(MAX_COST_BASIS_BOOST, loss_pct * 2)
        return min(1.0, score + cost_basis_boost)

    return score


def _apply_concentration_penalty(
    position_value: float, score: float, portfolio_context: PortfolioContext
) -> float:
    """Apply penalty for over-concentration."""
    total_value = portfolio_context.total_value
    if total_value <= 0:
        return score

    position_pct = position_value / total_value
    if position_pct > CONCENTRATION_HIGH:
        return score * 0.7
    elif position_pct > CONCENTRATION_MED:
        return score * 0.9

    return score


def calculate_diversification_score(
    symbol: str,
    country: str,
    industry: Optional[str],
    quality_score: float,
    opportunity_score: float,
    portfolio_context: PortfolioContext,
) -> ScoreResult:
    """
    Calculate diversification score based on portfolio awareness.

    Args:
        symbol: Stock symbol
        country: Stock country (e.g., "United States", "Germany")
        industry: Stock industry (comma-separated if multiple)
        quality_score: Pre-calculated quality score (0-1)
        opportunity_score: Pre-calculated opportunity score (0-1)
        portfolio_context: Portfolio weights and positions

    Returns:
        ScoreResult with score and sub_scores
        sub_scores: {"country": float, "industry": float, "averaging": float}
    """
    geo_gap_score = _calculate_geo_gap_score(country, portfolio_context)
    industry_gap_score = _calculate_industry_gap_score(industry, portfolio_context)
    averaging_down_score = _calculate_averaging_down_score(
        symbol, quality_score, opportunity_score, portfolio_context
    )

    total = (
        geo_gap_score * WEIGHT_GEOGRAPHY
        + industry_gap_score * WEIGHT_INDUSTRY
        + averaging_down_score * WEIGHT_AVERAGING
    )

    sub_components = {
        "country": round(geo_gap_score, 3),
        "industry": round(industry_gap_score, 3),
        "averaging": round(averaging_down_score, 3),
    }

    return ScoreResult(score=round(min(1.0, total), 3), sub_scores=sub_components)


async def _get_cached_portfolio_score(portfolio_hash: str) -> Optional[PortfolioScore]:
    """Get cached portfolio score if available."""
    from app.infrastructure.recommendation_cache import get_recommendation_cache

    rec_cache = get_recommendation_cache()
    cache_key = f"portfolio_score:{portfolio_hash}"
    cached = await rec_cache.get_analytics(cache_key)
    if cached:
        logger.debug(f"Using cached portfolio score for hash {portfolio_hash[:8]}...")
        return PortfolioScore(
            diversification_score=cached["diversification_score"],
            dividend_score=cached["dividend_score"],
            quality_score=cached["quality_score"],
            total=cached["total"],
        )
    return None


async def _cache_portfolio_score(score: PortfolioScore, portfolio_hash: str) -> None:
    """Cache portfolio score result."""
    from app.infrastructure.recommendation_cache import get_recommendation_cache

    rec_cache = get_recommendation_cache()
    cache_key = f"portfolio_score:{portfolio_hash}"
    await rec_cache.set_analytics(
        cache_key,
        {
            "diversification_score": score.diversification_score,
            "dividend_score": score.dividend_score,
            "quality_score": score.quality_score,
            "total": score.total,
        },
        ttl_hours=24,
    )


def _calculate_diversification_score(
    portfolio_context: PortfolioContext, total_value: float
) -> float:
    """Calculate diversification score (40% weight)."""
    country_deviations = []
    if portfolio_context.security_countries:
        # Map individual countries to groups and aggregate by group
        country_to_group = portfolio_context.country_to_group or {}
        group_values: Dict[str, float] = {}
        for symbol, value in portfolio_context.positions.items():
            country = portfolio_context.security_countries.get(symbol, "OTHER")
            group = country_to_group.get(country, "OTHER")
            group_values[group] = group_values.get(group, 0) + value

        # Compare group allocations to group targets
        for group, weight in portfolio_context.country_weights.items():
            target_pct = weight  # Group targets are already percentages (0-1)
            current_pct = (
                group_values.get(group, 0) / total_value if total_value > 0 else 0
            )
            deviation = abs(current_pct - target_pct)
            country_deviations.append(deviation)

    avg_country_deviation = (
        sum(country_deviations) / len(country_deviations) if country_deviations else 0.2
    )
    return max(0, 100 * (1 - avg_country_deviation / 0.3))


def _calculate_dividend_score(
    portfolio_context: PortfolioContext, total_value: float
) -> float:
    """Calculate dividend score (30% weight)."""
    if not portfolio_context.security_dividends:
        return 50.0

    weighted_dividend = 0.0
    for symbol, value in portfolio_context.positions.items():
        div_yield = portfolio_context.security_dividends.get(symbol, 0) or 0
        weighted_dividend += div_yield * (value / total_value)
    return min(100, 30 + weighted_dividend * 1000)


def _calculate_quality_score(
    portfolio_context: PortfolioContext, total_value: float
) -> float:
    """Calculate quality score (30% weight)."""
    if not portfolio_context.security_scores:
        return 50.0

    weighted_quality = 0.0
    for symbol, value in portfolio_context.positions.items():
        quality = portfolio_context.security_scores.get(symbol, 0.5) or 0.5
        weighted_quality += quality * (value / total_value)
    return weighted_quality * 100


async def calculate_portfolio_score(
    portfolio_context: PortfolioContext, portfolio_hash: Optional[str] = None
) -> PortfolioScore:
    """
    Calculate overall portfolio health score.

    Components:
    - Diversification (40%): How close to target geo/industry allocations
    - Dividend (30%): Weighted average dividend yield across positions
    - Quality (30%): Weighted average stock quality scores

    Args:
        portfolio_context: Portfolio context with positions and weights
        portfolio_hash: Optional portfolio hash for caching. If provided, will check cache first.

    Returns:
        PortfolioScore with component scores and total (0-100 scale)
    """
    if portfolio_hash:
        cached = await _get_cached_portfolio_score(portfolio_hash)
        if cached:
            return cached

    total_value = portfolio_context.total_value
    if total_value <= 0:
        score = PortfolioScore(
            diversification_score=50.0,
            dividend_score=50.0,
            quality_score=50.0,
            total=50.0,
        )
        if portfolio_hash:
            await _cache_portfolio_score(score, portfolio_hash)
        return score

    diversification_score = _calculate_diversification_score(
        portfolio_context, total_value
    )
    dividend_score = _calculate_dividend_score(portfolio_context, total_value)
    quality_score = _calculate_quality_score(portfolio_context, total_value)

    total = diversification_score * 0.40 + dividend_score * 0.30 + quality_score * 0.30

    score = PortfolioScore(
        diversification_score=round(diversification_score, 1),
        dividend_score=round(dividend_score, 1),
        quality_score=round(quality_score, 1),
        total=round(total, 1),
    )

    if portfolio_hash:
        await _cache_portfolio_score(score, portfolio_hash)

    return score


async def calculate_post_transaction_score(
    symbol: str,
    country: str,
    industry: Optional[str],
    proposed_value: float,
    stock_quality: float,
    stock_dividend: float,
    portfolio_context: PortfolioContext,
    portfolio_hash: Optional[str] = None,
) -> tuple:
    """
    Calculate portfolio score AFTER a proposed transaction.

    Args:
        symbol: Stock symbol to buy
        country: Stock country (e.g., "United States", "Germany")
        industry: Stock industry
        proposed_value: Transaction value (min_lot * price)
        stock_quality: Quality score of the stock (0-1)
        stock_dividend: Dividend yield of the stock (0-1)
        portfolio_context: Current portfolio context
        portfolio_hash: Optional portfolio hash for caching. If provided, will check cache first.

    Returns:
        Tuple of (new_portfolio_score, score_change)
    """
    # Round trade amount to nearest 10 EUR to increase cache hit rate
    rounded_amount = round(proposed_value / 10) * 10

    # Check cache if portfolio_hash is provided
    if portfolio_hash:
        from app.infrastructure.recommendation_cache import get_recommendation_cache

        rec_cache = get_recommendation_cache()
        cache_key = f"scenario:{portfolio_hash}:{symbol}:{rounded_amount}"
        cached = await rec_cache.get_analytics(cache_key)
        if cached:
            logger.debug(
                f"Using cached scenario score for {symbol} with hash {portfolio_hash[:8]}..."
            )
            return (
                PortfolioScore(
                    diversification_score=cached["new_portfolio_score"][
                        "diversification_score"
                    ],
                    dividend_score=cached["new_portfolio_score"]["dividend_score"],
                    quality_score=cached["new_portfolio_score"]["quality_score"],
                    total=cached["new_portfolio_score"]["total"],
                ),
                cached["score_change"],
            )

    # Calculate current portfolio score
    current_score = await calculate_portfolio_score(
        portfolio_context, portfolio_hash=portfolio_hash
    )

    # Create modified context with proposed transaction
    new_positions = dict(portfolio_context.positions)
    new_positions[symbol] = new_positions.get(symbol, 0) + proposed_value

    new_geographies = dict(portfolio_context.security_countries or {})
    new_geographies[symbol] = country

    new_industries = dict(portfolio_context.security_industries or {})
    if industry:
        new_industries[symbol] = industry

    new_scores = dict(portfolio_context.security_scores or {})
    new_scores[symbol] = stock_quality

    new_dividends = dict(portfolio_context.security_dividends or {})
    new_dividends[symbol] = stock_dividend

    new_context = PortfolioContext(
        country_weights=portfolio_context.country_weights,
        industry_weights=portfolio_context.industry_weights,
        positions=new_positions,
        total_value=portfolio_context.total_value + proposed_value,
        security_countries=new_geographies,
        security_industries=new_industries,
        security_scores=new_scores,
        security_dividends=new_dividends,
    )

    # Calculate new portfolio score (don't cache post-transaction portfolio score separately)
    new_score = await calculate_portfolio_score(new_context, portfolio_hash=None)
    score_change = new_score.total - current_score.total

    # Cache the scenario result if portfolio_hash provided
    if portfolio_hash:
        from app.infrastructure.recommendation_cache import get_recommendation_cache

        rec_cache = get_recommendation_cache()
        cache_key = f"scenario:{portfolio_hash}:{symbol}:{rounded_amount}"
        await rec_cache.set_analytics(
            cache_key,
            {
                "new_portfolio_score": {
                    "diversification_score": new_score.diversification_score,
                    "dividend_score": new_score.dividend_score,
                    "quality_score": new_score.quality_score,
                    "total": new_score.total,
                },
                "score_change": score_change,
            },
            ttl_hours=96,
        )

    return new_score, score_change
