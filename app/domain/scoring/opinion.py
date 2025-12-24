"""
Opinion Score - External analyst opinions and price targets.

Components:
- Recommendation (60%): Buy/Hold/Sell consensus
- Price Target (40%): Upside potential
"""

import logging
from typing import Optional

from app.services import yahoo

logger = logging.getLogger(__name__)


def calculate_opinion_score(
    symbol: str,
    yahoo_symbol: str = None
) -> tuple:
    """
    Calculate opinion score from analyst recommendations and price targets.

    Args:
        symbol: Tradernet symbol
        yahoo_symbol: Optional explicit Yahoo symbol override

    Returns:
        Tuple of (total_score, sub_components_dict)
        sub_components_dict: {"recommendation": float, "price_target": float}
    """
    try:
        data = yahoo.get_analyst_data(symbol, yahoo_symbol=yahoo_symbol)

        if not data:
            sub_components = {"recommendation": 0.5, "price_target": 0.5}
            return 0.5, sub_components

        # Recommendation score (already 0-1 from yahoo service)
        recommendation_score = data.recommendation_score

        # Target score: based on upside potential
        # 0% upside = 0.5, 20%+ upside = 1.0, -20% = 0.0
        upside = data.upside_pct / 100  # Convert to decimal
        target_score = 0.5 + (upside * 2.5)  # Scale
        target_score = max(0, min(1, target_score))

        # Combined (60% recommendation, 40% target)
        total = recommendation_score * 0.60 + target_score * 0.40

        sub_components = {
            "recommendation": round(recommendation_score, 3),
            "price_target": round(target_score, 3),
        }

        return round(total, 3), sub_components

    except Exception as e:
        logger.error(f"Failed to calculate opinion score for {symbol}: {e}")
        sub_components = {"recommendation": 0.5, "price_target": 0.5}
        return 0.5, sub_components
