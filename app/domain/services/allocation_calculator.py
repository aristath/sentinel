"""Portfolio allocation and rebalancing logic."""

import logging
from typing import Optional

from app.config import settings
from app.domain.constants import (
    MIN_CONVICTION_MULTIPLIER,
    MAX_CONVICTION_MULTIPLIER,
    MIN_PRIORITY_MULTIPLIER,
    MAX_PRIORITY_MULTIPLIER,
    MIN_VOLATILITY_MULTIPLIER,
    MAX_POSITION_SIZE_MULTIPLIER,
    # Risk parity constants
    TARGET_PORTFOLIO_VOLATILITY,
    MIN_VOLATILITY_FOR_SIZING,
    MAX_VOL_WEIGHT,
    MIN_VOL_WEIGHT,
    DEFAULT_VOLATILITY,
)
from app.domain.models import StockPriority

logger = logging.getLogger(__name__)


def parse_industries(industry_str: str) -> list[str]:
    """
    Parse comma-separated industry string into list.

    Args:
        industry_str: Comma-separated industries (e.g., "Industrial, Defense")

    Returns:
        List of industry names, or empty list if None/empty
    """
    if not industry_str:
        return []
    return [ind.strip() for ind in industry_str.split(",") if ind.strip()]


def calculate_position_size(
    candidate: StockPriority,
    base_size: float,
    min_size: float,
    sortino_ratio: Optional[float] = None,
) -> float:
    """
    Calculate position size based on conviction, risk, and risk-adjusted returns.

    Args:
        candidate: Stock priority data
        base_size: Base investment amount per trade
        min_size: Minimum trade size
        sortino_ratio: Optional Sortino ratio for risk-adjusted sizing

    Returns:
        Adjusted position size (0.8x to 1.2x of base)
    """
    # Conviction multiplier based on stock score
    conviction_mult = MIN_CONVICTION_MULTIPLIER + (candidate.stock_score - 0.5) * 0.8
    conviction_mult = max(MIN_CONVICTION_MULTIPLIER, min(MAX_CONVICTION_MULTIPLIER, conviction_mult))

    # Priority multiplier based on combined priority
    priority_mult = MIN_PRIORITY_MULTIPLIER + (candidate.combined_priority / 3.0) * 0.2
    priority_mult = max(MIN_PRIORITY_MULTIPLIER, min(MAX_PRIORITY_MULTIPLIER, priority_mult))

    # Volatility penalty (if available)
    if candidate.volatility is not None:
        vol_mult = max(MIN_VOLATILITY_MULTIPLIER, 1.0 - (candidate.volatility - 0.15) * 0.5)
    else:
        vol_mult = 1.0

    # Risk-adjusted multiplier based on Sortino ratio (PyFolio enhancement)
    risk_mult = 1.0
    if sortino_ratio is not None:
        if sortino_ratio > 2.0:
            # Excellent risk-adjusted returns - increase size
            risk_mult = 1.15
        elif sortino_ratio > 1.5:
            # Good risk-adjusted returns - slight increase
            risk_mult = 1.05
        elif sortino_ratio < 0.5:
            # Poor risk-adjusted returns - reduce size
            risk_mult = 0.8
        elif sortino_ratio < 1.0:
            # Below average - slight reduction
            risk_mult = 0.9

    size = base_size * conviction_mult * priority_mult * vol_mult * risk_mult
    return max(min_size, min(size, base_size * MAX_POSITION_SIZE_MULTIPLIER))


def calculate_position_size_risk_parity(
    candidate: StockPriority,
    base_size: float,
    min_size: float,
) -> float:
    """
    Calculate position size using inverse-volatility weighting (risk parity).

    Based on MOSEK Portfolio Cookbook principles: size positions so each
    contributes roughly equal risk to the portfolio. Stock score provides
    a small ±10% adjustment on top.

    Args:
        candidate: Stock priority data (must have volatility)
        base_size: Base investment amount per trade
        min_size: Minimum trade size

    Returns:
        Adjusted position size (0.5x to 2.0x of base, ±10% for score)
    """
    # Use stock volatility, or default if unknown
    stock_vol = candidate.volatility if candidate.volatility else DEFAULT_VOLATILITY

    # Inverse volatility weight
    # If target is 15% and stock is 30%, position = base * (0.15/0.30) = 0.5x
    # If target is 15% and stock is 10%, position = base * (0.15/0.10) = 1.5x
    vol_weight = TARGET_PORTFOLIO_VOLATILITY / max(stock_vol, MIN_VOLATILITY_FOR_SIZING)
    vol_weight = max(MIN_VOL_WEIGHT, min(MAX_VOL_WEIGHT, vol_weight))

    # Small stock score adjustment (±10%)
    # Score 1.0 = +10%, Score 0.5 = -10%
    score_adj = 1.0 + (candidate.stock_score - 0.5) * 0.2
    score_adj = max(0.9, min(1.1, score_adj))

    size = base_size * vol_weight * score_adj
    return max(min_size, size)


def get_max_trades(cash: float) -> int:
    """
    Calculate maximum trades based on available cash.
    
    Args:
        cash: Available cash in EUR
        
    Returns:
        Maximum number of trades (0 to max_trades_per_cycle)
    """
    if cash < settings.min_trade_size:
        return 0
    return min(
        settings.max_trades_per_cycle,
        int(cash / settings.min_trade_size)
    )


# Removed calculate_rebalance_trades() - use RebalancingService.calculate_rebalance_trades() instead
# Removed execute_trades() - use TradeExecutionService.execute_trades() instead
