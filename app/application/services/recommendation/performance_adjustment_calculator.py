"""Performance adjustment calculator for rebalancing operations.

Calculates performance-adjusted allocation weights based on PyFolio attribution.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

from app.domain.repositories.protocols import IAllocationRepository
from app.infrastructure.recommendation_cache import get_recommendation_cache
from app.modules.analytics.domain import (
    calculate_portfolio_returns,
    get_performance_attribution,
    reconstruct_portfolio_values,
)

logger = logging.getLogger(__name__)


def _adjust_country_weights(
    base_country_weights: dict, country_attribution: dict, avg_country_return: float
) -> dict:
    """Adjust country weights based on performance attribution."""
    adjusted = {}
    for country, base_weight in base_country_weights.items():
        country_return = country_attribution.get(country, avg_country_return)
        if country_return > avg_country_return:
            adjusted[country] = base_weight * 1.1
        elif country_return < avg_country_return:
            adjusted[country] = base_weight * 0.9
        else:
            adjusted[country] = base_weight
    return adjusted


def _adjust_ind_weights(
    base_ind_weights: dict, ind_attribution: dict, avg_ind_return: float
) -> dict:
    """Adjust industry weights based on performance attribution."""
    adjusted = {}
    for ind, base_weight in base_ind_weights.items():
        ind_return = ind_attribution.get(ind, avg_ind_return)
        if ind_return > avg_ind_return:
            adjusted[ind] = base_weight * 1.1
        elif ind_return < avg_ind_return:
            adjusted[ind] = base_weight * 0.9
        else:
            adjusted[ind] = base_weight
    return adjusted


async def get_performance_adjusted_weights(
    allocation_repo: IAllocationRepository,
    portfolio_hash: Optional[str] = None,
) -> Tuple[Dict[str, float], Dict[str, float]]:
    """Get performance-adjusted allocation weights based on PyFolio attribution.

    Args:
        allocation_repo: Repository for allocation targets
        portfolio_hash: Optional portfolio hash for caching (48h TTL)

    Returns:
        Tuple of (adjusted_country_weights, adjusted_ind_weights)
    """
    try:
        # Check cache first if we have a portfolio hash
        rec_cache = get_recommendation_cache()
        if portfolio_hash:
            cache_key = f"perf:weights:{portfolio_hash}"
            cached = await rec_cache.get_analytics(cache_key)
            if cached:
                logger.debug("Using cached performance-adjusted weights")
                return cached.get("country", {}), cached.get("ind", {})

        # Calculate date range (last 365 days)
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

        # Reconstruct portfolio and get returns
        portfolio_values = await reconstruct_portfolio_values(start_date, end_date)
        returns = calculate_portfolio_returns(portfolio_values)

        if returns.empty or len(returns) < 30:
            # Not enough data, return empty dicts (use base weights)
            return {}, {}

        # Get performance attribution (EXPENSIVE - ~27 seconds)
        attribution = await get_performance_attribution(returns, start_date, end_date)

        country_attribution = attribution.get("country", {})
        ind_attribution = attribution.get("industry", {})

        allocations = await allocation_repo.get_all()

        base_country_weights = {
            key.split(":", 1)[1]: val
            for key, val in allocations.items()
            if key.startswith("country:")
        }
        base_ind_weights = {
            key.split(":", 1)[1]: val
            for key, val in allocations.items()
            if key.startswith("industry:")
        }

        avg_country_return = (
            sum(country_attribution.values()) / len(country_attribution)
            if country_attribution
            else 0.0
        )
        avg_ind_return = (
            sum(ind_attribution.values()) / len(ind_attribution)
            if ind_attribution
            else 0.0
        )

        adjusted_country = _adjust_country_weights(
            base_country_weights, country_attribution, avg_country_return
        )
        adjusted_ind = _adjust_ind_weights(
            base_ind_weights, ind_attribution, avg_ind_return
        )

        # Cache the result (48h TTL)
        if portfolio_hash and (adjusted_country or adjusted_ind):
            await rec_cache.set_analytics(
                cache_key,
                {"country": adjusted_country, "ind": adjusted_ind},
                ttl_hours=48,
            )

        return adjusted_country, adjusted_ind

    except Exception as e:
        logger.debug(f"Could not calculate performance-adjusted weights: {e}")
        # Return empty dicts on error (use base weights)
        return {}, {}
