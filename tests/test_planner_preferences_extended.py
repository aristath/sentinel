"""Tests for preferences.py — additional coverage for missing functions."""

from datetime import datetime, timezone

import pytest

from sentinel.planner.preferences import (
    age_weeks,
    apply_max_cap,
    normalize_user_multiplier,
    normalize_weights,
    parse_utc_datetime,
    preference_snapshot,
    preference_tilt,
    utc_now_iso,
)


class TestParseUtcDatetime:
    """Tests for parse_utc_datetime function."""

    def test_none_returns_none(self):
        assert parse_utc_datetime(None) is None

    def test_int_timestamp(self):
        result = parse_utc_datetime(1700000000)
        assert result is not None
        assert result.tzinfo is not None

    def test_float_timestamp(self):
        result = parse_utc_datetime(1700000000.5)
        assert result is not None

    def test_iso_string_with_z(self):
        result = parse_utc_datetime("2025-01-15T10:30:00Z")
        assert result is not None
        assert result.tzinfo is not None

    def test_iso_string_with_offset(self):
        result = parse_utc_datetime("2025-01-15T10:30:00+00:00")
        assert result is not None

    def test_iso_string_without_tz(self):
        result = parse_utc_datetime("2025-01-15T10:30:00")
        assert result is not None
        assert result.tzinfo is not None

    def test_empty_string_returns_none(self):
        assert parse_utc_datetime("") is None

    def test_whitespace_string_returns_none(self):
        assert parse_utc_datetime("   ") is None

    def test_invalid_string_returns_none(self):
        assert parse_utc_datetime("not-a-date") is None

    def test_non_string_returns_none(self):
        assert parse_utc_datetime(["2025-01-01"]) is None


class TestAgeWeeks:
    """Tests for age_weeks function."""

    def test_none_age(self):
        assert age_weeks(None) == 0.0

    def test_exact_now(self):
        now = datetime.now(timezone.utc)
        age = age_weeks(now)
        assert age >= 0.0
        assert age < 1.0 / 7  # less than a day

    def test_one_week_ago(self):
        one_week_ago = datetime.now(timezone.utc).timestamp() - 7 * 86400
        age = age_weeks(one_week_ago)
        assert abs(age - 1.0) < 0.01

    def test_two_weeks_ago(self):
        two_weeks_ago = datetime.now(timezone.utc).timestamp() - 14 * 86400
        age = age_weeks(two_weeks_ago)
        assert abs(age - 2.0) < 0.01

    def test_past_date_returns_positive(self):
        past = datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat()
        age = age_weeks(past)
        assert age > 0

    def test_future_date_returns_zero(self):
        future = datetime(2030, 1, 1, tzinfo=timezone.utc).isoformat()
        age = age_weeks(future)
        assert age == 0.0

    def test_custom_now(self):
        now = datetime(2025, 6, 15, tzinfo=timezone.utc)
        one_week_ago = datetime(2025, 6, 8, tzinfo=timezone.utc).isoformat()
        age = age_weeks(one_week_ago, now=now)
        assert abs(age - 1.0) < 0.01


class TestNormalizeWeights:
    """Tests for normalize_weights function."""

    def test_normal_case(self):
        weights = {"A": 1.0, "B": 2.0, "C": 3.0}
        result = normalize_weights(weights)
        assert abs(sum(result.values()) - 1.0) < 1e-9
        assert result["B"] == pytest.approx(2.0 / 6.0)

    def test_single_weight(self):
        weights = {"A": 1.0}
        result = normalize_weights(weights)
        assert result == {"A": 1.0}

    def test_empty_dict(self):
        result = normalize_weights({})
        assert result == {}

    def test_all_zero_weights(self):
        weights = {"A": 0.0, "B": 0.0}
        result = normalize_weights(weights)
        assert result == {}

    def test_negative_weights_ignored(self):
        weights = {"A": 1.0, "B": -1.0, "C": 2.0}
        result = normalize_weights(weights)
        assert "B" not in result
        assert abs(sum(result.values()) - 1.0) < 1e-9

    def test_nan_weights_ignored(self):
        weights = {"A": 1.0, "B": float("nan"), "C": 2.0}
        result = normalize_weights(weights)
        assert "B" not in result

    def test_inf_weights_ignored(self):
        weights = {"A": 1.0, "B": float("inf"), "C": 2.0}
        result = normalize_weights(weights)
        assert "B" not in result

    def test_non_numeric_ignored(self):
        weights = {"A": 1.0, "B": "not-a-number", "C": 2.0}
        result = normalize_weights(weights)
        assert "B" not in result

    def test_preserves_relative_ratios(self):
        weights = {"A": 1.0, "B": 3.0}
        result = normalize_weights(weights)
        assert result["B"] == pytest.approx(3 * result["A"])


