"""AI research multiplier helpers.

The `ai_research_multiplier` (range 0..1, with 0.5 = neutral) is Sentinel's
AI-research rating for a security. Historically, this was faded
toward neutral at read time by computing an "effective" value from a
freshness coefficient. That design is gone — the stored value now BECOMES
the effective value and gracefully decays back to 0.5 via a scheduled
weekly job (`decay:ai_research_multipliers`).

The atomic decay step is `decayed_ai_research_multiplier`, defined below.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

SECONDS_PER_WEEK = 7 * 24 * 60 * 60
NEUTRAL_AI_RESEARCH_MULTIPLIER = 0.5
STRATEGIC_BUY_PRESSURE_THRESHOLD = 0.70

# Default per-week fade factor. One decay step at this rate leaves 90% of the
# deviation from neutral; 52 successive steps leave (0.9 ** 52) ≈ 0.0042 of
# the original — effectively neutral after a year of no human touch.
DEFAULT_DECAY_FADE_FACTOR = 0.9


def stored_ai_research_multiplier(value: Any) -> float | None:
    """Read a rating without manufacturing one for missing/invalid data."""
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(parsed):
        return None
    return max(0.0, min(1.0, parsed))


def normalize_ai_research_multiplier(value: Any) -> float:
    """Numeric neutral tilt for internal arithmetic, never a stored/API rating."""
    rating = stored_ai_research_multiplier(value)
    return NEUTRAL_AI_RESEARCH_MULTIPLIER if rating is None else rating


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


def decayed_ai_research_multiplier(value: object, fade_factor: float = DEFAULT_DECAY_FADE_FACTOR) -> float:
    """One step of fade for a stored `ai_research_multiplier`.

    `new = 0.5 + (value - 0.5) * fade_factor`

    The factor is clamped to [0, 1]:
    - `1.0` → identity (no fade).
    - `0.0` → snap to neutral in one step.
    - Default `0.9` → leaves 90% of the deviation each step; 52 successive
      steps leave (0.9 ** 52) ≈ 0.4% of the original — what the weekly job
      uses so a year of untouched ratings converges to neutral.

    The job applies this once per row per ~7 days; touching the slider via the
    `/securities/preference` endpoint resets the stored value (and the
    `ai_research_multiplier_updated_at` clock that gates the next decay).
    """
    normalized_value = normalize_ai_research_multiplier(value)
    try:
        factor = float(fade_factor)
    except (TypeError, ValueError, OverflowError):
        factor = 0.0
    if not math.isfinite(factor):
        factor = 0.0
    factor = max(0.0, min(1.0, factor))
    return NEUTRAL_AI_RESEARCH_MULTIPLIER + (normalized_value - NEUTRAL_AI_RESEARCH_MULTIPLIER) * factor


def preference_tilt(effective_multiplier: float, strength: float) -> float:
    """Turn a stored AI research multiplier into an allocation tilt."""
    try:
        parsed_strength = float(strength)
    except (TypeError, ValueError, OverflowError):
        parsed_strength = 0.0
    if not math.isfinite(parsed_strength):
        parsed_strength = 0.0
    exponent = parsed_strength * (
        normalize_ai_research_multiplier(effective_multiplier) - NEUTRAL_AI_RESEARCH_MULTIPLIER
    )
    return math.exp(max(-20.0, min(20.0, exponent)))


def has_strategic_buy_pressure(
    effective_multiplier: object,
    threshold: object = STRATEGIC_BUY_PRESSURE_THRESHOLD,
) -> bool:
    """Return whether a stored preference is meaningfully above neutral."""
    rating = stored_ai_research_multiplier(effective_multiplier)
    return rating is not None and rating >= normalize_ai_research_multiplier(threshold)


def is_explicit_downgrade(security: dict[str, Any]) -> bool:
    """Return whether a security was *deliberately* rated at or below neutral.

    "Done with this name" — used to make a position a preferred funding source
    (first to be sold, loss or not, when cash is needed elsewhere). It is true
    only when BOTH hold:

    - `ai_research_multiplier <= 0.5` (at or below neutral), and
    - `ai_research_multiplier_updated_at` is present (the slider was actually touched).

    Never-rated securities have a NULL rating and timestamp, so they
    are NOT downgrades — a name nobody has assessed must not be sold at a loss
    just because it has no rating. The weekly decay job only ever fades
    values *toward* 0.5 (never across it) and skips already-neutral rows, so a
    `<= 0.5` value carrying a timestamp always traces back to a deliberate rating.
    """
    if parse_utc_datetime(security.get("ai_research_multiplier_updated_at")) is None:
        return False
    rating = stored_ai_research_multiplier(security.get("ai_research_multiplier"))
    return rating is not None and rating <= NEUTRAL_AI_RESEARCH_MULTIPLIER


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
        # The requested invested total is infeasible. Maximize safe deployment
        # by placing every eligible name at the cap; the planner represents the
        # unavoidable remainder explicitly as cash.
        return {symbol: cap for symbol in normalized}

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


def preference_snapshot(security: dict[str, Any], *, now: datetime | None = None) -> dict[str, float | None]:
    """Return preference info for one security.

    The "effective" value is now identical to the stored value (no read-time
    fade), but we still surface `ai_research_multiplier_age_weeks` so the UI can show
    when the slider was last touched.
    """
    stored = stored_ai_research_multiplier(security.get("ai_research_multiplier"))
    timestamp = security.get("ai_research_multiplier_updated_at")
    weeks = age_weeks(timestamp, now=now) if stored is not None and parse_utc_datetime(timestamp) is not None else None
    return {
        "ai_research_multiplier": stored,
        "ai_research_multiplier_age_weeks": weeks,
    }
