"""Portfolio allocation and rebalancing logic."""

import logging
from typing import Optional

from app.config import settings
from app.domain.constants import (
    DEFAULT_VOLATILITY,
    MAX_VOL_WEIGHT,
    MIN_VOL_WEIGHT,
    MIN_VOLATILITY_FOR_SIZING,
    REBALANCE_BAND_HIGH_PRIORITY,
    REBALANCE_BAND_MEDIUM,
    REBALANCE_BAND_SMALL,
    TARGET_PORTFOLIO_VOLATILITY,
)
from app.domain.models import SecurityPriority

logger = logging.getLogger(__name__)


def is_outside_rebalance_band(
    current_weight: float,
    target_weight: float,
    band_pct: Optional[float] = None,
    position_size_pct: Optional[float] = None,
) -> bool:
    """
    Check if a position has drifted enough from target to warrant rebalancing.

    Based on MOSEK Portfolio Cookbook principles: avoid frequent small trades
    by only rebalancing when positions drift significantly from targets.

    Uses tiered rebalancing bands based on position size:
    - High-priority positions (>10%): 5% band (tighter control)
    - Medium positions (5-10%): 7% band (current default)
    - Small positions (<5%): 10% band (allow more drift)

    Args:
        current_weight: Current allocation weight (0.0 to 1.0)
        target_weight: Target allocation weight (0.0 to 1.0)
        band_pct: Explicit deviation threshold (overrides tiered calculation)
        position_size_pct: Position size as percentage of portfolio (for tiered bands)

    Returns:
        True if position is outside the band and should be considered for rebalancing
    """
    # Use explicit band if provided
    if band_pct is not None:
        deviation = abs(current_weight - target_weight)
        return deviation > band_pct

    # Calculate tiered band based on position size
    if position_size_pct is not None:
        if position_size_pct > 0.10:  # >10% of portfolio
            band_pct = REBALANCE_BAND_HIGH_PRIORITY  # 5%
        elif position_size_pct >= 0.05:  # 5-10% of portfolio
            band_pct = REBALANCE_BAND_MEDIUM  # 7%
        else:  # <5% of portfolio
            band_pct = REBALANCE_BAND_SMALL  # 10%
    else:
        # Fallback to default if position size not provided
        # Use larger of current or target weight as proxy for position size
        position_size_pct = max(current_weight, target_weight)
        if position_size_pct > 0.10:
            band_pct = REBALANCE_BAND_HIGH_PRIORITY
        elif position_size_pct >= 0.05:
            band_pct = REBALANCE_BAND_MEDIUM
        else:
            band_pct = REBALANCE_BAND_SMALL

    deviation = abs(current_weight - target_weight)
    return deviation > band_pct


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
    candidate: SecurityPriority,
    base_size: float,
    min_size: float,
) -> float:
    """
    Calculate position size using inverse-volatility weighting (risk parity).

    Based on MOSEK Portfolio Cookbook principles: size positions so each
    contributes roughly equal risk to the portfolio. Security score provides
    a ±20% adjustment on top for conviction expression.

    Args:
        candidate: Security priority data (must have volatility)
        base_size: Base investment amount per trade
        min_size: Minimum trade size

    Returns:
        Adjusted position size (0.5x to 2.0x of base, ±20% for score)
    """
    # Use security volatility, or default if unknown
    stock_vol = candidate.volatility if candidate.volatility else DEFAULT_VOLATILITY

    # Inverse volatility weight
    # If target is 15% and security is 30%, position = base * (0.15/0.30) = 0.5x
    # If target is 15% and security is 10%, position = base * (0.15/0.10) = 1.5x
    vol_weight = TARGET_PORTFOLIO_VOLATILITY / max(stock_vol, MIN_VOLATILITY_FOR_SIZING)
    vol_weight = max(MIN_VOL_WEIGHT, min(MAX_VOL_WEIGHT, vol_weight))

    # Security score adjustment (±20% range for better conviction expression)
    # Score 1.0 = +20%, Score 0.5 = 0%, Score 0.0 = -20%
    score_adj = 1.0 + (candidate.security_score - 0.5) * 0.4
    score_adj = max(0.8, min(1.2, score_adj))

    size = base_size * vol_weight * score_adj
    return max(min_size, size)


def get_max_trades(cash: float, min_trade_amount: float = 250.0) -> int:
    """
    Calculate maximum trades based on available cash.

    Args:
        cash: Available cash in EUR
        min_trade_amount: Minimum trade amount (calculated from transaction costs)
                         Default 250 is based on €2 + 0.2% = 1% cost at €250

    Returns:
        Maximum number of trades (0 to max_trades_per_cycle)
    """
    if cash < min_trade_amount:
        return 0
    return min(settings.max_trades_per_cycle, int(cash / min_trade_amount))


# Removed calculate_rebalance_trades() - use RebalancingService.calculate_rebalance_trades() instead
# Removed execute_trades() - use TradeExecutionService.execute_trades() instead
