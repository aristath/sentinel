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


def _parse_date_string(date_str: str) -> Optional[datetime]:
    """Parse ISO date string, handling timezone."""
    try:
        date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        if date.tzinfo:
            date = date.replace(tzinfo=None)
        return date
    except (ValueError, TypeError):
        return None


def _check_min_hold_time(
    first_bought_at: Optional[str], min_hold_days: int
) -> tuple[bool, Optional[str]]:
    """Check if position has been held for minimum required days."""
    if not first_bought_at:
        return True, None

    bought_date = _parse_date_string(first_bought_at)
    if not bought_date:
        return True, None  # Unknown date - allow

    days_held = (datetime.now() - bought_date).days
    if days_held < min_hold_days:
        return False, f"Held only {days_held} days (min {min_hold_days})"

    return True, None


def _check_sell_cooldown(
    last_sold_at: Optional[str], sell_cooldown_days: int
) -> tuple[bool, Optional[str]]:
    """Check if enough time has passed since last sell."""
    if not last_sold_at:
        return True, None

    sold_date = _parse_date_string(last_sold_at)
    if not sold_date:
        return True, None  # Unknown date - allow

    days_since_sell = (datetime.now() - sold_date).days
    if days_since_sell < sell_cooldown_days:
        return (
            False,
            f"Sold {days_since_sell} days ago (cooldown {sell_cooldown_days})",
        )

    return True, None


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
    if not allow_sell:
        return False, "allow_sell=false"

    if profit_pct < max_loss_threshold:
        return (
            False,
            f"Loss {profit_pct*100:.1f}% exceeds {max_loss_threshold*100:.0f}% threshold",
        )

    eligible, reason = _check_min_hold_time(first_bought_at, min_hold_days)
    if not eligible:
        return False, reason

    eligible, reason = _check_sell_cooldown(last_sold_at, sell_cooldown_days)
    if not eligible:
        return False, reason

    return True, None
