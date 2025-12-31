"""
Scoring Constants - All thresholds and weights for scoring calculations.

These values have been carefully tuned for long-term value investing.
DO NOT change without understanding the impact on portfolio behavior.
"""

# =============================================================================
# Quality Score Constants
# =============================================================================

# Bell curve target for total return (CAGR + dividend)
# 11% is optimal for ~€1M retirement goal over 20 years
OPTIMAL_CAGR = 0.11
DEFAULT_TARGET_ANNUAL_RETURN = 0.11

# Bell curve shape parameters (asymmetric Gaussian)
BELL_CURVE_SIGMA_LEFT = 0.06  # Steeper rise (0% to peak)
BELL_CURVE_SIGMA_RIGHT = 0.10  # Gentler fall (peak to high growth)
BELL_CURVE_FLOOR = 0.15  # Minimum score for any positive return

# Dividend thresholds for DRIP priority bonus
HIGH_DIVIDEND_THRESHOLD = 0.06  # 6%+ yield gets max bonus (+0.10)
MID_DIVIDEND_THRESHOLD = 0.03  # 3%+ yield gets mid bonus (+0.07)
LOW_DIVIDEND_BONUS = 0.03  # Any dividend gets small bonus
MID_DIVIDEND_BONUS = 0.07
HIGH_DIVIDEND_BONUS = 0.10

# Dividend reinvestment strategy threshold
HIGH_DIVIDEND_REINVESTMENT_THRESHOLD = 0.03  # 3%+ yield: reinvest in same stock

# Quality score component weights (must sum to 1.0)
QUALITY_WEIGHT_TOTAL_RETURN = 0.40
QUALITY_WEIGHT_CONSISTENCY = 0.20
QUALITY_WEIGHT_FINANCIAL_STRENGTH = 0.20
QUALITY_WEIGHT_SHARPE = 0.10
QUALITY_WEIGHT_MAX_DRAWDOWN = 0.10

# Sharpe ratio thresholds
SHARPE_EXCELLENT = 2.0  # Score = 1.0
SHARPE_GOOD = 1.0  # Score = 0.7
SHARPE_OK = 0.5  # Score = 0.4

# Max drawdown thresholds (as positive percentages)
DRAWDOWN_EXCELLENT = 0.10  # <10% drawdown = 1.0
DRAWDOWN_GOOD = 0.20  # <20% drawdown = 0.8+
DRAWDOWN_OK = 0.30  # <30% drawdown = 0.6+
DRAWDOWN_POOR = 0.50  # <50% drawdown = 0.2+

# =============================================================================
# Opportunity Score Constants
# =============================================================================

# Market average P/E for comparison
DEFAULT_MARKET_AVG_PE = 22

# Forward-looking market indicator thresholds and adjustments
# VIX thresholds (volatility/fear index)
VIX_LOW = 15.0  # Low volatility = optimistic
VIX_NORMAL = 20.0  # Normal volatility
VIX_HIGH = 30.0  # High volatility = pessimistic
VIX_ADJUSTMENT_MAX = 0.10  # Max ±10% adjustment for VIX

# Yield curve slope thresholds
YIELD_CURVE_NORMAL = 0.01  # 1%+ slope = normal (expansionary)
YIELD_CURVE_FLAT = 0.0  # Flat curve
YIELD_CURVE_INVERTED = -0.01  # Negative = inverted (recession signal)
YIELD_CURVE_ADJUSTMENT_MAX = 0.15  # Max ±15% adjustment for yield curve

# Market P/E thresholds (vs historical average of 22)
PE_CHEAP = 18.0  # Below average = cheap market
PE_FAIR = 22.0  # At average = fair value
PE_EXPENSIVE = 26.0  # Above average = expensive market
PE_ADJUSTMENT_MAX = 0.10  # Max ±10% adjustment for P/E

# 52-week high thresholds
BELOW_HIGH_EXCELLENT = 0.30  # 30%+ below = 1.0
BELOW_HIGH_GOOD = 0.20  # 20-30% below = 0.8-1.0
BELOW_HIGH_OK = 0.10  # 10-20% below = 0.5-0.8

# EMA distance thresholds
EMA_VERY_BELOW = -0.10  # 10%+ below EMA = 1.0
EMA_BELOW = -0.05  # 5-10% below = 0.7-1.0
EMA_VERY_ABOVE = 0.10  # 10%+ above = 0.2

# RSI thresholds
RSI_OVERSOLD = 30  # Below = 1.0 (buy signal)
RSI_OVERBOUGHT = 70  # Above = 0.0 (sell signal)

