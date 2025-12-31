"""Score group orchestrators.

These modules orchestrate calculations and scorers to produce composite scores.
Each group combines multiple sub-components with configurable weights.
"""

from app.modules.scoring.domain.groups.dividends import calculate_dividends_score
from app.modules.scoring.domain.groups.fundamentals import calculate_fundamentals_score
from app.modules.scoring.domain.groups.long_term import calculate_long_term_score
from app.modules.scoring.domain.groups.opinion import calculate_opinion_score
from app.modules.scoring.domain.groups.opportunity import (
    calculate_opportunity_score,
    is_price_too_high,
)
from app.modules.scoring.domain.groups.short_term import calculate_short_term_score
from app.modules.scoring.domain.groups.technicals import calculate_technicals_score

__all__ = [
    "calculate_long_term_score",
    "calculate_fundamentals_score",
    "calculate_opportunity_score",
    "calculate_dividends_score",
    "calculate_short_term_score",
    "calculate_technicals_score",
    "calculate_opinion_score",
    "is_price_too_high",
]
