"""Clara strategic preference helpers."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

SECONDS_PER_WEEK = 7 * 24 * 60 * 60
NEUTRAL_USER_MULTIPLIER = 0.5
STRATEGIC_BUY_PRESSURE_THRESHOLD = 0.55


def normalize_user_multiplier(value: Any) -> float:
    """Normalize a user multiplier/preference value into [0.0, 1.0]."""
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError):
        return NEUTRAL_USER_MULTIPLIER
    if not math.isfinite(parsed):
        return NEUTRAL_USER_MULTIPLIER
    return max(0.0, min(1.0, parsed))


def parse_utc_datetime(value: object) -> datetime | None:
    """Parse an ISO-ish UTC datetime value."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        timestamp = float(value)
        if not math.isfinite(timestamp):
            return None
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def utc_now_iso() -> str:
    """Return current UTC datetime as an ISO string."""
    return datetime.now(timezone.utc).isoformat()


def age_weeks(updated_at: object, *, now: datetime | None = None) -> float:
    """Return non-negative age in weeks for a timestamp."""
    parsed = parse_utc_datetime(updated_at)
    if parsed is None:
        return 0.0
    now_dt = now or datetime.now(timezone.utc)
    if now_dt.tzinfo is None:
        now_dt = now_dt.replace(tzinfo=timezone.utc)
    delta_seconds = (now_dt.astimezone(timezone.utc) - parsed).total_seconds()
    return max(0.0, delta_seconds / SECONDS_PER_WEEK)


def freshness_from_timestamp(updated_at: object, weekly_fade: float, *, now: datetime | None = None) -> float:
    """Return freshness coefficient where 1.0 is fresh and 0.0 is stale."""
    if parse_utc_datetime(updated_at) is None:
        return 0.0
    try:
        parsed_fade = float(weekly_fade)
    except (TypeError, ValueError, OverflowError):
        parsed_fade = 0.0
    if not math.isfinite(parsed_fade):
        parsed_fade = 0.0
    fade = max(0.0, min(1.0, parsed_fade))
    return fade ** age_weeks(updated_at, now=now)


def effective_user_multiplier(
    value: object,
    updated_at: object,
    weekly_fade: float,
    *,
    now: datetime | None = None,
) -> float:
    """Return user multiplier after fading toward neutral."""
    stored = normalize_user_multiplier(value)
    freshness = freshness_from_timestamp(updated_at, weekly_fade, now=now)
    return NEUTRAL_USER_MULTIPLIER + ((stored - NEUTRAL_USER_MULTIPLIER) * freshness)


def preference_tilt(effective_multiplier: float, strength: float) -> float:
    """Turn an effective user multiplier into a strategic allocation tilt."""
    try:
        parsed_strength = float(strength)
    except (TypeError, ValueError, OverflowError):
        parsed_strength = 0.0
    if not math.isfinite(parsed_strength):
        parsed_strength = 0.0
    exponent = parsed_strength * (normalize_user_multiplier(effective_multiplier) - NEUTRAL_USER_MULTIPLIER)
    return math.exp(max(-20.0, min(20.0, exponent)))


def has_strategic_buy_pressure(effective_multiplier: object) -> bool:
    """Return whether a faded preference is meaningfully above neutral."""
    return normalize_user_multiplier(effective_multiplier) >= STRATEGIC_BUY_PRESSURE_THRESHOLD


def normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    """Normalize positive weights to sum to one."""
    positive: dict[str, float] = {}
    for symbol, value in weights.items():
        try:
            parsed = float(value)
        except (TypeError, ValueError, OverflowError):
            continue
        if math.isfinite(parsed) and parsed > 0:
            positive[symbol] = parsed
    total = sum(positive.values())
    if total <= 0:
        return {}
    return {symbol: value / total for symbol, value in positive.items()}


def apply_max_cap(weights: dict[str, float], max_position: float) -> dict[str, float]:
    """Apply a per-symbol cap using water-fill redistribution."""
    normalized = normalize_weights(weights)
    if not normalized:
        return {}
    try:
        parsed_cap = float(max_position)
    except (TypeError, ValueError, OverflowError):
        parsed_cap = 0.0
    if not math.isfinite(parsed_cap):
        parsed_cap = 0.0
    cap = max(0.0, min(1.0, parsed_cap))
    if cap <= 0:
        return {}
    if len(normalized) * cap < 1.0:
        return {symbol: min(cap, weight) for symbol, weight in normalized.items()}

    capped: dict[str, float] = {}
    remaining = dict(normalized)
    remaining_capacity = 1.0

    while remaining:
        total_remaining = sum(remaining.values())
        if total_remaining <= 0:
            break
        over_cap: dict[str, float] = {}
        tentative = {symbol: (weight / total_remaining) * remaining_capacity for symbol, weight in remaining.items()}
        for symbol, weight in tentative.items():
            if weight > cap:
                over_cap[symbol] = cap
        if not over_cap:
            capped.update(tentative)
            break
        for symbol, weight in over_cap.items():
            capped[symbol] = weight
            remaining.pop(symbol, None)
        remaining_capacity = max(0.0, 1.0 - sum(capped.values()))

    return {symbol: weight for symbol, weight in capped.items() if weight > 0}


def preference_snapshot(
    security: dict[str, Any],
    *,
    weekly_fade: float,
    now: datetime | None = None,
) -> dict[str, float]:
    """Return stored/effective preference details for one security."""
    stored = normalize_user_multiplier(security.get("user_multiplier", NEUTRAL_USER_MULTIPLIER))
    updated_at = security.get("user_multiplier_updated_at")
    weeks = age_weeks(updated_at, now=now)
    effective = effective_user_multiplier(stored, updated_at, weekly_fade, now=now)
    return {
        "user_multiplier": stored,
        "effective_user_multiplier": effective,
        "user_multiplier_age_weeks": weeks,
    }
