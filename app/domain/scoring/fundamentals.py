"""
Fundamentals Score - Company health and stability.

Components:
- Financial Strength (60%): Profit margin, debt/equity, current ratio
- Consistency (40%): 5-year vs 10-year CAGR similarity
"""

import logging
from typing import Optional, List, Dict

from app.domain.scoring.constants import MIN_MONTHS_FOR_CAGR

logger = logging.getLogger(__name__)

# Internal weights for sub-components (hardcoded)
WEIGHT_FINANCIAL_STRENGTH = 0.60
WEIGHT_CONSISTENCY = 0.40


def calculate_financial_strength_score(fundamentals) -> float:
    """
    Calculate financial strength from fundamental data.

    Components:
    - Profit Margin (40%): Higher = better
    - Debt/Equity (30%): Lower = better
    - Current Ratio (30%): Higher = better (up to 3)

    Returns:
        Score from 0 to 1.0
    """
    if not fundamentals:
        return 0.5

    # Profit margin (40%): Higher = better
    margin = fundamentals.profit_margin or 0
    if margin >= 0:
        margin_score = min(1.0, 0.5 + margin * 2.5)
    else:
        margin_score = max(0, 0.5 + margin * 2)

    # Debt/Equity (30%): Lower = better (cap at 200)
    de = min(200, fundamentals.debt_to_equity or 50)
    de_score = max(0, 1 - de / 200)

    # Current ratio (30%): Higher = better (cap at 3)
    cr = min(3, fundamentals.current_ratio or 1)
    cr_score = min(1.0, cr / 2)

    return (
        margin_score * 0.40 +
        de_score * 0.30 +
        cr_score * 0.30
    )


def calculate_cagr(prices: List[Dict], months: int) -> Optional[float]:
    """Calculate CAGR from monthly prices."""
    if len(prices) < MIN_MONTHS_FOR_CAGR:
        return None

    use_months = min(months, len(prices))
    price_slice = prices[-use_months:]

    start_price = price_slice[0].get("avg_adj_close")
    end_price = price_slice[-1].get("avg_adj_close")

    if not start_price or not end_price or start_price <= 0:
        return None

    years = use_months / 12.0
    if years < 0.25:
        return (end_price / start_price) - 1

    try:
        return (end_price / start_price) ** (1 / years) - 1
    except (ValueError, ZeroDivisionError):
        return None


def calculate_consistency_score(cagr_5y: float, cagr_10y: Optional[float]) -> float:
    """
    Calculate consistency score based on 5y vs 10y CAGR similarity.

    Consistent growers (similar CAGR over different periods) score higher.

    Returns:
        Score from 0.4 to 1.0
    """
    if cagr_10y is None:
        return 0.6  # Neutral for newer stocks

    diff = abs(cagr_5y - cagr_10y)

    if diff < 0.02:  # Within 2%
        return 1.0
    elif diff < 0.05:  # Within 5%
        return 0.8
    else:
        return max(0.4, 1.0 - diff * 4)


def calculate_fundamentals_score(
    monthly_prices: List[Dict],
    fundamentals,
) -> tuple:
    """
    Calculate fundamentals score.

    Args:
        monthly_prices: Monthly price data for consistency
        fundamentals: Yahoo fundamentals data

    Returns:
        Tuple of (total_score, sub_components_dict)
        sub_components_dict: {"financial_strength": float, "consistency": float}
    """
    # Financial strength
    financial_score = calculate_financial_strength_score(fundamentals)

    # Consistency
    cagr_5y = calculate_cagr(monthly_prices, 60)
    if cagr_5y is None:
        cagr_5y = calculate_cagr(monthly_prices, len(monthly_prices))

    cagr_10y = None
    if len(monthly_prices) > 60:
        cagr_10y = calculate_cagr(monthly_prices, len(monthly_prices))

    consistency_score = calculate_consistency_score(cagr_5y or 0, cagr_10y)

    # Combine with internal weights
    total = (
        financial_score * WEIGHT_FINANCIAL_STRENGTH +
        consistency_score * WEIGHT_CONSISTENCY
    )

    sub_components = {
        "financial_strength": round(financial_score, 3),
        "consistency": round(consistency_score, 3),
    }

    return round(min(1.0, total), 3), sub_components