class TestApplyMaxCap:
    """Tests for apply_max_cap function."""

    def test_no_cap_exceeded(self):
        weights = {"A": 0.2, "B": 0.3, "C": 0.5}
        result = apply_max_cap(weights, 0.5)
        assert result == {"A": 0.2, "B": 0.3, "C": 0.5}

    def test_cap_exceeded_waterfill(self):
        weights = {"A": 0.4, "B": 0.3, "C": 0.3}
        result = apply_max_cap(weights, 0.35)
        # A is capped at 0.35, excess redistributed to B and C
        assert result["A"] == 0.35
        assert result["B"] + result["C"] + result["A"] == pytest.approx(1.0)

    def test_all_exceed_cap(self):
        weights = {"A": 0.4, "B": 0.4, "C": 0.2}
        result = apply_max_cap(weights, 0.3)
        # The full target is infeasible, so every eligible name is filled to the
        # safe cap and the planner represents the remaining 10% as cash.
        assert result["A"] == 0.3
        assert result["B"] == 0.3
        assert result["C"] == 0.3
        assert sum(result.values()) == pytest.approx(0.9)

    def test_empty_dict(self):
        result = apply_max_cap({}, 0.5)
        assert result == {}

    def test_zero_cap(self):
        result = apply_max_cap({"A": 0.5, "B": 0.5}, 0.0)
        assert result == {}

    def test_cap_above_one(self):
        weights = {"A": 0.3, "B": 0.7}
        result = apply_max_cap(weights, 2.0)
        assert result == {"A": 0.3, "B": 0.7}

    def test_single_symbol_at_cap(self):
        weights = {"A": 1.0}
        result = apply_max_cap(weights, 0.5)
        # len(normalized) * cap = 1 * 0.5 = 0.5 < 1.0, so capped at 0.5
        assert result == {"A": 0.5}

    def test_many_symbols_below_cap(self):
        weights = {f"S{i}": 0.1 for i in range(10)}
        result = apply_max_cap(weights, 0.2)
        assert result == weights

    def test_mixed_above_and_below_cap(self):
        weights = {"A": 0.5, "B": 0.1, "C": 0.1, "D": 0.1, "E": 0.1, "F": 0.1}
        result = apply_max_cap(weights, 0.2)
        assert result["A"] == 0.2
        # Remaining 0.8 distributed among B,C,D,E,F
        remaining = sum(result[k] for k in ["B", "C", "D", "E", "F"])
        assert remaining == pytest.approx(0.8)
        assert all(result[k] <= 0.2 for k in ["B", "C", "D", "E", "F"])


class TestPreferenceSnapshot:
    """Tests for preference_snapshot function."""

    def test_basic_snapshot(self):
        security = {
            "user_multiplier": 0.8,
            "user_multiplier_updated_at": datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(),
        }
        now = datetime(2025, 2, 1, tzinfo=timezone.utc)
        snap = preference_snapshot(security, now=now)
        assert snap["user_multiplier"] == 0.8
        assert snap["user_multiplier_age_weeks"] > 0

    def test_neutral_multiplier(self):
        security = {"user_multiplier": 0.5}
        snap = preference_snapshot(security)
        assert snap["user_multiplier"] == 0.5

    def test_missing_updated_at(self):
        security = {"user_multiplier": 0.8}
        snap = preference_snapshot(security)
        assert snap["user_multiplier"] == 0.8
        # age should be 0 since no updated_at
        assert snap["user_multiplier_age_weeks"] == 0.0

    def test_missing_multiplier_defaults_to_neutral(self):
        security = {}
        snap = preference_snapshot(security)
        assert snap["user_multiplier"] == 0.5

    def test_clamped_multiplier(self):
        security = {"user_multiplier": 1.5}
        snap = preference_snapshot(security)
        assert snap["user_multiplier"] == 1.0

    def test_clamped_multiplier_below_zero(self):
        security = {"user_multiplier": -0.5}
        snap = preference_snapshot(security)
        assert snap["user_multiplier"] == 0.0


class TestUtcNowIso:
    """Tests for utc_now_iso function."""

    def test_returns_string(self):
        result = utc_now_iso()
        assert isinstance(result, str)

    def test_parses_to_utc_datetime(self):
        from sentinel.planner.preferences import parse_utc_datetime

        result = utc_now_iso()
        dt = parse_utc_datetime(result)
        assert dt is not None
        assert dt.tzinfo is not None


class TestNormalizeUserMultiplierEdgeCases:
    """Additional edge cases for normalize_user_multiplier."""

    def test_string_number(self):
        assert normalize_user_multiplier("0.8") == 0.8

    def test_string_zero(self):
        assert normalize_user_multiplier("0") == 0.0

    def test_string_one(self):
        assert normalize_user_multiplier("1") == 1.0

    def test_negative_string(self):
        assert normalize_user_multiplier("-0.5") == 0.0

    def test_above_one_string(self):
        assert normalize_user_multiplier("1.5") == 1.0

    def test_none(self):
        assert normalize_user_multiplier(None) == 0.5

    def test_boolean_true(self):
        assert normalize_user_multiplier(True) == 1.0

    def test_boolean_false(self):
        assert normalize_user_multiplier(False) == 0.0


class TestPreferenceTiltEdgeCases:
    """Additional edge cases for preference_tilt."""

    def test_neutral_multiplier(self):
        assert preference_tilt(0.5, 5.0) == pytest.approx(1.0)

    def test_zero_strength(self):
        assert preference_tilt(0.8, 0.0) == pytest.approx(1.0)

    def test_high_strength_extreme(self):
        result = preference_tilt(1.0, 10.0)
        assert result > 1.0

    def test_low_strength_extreme(self):
        result = preference_tilt(0.0, 10.0)
        assert result < 1.0
