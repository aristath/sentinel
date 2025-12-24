"""
Scoring Domain - Stock and portfolio scoring calculations.

This module provides all scoring functionality for the trading system:
- Quality scoring (long-term value assessment)
- Opportunity scoring (buy-the-dip signals)
- Analyst scoring (recommendations and price targets)
- Allocation fit scoring (portfolio awareness)
- Sell scoring (when and how much to sell)
- Portfolio scoring (overall portfolio health)

Usage:
    from app.domain.scoring import (
        calculate_stock_score,
        calculate_quality_score,
        calculate_opportunity_score,
        calculate_analyst_score,
        calculate_allocation_fit_score,
        calculate_sell_score,
        calculate_all_sell_scores,
        calculate_portfolio_score,
    )

All scoring logic has been preserved exactly from the original
scorer.py and sell_scorer.py implementations.
"""

# Models - All dataclasses for scoring
from app.domain.scoring.models import (
    QualityScore,
    OpportunityScore,
    AnalystScore,
    AllocationFitScore,
    PortfolioContext,
    PortfolioScore,
    CalculatedStockScore,
    PrefetchedStockData,
    TechnicalData,
    SellScore,
)

# Constants - All thresholds and weights
from app.domain.scoring.constants import (
    # Quality constants
    OPTIMAL_CAGR,
    DEFAULT_TARGET_ANNUAL_RETURN,
    HIGH_DIVIDEND_THRESHOLD,
    MID_DIVIDEND_THRESHOLD,
    # Opportunity constants
    DEFAULT_MARKET_AVG_PE,
    # Combined score weights
    SCORE_WEIGHT_QUALITY,
    SCORE_WEIGHT_OPPORTUNITY,
    SCORE_WEIGHT_ANALYST,
    SCORE_WEIGHT_ALLOCATION_FIT,
    # Sell constants
    DEFAULT_MIN_HOLD_DAYS,
    DEFAULT_SELL_COOLDOWN_DAYS,
    DEFAULT_MAX_LOSS_THRESHOLD,
)

# Quality scoring
from app.domain.scoring.quality import (
    calculate_quality_score,
    score_total_return,
    calculate_dividend_bonus,
    calculate_cagr,
    calculate_consistency_score,
    calculate_financial_strength_score,
)

# Opportunity scoring
from app.domain.scoring.opportunity import (
    calculate_opportunity_score,
    score_below_52w_high,
    score_ema_distance,
    score_pe_ratio,
    score_rsi,
    score_bollinger,
)

# Analyst scoring
from app.domain.scoring.analyst import calculate_analyst_score

# Allocation fit scoring
from app.domain.scoring.allocation import (
    calculate_allocation_fit_score,
    calculate_portfolio_score,
    calculate_post_transaction_score,
)

# Sell scoring
from app.domain.scoring.sell import (
    calculate_sell_score,
    calculate_all_sell_scores,
    calculate_underperformance_score,
    calculate_time_held_score,
    calculate_portfolio_balance_score,
    calculate_instability_score,
    check_sell_eligibility,
    determine_sell_quantity,
    get_sell_settings,
)

# Stock scorer (orchestrator)
from app.domain.scoring.stock_scorer import (
    calculate_stock_score,
    calculate_stock_score_from_prefetched,
    create_default_quality_score,
    create_default_opportunity_score,
    create_default_analyst_score,
)

# Technical indicators
from app.domain.scoring.technical import (
    calculate_ema,
    calculate_rsi,
    calculate_bollinger_bands,
    calculate_bollinger_position,
    calculate_volatility,
    calculate_sharpe_ratio,
    calculate_max_drawdown,
    get_52_week_high,
    get_52_week_low,
    calculate_distance_from_ma,
)

__all__ = [
    # Models
    "QualityScore",
    "OpportunityScore",
    "AnalystScore",
    "AllocationFitScore",
    "PortfolioContext",
    "PortfolioScore",
    "CalculatedStockScore",
    "PrefetchedStockData",
    "TechnicalData",
    "SellScore",
    # Main scoring functions
    "calculate_stock_score",
    "calculate_stock_score_from_prefetched",
    "calculate_quality_score",
    "calculate_opportunity_score",
    "calculate_analyst_score",
    "calculate_allocation_fit_score",
    "calculate_sell_score",
    "calculate_all_sell_scores",
    "calculate_portfolio_score",
    "calculate_post_transaction_score",
    # Quality helpers
    "score_total_return",
    "calculate_dividend_bonus",
    "calculate_cagr",
    "calculate_consistency_score",
    "calculate_financial_strength_score",
    # Opportunity helpers
    "score_below_52w_high",
    "score_ema_distance",
    "score_pe_ratio",
    "score_rsi",
    "score_bollinger",
    # Sell helpers
    "calculate_underperformance_score",
    "calculate_time_held_score",
    "calculate_portfolio_balance_score",
    "calculate_instability_score",
    "check_sell_eligibility",
    "determine_sell_quantity",
    "get_sell_settings",
    # Technical indicators
    "calculate_ema",
    "calculate_rsi",
    "calculate_bollinger_bands",
    "calculate_bollinger_position",
    "calculate_volatility",
    "calculate_sharpe_ratio",
    "calculate_max_drawdown",
    "get_52_week_high",
    "get_52_week_low",
    "calculate_distance_from_ma",
    # Default score creators
    "create_default_quality_score",
    "create_default_opportunity_score",
    "create_default_analyst_score",
    # Constants
    "OPTIMAL_CAGR",
    "DEFAULT_TARGET_ANNUAL_RETURN",
    "DEFAULT_MARKET_AVG_PE",
    "HIGH_DIVIDEND_THRESHOLD",
    "MID_DIVIDEND_THRESHOLD",
    "SCORE_WEIGHT_QUALITY",
    "SCORE_WEIGHT_OPPORTUNITY",
    "SCORE_WEIGHT_ANALYST",
    "SCORE_WEIGHT_ALLOCATION_FIT",
    "DEFAULT_MIN_HOLD_DAYS",
    "DEFAULT_SELL_COOLDOWN_DAYS",
    "DEFAULT_MAX_LOSS_THRESHOLD",
]
