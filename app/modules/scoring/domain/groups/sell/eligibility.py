"""Sell eligibility checking functions.

Functions to check if a position is eligible to be sold based on hard blocks.
"""

from datetime import datetime
from typing import Optional

from app.modules.scoring.domain.constants import (
    DEFAULT_MAX_LOSS_THRESHOLD,
    DEFAULT_MIN_HOLD_DAYS,
    DEFAULT_SELL_COOLDOWN_DAYS,
)


def _parse_date_string(date_str: str) -> Optional[datetime]:
    """Parse ISO date string, handling timezone."""
    from app.shared.utils import safe_parse_datetime_string

    return safe_parse_datetime_string(date_str)


def _check_min_hold_time(
    last_transaction_at: Optional[str], min_hold_days: int
) -> tuple[bool, Optional[str]]:
    """Check if position has been held for minimum required days.

    Uses the last transaction date (buy or sell) to calculate hold time.
    """
    if not last_transaction_at:
        return True, None

    transaction_date = _parse_date_string(last_transaction_at)
    if not transaction_date:
        return True, None  # Unknown date - allow

    days_held = (datetime.now() - transaction_date).days
    if days_held < min_hold_days:
        return False, f"Held only {days_held} days (min {min_hold_days})"

    return True, None


def _check_sell_cooldown(
    last_transaction_at: Optional[str], sell_cooldown_days: int
) -> tuple[bool, Optional[str]]:
    """Check if enough time has passed since last transaction (buy or sell).

    Uses the last transaction date to calculate cooldown period.
    """
    if not last_transaction_at:
        return True, None

    transaction_date = _parse_date_string(last_transaction_at)
    if not transaction_date:
        return True, None  # Unknown date - allow

    days_since_transaction = (datetime.now() - transaction_date).days
    if days_since_transaction < sell_cooldown_days:
        return (
            False,
            f"Last transaction {days_since_transaction} days ago (cooldown {sell_cooldown_days})",
        )

    return True, None


def check_sell_eligibility(
    allow_sell: bool,
    profit_pct: float,
    last_transaction_at: Optional[str],
    max_loss_threshold: float = DEFAULT_MAX_LOSS_THRESHOLD,
    min_hold_days: int = DEFAULT_MIN_HOLD_DAYS,
    sell_cooldown_days: int = DEFAULT_SELL_COOLDOWN_DAYS,
) -> tuple:
    """
    Check if selling is allowed based on hard blocks.

    Args:
        allow_sell: Whether selling is enabled for this security
        profit_pct: Current profit/loss percentage
        last_transaction_at: Date of last transaction (buy or sell) for this symbol
        max_loss_threshold: Maximum loss threshold (default: DEFAULT_MAX_LOSS_THRESHOLD)
        min_hold_days: Minimum hold period in days (default: DEFAULT_MIN_HOLD_DAYS)
        sell_cooldown_days: Sell cooldown period in days (default: DEFAULT_SELL_COOLDOWN_DAYS)

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

    eligible, reason = _check_min_hold_time(last_transaction_at, min_hold_days)
    if not eligible:
        return False, reason

    eligible, reason = _check_sell_cooldown(last_transaction_at, sell_cooldown_days)
    if not eligible:
        return False, reason

    return True, None
