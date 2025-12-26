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

# Technical indicators - Caching layer
from app.domain.scoring.caching import (
    calculate_distance_from_ma,
    get_52_week_high,
    get_52_week_low,
    get_bollinger_bands,
    get_ema,
    get_max_drawdown,
    get_rsi,
    get_sharpe_ratio,
)

# Technical indicators - Pure calculation functions
from app.domain.scoring.calculations import (
    calculate_bollinger_bands,
    calculate_ema,
    calculate_max_drawdown,
    calculate_rsi,
    calculate_sharpe_ratio,
    calculate_volatility,
)

# Constants - All thresholds and weights
from app.domain.scoring.constants import (
    DEFAULT_MARKET_AVG_PE,
    DEFAULT_MAX_LOSS_THRESHOLD,
    DEFAULT_MIN_HOLD_DAYS,
    DEFAULT_SELL_COOLDOWN_DAYS,
    DEFAULT_TARGET_ANNUAL_RETURN,
    HIGH_DIVIDEND_THRESHOLD,
    MID_DIVIDEND_THRESHOLD,
    OPTIMAL_CAGR,
)

# Diversification scoring (renamed from allocation)
from app.domain.scoring.diversification import (
    calculate_diversification_score,
    calculate_portfolio_score,
    calculate_post_transaction_score,
)

# Dividend history analysis
from app.domain.scoring.dividend_history import (
    calculate_dividend_growth_rate,
    calculate_dividend_stability_score,
    get_dividend_analysis,
    has_big_dividend_cut,
    is_dividend_consistent,
)

# End-state scoring (for holistic planner)
from app.domain.scoring.end_state import (
    calculate_long_term_promise,
    calculate_portfolio_end_state_score,
    calculate_stability_score,
    calculate_total_return_score,
)

# Score group orchestrators
from app.domain.scoring.groups import (
    calculate_dividends_score,
    calculate_fundamentals_score,
    calculate_long_term_score,
    calculate_opinion_score,
    calculate_opportunity_score,
    calculate_short_term_score,
    calculate_technicals_score,
)

# Models - All dataclasses for scoring
from app.domain.scoring.models import (
    CalculatedStockScore,
    PortfolioContext,
    PortfolioScore,
    PrefetchedStockData,
    SellScore,
    TechnicalData,
)

# Scorer functions (exported for convenience)
from app.domain.scoring.scorers import (
    score_below_52w_high,
    score_bollinger,
    score_ema_distance,
    score_pe_ratio,
    score_rsi,
)

# Sell scoring
from app.domain.scoring.sell import (
    calculate_all_sell_scores,
    calculate_instability_score,
    calculate_portfolio_balance_score,
    calculate_sell_score,
    calculate_time_held_score,
    calculate_underperformance_score,
    check_sell_eligibility,
    determine_sell_quantity,
    get_sell_settings,
)

# Stock scorer (orchestrator)
from app.domain.scoring.stock_scorer import (
    calculate_stock_score,
    calculate_stock_score_from_prefetched,
)

# Windfall detection (profit-taking signals)
from app.domain.scoring.windfall import (
    calculate_excess_gain,
    calculate_windfall_score,
    get_windfall_recommendation,
    should_take_profits,
)

# === 8-GROUP SCORING MODULES ===


# === HOLISTIC PLANNING SCORING ===


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
    # Holistic planning - End state scoring
    "calculate_total_return_score",
    "calculate_long_term_promise",
    "calculate_stability_score",
    "calculate_portfolio_end_state_score",
    # Holistic planning - Windfall detection
    "calculate_excess_gain",
    "calculate_windfall_score",
    "should_take_profits",
    "get_windfall_recommendation",
    # Holistic planning - Dividend history
    "has_big_dividend_cut",
    "calculate_dividend_growth_rate",
    "calculate_dividend_stability_score",
    "get_dividend_analysis",
    "is_dividend_consistent",
]
