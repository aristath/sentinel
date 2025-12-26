"""Sell scoring helper functions.

Pure functions for calculating individual sell score components.
These functions are used by the main sell scoring orchestrator.
"""

from datetime import datetime
from typing import Dict, Optional

from app.domain.scoring.constants import (
    DEFAULT_MAX_LOSS_THRESHOLD,
    DEFAULT_MIN_HOLD_DAYS,
    INSTABILITY_RATE_HOT,
    INSTABILITY_RATE_VERY_HOT,
    INSTABILITY_RATE_WARM,
    TARGET_RETURN_MAX,
    TARGET_RETURN_MIN,
    VALUATION_STRETCH_HIGH,
    VALUATION_STRETCH_LOW,
    VALUATION_STRETCH_MED,
    VOLATILITY_SPIKE_HIGH,
    VOLATILITY_SPIKE_LOW,
    VOLATILITY_SPIKE_MED,
)


def calculate_underperformance_score(
    current_price: float,
    avg_price: float,
    days_held: int,
    max_loss_threshold: float = DEFAULT_MAX_LOSS_THRESHOLD,
) -> tuple:
    """
    Calculate underperformance score based on annualized return vs target.

    Returns:
        (score, profit_pct) tuple
    """
    if avg_price <= 0 or days_held <= 0:
        return 0.5, 0.0

    # Calculate profit percentage
    profit_pct = (current_price - avg_price) / avg_price

    # Calculate annualized return (CAGR)
    years_held = days_held / 365.0
    if years_held < 0.25:  # Less than 3 months - not enough data
        annualized_return = profit_pct  # Use simple return
    else:
        try:
            annualized_return = ((current_price / avg_price) ** (1 / years_held)) - 1
        except (ValueError, ZeroDivisionError):
            annualized_return = profit_pct

    # Score based on return vs target (8-15% annual ideal)
    # Higher score = more reason to sell
    if profit_pct < max_loss_threshold:
        # BLOCKED - loss too big
        return 0.0, profit_pct
    elif annualized_return < -0.05:
        # Loss of -5% to -20%: high sell priority (cut losses)
        return 0.9, profit_pct
    elif annualized_return < 0:
        # Small loss (-5% to 0%): stagnant, free up capital
        return 0.7, profit_pct
    elif annualized_return < TARGET_RETURN_MIN:
        # 0-8%: underperforming target
        return 0.5, profit_pct
    elif annualized_return <= TARGET_RETURN_MAX:
        # 8-15%: ideal range, don't sell
        return 0.1, profit_pct
    else:
        # >15%: exceeding target, consider taking profits
        return 0.3, profit_pct


def calculate_time_held_score(
    first_bought_at: Optional[str], min_hold_days: int = DEFAULT_MIN_HOLD_DAYS
) -> tuple:
    """
    Calculate time held score. Longer hold with underperformance = higher sell priority.

    Returns:
        (score, days_held) tuple
    """
    if not first_bought_at:
        # Unknown hold time - assume long enough
        return 0.6, 365

    try:
        bought_date = datetime.fromisoformat(first_bought_at.replace("Z", "+00:00"))
        if bought_date.tzinfo:
            bought_date = bought_date.replace(tzinfo=None)
        days_held = (datetime.now() - bought_date).days
    except (ValueError, TypeError):
        return 0.6, 365

    if days_held < min_hold_days:
        # BLOCKED - held less than 3 months
        return 0.0, days_held
    elif days_held < 180:
        # 3-6 months
        return 0.3, days_held
    elif days_held < 365:
        # 6-12 months
        return 0.6, days_held
    elif days_held < 730:
        # 12-24 months
        return 0.8, days_held
    else:
        # 24+ months - if still underperforming, time to cut
        return 1.0, days_held


