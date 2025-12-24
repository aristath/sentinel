"""
Diversification Score - Portfolio fit and balance.

Components:
- Geography Gap (40%): Boost underweight regions
- Industry Gap (30%): Boost underweight sectors
- Averaging Down (30%): Bonus for quality dips we own
"""

import logging
from typing import Optional

from app.domain.scoring.models import PortfolioContext
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
