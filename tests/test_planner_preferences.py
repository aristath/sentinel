import pytest

from sentinel.planner.preferences import (
    DEFAULT_DECAY_FADE_FACTOR,
    decayed_user_multiplier,
    has_strategic_buy_pressure,
    is_explicit_downgrade,
    normalize_user_multiplier,
    preference_tilt,
)

# --- is_explicit_downgrade -----------------------------------------------


def test_explicit_downgrade_requires_timestamp():
    """A <= 0.5 value with no timestamp (never rated) is NOT a downgrade."""
    assert is_explicit_downgrade({"user_multiplier": 0.5, "user_multiplier_updated_at": None}) is False
    assert is_explicit_downgrade({"user_multiplier": 0.2}) is False


def test_explicit_downgrade_true_when_rated_at_or_below_neutral():
    assert is_explicit_downgrade({"user_multiplier": 0.5, "user_multiplier_updated_at": "2026-06-01T00:00:00Z"}) is True
    assert is_explicit_downgrade({"user_multiplier": 0.1, "user_multiplier_updated_at": "2026-06-01T00:00:00Z"}) is True


def test_explicit_downgrade_false_above_neutral():
    """An endorsed name (> 0.5) is never a funding-first downgrade."""
    assert (
        is_explicit_downgrade({"user_multiplier": 0.8, "user_multiplier_updated_at": "2026-06-01T00:00:00Z"}) is False
    )


# --- decayed_user_multiplier ---------------------------------------------


def test_decay_moves_above_neutral_value_toward_neutral():
    # 0.7 is 0.2 above neutral; one decay step at 0.9 leaves 0.18 above -> 0.68.
    assert decayed_user_multiplier(0.7, 0.9) == pytest.approx(0.68, abs=1e-9)


def test_decay_moves_below_neutral_value_toward_neutral():
    # 0.3 is 0.2 below neutral; one decay step at 0.9 leaves 0.18 below -> 0.32.
    assert decayed_user_multiplier(0.3, 0.9) == pytest.approx(0.32, abs=1e-9)


def test_decay_leaves_neutral_value_unchanged():
    assert decayed_user_multiplier(0.5, 0.9) == 0.5


def test_decay_with_factor_one_is_identity():
    # No fade applied.
    assert decayed_user_multiplier(0.7, 1.0) == 0.7


def test_decay_with_factor_zero_snaps_to_neutral():
    assert decayed_user_multiplier(0.7, 0.0) == 0.5
    assert decayed_user_multiplier(0.0, 0.0) == 0.5


def test_decay_52_iterations_converges_close_to_neutral():
    """52 weeks of decay at the default factor should land within ~1% of neutral
    for an extreme starting value — the whole point of the fade."""
    value = 1.0
    for _ in range(52):
        value = decayed_user_multiplier(value, DEFAULT_DECAY_FADE_FACTOR)
    assert abs(value - 0.5) < 0.01


def test_decay_normalizes_non_finite_inputs():
    # Non-finite values are treated as neutral (the same convention used by
    # `normalize_user_multiplier`), which means a single decay step leaves
    # them at neutral — there's no "true" extremity to fade from.
    assert decayed_user_multiplier(float("nan"), 0.9) == 0.5
    assert decayed_user_multiplier(float("inf"), 0.9) == 0.5
    assert decayed_user_multiplier(float("-inf"), 0.9) == 0.5


def test_decay_clamps_factor_into_unit_interval():
    # Factors outside [0, 1] are clamped (a 1.5 factor would amplify deviation
    # away from neutral — clearly wrong and never desired).
    assert decayed_user_multiplier(0.7, 1.5) == decayed_user_multiplier(0.7, 1.0)
    assert decayed_user_multiplier(0.7, -0.1) == decayed_user_multiplier(0.7, 0.0)


def test_decay_handles_extreme_values():
    # 0.0 (avoid) → 0.05 above the floor after one step.
    assert decayed_user_multiplier(0.0, 0.9) == pytest.approx(0.05, abs=1e-9)
    assert decayed_user_multiplier(1.0, 0.9) == pytest.approx(0.95, abs=1e-9)


# --- preference_tilt (kept the same) -------------------------------------


def test_non_finite_preference_values_fall_back_to_neutral():
    assert normalize_user_multiplier(float("nan")) == 0.5
    assert normalize_user_multiplier(float("inf")) == 0.5
    assert preference_tilt(float("nan"), 5.0) == 1.0


def test_low_preference_gets_small_strategic_tilt():
    assert preference_tilt(0.02, 5.0) < 0.1


def test_strategic_buy_pressure_requires_meaningfully_positive_preference():
    assert has_strategic_buy_pressure(0.70)
    assert not has_strategic_buy_pressure(0.5)
    assert not has_strategic_buy_pressure(0.699)
    assert has_strategic_buy_pressure(0.55, threshold=0.55)


def test_default_decay_factor_targets_52_week_convergence():
    """Document the design intent — 52 iterations should crush a 0.5-wide
    initial deviation to <1% of original. `math.log` math, not a guess."""
    surviving_fraction = DEFAULT_DECAY_FADE_FACTOR**52
    assert surviving_fraction < 0.01