def calculate_portfolio_balance_score(
    position_value: float,
    total_portfolio_value: float,
    geography: str,
    industry: str,
    geo_allocations: Dict[str, float],
    ind_allocations: Dict[str, float],
) -> float:
    """
    Calculate portfolio balance score. Overweight positions score higher.

    Args:
        position_value: Current position value in EUR
        total_portfolio_value: Total portfolio value in EUR
        geography: Stock's geography (EU, US, ASIA)
        industry: Stock's industry
        geo_allocations: Current geography allocation percentages
        ind_allocations: Current industry allocation percentages
    """
    if total_portfolio_value <= 0:
        return 0.5

    score = 0.0

    # Geography overweight (50% of this component)
    geo_current = geo_allocations.get(geography, 0)
    # Higher allocation = more reason to sell from this region
    geo_score = min(1.0, geo_current / 0.5)  # Normalize to ~1.0 at 50% allocation
    score += geo_score * 0.5

    # Industry overweight (30% of this component)
    # Handle multiple industries
    if industry:
        industries = [i.strip() for i in industry.split(",")]
        ind_scores = []
        for ind in industries:
            ind_current = ind_allocations.get(ind, 0)
            ind_scores.append(min(1.0, ind_current / 0.3))  # Normalize to ~1.0 at 30%
        ind_score = sum(ind_scores) / len(ind_scores) if ind_scores else 0.5
    else:
        ind_score = 0.5
    score += ind_score * 0.3

    # Concentration risk (20% of this component)
    position_pct = position_value / total_portfolio_value
    if position_pct > 0.10:
        # >10% in one position - high concentration
        conc_score = min(1.0, position_pct / 0.15)
    else:
        conc_score = position_pct / 0.10
    score += conc_score * 0.2

    return score


def _calculate_rate_of_gain_score(profit_pct: float, days_held: int) -> float:
    """Calculate rate of gain component score (40% weight)."""
    if days_held <= 30:
        return 0.5  # Too early to tell

    years = days_held / 365.0
    try:
        annualized = (
            ((1 + profit_pct) ** (1 / years)) - 1 if years > 0 else profit_pct
        )
    except (ValueError, OverflowError):
        annualized = profit_pct

    if annualized > INSTABILITY_RATE_VERY_HOT:  # >50% annualized = very hot
        return 1.0
    elif annualized > INSTABILITY_RATE_HOT:  # >30% annualized = hot
        return 0.7
    elif annualized > INSTABILITY_RATE_WARM:  # >20% annualized = warm
        return 0.4
    else:
        return 0.1  # Sustainable pace


def _calculate_volatility_spike_score(
    current_volatility: float, historical_volatility: float
) -> float:
    """Calculate volatility spike component score (30% weight)."""
    if historical_volatility <= 0:
        return 0.3  # No historical data - neutral

    vol_ratio = current_volatility / historical_volatility
    if vol_ratio > VOLATILITY_SPIKE_HIGH:  # Vol doubled
        return 1.0
    elif vol_ratio > VOLATILITY_SPIKE_MED:  # Vol up 50%
        return 0.7
    elif vol_ratio > VOLATILITY_SPIKE_LOW:  # Vol up 20%
        return 0.4
    else:
        return 0.1  # Normal volatility


def _calculate_valuation_stretch_score(distance_from_ma_200: float) -> float:
    """Calculate valuation stretch component score (30% weight)."""
    if distance_from_ma_200 > VALUATION_STRETCH_HIGH:  # >30% above MA
        return 1.0
    elif distance_from_ma_200 > VALUATION_STRETCH_MED:  # >20% above MA
        return 0.7
    elif distance_from_ma_200 > VALUATION_STRETCH_LOW:  # >10% above MA
        return 0.4
    else:
        return 0.1  # Near or below MA


def _apply_profit_floor(score: float, profit_pct: float) -> float:
    """Apply floor for extreme profits (safety net)."""
    if profit_pct > 1.0:  # >100% gain
        return max(score, 0.2)
    elif profit_pct > 0.75:  # >75% gain
        return max(score, 0.1)
    return score


def calculate_instability_score(
    profit_pct: float,
    days_held: int,
    current_volatility: float,
    historical_volatility: float,
    distance_from_ma_200: float,
) -> float:
    """
    Detect potential instability/bubble conditions.
    High score = signs of unsustainable gains, consider trimming.

    Components:
    - Rate of gain (40%): Annualized return - penalize if unsustainably high
    - Volatility spike (30%): Current vs historical volatility
    - Valuation stretch (30%): Distance above 200-day MA
    """
    score = 0.0

    rate_score = _calculate_rate_of_gain_score(profit_pct, days_held)
    score += rate_score * 0.40

    vol_score = _calculate_volatility_spike_score(
        current_volatility, historical_volatility
    )
    score += vol_score * 0.30

    valuation_score = _calculate_valuation_stretch_score(distance_from_ma_200)
    score += valuation_score * 0.30

    score = _apply_profit_floor(score, profit_pct)

    return score
