"""CAGR (Compound Annual Growth Rate) calculation.

This module provides the single source of truth for CAGR calculations
used across the scoring system.
"""

from typing import Dict, List, Optional

# Minimum months required for reliable CAGR calculation
MIN_MONTHS_FOR_CAGR = 12


def calculate_cagr(prices: List[Dict], months: int) -> Optional[float]:
    """
    Calculate CAGR from monthly prices.

    Args:
        prices: List of dicts with year_month and avg_adj_close
        months: Number of months to use (e.g., 60 for 5 years)

    Returns:
        CAGR as decimal or None if insufficient data
    """
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