# Opportunity score component weights (must sum to 1.0)
OPPORTUNITY_WEIGHT_52W_HIGH = 0.30
OPPORTUNITY_WEIGHT_EMA = 0.25
OPPORTUNITY_WEIGHT_PE = 0.25
OPPORTUNITY_WEIGHT_RSI = 0.10
OPPORTUNITY_WEIGHT_BOLLINGER = 0.10

# =============================================================================
# Combined Score Weights
# =============================================================================

# Final score weights for BUY decisions (must sum to 1.0)
SCORE_WEIGHT_QUALITY = 0.35
SCORE_WEIGHT_OPPORTUNITY = 0.35
SCORE_WEIGHT_ANALYST = 0.05  # Reduced from 0.15 - tiebreaker only
SCORE_WEIGHT_ALLOCATION_FIT = 0.25  # Increased from 0.15 - prioritize diversification

# Without allocation fit, these 3 sum to 0.75, normalized to 1.0
SCORE_WEIGHT_BASE = 0.75  # Quality + Opportunity + Analyst

# =============================================================================
# Allocation Fit Constants
# =============================================================================

# Allocation fit component weights (must sum to 1.0)
ALLOCATION_WEIGHT_GEOGRAPHY = 0.40
ALLOCATION_WEIGHT_INDUSTRY = 0.30
ALLOCATION_WEIGHT_AVERAGING_DOWN = 0.30

# Averaging down boost for positions underwater
MAX_COST_BASIS_BOOST = 0.40  # Max boost at 20% loss
COST_BASIS_BOOST_THRESHOLD = 0.20  # No boost beyond 20% loss

# Concentration limits
CONCENTRATION_HIGH = 0.10  # >10% = reduce enthusiasm
CONCENTRATION_MED = 0.05  # 5-10% = slight reduction

# =============================================================================
# Sell Score Constants
# =============================================================================

# Hard blocks (NEVER sell if any apply)
DEFAULT_MIN_HOLD_DAYS = 90  # 3 months minimum hold
DEFAULT_SELL_COOLDOWN_DAYS = 180  # 6 months between sells
DEFAULT_MAX_LOSS_THRESHOLD = -0.20  # Never sell if down more than 20%
DEFAULT_MIN_SELL_VALUE_EUR = 100  # Minimum sell value in EUR

# Sell quantity limits
MIN_SELL_PCT = 0.10  # Minimum 10% of position
MAX_SELL_PCT = 0.50  # Maximum 50% of position

# Target annual return range (ideal performance)
TARGET_RETURN_MIN = 0.08  # 8%
TARGET_RETURN_MAX = 0.15  # 15%

# Sell score component weights (must sum to 1.0)
SELL_WEIGHT_UNDERPERFORMANCE = 0.35  # Primary factor
SELL_WEIGHT_TIME_HELD = 0.18
SELL_WEIGHT_PORTFOLIO_BALANCE = 0.18
SELL_WEIGHT_INSTABILITY = 0.14
SELL_WEIGHT_DRAWDOWN = 0.15  # PyFolio-based drawdown analysis

# Instability detection thresholds
INSTABILITY_RATE_VERY_HOT = 0.50  # >50% annualized = 1.0
INSTABILITY_RATE_HOT = 0.30  # >30% = 0.7
INSTABILITY_RATE_WARM = 0.20  # >20% = 0.4

VOLATILITY_SPIKE_HIGH = 2.0  # Vol doubled = 1.0
VOLATILITY_SPIKE_MED = 1.5  # Vol up 50% = 0.7
VOLATILITY_SPIKE_LOW = 1.2  # Vol up 20% = 0.4

VALUATION_STRETCH_HIGH = 0.30  # >30% above MA = 1.0
VALUATION_STRETCH_MED = 0.20  # >20% = 0.7
VALUATION_STRETCH_LOW = 0.10  # >10% = 0.4

# =============================================================================
# Technical Indicator Parameters
# =============================================================================

TRADING_DAYS_PER_YEAR = 252
EMA_LENGTH = 200
RSI_LENGTH = 14
BOLLINGER_LENGTH = 20
BOLLINGER_STD = 2

# Minimum data requirements
MIN_DAYS_FOR_OPPORTUNITY = 50
MIN_MONTHS_FOR_CAGR = 12
MIN_DAYS_FOR_VOLATILITY = 30

# =============================================================================
# Metric TTL Configuration (for calculations.db cache)
# =============================================================================

