"""Performance adjustment calculator for rebalancing operations.

Calculates performance-adjusted allocation weights based on PyFolio attribution.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

from app.domain.analytics import (
    calculate_portfolio_returns,
    get_performance_attribution,
    reconstruct_portfolio_values,
)
from app.domain.repositories.protocols import IAllocationRepository
from app.infrastructure.recommendation_cache import get_recommendation_cache

logger = logging.getLogger(__name__)


async def get_performance_adjusted_weights(
    allocation_repo: IAllocationRepository,
    portfolio_hash: Optional[str] = None,
) -> Tuple[Dict[str, float], Dict[str, float]]:
    """Get performance-adjusted allocation weights based on PyFolio attribution.

    Args:
        allocation_repo: Repository for allocation targets
        portfolio_hash: Optional portfolio hash for caching (48h TTL)

    Returns:
        Tuple of (adjusted_geo_weights, adjusted_ind_weights)
    """
    try:
        # Check cache first if we have a portfolio hash
        rec_cache = get_recommendation_cache()
        if portfolio_hash:
            cache_key = f"perf:weights:{portfolio_hash}"
            cached = await rec_cache.get_analytics(cache_key)
            if cached:
                logger.debug("Using cached performance-adjusted weights")
                return cached.get("geo", {}), cached.get("ind", {})

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

        geo_attribution = attribution.get("geography", {})
        ind_attribution = attribution.get("industry", {})

        # Adjust weights based on performance
        # If a geography/industry outperformed, increase its target slightly
        adjusted_geo: Dict[str, float] = {}
        adjusted_ind: Dict[str, float] = {}

        # Get base allocation targets
        allocations = await allocation_repo.get_all()

        base_geo_weights = {
            key.split(":", 1)[1]: val
            for key, val in allocations.items()
            if key.startswith("geography:")
        }
        base_ind_weights = {
            key.split(":", 1)[1]: val
            for key, val in allocations.items()
            if key.startswith("industry:")
        }

        # Calculate average return for comparison
        avg_geo_return = (
            sum(geo_attribution.values()) / len(geo_attribution)
            if geo_attribution
            else 0.0
        )
        avg_ind_return = (
            sum(ind_attribution.values()) / len(ind_attribution)
            if ind_attribution
            else 0.0
        )

        # Adjust geography weights (max 3% adjustment - reduced influence)
        for geo, base_weight in base_geo_weights.items():
            perf_return = geo_attribution.get(geo, 0.0)
            if perf_return > avg_geo_return * 1.2:  # 20% above average
                # Increase weight by up to 3%
                adjustment = min(0.03, (perf_return - avg_geo_return) * 0.1)
                adjusted_geo[geo] = base_weight + adjustment
            elif perf_return < avg_geo_return * 0.8:  # 20% below average
                # Decrease weight by up to 3%
                adjustment = min(0.03, (avg_geo_return - perf_return) * 0.1)
                adjusted_geo[geo] = max(0.0, base_weight - adjustment)
            else:
                adjusted_geo[geo] = base_weight

        # Adjust industry weights (max 2% adjustment - reduced influence)
        for ind, base_weight in base_ind_weights.items():
            perf_return = ind_attribution.get(ind, 0.0)
            if perf_return > avg_ind_return * 1.2:  # 20% above average
                adjustment = min(0.02, (perf_return - avg_ind_return) * 0.1)
                adjusted_ind[ind] = base_weight + adjustment
            elif perf_return < avg_ind_return * 0.8:  # 20% below average
                adjustment = min(0.02, (avg_ind_return - perf_return) * 0.1)
                adjusted_ind[ind] = max(0.0, base_weight - adjustment)
            else:
                adjusted_ind[ind] = base_weight

        # Cache the result (48h TTL)
        if portfolio_hash and (adjusted_geo or adjusted_ind):
            await rec_cache.set_analytics(
                cache_key, {"geo": adjusted_geo, "ind": adjusted_ind}, ttl_hours=48
            )

        return adjusted_geo, adjusted_ind

    except Exception as e:
        logger.debug(f"Could not calculate performance-adjusted weights: {e}")
        # Return empty dicts on error (use base weights)
        return {}, {}
