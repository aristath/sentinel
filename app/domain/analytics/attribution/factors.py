"""Factor attribution calculation.

Analyzes which factors contributed most to portfolio returns.
"""

import empyrical
import numpy as np
import pandas as pd

from app.domain.analytics.attribution.performance import get_performance_attribution


async def get_factor_attribution(
    returns: pd.Series, start_date: str, end_date: str
) -> dict[str, float]:
    """
    Analyze which factors contributed most to returns.

    Returns:
        Dict with factor contributions as weighted averages of attributed returns.
    """
    if returns.empty:
        return {
            "geography_contribution": 0.0,
            "industry_contribution": 0.0,
            "total_return": 0.0,
        }

    # Get performance attribution
    attribution = await get_performance_attribution(returns, start_date, end_date)

    # Calculate total portfolio return using empyrical
    total_return = float(empyrical.annual_return(returns))
    if not np.isfinite(total_return):
        total_return = 0.0

    # Calculate weighted contributions (average of attributed returns)
    geo_attribution = attribution.get("geography", {})
    ind_attribution = attribution.get("industry", {})

    geo_contribution = 0.0
    ind_contribution = 0.0

    # Average the attributed returns (already weighted by position value in get_performance_attribution)
    if geo_attribution:
        geo_contribution = sum(geo_attribution.values()) / len(geo_attribution)
    if ind_attribution:
        ind_contribution = sum(ind_attribution.values()) / len(ind_attribution)

    return {
        "geography_contribution": (
            geo_contribution if np.isfinite(geo_contribution) else 0.0
        ),
        "industry_contribution": (
            ind_contribution if np.isfinite(ind_contribution) else 0.0
        ),
        "total_return": total_return,
    }
