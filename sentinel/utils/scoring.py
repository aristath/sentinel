"""
Scoring Utilities - Single source of truth for score adjustments.

Usage:
    adjusted = adjust_score_for_conviction(base_score, user_multiplier)
"""


def adjust_score_for_conviction(base_score: float, user_multiplier: float) -> float:
    """
    Apply user conviction (0..1) to a score.

    Conviction is additive (not multiplicative) and centered at 0.5:
    - 0.50 = neutral (no change)
    - 1.00 = +0.20 boost
    - 0.00 = -0.20 penalty

    Args:
        base_score: The original score (e.g., expected return)
        user_multiplier: User conviction in range [0.0, 1.0]

    Returns:
        Adjusted score with conviction applied
    """
    # Handle None or missing conviction
    if user_multiplier is None:
        user_multiplier = 0.5

    conviction = max(0.0, min(1.0, float(user_multiplier)))
    conviction_boost = (conviction - 0.5) * 0.4

    return base_score + conviction_boost
