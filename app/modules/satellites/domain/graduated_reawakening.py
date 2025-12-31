"""Graduated re-awakening system - cautious recovery after hibernation.

After a satellite exits hibernation, gradually increase position sizes:
- First trade: 25% of normal size
- After win: 50% of normal size
- After second win: 75% of normal size
- After third win: 100% (fully re-awakened)
- Any loss during re-awakening: Reset to 25%

This prevents immediately jumping back to full aggression after a severe
drawdown, ensuring the strategy proves itself before full capital deployment.
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ReawakeningStatus:
    """Re-awakening status for a bucket recovering from hibernation."""

    bucket_id: str
    in_reawakening: bool
    current_stage: int  # 0=not started, 1=25%, 2=50%, 3=75%, 4=100% (complete)
    consecutive_wins: int
    aggression_multiplier: float  # Current multiplier (0.25, 0.5, 0.75, or 1.0)
    trades_since_awakening: int
    ready_for_full_aggression: bool


REAWAKENING_STAGES = {
    0: 0.0,  # Hibernating
    1: 0.25,  # First stage - 25%
    2: 0.50,  # Second stage - 50%
    3: 0.75,  # Third stage - 75%
    4: 1.00,  # Fully re-awakened
}


def check_reawakening_status(
    bucket_id: str,
    currently_in_reawakening: bool,
    current_stage: int,
    consecutive_wins: int,
    trades_since_awakening: int,
) -> ReawakeningStatus:
    """Check current re-awakening status.

    Args:
        bucket_id: Bucket ID
        currently_in_reawakening: Whether bucket is currently in re-awakening
        current_stage: Current stage (1-4)
        consecutive_wins: Consecutive wins since awakening
        trades_since_awakening: Total trades since awakening

    Returns:
        ReawakeningStatus with current state
    """
    if not currently_in_reawakening or current_stage >= 4:
        # Not in re-awakening or fully complete
        return ReawakeningStatus(
            bucket_id=bucket_id,
            in_reawakening=False,
            current_stage=4,
            consecutive_wins=consecutive_wins,
            aggression_multiplier=1.0,
            trades_since_awakening=trades_since_awakening,
            ready_for_full_aggression=True,
        )

    # In re-awakening - determine stage based on consecutive wins
    if consecutive_wins >= 3:
        stage = 4  # Fully re-awakened after 3 wins
    elif consecutive_wins == 2:
        stage = 3  # 75% after 2 wins
    elif consecutive_wins == 1:
        stage = 2  # 50% after 1 win
    else:
        stage = 1  # 25% initially or after a loss

    multiplier = REAWAKENING_STAGES[stage]
    fully_ready = stage >= 4

    logger.info(
        f"{bucket_id}: Re-awakening stage {stage}/4 "
        f"({multiplier*100:.0f}% aggression) - "
        f"{consecutive_wins} consecutive wins"
    )

    return ReawakeningStatus(
        bucket_id=bucket_id,
        in_reawakening=True,
        current_stage=stage,
        consecutive_wins=consecutive_wins,
        aggression_multiplier=multiplier,
        trades_since_awakening=trades_since_awakening,
        ready_for_full_aggression=fully_ready,
    )


def start_reawakening(bucket_id: str) -> ReawakeningStatus:
    """Start graduated re-awakening process.

    Called when a bucket exits hibernation.

    Args:
        bucket_id: Bucket ID

    Returns:
        ReawakeningStatus at initial stage (25%)
    """
    logger.warning(
        f"{bucket_id}: Starting graduated re-awakening - "
        "beginning at 25% aggression until proven"
    )

    return ReawakeningStatus(
        bucket_id=bucket_id,
        in_reawakening=True,
        current_stage=1,
        consecutive_wins=0,
        aggression_multiplier=0.25,
        trades_since_awakening=0,
        ready_for_full_aggression=False,
    )


def record_trade_result(
    current_status: ReawakeningStatus, is_win: bool
) -> ReawakeningStatus:
    """Record a trade result and update re-awakening status.

    Args:
        current_status: Current re-awakening status
        is_win: Whether the trade was profitable

    Returns:
        Updated ReawakeningStatus
    """
    if not current_status.in_reawakening:
        # Not in re-awakening, nothing to update
        return current_status

    trades = current_status.trades_since_awakening + 1

    if is_win:
        # Increment consecutive wins, advance stage
        wins = current_status.consecutive_wins + 1

        if wins >= 3:
            # Fully re-awakened!
            logger.info(
                f"{current_status.bucket_id}: FULLY RE-AWAKENED after 3 consecutive wins! "
                f"Resuming 100% aggression."
            )
            return ReawakeningStatus(
                bucket_id=current_status.bucket_id,
                in_reawakening=False,
                current_stage=4,
                consecutive_wins=wins,
                aggression_multiplier=1.0,
                trades_since_awakening=trades,
                ready_for_full_aggression=True,
            )
        else:
            # Advance to next stage
            new_stage = wins + 1  # Stage 2 after 1 win, stage 3 after 2 wins
            new_multiplier = REAWAKENING_STAGES[new_stage]

            logger.info(
                f"{current_status.bucket_id}: Re-awakening progress - "
                f"advanced to stage {new_stage}/4 ({new_multiplier*100:.0f}% aggression) "
                f"after {wins} consecutive wins"
            )

            return ReawakeningStatus(
                bucket_id=current_status.bucket_id,
                in_reawakening=True,
                current_stage=new_stage,
                consecutive_wins=wins,
                aggression_multiplier=new_multiplier,
                trades_since_awakening=trades,
                ready_for_full_aggression=False,
            )

    else:
        # Loss - reset to stage 1 (25%)
        logger.warning(
            f"{current_status.bucket_id}: Re-awakening RESET due to loss! "
            f"Back to 25% aggression (was at stage {current_status.current_stage}/4)"
        )

        return ReawakeningStatus(
            bucket_id=current_status.bucket_id,
            in_reawakening=True,
            current_stage=1,
            consecutive_wins=0,
            aggression_multiplier=0.25,
            trades_since_awakening=trades,
            ready_for_full_aggression=False,
        )


def apply_reawakening_to_aggression(
    base_aggression: float, reawakening_status: ReawakeningStatus
) -> float:
    """Apply re-awakening multiplier to aggression.

    Args:
        base_aggression: Base aggression from aggression_calculator
        reawakening_status: Current re-awakening status

    Returns:
        Adjusted aggression (reduced if in re-awakening)
    """
    if not reawakening_status.in_reawakening:
        return base_aggression

    adjusted = base_aggression * reawakening_status.aggression_multiplier

    logger.info(
        f"{reawakening_status.bucket_id}: Re-awakening stage {reawakening_status.current_stage}/4 - "
        f"aggression {base_aggression*100:.0f}% → {adjusted*100:.0f}% "
        f"(multiplier: {reawakening_status.aggression_multiplier*100:.0f}%)"
    )

    return adjusted


def get_reawakening_description(reawakening_status: ReawakeningStatus) -> str:
    """Get human-readable description of re-awakening status.

    Args:
        reawakening_status: Re-awakening status

    Returns:
        Description string
    """
    if not reawakening_status.in_reawakening:
        if reawakening_status.trades_since_awakening > 0:
            return (
                f"Fully re-awakened after {reawakening_status.consecutive_wins} "
                f"consecutive wins ({reawakening_status.trades_since_awakening} trades total)"
            )
        else:
            return "Not in re-awakening process"

    stage = reawakening_status.current_stage
    multiplier = reawakening_status.aggression_multiplier
    wins = reawakening_status.consecutive_wins
    wins_needed = 3 - wins

    return (
        f"RE-AWAKENING: Stage {stage}/4 ({multiplier*100:.0f}% aggression). "
        f"{wins} consecutive wins so far, need {wins_needed} more to fully re-awaken. "
        f"Any loss resets to 25%."
    )
