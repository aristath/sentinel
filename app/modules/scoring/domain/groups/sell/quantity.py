"""Sell quantity determination functions.

Functions to calculate how much of a position should be sold based on scores.
"""

from app.modules.scoring.domain.constants import (
    DEFAULT_MIN_SELL_VALUE_EUR,
    MAX_SELL_PCT,
    MIN_SELL_PCT,
)
from app.modules.trading.domain.trade_sizing_service import TradeSizingService


def determine_sell_quantity(
    sell_score: float,
    quantity: float,
    min_lot: int,
    current_price: float,
    min_sell_value: float = DEFAULT_MIN_SELL_VALUE_EUR,
) -> tuple:
    """
    Determine how much to sell based on score.

    Returns:
        (quantity_to_sell, sell_pct) tuple
    """
    # Calculate sell percentage based on score (10% to 50%)
    sell_pct = min(MAX_SELL_PCT, max(MIN_SELL_PCT, MIN_SELL_PCT + (sell_score * 0.40)))

    # Calculate raw quantity
    raw_quantity = quantity * sell_pct

    # Round to min_lot using TradeSizingService
    sell_quantity = TradeSizingService.round_to_lots(raw_quantity, min_lot)

    # Ensure we don't sell everything (keep at least 1 lot)
    max_sell = quantity - min_lot
    if sell_quantity >= max_sell:
        sell_quantity = TradeSizingService.round_to_lots(max_sell, min_lot)

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
