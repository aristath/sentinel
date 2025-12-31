"""Win cooldown system - prevents overconfidence after hot streaks.

After exceptional gains (>20% in a month), temporarily reduce aggression
to prevent overleveraging during euphoric periods. Helps enforce discipline
and avoid giving back gains during market reversals.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class CooldownStatus:
    """Cooldown status for a bucket."""

    bucket_id: str
    in_cooldown: bool
    cooldown_start: Optional[str]  # ISO timestamp
    cooldown_end: Optional[str]  # ISO timestamp
    trigger_gain: Optional[float]  # Gain % that triggered cooldown
    days_remaining: int
    aggression_reduction: float  # Multiplier (e.g., 0.75 for 25% reduction)


def check_win_cooldown(
    bucket_id: str,
    recent_return: float,
    current_cooldown_start: Optional[str] = None,
    cooldown_days: int = 30,
    trigger_threshold: float = 0.20,
    aggression_reduction: float = 0.25,
) -> CooldownStatus:
    """Check if bucket should enter or is in win cooldown.

    Args:
        bucket_id: Bucket ID
        recent_return: Recent return (e.g., 0.25 for 25%)
        current_cooldown_start: Existing cooldown start date (if any)
        cooldown_days: How long cooldown lasts (default 30 days)
        trigger_threshold: Return threshold to trigger (default 20%)
        aggression_reduction: How much to reduce aggression (default 25%)

    Returns:
        CooldownStatus indicating current state
    """
    now = datetime.now()

    # Check if already in cooldown
    if current_cooldown_start:
        start_date = datetime.fromisoformat(current_cooldown_start)
        end_date = start_date + timedelta(days=cooldown_days)

        if now < end_date:
            days_remaining = (end_date - now).days
            logger.info(
                f"{bucket_id}: In win cooldown ({days_remaining} days remaining)"
            )
            return CooldownStatus(
                bucket_id=bucket_id,
                in_cooldown=True,
                cooldown_start=current_cooldown_start,
                cooldown_end=end_date.isoformat(),
                trigger_gain=None,  # Don't know original trigger
                days_remaining=days_remaining,
                aggression_reduction=1.0 - aggression_reduction,
            )
        else:
            # Cooldown expired
            logger.info(f"{bucket_id}: Win cooldown expired")
            return CooldownStatus(
                bucket_id=bucket_id,
                in_cooldown=False,
                cooldown_start=None,
                cooldown_end=None,
                trigger_gain=None,
                days_remaining=0,
                aggression_reduction=1.0,
            )

    # Check if should enter cooldown
    if recent_return >= trigger_threshold:
        cooldown_start = now.isoformat()
        cooldown_end = (now + timedelta(days=cooldown_days)).isoformat()

        logger.warning(
            f"{bucket_id}: Entering win cooldown! "
            f"Recent return: {recent_return*100:.1f}% "
            f"(threshold: {trigger_threshold*100:.1f}%). "
            f"Cooldown for {cooldown_days} days."
        )

        return CooldownStatus(
            bucket_id=bucket_id,
            in_cooldown=True,
            cooldown_start=cooldown_start,
            cooldown_end=cooldown_end,
            trigger_gain=recent_return,
            days_remaining=cooldown_days,
            aggression_reduction=1.0 - aggression_reduction,
        )

    # Not in cooldown and below threshold
    return CooldownStatus(
        bucket_id=bucket_id,
        in_cooldown=False,
        cooldown_start=None,
        cooldown_end=None,
        trigger_gain=None,
        days_remaining=0,
        aggression_reduction=1.0,
    )


def apply_cooldown_to_aggression(
    base_aggression: float, cooldown_status: CooldownStatus
) -> float:
    """Apply cooldown reduction to aggression level.

    Args:
        base_aggression: Base aggression from aggression_calculator
        cooldown_status: Current cooldown status

    Returns:
        Adjusted aggression (reduced if in cooldown)
    """
    if not cooldown_status.in_cooldown:
        return base_aggression

    # Apply reduction
    adjusted = base_aggression * cooldown_status.aggression_reduction

    logger.info(
        f"{cooldown_status.bucket_id}: Win cooldown applied - "
        f"aggression {base_aggression*100:.0f}% → {adjusted*100:.0f}% "
        f"(reduction: {(1-cooldown_status.aggression_reduction)*100:.0f}%)"
    )

    return adjusted


def calculate_recent_return(current_value: float, starting_value: float) -> float:
    """Calculate return over a period.

    Args:
        current_value: Current bucket value
        starting_value: Starting bucket value

    Returns:
        Return as decimal (e.g., 0.25 for 25%)
    """
    if starting_value <= 0:
        return 0.0

    return (current_value - starting_value) / starting_value


def get_cooldown_description(cooldown_status: CooldownStatus) -> str:
    """Get human-readable description of cooldown status.

    Args:
        cooldown_status: Cooldown status

    Returns:
        Description string
    """
    if not cooldown_status.in_cooldown:
        return "No win cooldown active"

    reduction_pct = (1 - cooldown_status.aggression_reduction) * 100

    if cooldown_status.trigger_gain:
        return (
            f"WIN COOLDOWN ACTIVE: Triggered by {cooldown_status.trigger_gain*100:.1f}% gain. "
            f"Aggression reduced by {reduction_pct:.0f}% for {cooldown_status.days_remaining} more days. "
            f"Prevents overconfidence after hot streak."
        )
    else:
        return (
            f"WIN COOLDOWN ACTIVE: Aggression reduced by {reduction_pct:.0f}% "
            f"for {cooldown_status.days_remaining} more days."
        )
