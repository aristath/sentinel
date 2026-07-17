"""Model-agnostic time-series forecasting support."""

from sentinel.forecasting.scoring import adjusted_opportunity_score, combine_forecast_scores, score_forecast_return
from sentinel.forecasting.series import (
    WeeklyReturnPoint,
    align_weekly_return_series,
    build_weekly_return_series,
    realized_return_after_weeks,
)

__all__ = [
    "WeeklyReturnPoint",
    "align_weekly_return_series",
    "adjusted_opportunity_score",
    "build_weekly_return_series",
    "combine_forecast_scores",
    "realized_return_after_weeks",
    "score_forecast_return",
]
