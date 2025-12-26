"""Sell eligibility checking functions.

Functions to check if a position is eligible to be sold based on hard blocks.
"""

from datetime import datetime
from typing import Optional

from app.domain.scoring.constants import (
    DEFAULT_MAX_LOSS_THRESHOLD,
    DEFAULT_MIN_HOLD_DAYS,
    DEFAULT_SELL_COOLDOWN_DAYS,
)


def check_sell_eligibility(
    allow_sell: bool,
    profit_pct: float,
    first_bought_at: Optional[str],
    last_sold_at: Optional[str],
    max_loss_threshold: float = DEFAULT_MAX_LOSS_THRESHOLD,
    min_hold_days: int = DEFAULT_MIN_HOLD_DAYS,
    sell_cooldown_days: int = DEFAULT_SELL_COOLDOWN_DAYS,
) -> tuple:
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
        return (
            False,
            f"Loss {profit_pct*100:.1f}% exceeds {max_loss_threshold*100:.0f}% threshold",
        )

    # Check minimum hold time
    if first_bought_at:
        try:
            bought_date = datetime.fromisoformat(first_bought_at.replace("Z", "+00:00"))
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
            sold_date = datetime.fromisoformat(last_sold_at.replace("Z", "+00:00"))
            if sold_date.tzinfo:
                sold_date = sold_date.replace(tzinfo=None)
            days_since_sell = (datetime.now() - sold_date).days
            if days_since_sell < sell_cooldown_days:
                return (
                    False,
                    f"Sold {days_since_sell} days ago (cooldown {sell_cooldown_days})",
                )
        except (ValueError, TypeError):
            pass  # Unknown date - allow

    return True, None
