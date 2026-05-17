from datetime import datetime, timedelta, timezone

from sentinel.planner.preferences import (
    effective_user_multiplier,
    has_strategic_buy_pressure,
    normalize_user_multiplier,
    preference_tilt,
)


def test_effective_user_multiplier_fades_toward_neutral():
    now = datetime(2026, 5, 17, tzinfo=timezone.utc)
    updated_at = now - timedelta(weeks=4)

    effective = effective_user_multiplier(0.9, updated_at.isoformat(), 0.9, now=now)

    assert 0.76 < effective < 0.77


def test_missing_or_invalid_preference_timestamp_fades_to_neutral():
    assert effective_user_multiplier(0.9, None, 0.9) == 0.5
    assert effective_user_multiplier(0.1, "not-a-date", 0.9) == 0.5


def test_non_finite_preference_values_fall_back_to_neutral():
    assert normalize_user_multiplier(float("nan")) == 0.5
    assert normalize_user_multiplier(float("inf")) == 0.5
    assert preference_tilt(float("nan"), 5.0) == 1.0


def test_low_effective_preference_gets_small_strategic_tilt():
    assert preference_tilt(0.02, 5.0) < 0.1


def test_strategic_buy_pressure_requires_meaningfully_positive_preference():
    assert has_strategic_buy_pressure(0.55)
    assert not has_strategic_buy_pressure(0.5)
    assert not has_strategic_buy_pressure(0.549)
