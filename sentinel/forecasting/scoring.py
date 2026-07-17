"""Derived forecast score helpers."""

from __future__ import annotations

import math


def _clip(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def score_forecast_return(
    *,
    median_return: float | None,
) -> dict[str, float]:
    """Convert a monthly median return forecast into a timing score.

    Score mapping is deliberately plain: -5% => 0, 0% => 0.5, +5% => 1.
    """

    if median_return is None or not math.isfinite(median_return):
        return {"score": 0.5}

    return {"score": _clip(0.5 + (median_return * 10.0))}


def combine_forecast_scores(scope_scores: dict[str, dict[str, float]]) -> dict[str, float] | None:
    """Combine solo and grouped scope scores into one planner-facing score."""

    available = {
        scope: values
        for scope, values in scope_scores.items()
        if values.get("forecast_return_4w") is not None and values.get("score") is not None
    }
    if not available:
        return None

    medians = [float(values["forecast_return_4w"]) for values in available.values()]
    scores = [float(values["score"]) for values in available.values()]

    median = sum(medians) / len(medians)
    score = sum(scores) / len(scores)

    agreement = 0.75
    if len(medians) >= 2:
        agreement = _clip(1.0 - (abs(medians[0] - medians[1]) / 0.10))

    q10_values: list[float] = []
    q90_values: list[float] = []
    for values in available.values():
        q10 = values.get("q10_return_4w")
        q90 = values.get("q90_return_4w")
        if q10 is not None:
            q10_values.append(float(q10))
        if q90 is not None:
            q90_values.append(float(q90))
    return {
        "forecast_return_4w": median,
        "q10_return_4w": min(q10_values) if q10_values else median,
        "q90_return_4w": max(q90_values) if q90_values else median,
        "score": _clip(score),
        "agreement": agreement,
    }


def adjusted_opportunity_score(
    *,
    current_opp_score: float,
    forecast_score: float | None,
    weight: float,
) -> float:
    """Apply the bounded forecast timing modifier to an existing opportunity score."""

    if forecast_score is None:
        return _clip(current_opp_score)
    modifier = max(0.0, weight) * ((2.0 * _clip(forecast_score)) - 1.0)
    return _clip(current_opp_score + modifier)
