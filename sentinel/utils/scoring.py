"""
Scoring Utilities - Single source of truth for score adjustments.

Usage:
    adjusted = adjust_score_for_conviction(base_score, user_multiplier)
"""


def adjust_score_for_conviction(base_score: float, user_multiplier: float) -> float:
    """
    Apply user conviction multiplier to a score.

    The conviction adjustment is additive rather than multiplicative,
    allowing users to override negative/missing signals with high conviction:
    - multiplier 1.0 = no change (neutral)
    - multiplier 2.0 = +0.3 boost (strong bullish conviction)
    - multiplier 0.5 = -0.15 penalty (bearish conviction)

    Args:
        base_score: The original score (e.g., expected return)
        user_multiplier: User's conviction multiplier (0.25 to 2.0)

    Returns:
        Adjusted score with conviction applied
    """
    # Handle None or missing multiplier
    if user_multiplier is None:
        user_multiplier = 1.0

    # Calculate additive boost: (multiplier - 1.0) * 0.3
    conviction_boost = (user_multiplier - 1.0) * 0.3

    return base_score + conviction_boost
