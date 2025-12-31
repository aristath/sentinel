"""Scorer functions for converting raw metrics to scores (0-1 range).

Scorer functions convert calculated metrics (CAGR, Sharpe, RSI, etc.) into
normalized scores (0.0 to 1.0) for use in composite scoring.
"""

from app.modules.scoring.domain.scorers.dividends import (
    score_dividend_consistency,
    score_dividend_yield,
)
from app.modules.scoring.domain.scorers.end_state import score_total_return
from app.modules.scoring.domain.scorers.long_term import (
    score_cagr,
    score_sharpe,
    score_sortino,
)
from app.modules.scoring.domain.scorers.opportunity import (
    score_below_52w_high,
    score_pe_ratio,
)
from app.modules.scoring.domain.scorers.short_term import score_drawdown, score_momentum
from app.modules.scoring.domain.scorers.technicals import (
    score_bollinger,
    score_ema_distance,
    score_rsi,
)

__all__ = [
    # Long-term scorers
    "score_cagr",
    "score_sharpe",
    "score_sortino",
    # Technical scorers
    "score_rsi",
    "score_bollinger",
    "score_ema_distance",
    # Opportunity scorers
    "score_below_52w_high",
    "score_pe_ratio",
    # Dividend scorers
    "score_dividend_yield",
    "score_dividend_consistency",
    # Short-term scorers
    "score_momentum",
    "score_drawdown",
    # End-state scorers
    "score_total_return",
]
