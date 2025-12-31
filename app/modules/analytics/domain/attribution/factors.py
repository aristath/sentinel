"""Factor attribution calculation.

Analyzes which factors contributed most to portfolio returns.
"""

import empyrical
import numpy as np
import pandas as pd

from app.modules.analytics.domain.attribution.performance import (
    get_performance_attribution,
)


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
            "country_contribution": 0.0,
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
    country_attribution = attribution.get("country", {})
    ind_attribution = attribution.get("industry", {})

    country_contribution = 0.0
    ind_contribution = 0.0

    # Average the attributed returns (already weighted by position value in get_performance_attribution)
    if country_attribution:
        country_contribution = sum(country_attribution.values()) / len(
            country_attribution
        )
    if ind_attribution:
        ind_contribution = sum(ind_attribution.values()) / len(ind_attribution)

    return {
        "country_contribution": (
            country_contribution if np.isfinite(country_contribution) else 0.0
        ),
        "industry_contribution": (
            ind_contribution if np.isfinite(ind_contribution) else 0.0
        ),
        "total_return": total_return,
    }
