"""
Opinion Score - External analyst opinions and price targets.

Components:
- Recommendation (60%): Buy/Hold/Sell consensus
- Price Target (40%): Upside potential
"""

import logging
from typing import Optional

from app.domain.responses import ScoreResult
from app.infrastructure.external import yahoo_finance as yahoo

logger = logging.getLogger(__name__)


async def calculate_opinion_score(symbol: str, yahoo_symbol: str = None) -> ScoreResult:
    """
    Calculate opinion score from analyst recommendations and price targets.

    Args:
        symbol: Tradernet symbol
        yahoo_symbol: Optional explicit Yahoo symbol override

    Returns:
        ScoreResult with score and sub_scores
        sub_scores: {"recommendation": float, "price_target": float}
    """
    from app.repositories.calculations import CalculationsRepository

    calc_repo = CalculationsRepository()

    # Check cache first
    cached_rec = await calc_repo.get_metric(symbol, "ANALYST_RECOMMENDATION")
    cached_upside = await calc_repo.get_metric(symbol, "PRICE_TARGET_UPSIDE")

    if cached_rec is not None and cached_upside is not None:
        # Use cached values
        recommendation_score = cached_rec
        upside = cached_upside / 100  # Convert from percentage to decimal
        target_score = 0.5 + (upside * 2.5)  # Scale
        target_score = max(0, min(1, target_score))
    else:
        # Fetch from Yahoo
        try:
            data = yahoo.get_analyst_data(symbol, yahoo_symbol=yahoo_symbol)

            if not data:
                sub_components = {"recommendation": 0.5, "price_target": 0.5}
                return ScoreResult(score=0.5, sub_scores=sub_components)

            # Recommendation score (already 0-1 from yahoo service)
            recommendation_score = data.recommendation_score

            # Target score: based on upside potential
            # 0% upside = 0.5, 20%+ upside = 1.0, -20% = 0.0
            upside = data.upside_pct / 100  # Convert to decimal
            target_score = 0.5 + (upside * 2.5)  # Scale
            target_score = max(0, min(1, target_score))

            # Cache the values
            await calc_repo.set_metric(
                symbol, "ANALYST_RECOMMENDATION", recommendation_score, source="yahoo"
            )
            await calc_repo.set_metric(
                symbol, "PRICE_TARGET_UPSIDE", data.upside_pct, source="yahoo"
            )

        except Exception as e:
            logger.error(f"Failed to calculate opinion score for {symbol}: {e}")
            sub_components = {"recommendation": 0.5, "price_target": 0.5}
            return ScoreResult(score=0.5, sub_scores=sub_components)

    # Combined (60% recommendation, 40% target)
    total = recommendation_score * 0.60 + target_score * 0.40

    sub_components = {
        "recommendation": round(recommendation_score, 3),
        "price_target": round(target_score, 3),
    }

    return ScoreResult(score=round(total, 3), sub_scores=sub_components)
