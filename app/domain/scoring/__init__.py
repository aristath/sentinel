"""
Scoring Domain - Stock and portfolio scoring calculations.

8-Group Buy Scoring Structure (configurable weights):
- Long-term Performance (20%): CAGR, Sortino, Sharpe
- Fundamentals (15%): Financial strength, Consistency
- Opportunity (15%): 52W high distance, P/E ratio
- Dividends (12%): Yield, Dividend consistency
- Short-term Performance (10%): Recent momentum, Drawdown
- Technicals (10%): RSI, Bollinger, EMA
- Opinion (10%): Analyst recommendations, Price targets
- Diversification (8%): Geography, Industry, Averaging

5-Group Sell Scoring Structure (configurable weights):
- Underperformance (35%): Return vs target
- Time Held (18%): Position age
- Portfolio Balance (18%): Overweight detection
- Instability (14%): Bubble/volatility signals
- Drawdown (15%): Current drawdown severity
"""

# Models - All dataclasses for scoring
from app.domain.scoring.models import (
    PortfolioContext,
    PortfolioScore,
    CalculatedStockScore,
    PrefetchedStockData,
    TechnicalData,
    SellScore,
)

# Constants - All thresholds and weights
from app.domain.scoring.constants import (
    OPTIMAL_CAGR,
    DEFAULT_TARGET_ANNUAL_RETURN,
    HIGH_DIVIDEND_THRESHOLD,
    MID_DIVIDEND_THRESHOLD,
    DEFAULT_MARKET_AVG_PE,
    DEFAULT_MIN_HOLD_DAYS,
    DEFAULT_SELL_COOLDOWN_DAYS,
    DEFAULT_MAX_LOSS_THRESHOLD,
)

# === NEW 8-GROUP SCORING MODULES ===

# Long-term Performance scoring
from app.domain.scoring.long_term import calculate_long_term_score

# Fundamentals scoring
from app.domain.scoring.fundamentals import calculate_fundamentals_score

# Opportunity scoring (refactored - 52W high + P/E only)
from app.domain.scoring.opportunity import (
    calculate_opportunity_score,
    score_below_52w_high,
    score_pe_ratio,
)

# Dividends scoring
from app.domain.scoring.dividends import calculate_dividends_score

# Short-term Performance scoring
from app.domain.scoring.short_term import calculate_short_term_score

# Technicals scoring (RSI, Bollinger, EMA)
from app.domain.scoring.technicals import (
    calculate_technicals_score,
    score_rsi,
    score_bollinger,
    score_ema_distance,
)

# Opinion scoring (renamed from analyst)
from app.domain.scoring.opinion import calculate_opinion_score

# Diversification scoring (renamed from allocation)
from app.domain.scoring.diversification import (
    calculate_diversification_score,
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
)

# Technical indicators
from app.domain.scoring.technical import (
    # Async functions (check cache first)
    get_ema,
    get_rsi,
    get_bollinger_bands,
    get_sharpe_ratio,
    get_max_drawdown,
    get_52_week_high,
    get_52_week_low,
    # Sync functions (internal use, or when cache not needed)
    calculate_ema,
    calculate_rsi,
    calculate_bollinger_bands,
    calculate_volatility,
    calculate_sharpe_ratio,
    calculate_max_drawdown,
    calculate_distance_from_ma,
)


__all__ = [
    # Models
    "PortfolioContext",
    "PortfolioScore",
    "CalculatedStockScore",
    "PrefetchedStockData",
    "TechnicalData",
    "SellScore",
    # Main scoring functions
    "calculate_stock_score",
    "calculate_stock_score_from_prefetched",
    "calculate_sell_score",
    "calculate_all_sell_scores",
    # 8-group scoring functions
    "calculate_long_term_score",
    "calculate_fundamentals_score",
    "calculate_opportunity_score",
    "calculate_dividends_score",
    "calculate_short_term_score",
    "calculate_technicals_score",
    "calculate_opinion_score",
    "calculate_diversification_score",
    "calculate_portfolio_score",
    "calculate_post_transaction_score",
    # Scoring helpers
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
    # Technical indicators (async - check cache first)
    "get_ema",
    "get_rsi",
    "get_bollinger_bands",
    "get_sharpe_ratio",
    "get_max_drawdown",
    "get_52_week_high",
    "get_52_week_low",
    # Technical indicators (sync - internal use)
    "calculate_ema",
    "calculate_rsi",
    "calculate_bollinger_bands",
    "calculate_volatility",
    "calculate_sharpe_ratio",
    "calculate_max_drawdown",
    "calculate_distance_from_ma",
    # Constants
    "OPTIMAL_CAGR",
    "DEFAULT_TARGET_ANNUAL_RETURN",
    "DEFAULT_MARKET_AVG_PE",
    "HIGH_DIVIDEND_THRESHOLD",
    "MID_DIVIDEND_THRESHOLD",
    "DEFAULT_MIN_HOLD_DAYS",
    "DEFAULT_SELL_COOLDOWN_DAYS",
    "DEFAULT_MAX_LOSS_THRESHOLD",
]
