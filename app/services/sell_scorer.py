"""Sell scoring module for determining when and how much to sell.

This module implements a 4-component weighted scoring model for SELL decisions:
- Underperformance Score (40%): How poorly stock performed vs target (8-15% annual)
- Time Held Score (20%): Longer hold with underperformance = higher sell priority
- Portfolio Balance Score (20%): Overweight positions score higher
- Instability Score (20%): Detect potential bubbles and unsustainable gains

The instability score evaluates:
- Rate of gain: How fast did the gain happen? (annualized return)
- Volatility spike: Is current volatility elevated vs historical?
- Valuation stretch: How far above 200-day MA?

Hard Blocks (NEVER sell if any apply):
- allow_sell=false
- Loss >20%
- Held <3 months
- Last sold <6 months ago
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

# Default constants for sell scoring (can be overridden via settings)
DEFAULT_MIN_HOLD_DAYS = 90  # 3 months minimum hold
DEFAULT_SELL_COOLDOWN_DAYS = 180  # 6 months between sells
DEFAULT_MAX_LOSS_THRESHOLD = -0.20  # Never sell if down more than 20%
DEFAULT_MIN_SELL_VALUE_EUR = 100  # Minimum sell value in EUR
MIN_SELL_PCT = 0.10  # Minimum 10% of position
MAX_SELL_PCT = 0.50  # Maximum 50% of position

# Target annual return range (ideal performance)
TARGET_RETURN_MIN = 0.08  # 8%
TARGET_RETURN_MAX = 0.15  # 15%


async def get_sell_settings() -> dict:
    """Load sell-related settings from database, with defaults fallback."""
    from app.api.settings import get_setting_value
    return {
        "min_hold_days": int(await get_setting_value("min_hold_days")),
        "sell_cooldown_days": int(await get_setting_value("sell_cooldown_days")),
        "max_loss_threshold": await get_setting_value("max_loss_threshold"),
        "min_sell_value": await get_setting_value("min_sell_value"),
    }


@dataclass
class TechnicalData:
    """Technical indicators for instability detection."""
    current_volatility: float    # Last 60 days
    historical_volatility: float  # Last 365 days
    distance_from_ma_200: float  # Positive = above MA, negative = below


@dataclass
class SellScore:
    """Result of sell score calculation."""
    symbol: str
    eligible: bool  # Whether sell is allowed at all
    block_reason: Optional[str]  # If not eligible, why
    underperformance_score: float
    time_held_score: float
    portfolio_balance_score: float
    instability_score: float
    total_score: float
    suggested_sell_pct: float  # 0.10 to 0.50
    suggested_sell_quantity: int
    suggested_sell_value: float
    profit_pct: float
    days_held: int


def calculate_underperformance_score(
    current_price: float,
    avg_price: float,
    days_held: int,
    max_loss_threshold: float = DEFAULT_MAX_LOSS_THRESHOLD
) -> tuple[float, float]:
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
    first_bought_at: Optional[str],
    min_hold_days: int = DEFAULT_MIN_HOLD_DAYS
) -> tuple[float, int]:
    """
    Calculate time held score. Longer hold with underperformance = higher sell priority.

    Returns:
        (score, days_held) tuple
    """
    if not first_bought_at:
        # Unknown hold time - assume long enough
        return 0.6, 365

    try:
        bought_date = datetime.fromisoformat(first_bought_at.replace('Z', '+00:00'))
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
    ind_allocations: Dict[str, float]
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
        industries = [i.strip() for i in industry.split(',')]
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

    # 1. Rate of gain (40%)
    if days_held > 30:
        years = days_held / 365.0
        try:
            annualized = ((1 + profit_pct) ** (1 / years)) - 1 if years > 0 else profit_pct
        except (ValueError, OverflowError):
            annualized = profit_pct

        if annualized > 0.50:      # >50% annualized = very hot
            rate_score = 1.0
        elif annualized > 0.30:    # >30% annualized = hot
            rate_score = 0.7
        elif annualized > 0.20:    # >20% annualized = warm
            rate_score = 0.4
        else:
            rate_score = 0.1       # Sustainable pace
    else:
        rate_score = 0.5  # Too early to tell
    score += rate_score * 0.40

    # 2. Volatility spike (30%)
    if historical_volatility > 0:
        vol_ratio = current_volatility / historical_volatility
        if vol_ratio > 2.0:        # Vol doubled
            vol_score = 1.0
        elif vol_ratio > 1.5:      # Vol up 50%
            vol_score = 0.7
        elif vol_ratio > 1.2:      # Vol up 20%
            vol_score = 0.4
        else:
            vol_score = 0.1        # Normal volatility
    else:
        vol_score = 0.3  # No historical data - neutral
    score += vol_score * 0.30

    # 3. Valuation stretch (30%)
    if distance_from_ma_200 > 0.30:    # >30% above MA
        valuation_score = 1.0
    elif distance_from_ma_200 > 0.20:  # >20% above MA
        valuation_score = 0.7
    elif distance_from_ma_200 > 0.10:  # >10% above MA
        valuation_score = 0.4
    else:
        valuation_score = 0.1          # Near or below MA
    score += valuation_score * 0.30

    # Floor for extreme profits (safety net)
    if profit_pct > 1.0:  # >100% gain
        score = max(score, 0.2)
    elif profit_pct > 0.75:  # >75% gain
        score = max(score, 0.1)

    return score


def check_sell_eligibility(
    allow_sell: bool,
    profit_pct: float,
    first_bought_at: Optional[str],
    last_sold_at: Optional[str],
    max_loss_threshold: float = DEFAULT_MAX_LOSS_THRESHOLD,
    min_hold_days: int = DEFAULT_MIN_HOLD_DAYS,
    sell_cooldown_days: int = DEFAULT_SELL_COOLDOWN_DAYS
) -> tuple[bool, Optional[str]]:
    """
    Check if selling is allowed based on hard blocks.

    Returns:
        (is_eligible, block_reason) tuple
    """
    # Check allow_sell flag
    if not allow_sell:
        return False, "allow_sell=false"

    # Check loss threshold
    if profit_pct < max_loss_threshold:
        return False, f"Loss {profit_pct*100:.1f}% exceeds {max_loss_threshold*100:.0f}% threshold"

    # Check minimum hold time
    if first_bought_at:
        try:
            bought_date = datetime.fromisoformat(first_bought_at.replace('Z', '+00:00'))
            if bought_date.tzinfo:
                bought_date = bought_date.replace(tzinfo=None)
            days_held = (datetime.now() - bought_date).days
            if days_held < min_hold_days:
                return False, f"Held only {days_held} days (min {min_hold_days})"
        except (ValueError, TypeError):
            pass  # Unknown date - allow

    # Check cooldown from last sell
    if last_sold_at:
        try:
            sold_date = datetime.fromisoformat(last_sold_at.replace('Z', '+00:00'))
            if sold_date.tzinfo:
                sold_date = sold_date.replace(tzinfo=None)
            days_since_sell = (datetime.now() - sold_date).days
            if days_since_sell < sell_cooldown_days:
                return False, f"Sold {days_since_sell} days ago (cooldown {sell_cooldown_days})"
        except (ValueError, TypeError):
            pass  # Unknown date - allow

    return True, None


def determine_sell_quantity(
    sell_score: float,
    quantity: float,
    min_lot: int,
    current_price: float,
    min_sell_value: float = DEFAULT_MIN_SELL_VALUE_EUR
) -> tuple[int, float]:
    """
    Determine how much to sell based on score.

    Returns:
        (quantity_to_sell, sell_pct) tuple
    """
    # Calculate sell percentage based on score (10% to 50%)
    sell_pct = min(MAX_SELL_PCT, max(MIN_SELL_PCT, MIN_SELL_PCT + (sell_score * 0.40)))

    # Calculate raw quantity
    raw_quantity = quantity * sell_pct

    # Round to min_lot
    if min_lot > 1:
        sell_quantity = int(raw_quantity // min_lot) * min_lot
    else:
        sell_quantity = int(raw_quantity)

    # Ensure we don't sell everything (keep at least 1 lot)
    max_sell = quantity - min_lot
    if sell_quantity >= max_sell:
        sell_quantity = int(max_sell // min_lot) * min_lot if min_lot > 1 else int(max_sell)

    # Ensure minimum sell quantity
    if sell_quantity < min_lot:
        sell_quantity = 0  # Can't sell less than min_lot

    # Check minimum value
    sell_value = sell_quantity * current_price
    if sell_value < min_sell_value:
        sell_quantity = 0  # Below minimum value threshold
        sell_pct = 0
    else:
        # Recalculate actual sell percentage
        sell_pct = sell_quantity / quantity if quantity > 0 else 0

    return sell_quantity, sell_pct


def calculate_sell_score(
    symbol: str,
    quantity: float,
    avg_price: float,
    current_price: float,
    min_lot: int,
    allow_sell: bool,
    first_bought_at: Optional[str],
    last_sold_at: Optional[str],
    geography: str,
    industry: str,
    total_portfolio_value: float,
    geo_allocations: Dict[str, float],
    ind_allocations: Dict[str, float],
    technical_data: Optional[TechnicalData] = None,
    settings: Optional[Dict] = None
) -> SellScore:
    """
    Calculate complete sell score for a position.

    Args:
        symbol: Stock symbol
        quantity: Current position quantity
        avg_price: Average purchase price
        current_price: Current market price
        min_lot: Minimum lot size for this stock
        allow_sell: Whether selling is enabled for this stock
        first_bought_at: When position was first opened
        last_sold_at: When position was last sold (for cooldown)
        geography: Stock's geography
        industry: Stock's industry (comma-separated if multiple)
        total_portfolio_value: Total portfolio value in EUR
        geo_allocations: Current geography allocation percentages
        ind_allocations: Current industry allocation percentages
        technical_data: Technical indicators for instability detection

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

    # Check eligibility (hard blocks)
    eligible, block_reason = check_sell_eligibility(
        allow_sell, profit_pct, first_bought_at, last_sold_at,
        max_loss_threshold=max_loss_threshold,
        min_hold_days=min_hold_days,
        sell_cooldown_days=sell_cooldown_days
    )

    # Calculate time held
    time_held_score, days_held = calculate_time_held_score(
        first_bought_at, min_hold_days=min_hold_days
    )

    # If blocked by time held, mark as ineligible
    if time_held_score == 0.0 and first_bought_at and days_held < min_hold_days:
        eligible = False
        block_reason = block_reason or f"Held only {days_held} days (min {min_hold_days})"

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
            days_held=days_held
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
            days_held=days_held
        )

    portfolio_balance_score = calculate_portfolio_balance_score(
        position_value, total_portfolio_value,
        geography, industry,
        geo_allocations, ind_allocations
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

    # Calculate total score (weighted)
    # Weights: underperformance 40%, time_held 20%, portfolio_balance 20%, instability 20%
    total_score = (
        (underperformance_score * 0.40) +
        (time_held_score * 0.20) +
        (portfolio_balance_score * 0.20) +
        (instability_score * 0.20)
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
        days_held=days_held
    )


def calculate_all_sell_scores(
    positions: List[dict],
    total_portfolio_value: float,
    geo_allocations: Dict[str, float],
    ind_allocations: Dict[str, float],
    technical_data: Optional[Dict[str, TechnicalData]] = None,
    settings: Optional[Dict] = None
) -> List[SellScore]:
    """
    Calculate sell scores for all positions.

    Args:
        positions: List of position dicts with stock info (from get_with_stock_info)
        total_portfolio_value: Total portfolio value in EUR
        geo_allocations: Current geography allocation percentages
        ind_allocations: Current industry allocation percentages
        technical_data: Dict mapping symbol to TechnicalData for instability detection
        settings: Optional settings dict with min_hold_days, sell_cooldown_days, etc.

    Returns:
        List of SellScore objects, sorted by total_score descending
    """
    scores = []
    technical_data = technical_data or {}

    for pos in positions:
        symbol = pos['symbol']
        score = calculate_sell_score(
            symbol=symbol,
            quantity=pos['quantity'],
            avg_price=pos['avg_price'],
            current_price=pos['current_price'] or pos['avg_price'],
            min_lot=pos.get('min_lot', 1),
            allow_sell=bool(pos.get('allow_sell', False)),
            first_bought_at=pos.get('first_bought_at'),
            last_sold_at=pos.get('last_sold_at'),
            geography=pos.get('geography', ''),
            industry=pos.get('industry', ''),
            total_portfolio_value=total_portfolio_value,
            geo_allocations=geo_allocations,
            ind_allocations=ind_allocations,
            technical_data=technical_data.get(symbol),
            settings=settings
        )
        scores.append(score)

    # Sort by total_score descending (highest sell priority first)
    scores.sort(key=lambda s: s.total_score, reverse=True)

    return scores
