"""
Dividends Score - Income and dividend quality.

Components:
- Dividend Yield (70%): Current yield level
- Dividend Growth (30%): Consistency and growth of dividends
"""

import logging

from app.domain.responses import ScoreResult
from app.modules.scoring.domain.scorers.dividends import (
    score_dividend_consistency,
    score_dividend_yield,
)

logger = logging.getLogger(__name__)


async def calculate_dividends_score(symbol: str, fundamentals) -> ScoreResult:
    """
    Calculate dividends score.

    Args:
        symbol: Stock symbol (for cache lookup)
        fundamentals: Yahoo fundamentals data

    Returns:
        ScoreResult with score and sub_scores
        sub_scores: {"yield": float, "consistency": float}
    """
    from app.repositories.calculations import CalculationsRepository

    calc_repo = CalculationsRepository()

    dividend_yield = fundamentals.dividend_yield if fundamentals else None
    payout_ratio = (
        fundamentals.payout_ratio if hasattr(fundamentals, "payout_ratio") else None
    )

    # Cache dividend metrics
    if dividend_yield is not None:
        await calc_repo.set_metric(
            symbol, "DIVIDEND_YIELD", dividend_yield, source="yahoo"
        )
    if payout_ratio is not None:
        await calc_repo.set_metric(symbol, "PAYOUT_RATIO", payout_ratio, source="yahoo")

    yield_score = score_dividend_yield(dividend_yield)
    consistency_score = score_dividend_consistency(fundamentals)

    # 70% yield, 30% consistency
    total = yield_score * 0.70 + consistency_score * 0.30

    sub_components = {
        "yield": round(yield_score, 3),
        "consistency": round(consistency_score, 3),
    }

    return ScoreResult(score=round(min(1.0, total), 3), sub_scores=sub_components)