# TTL in seconds for each metric type
# These determine how long calculated metrics are cached before recalculation
METRIC_TTL = {
    # Real-time (24 hours) - Changes daily after market close
    "RSI_14": 86400,
    "RSI_30": 86400,
    "EMA_50": 86400,
    "EMA_200": 86400,
    "BB_LOWER": 86400,
    "BB_MIDDLE": 86400,
    "BB_UPPER": 86400,
    "BB_POSITION": 86400,
    "DISTANCE_FROM_EMA_200": 86400,
    "MOMENTUM_30D": 86400,
    "MOMENTUM_90D": 86400,
    "MAX_DRAWDOWN": 86400,
    "CURRENT_DRAWDOWN": 86400,
    "VOLATILITY_30D": 86400,
    "VOLATILITY_ANNUAL": 86400,
    "HIGH_52W": 86400,
    "LOW_52W": 86400,
    "DISTANCE_FROM_52W_HIGH": 86400,
    # Daily (7 days) - Stable calculation, but recalculated daily
    "SHARPE": 604800,
    "SORTINO": 604800,
    # Weekly (7 days) - Slow-changing historical metrics
    "CAGR_5Y": 604800,
    "CAGR_10Y": 604800,
    "CONSISTENCY_SCORE": 604800,
    # Quarterly (30 days) - Fundamentals update with earnings
    "PE_RATIO": 2592000,
    "FORWARD_PE": 2592000,
    "PROFIT_MARGIN": 2592000,
    "DEBT_TO_EQUITY": 2592000,
    "CURRENT_RATIO": 2592000,
    "FINANCIAL_STRENGTH": 2592000,
    "DIVIDEND_YIELD": 2592000,
    "PAYOUT_RATIO": 2592000,
    "DIVIDEND_CONSISTENCY": 2592000,
    # On-demand (24 hours) - Analyst data fetched when needed
    "ANALYST_RECOMMENDATION": 86400,
    "PRICE_TARGET_UPSIDE": 86400,
    # Holistic planning metrics
    "TOTAL_RETURN": 604800,  # 7 days - CAGR + dividend yield
    "LONG_TERM_PROMISE": 604800,  # 7 days - Composite promise score
    "STABILITY_SCORE": 86400,  # 24 hours - Volatility-based
    "EXCESS_GAIN": 86400,  # 24 hours - Windfall detection
    "WINDFALL_SCORE": 86400,  # 24 hours - Profit-taking signal
}

# Default TTL for unknown metrics (24 hours)
DEFAULT_METRIC_TTL = 86400

# =============================================================================
# Holistic Planning Constants
# =============================================================================

# Windfall detection thresholds
WINDFALL_EXCESS_HIGH = 0.50  # 50%+ above expected = high windfall
WINDFALL_EXCESS_MEDIUM = 0.25  # 25-50% above expected = medium windfall
WINDFALL_SELL_PCT_HIGH = 0.40  # Sell 40% on high windfall
WINDFALL_SELL_PCT_MEDIUM = 0.20  # Sell 20% on medium windfall
CONSISTENT_DOUBLE_SELL_PCT = 0.30  # Sell 30% on consistent doubler

# Dividend cut threshold
DIVIDEND_CUT_THRESHOLD = 0.20  # 20% YoY cut = "big cut"

# =============================================================================
# Portfolio Optimization Constants
# =============================================================================

# Target return for Mean-Variance optimization
OPTIMIZER_TARGET_RETURN = 0.11  # 11% annual target

# Expected returns calculation weights
EXPECTED_RETURNS_CAGR_WEIGHT = 0.70  # 70% historical CAGR
EXPECTED_RETURNS_SCORE_WEIGHT = 0.30  # 30% score-adjusted

# Covariance matrix parameters
COVARIANCE_LOOKBACK_DAYS = 365  # 1 year of daily returns
COVARIANCE_MIN_HISTORY = 60  # Minimum days needed for covariance

# Weight cutoffs
OPTIMIZER_WEIGHT_CUTOFF = 0.005  # Ignore weights below 0.5%
MAX_CONCENTRATION = 0.20  # Maximum 20% in any single stock

# Expected return bounds (clamp to reasonable range)
EXPECTED_RETURN_MIN = -0.10  # -10% floor
EXPECTED_RETURN_MAX = 0.30  # +30% ceiling

# Allocation tolerance bands for sector constraints
GEO_ALLOCATION_TOLERANCE = 0.10  # +/- 10% from target
IND_ALLOCATION_TOLERANCE = 0.15  # +/- 15% from target

# Hard concentration limits (safety guardrails)
MAX_COUNTRY_CONCENTRATION = 0.35  # 35% max per country
MAX_SECTOR_CONCENTRATION = 0.30  # 30% max per sector
MAX_POSITION_CONCENTRATION = (
    0.15  # 15% max per position (matches MAX_POSITION_PCT in domain/constants.py)
)

# Alert thresholds (80% of caps)
COUNTRY_ALERT_THRESHOLD = 0.28  # Alert at 28% (80% of 35%)
SECTOR_ALERT_THRESHOLD = 0.24  # Alert at 24% (80% of 30%)
POSITION_ALERT_THRESHOLD = 0.12  # Alert at 12% (80% of 15%)
