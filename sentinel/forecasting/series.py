"""Forecast input-series preparation.

Sentinel stores daily prices, but the forecasting layer consumes weekly log
returns. This module is intentionally model-agnostic; it knows nothing about
Toto or any future forecasting backend.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable


@dataclass(frozen=True)
class WeeklyReturnPoint:
    """One weekly log-return observation."""

    week_start: str
    week_end: str
    value: float


def _parse_date(value: object) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    if not isinstance(value, str) or not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def build_weekly_return_series(
    price_rows: Iterable[dict],
    *,
    max_points: int | None = None,
) -> list[WeeklyReturnPoint]:
    """Build oldest-first weekly log returns from daily price rows.

    The last available close within each ISO week becomes that week's close.
    No missing weeks are synthesized here; grouped multivariate batches handle
    masks during alignment.
    """

    weekly: dict[str, tuple[date, float]] = {}
    for row in price_rows:
        d = _parse_date(row.get("date"))
        if d is None:
            continue
        raw_close = row.get("close")
        if raw_close is None:
            continue
        try:
            close = float(raw_close)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(close) or close <= 0:
            continue
        start = _week_start(d)
        key = start.isoformat()
        existing = weekly.get(key)
        if existing is None or d >= existing[0]:
            weekly[key] = (d, close)

    closes = sorted((date.fromisoformat(key), end, close) for key, (end, close) in weekly.items())
    points: list[WeeklyReturnPoint] = []
    for previous, current in zip(closes, closes[1:], strict=False):
        _, _, previous_close = previous
        start, end, current_close = current
        if previous_close <= 0 or current_close <= 0:
            continue
        points.append(
            WeeklyReturnPoint(
                week_start=start.isoformat(),
                week_end=end.isoformat(),
                value=math.log(current_close / previous_close),
            )
        )

    if max_points is not None and max_points > 0:
        return points[-max_points:]
    return points


def align_weekly_return_series(
    series_by_symbol: dict[str, list[WeeklyReturnPoint]],
    *,
    max_points: int,
) -> dict[str, list[dict[str, float | bool | str]]]:
    """Align weekly return series onto a shared calendar with masks.

    Returns per-symbol rows oldest-first:
    `{"week_start": str, "value": float, "mask": bool}`.
    Missing values are encoded as 0.0 with `mask=False`; the forecasting
    service decides how the provider consumes that mask.
    """

    weeks = sorted({point.week_start for series in series_by_symbol.values() for point in series})
    if max_points > 0:
        weeks = weeks[-max_points:]

    aligned: dict[str, list[dict[str, float | bool | str]]] = {}
    for symbol, series in series_by_symbol.items():
        lookup = {point.week_start: point.value for point in series}
        aligned[symbol] = [
            {
                "week_start": week,
                "value": float(lookup.get(week, 0.0)),
                "mask": week in lookup,
            }
            for week in weeks
        ]
    return aligned


def realized_return_after_weeks(
    price_rows: Iterable[dict],
    *,
    start_ts: int,
    horizon_weeks: int,
    max_lookup_days: int = 10,
) -> float | None:
    """Return actual simple return from `start_ts` to `horizon_weeks` later.

    Uses the first available price on or after each target date, within a small
    lookup window to accommodate weekends and market holidays.
    """

    price_by_date: dict[date, float] = {}
    for row in price_rows:
        d = _parse_date(row.get("date"))
        if d is None:
            continue
        raw_close = row.get("close")
        if raw_close is None:
            continue
        try:
            close = float(raw_close)
        except (TypeError, ValueError):
            continue
        if math.isfinite(close) and close > 0:
            price_by_date[d] = close

    if not price_by_date:
        return None

    start_date = datetime.fromtimestamp(start_ts).date()
    end_date = start_date + timedelta(weeks=horizon_weeks)

    def first_price_on_or_after(target: date) -> float | None:
        for offset in range(max_lookup_days + 1):
            price = price_by_date.get(target + timedelta(days=offset))
            if price is not None:
                return price
        return None

    start_price = first_price_on_or_after(start_date)
    end_price = first_price_on_or_after(end_date)
    if start_price is None or end_price is None or start_price <= 0:
        return None
    return (end_price / start_price) - 1.0
