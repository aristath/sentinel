"""Tests for regime detection and ML prediction dampening."""

from sentinel.regime_quote import apply_regime_dampening, calculate_regime_score


class TestCalculateRegimeScore:
    """Tests for calculate_regime_score function."""

    def test_bullish_regime(self):
        """Strong positive momentum + high in range = bullish."""
        quote = {"chg5": 2, "chg22": 8, "chg110": 25, "chg220": 40, "ltp": 95, "x_max": 100, "x_min": 60}
        score = calculate_regime_score(quote)
        assert score > 0.5, f"Expected bullish (>0.5), got {score}"

    def test_bearish_regime(self):
        """Strong negative momentum + low in range = bearish."""
        quote = {"chg5": -3, "chg22": -10, "chg110": -30, "chg220": -45, "ltp": 65, "x_max": 100, "x_min": 60}
        score = calculate_regime_score(quote)
        assert score < -0.5, f"Expected bearish (<-0.5), got {score}"

    def test_neutral_regime(self):
        """Mixed signals = neutral."""
        quote = {"chg5": 1, "chg22": -2, "chg110": 5, "chg220": -3, "ltp": 80, "x_max": 100, "x_min": 60}
        score = calculate_regime_score(quote)
        assert -0.3 < score < 0.3, f"Expected neutral, got {score}"

    def test_missing_data_returns_neutral(self):
        """Missing data returns neutral (0.0)."""
        score = calculate_regime_score({})
        assert score == 0.0

    def test_none_values_treated_as_zero(self):
        """None values in quote data are treated as zero."""
        quote = {"chg5": None, "chg22": None, "chg110": None, "chg220": None, "ltp": None, "x_max": None, "x_min": None}
        score = calculate_regime_score(quote)
        assert score == 0.0

    def test_score_clamped_to_range(self):
        """Extreme values should be clamped to [-1, 1]."""
        # Extremely bullish
        quote = {"chg5": 100, "chg22": 200, "chg110": 300, "chg220": 400, "ltp": 100, "x_max": 100, "x_min": 10}
        score = calculate_regime_score(quote)
        assert score <= 1.0

        # Extremely bearish
        quote = {"chg5": -100, "chg22": -200, "chg110": -300, "chg220": -400, "ltp": 10, "x_max": 100, "x_min": 10}
        score = calculate_regime_score(quote)
        assert score >= -1.0

    def test_position_contribution(self):
        """Position in 52-week range affects score."""
        # Same momentum, different positions
        base = {"chg5": 0, "chg22": 0, "chg110": 0, "chg220": 0}

        # At 52-week high
        high_quote = {**base, "ltp": 100, "x_max": 100, "x_min": 50}
        high_score = calculate_regime_score(high_quote)

        # At 52-week low
        low_quote = {**base, "ltp": 50, "x_max": 100, "x_min": 50}
        low_score = calculate_regime_score(low_quote)

        assert high_score > low_score


class TestApplyRegimeDampening:
    """Tests for apply_regime_dampening function."""

    def test_ml_bullish_regime_bearish_dampens(self):
        """ML bullish + regime bearish = dampen."""
        result = apply_regime_dampening(0.08, -0.7)
        assert result < 0.08
        assert result > 0.08 * 0.6  # Max 40% dampening
        # Expected: 0.08 * (1 - 0.7 * 0.4) = 0.08 * 0.72 = 0.0576
        assert abs(result - 0.0576) < 0.001

    def test_ml_bearish_regime_bullish_dampens(self):
        """ML bearish + regime bullish = dampen."""
        result = apply_regime_dampening(-0.05, 0.8)
        assert result > -0.05
        assert result < -0.05 * 0.6
        # Expected: -0.05 * (1 - 0.8 * 0.4) = -0.05 * 0.68 = -0.034
        assert abs(result - (-0.034)) < 0.001

    def test_no_dampening_ml_bullish_regime_bullish(self):
        """ML bullish + regime bullish = no dampening."""
        result = apply_regime_dampening(0.08, 0.6)
        assert result == 0.08

    def test_no_dampening_ml_bearish_regime_bearish(self):
        """ML bearish + regime bearish = no dampening."""
        result = apply_regime_dampening(-0.05, -0.7)
        assert result == -0.05

    def test_no_dampening_neutral_regime(self):
        """Neutral regime (0) = no dampening."""
        result = apply_regime_dampening(0.08, 0.0)
        assert result == 0.08

    def test_no_dampening_ml_zero(self):
        """Zero ML prediction = no change."""
        result = apply_regime_dampening(0.0, -0.5)
        assert result == 0.0

    def test_custom_max_dampening(self):
        """Custom max_dampening parameter."""
        result = apply_regime_dampening(0.10, -1.0, max_dampening=0.5)
        # Should dampen by 50% max at regime -1.0
        assert result == 0.05

    def test_max_dampening_at_extreme_regime(self):
        """At regime = -1.0 or +1.0, dampening should be at max."""
        # Bullish ML, maximum bearish regime
        result = apply_regime_dampening(0.10, -1.0, max_dampening=0.4)
        # Dampening = 1.0 * 0.4 = 0.4 -> result = 0.10 * 0.6 = 0.06
        assert abs(result - 0.06) < 0.001

        # Bearish ML, maximum bullish regime
        result = apply_regime_dampening(-0.10, 1.0, max_dampening=0.4)
        # Dampening = 1.0 * 0.4 = 0.4 -> result = -0.10 * 0.6 = -0.06
        assert abs(result - (-0.06)) < 0.001

    def test_mild_disagreement_mild_dampening(self):
        """Mild regime disagreement produces mild dampening."""
        # ML bullish, mildly bearish regime
        result = apply_regime_dampening(0.08, -0.3)
        # Dampening = 0.3 * 0.4 = 0.12 -> result = 0.08 * 0.88 = 0.0704
        assert abs(result - 0.0704) < 0.001


class TestRegimeScoreInterpretation:
    """Tests for regime score interpretation ranges."""

    def test_strong_bullish_range(self):
        """Score > 0.5 indicates strong bullish."""
        quote = {"chg5": 5, "chg22": 15, "chg110": 35, "chg220": 50, "ltp": 98, "x_max": 100, "x_min": 50}
        score = calculate_regime_score(quote)
        assert score > 0.5

    def test_strong_bearish_range(self):
        """Score < -0.5 indicates strong bearish."""
        quote = {"chg5": -5, "chg22": -15, "chg110": -35, "chg220": -50, "ltp": 52, "x_max": 100, "x_min": 50}
        score = calculate_regime_score(quote)
        assert score < -0.5


class TestEdgeCases:
    """Edge case tests."""

    def test_zero_range_52_week(self):
        """x_max == x_min should use neutral position."""
        quote = {"chg5": 0, "chg22": 0, "chg110": 0, "chg220": 0, "ltp": 100, "x_max": 100, "x_min": 100}
        score = calculate_regime_score(quote)
        # With zero momentum and neutral position, score should be 0
        assert score == 0.0

    def test_negative_ltp(self):
        """Negative or zero ltp should use neutral position."""
        quote = {"chg5": 0, "chg22": 0, "chg110": 0, "chg220": 0, "ltp": 0, "x_max": 100, "x_min": 50}
        score = calculate_regime_score(quote)
        assert score == 0.0

    def test_very_small_ml_return(self):
        """Very small returns should still be dampened proportionally."""
        result = apply_regime_dampening(0.001, -0.5)
        expected = 0.001 * (1 - 0.5 * 0.4)
        assert abs(result - expected) < 0.0001
