"""
Sell Score - When and how much to sell.

This module implements a 4-component weighted scoring model for SELL decisions:
- Underperformance Score (40%): How poorly security performed vs target (8-15% annual)
- Time Held Score (20%): Longer hold with underperformance = higher sell priority
- Portfolio Balance Score (20%): Overweight positions score higher
- Instability Score (20%): Detect potential bubbles and unsustainable gains

Hard Blocks (NEVER sell if any apply):
- allow_sell=false
- Loss >20%
- Held <3 months
- Last sold <6 months ago
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from app.modules.scoring.domain.constants import (
    DEFAULT_MAX_LOSS_THRESHOLD,
    DEFAULT_MIN_HOLD_DAYS,
    DEFAULT_MIN_SELL_VALUE_EUR,
    DEFAULT_SELL_COOLDOWN_DAYS,
)
from app.modules.scoring.domain.models import SellScore, TechnicalData

# Fixed sell weights - no longer configurable via settings
# The portfolio optimizer now handles sell decisions via target weight gaps.
# These weights are used for sell score calculation when the heuristic path is used.
SELL_WEIGHTS = {
    "underperformance": 0.35,  # Return vs target
    "time_held": 0.18,  # Position age
    "portfolio_balance": 0.18,  # Overweight detection
    "instability": 0.14,  # Bubble/volatility
    "drawdown": 0.15,  # Current drawdown from PyFolio
}

from app.modules.scoring.domain.groups.sell import (  # noqa: E402
    calculate_instability_score,
    calculate_portfolio_balance_score,
    calculate_time_held_score,
    calculate_underperformance_score,
    check_sell_eligibility,
    determine_sell_quantity,
)

logger = logging.getLogger(__name__)


async def _calculate_drawdown_score(symbol: str) -> float:
    """Calculate drawdown score based on position drawdown severity and duration."""
    try:
        from datetime import datetime, timedelta

        from app.modules.analytics.domain import get_position_drawdown

        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

        drawdown_data = await get_position_drawdown(symbol, start_date, end_date)

        current_dd = drawdown_data.get("current_drawdown", 0) or 0
        days_in_dd = drawdown_data.get("days_in_drawdown", 0) or 0

        if current_dd < -0.25:  # >25% drawdown
            return 1.0
        elif current_dd < -0.15:  # >15% drawdown
            if days_in_dd and days_in_dd > 180:  # 6+ months
                return 0.9  # Extended deep drawdown
            elif days_in_dd and days_in_dd > 90:  # 3+ months
                return 0.7
            else:
                return 0.5
        elif current_dd < -0.10:  # >10% drawdown
            return 0.3
        else:
            return 0.1  # Minimal drawdown
    except Exception as e:
        logger.debug(f"Could not calculate drawdown for {symbol}: {e}")
        return 0.3  # Neutral on error


def _normalize_sell_weights(weights: Optional[Dict[str, float]]) -> Dict[str, float]:
    """Normalize sell score weights so they sum to 1.0."""
    if weights is None:
        return SELL_WEIGHTS

    sell_groups = [
        "underperformance",
        "time_held",
        "portfolio_balance",
        "instability",
        "drawdown",
    ]
    weight_sum = sum(weights.get(g, SELL_WEIGHTS[g]) for g in sell_groups)
    if weight_sum > 0:
        return {g: weights.get(g, SELL_WEIGHTS[g]) / weight_sum for g in sell_groups}
    else:
        return SELL_WEIGHTS


def _calculate_total_sell_score(
    underperformance_score: float,
    time_held_score: float,
    portfolio_balance_score: float,
    instability_score: float,
    drawdown_score: float,
    normalized_weights: Dict[str, float],
) -> float:
    """Calculate total sell score from component scores and weights."""
    return (
        (underperformance_score * normalized_weights["underperformance"])
        + (time_held_score * normalized_weights["time_held"])
        + (portfolio_balance_score * normalized_weights["portfolio_balance"])
        + (instability_score * normalized_weights["instability"])
        + (drawdown_score * normalized_weights["drawdown"])
    )


async def calculate_sell_score(
    symbol: str,
    quantity: float,
    avg_price: float,
    current_price: float,
    min_lot: int,
    allow_sell: bool,
    first_bought_at: Optional[str],
    last_sold_at: Optional[str],
    country: str,
    industry: str,
    total_portfolio_value: float,
    country_allocations: Dict[str, float],
    ind_allocations: Dict[str, float],
    technical_data: Optional[TechnicalData] = None,
    settings: Optional[Dict] = None,
    weights: Optional[Dict[str, float]] = None,
) -> SellScore:
    """
    Calculate complete sell score for a position.

    Args:
        symbol: Security symbol
        quantity: Current position quantity
        avg_price: Average purchase price
        current_price: Current market price
        min_lot: Minimum lot size for this security
        allow_sell: Whether selling is enabled for this security
        first_bought_at: When position was first opened
        last_sold_at: When position was last sold (for cooldown)
        country: Security's country (e.g., "United States", "Germany")
        industry: Security's industry (comma-separated if multiple)
        total_portfolio_value: Total portfolio value in EUR
        country_allocations: Current country allocation percentages
        ind_allocations: Current industry allocation percentages
        technical_data: Technical indicators for instability detection
        settings: Optional settings dict for thresholds
        weights: Optional sell score weights (loaded from settings)

    Returns:
        SellScore with all components and recommendations
    """
    # Extract settings with defaults
    settings = settings or {}
    min_hold_days = settings.get("min_hold_days", DEFAULT_MIN_HOLD_DAYS)
    sell_cooldown_days = settings.get("sell_cooldown_days", DEFAULT_SELL_COOLDOWN_DAYS)
    max_loss_threshold = settings.get("max_loss_threshold", DEFAULT_MAX_LOSS_THRESHOLD)
    min_sell_value = settings.get("min_sell_value", DEFAULT_MIN_SELL_VALUE_EUR)

    # Calculate position value
    position_value = quantity * current_price

    # Calculate profit percentage
    profit_pct = (current_price - avg_price) / avg_price if avg_price > 0 else 0

    # Calculate last transaction date (most recent of buy or sell)
    last_transaction_at = None
    if first_bought_at and last_sold_at:
        # Compare dates to find the most recent
        from app.shared.utils import safe_parse_datetime_string

        buy_date = safe_parse_datetime_string(first_bought_at)
        sell_date = safe_parse_datetime_string(last_sold_at)
        if buy_date and sell_date:
            last_transaction_at = (
                first_bought_at if buy_date > sell_date else last_sold_at
            )
        elif buy_date:
            last_transaction_at = first_bought_at
        elif sell_date:
            last_transaction_at = last_sold_at
    elif first_bought_at:
        last_transaction_at = first_bought_at
    elif last_sold_at:
        last_transaction_at = last_sold_at

    # Check eligibility (hard blocks)
    eligible, block_reason = check_sell_eligibility(
        allow_sell,
        profit_pct,
        last_transaction_at,
        max_loss_threshold=max_loss_threshold,
        min_hold_days=min_hold_days,
        sell_cooldown_days=sell_cooldown_days,
    )

    # Calculate time held (for scoring purposes, uses first_bought_at)
    time_held_score, days_held = calculate_time_held_score(
        first_bought_at, min_hold_days=min_hold_days
    )

    # Additional eligibility check: if last transaction was recent, block based on minimum hold
    if last_transaction_at:
        from app.shared.utils import safe_parse_datetime_string

        transaction_date = safe_parse_datetime_string(last_transaction_at)
        if transaction_date:
            days_since_transaction = (datetime.now() - transaction_date).days
            if days_since_transaction < min_hold_days:
                eligible = False
                block_reason = (
                    block_reason
                    or f"Last transaction {days_since_transaction} days ago (min {min_hold_days})"
                )

    if not eligible:
        return SellScore(
            symbol=symbol,
            eligible=False,
            block_reason=block_reason,
            underperformance_score=0,
            time_held_score=0,
            portfolio_balance_score=0,
            instability_score=0,
            total_score=0,
            suggested_sell_pct=0,
            suggested_sell_quantity=0,
            suggested_sell_value=0,
            profit_pct=profit_pct,
            days_held=days_held,
        )

    # Calculate component scores
    underperformance_score, _ = calculate_underperformance_score(
        current_price, avg_price, days_held, max_loss_threshold=max_loss_threshold
    )

    # If underperformance score is 0 (big loss), block the sell
    if underperformance_score == 0.0 and profit_pct < max_loss_threshold:
        return SellScore(
            symbol=symbol,
            eligible=False,
            block_reason=f"Loss {profit_pct*100:.1f}% exceeds {max_loss_threshold*100:.0f}% threshold",
            underperformance_score=0,
            time_held_score=time_held_score,
            portfolio_balance_score=0,
            instability_score=0,
            total_score=0,
            suggested_sell_pct=0,
            suggested_sell_quantity=0,
            suggested_sell_value=0,
            profit_pct=profit_pct,
            days_held=days_held,
        )

    portfolio_balance_score = calculate_portfolio_balance_score(
        position_value,
        total_portfolio_value,
        country,
        industry,
        country_allocations,
        ind_allocations,
    )

    # Calculate instability score using technical data
    if technical_data:
        instability_score = calculate_instability_score(
            profit_pct=profit_pct,
            days_held=days_held,
            current_volatility=technical_data.current_volatility,
            historical_volatility=technical_data.historical_volatility,
            distance_from_ma_200=technical_data.distance_from_ma_200,
        )
    else:
        # No technical data - use neutral instability score
        instability_score = 0.3

    drawdown_score = await _calculate_drawdown_score(symbol)
    normalized_weights = _normalize_sell_weights(weights)

    total_score = _calculate_total_sell_score(
        underperformance_score,
        time_held_score,
        portfolio_balance_score,
        instability_score,
        drawdown_score,
        normalized_weights,
    )

    # Determine sell quantity
    sell_quantity, sell_pct = determine_sell_quantity(
        total_score, quantity, min_lot, current_price, min_sell_value=min_sell_value
    )
    sell_value = sell_quantity * current_price

    return SellScore(
        symbol=symbol,
        eligible=sell_quantity > 0,
        block_reason=None if sell_quantity > 0 else "Below minimum sell value",
        underperformance_score=round(underperformance_score, 3),
        time_held_score=round(time_held_score, 3),
        portfolio_balance_score=round(portfolio_balance_score, 3),
        instability_score=round(instability_score, 3),
        total_score=round(total_score, 3),
        suggested_sell_pct=round(sell_pct, 3),
        suggested_sell_quantity=sell_quantity,
        suggested_sell_value=round(sell_value, 2),
        profit_pct=round(profit_pct, 4),
        days_held=days_held,
    )


async def get_sell_settings() -> dict:
    """Load sell-related settings from database, with defaults fallback."""
    from app.repositories import SettingsRepository

    settings_repo = SettingsRepository()
    return {
        "min_hold_days": await settings_repo.get_int(
            "min_hold_days", DEFAULT_MIN_HOLD_DAYS
        ),
        "sell_cooldown_days": await settings_repo.get_int(
            "sell_cooldown_days", DEFAULT_SELL_COOLDOWN_DAYS
        ),
        "max_loss_threshold": await settings_repo.get_float(
            "max_loss_threshold", DEFAULT_MAX_LOSS_THRESHOLD
        ),
        "min_sell_value": await settings_repo.get_float(
            "min_sell_value", DEFAULT_MIN_SELL_VALUE_EUR
        ),
    }


async def calculate_all_sell_scores(
    positions: List[dict],
    total_portfolio_value: float,
    country_allocations: Dict[str, float],
    ind_allocations: Dict[str, float],
    technical_data: Optional[Dict[str, TechnicalData]] = None,
    settings: Optional[Dict] = None,
    weights: Optional[Dict[str, float]] = None,
) -> List[SellScore]:
    """
    Calculate sell scores for all positions.

    Args:
        positions: List of position dicts with security info (from get_with_stock_info)
        total_portfolio_value: Total portfolio value in EUR
        country_allocations: Current country allocation percentages
        ind_allocations: Current industry allocation percentages
        technical_data: Dict mapping symbol to TechnicalData for instability detection
        settings: Optional settings dict with min_hold_days, sell_cooldown_days, etc.
        weights: Optional sell score weights (loaded from settings)

    Returns:
        List of SellScore objects, sorted by total_score descending
    """
    # Always use fixed weights - the optimizer handles portfolio-level decisions
    if weights is None:
        weights = SELL_WEIGHTS

    scores = []
    technical_data = technical_data or {}

    for pos in positions:
        symbol = pos["symbol"]
        score = await calculate_sell_score(
            symbol=symbol,
            quantity=pos["quantity"],
            avg_price=pos["avg_price"],
            current_price=pos["current_price"] or pos["avg_price"],
            min_lot=pos.get("min_lot", 1),
            allow_sell=bool(pos.get("allow_sell", False)),
            first_bought_at=pos.get("first_bought_at"),
            last_sold_at=pos.get("last_sold_at"),
            country=pos.get("country", ""),
            industry=pos.get("industry", ""),
            total_portfolio_value=total_portfolio_value,
            country_allocations=country_allocations,
            ind_allocations=ind_allocations,
            technical_data=technical_data.get(symbol),
            settings=settings,
            weights=weights,
        )
        scores.append(score)

    # Sort by total_score descending (highest sell priority first)
    scores.sort(key=lambda s: s.total_score, reverse=True)

    return scores
