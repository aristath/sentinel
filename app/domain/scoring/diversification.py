"""
Diversification Score - Portfolio fit and balance.

Components:
- Geography Gap (40%): Boost underweight regions
- Industry Gap (30%): Boost underweight sectors
- Averaging Down (30%): Bonus for quality dips we own
"""

import logging
from typing import Optional, Dict

from app.domain.scoring.models import PortfolioContext, PortfolioScore
from app.domain.scoring.constants import (
    MAX_COST_BASIS_BOOST,
    COST_BASIS_BOOST_THRESHOLD,
    CONCENTRATION_HIGH,
    CONCENTRATION_MED,
)

logger = logging.getLogger(__name__)

# Internal weights (hardcoded)
WEIGHT_GEOGRAPHY = 0.40
WEIGHT_INDUSTRY = 0.30
WEIGHT_AVERAGING = 0.30


def calculate_diversification_score(
    symbol: str,
    geography: str,
    industry: Optional[str],
    quality_score: float,
    opportunity_score: float,
    portfolio_context: PortfolioContext,
) -> tuple:
    """
    Calculate diversification score based on portfolio awareness.

    Args:
        symbol: Stock symbol
        geography: Stock geography (EU, ASIA, US)
        industry: Stock industry (comma-separated if multiple)
        quality_score: Pre-calculated quality score (0-1)
        opportunity_score: Pre-calculated opportunity score (0-1)
        portfolio_context: Portfolio weights and positions

    Returns:
        Tuple of (total_score, sub_components_dict)
        sub_components_dict: {"geography": float, "industry": float, "averaging": float}
    """
    # 1. Geography Gap Score (40%)
    geo_weight = portfolio_context.geo_weights.get(geography, 0)
    geo_gap_score = 0.5 + (geo_weight * 0.4)
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
            industry_gap_score = 0.5
    else:
        industry_gap_score = 0.5

    # 3. Averaging Down Score (30%)
    position_value = portfolio_context.positions.get(symbol, 0)

    if position_value > 0:
        avg_down_potential = quality_score * opportunity_score

        if avg_down_potential >= 0.5:
            averaging_down_score = 0.7 + (avg_down_potential - 0.5) * 0.6
        elif avg_down_potential >= 0.3:
            averaging_down_score = 0.5 + (avg_down_potential - 0.3) * 1.0
        else:
            averaging_down_score = 0.3

        # Cost basis bonus
        if (portfolio_context.position_avg_prices and
            portfolio_context.current_prices):
            avg_price = portfolio_context.position_avg_prices.get(symbol)
            current_price = portfolio_context.current_prices.get(symbol)

            if avg_price and current_price and avg_price > 0:
                price_vs_avg = (current_price - avg_price) / avg_price

                if price_vs_avg < 0:
                    loss_pct = abs(price_vs_avg)
                    if loss_pct <= COST_BASIS_BOOST_THRESHOLD:
                        cost_basis_boost = min(MAX_COST_BASIS_BOOST, loss_pct * 2)
                        averaging_down_score = min(1.0, averaging_down_score + cost_basis_boost)

        # Avoid over-concentration
        total_value = portfolio_context.total_value
        if total_value > 0:
            position_pct = position_value / total_value
            if position_pct > CONCENTRATION_HIGH:
                averaging_down_score *= 0.7
            elif position_pct > CONCENTRATION_MED:
                averaging_down_score *= 0.9
    else:
        averaging_down_score = 0.5

    # Combined score
    total = (
        geo_gap_score * WEIGHT_GEOGRAPHY +
        industry_gap_score * WEIGHT_INDUSTRY +
        averaging_down_score * WEIGHT_AVERAGING
    )

    sub_components = {
        "geography": round(geo_gap_score, 3),
        "industry": round(industry_gap_score, 3),
        "averaging": round(averaging_down_score, 3),
    }

    return round(min(1.0, total), 3), sub_components


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
    geo_deviations = []
    if portfolio_context.stock_geographies:
        # Calculate current geo allocations
        geo_values: Dict[str, float] = {}
        for symbol, value in portfolio_context.positions.items():
            geo = portfolio_context.stock_geographies.get(symbol, "OTHER")
            geo_values[geo] = geo_values.get(geo, 0) + value

        # Compare to targets
        for geo, weight in portfolio_context.geo_weights.items():
            target_pct = 0.33 + (weight * 0.15)  # Base 33% +/- 15%
            current_pct = geo_values.get(geo, 0) / total_value if total_value > 0 else 0
            deviation = abs(current_pct - target_pct)
            geo_deviations.append(deviation)

    avg_geo_deviation = sum(geo_deviations) / len(geo_deviations) if geo_deviations else 0.2
    # Convert deviation to score: 0 deviation = 100, 0.3+ deviation = 0
    diversification_score = max(0, 100 * (1 - avg_geo_deviation / 0.3))

    # 2. Dividend Score (30%)
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
    if portfolio_context.stock_scores:
        weighted_quality = 0.0
        for symbol, value in portfolio_context.positions.items():
            quality = portfolio_context.stock_scores.get(symbol, 0.5) or 0.5
            weighted_quality += quality * (value / total_value)
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
) -> tuple:
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

    # Create modified context with proposed transaction
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
