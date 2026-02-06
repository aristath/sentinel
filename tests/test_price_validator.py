"""Tests for price validation and interpolation.

These tests verify the intended behavior of the PriceValidator class:
1. Detection of price anomalies (spikes, crashes, outliers)
2. OHLC consistency validation
3. Interpolation of invalid prices
4. Trade blocking for dangerous anomalies
"""

import pytest

from sentinel.price_validator import (
    OHLCValidation,
    PriceValidator,
    check_trade_blocking,
    get_price_anomaly_warning,
)


class TestOHLCValidation:
    """Tests for the OHLCValidation dataclass."""

    def test_all_valid_when_all_true(self):
        """all_valid() returns True only when all components are valid."""
        v = OHLCValidation(open_valid=True, high_valid=True, low_valid=True, close_valid=True)
        assert v.all_valid() is True

    def test_all_valid_false_when_any_invalid(self):
        """all_valid() returns False if any component is invalid."""
        assert OHLCValidation(open_valid=False).all_valid() is False
        assert OHLCValidation(high_valid=False).all_valid() is False
        assert OHLCValidation(low_valid=False).all_valid() is False
        assert OHLCValidation(close_valid=False).all_valid() is False

    def test_needs_interpolation_when_any_invalid(self):
        """needs_interpolation() returns True when any component is invalid."""
        assert OHLCValidation(open_valid=False).needs_interpolation() is True
        assert OHLCValidation(high_valid=False).needs_interpolation() is True

    def test_needs_full_interpolation_only_when_close_invalid(self):
        """needs_full_interpolation() returns True only when close is invalid."""
        assert OHLCValidation(close_valid=False).needs_full_interpolation() is True
        assert OHLCValidation(close_valid=True, open_valid=False).needs_full_interpolation() is False


class TestPriceValidation:
    """Tests for price validation logic."""

    @pytest.fixture
    def validator(self):
        return PriceValidator()

    # =========================================================================
    # Zero/Negative Price Tests
    # =========================================================================

    def test_zero_close_is_invalid(self, validator):
        """A price with close=0 should be fully invalid."""
        price = {"open": 100, "high": 105, "low": 95, "close": 0}
        result = validator.validate_price(price, None, [])
        assert result.close_valid is False
        assert result.reason == "close_zero_or_negative"

    def test_negative_close_is_invalid(self, validator):
        """A price with negative close should be fully invalid."""
        price = {"open": 100, "high": 105, "low": 95, "close": -10}
        result = validator.validate_price(price, None, [])
        assert result.close_valid is False
        assert result.reason == "close_zero_or_negative"

    # =========================================================================
    # OHLC Consistency Tests
    # =========================================================================

    def test_valid_ohlc_passes(self, validator):
        """A valid OHLC price passes validation."""
        price = {"open": 100, "high": 105, "low": 95, "close": 102}
        result = validator.validate_price(price, None, [])
        assert result.all_valid() is True

    def test_high_below_low_is_invalid(self, validator):
        """High < Low is an OHLC consistency violation."""
        price = {"open": 100, "high": 90, "low": 95, "close": 92}
        result = validator.validate_price(price, None, [])
        assert result.high_valid is False
        assert result.low_valid is False
        assert result.reason == "high_below_low"

    def test_high_below_close_is_invalid(self, validator):
        """High < Close violates OHLC consistency."""
        price = {"open": 100, "high": 101, "low": 95, "close": 105}
        result = validator.validate_price(price, None, [])
        assert result.high_valid is False

    def test_high_below_open_is_invalid(self, validator):
        """High < Open violates OHLC consistency."""
        price = {"open": 110, "high": 105, "low": 95, "close": 100}
        result = validator.validate_price(price, None, [])
        assert result.high_valid is False

    def test_low_above_close_is_invalid(self, validator):
        """Low > Close violates OHLC consistency."""
        price = {"open": 100, "high": 105, "low": 102, "close": 98}
        result = validator.validate_price(price, None, [])
        assert result.low_valid is False

    def test_low_above_open_is_invalid(self, validator):
        """Low > Open violates OHLC consistency."""
        price = {"open": 95, "high": 105, "low": 98, "close": 100}
        result = validator.validate_price(price, None, [])
        assert result.low_valid is False

    # =========================================================================
    # Spike Detection Tests (>1000% change)
    # =========================================================================

    def test_spike_detected_over_1000_percent(self, validator):
        """Price increase >1000% from previous day is a spike."""
        previous = {"close": 100}
        # 1100% increase: 100 -> 1200
        price = {"open": 1200, "high": 1250, "low": 1150, "close": 1200}
        result = validator.validate_price(price, previous, [])
        assert result.close_valid is False
        assert result.reason == "spike_detected"

    def test_exactly_1000_percent_is_valid(self, validator):
        """Exactly 1000% increase should be valid (boundary test)."""
        previous = {"close": 100}
        # Exactly 1000% increase: 100 -> 1100
        price = {"open": 1100, "high": 1150, "low": 1050, "close": 1100}
        result = validator.validate_price(price, previous, [])
        # 1000% is the threshold, so 1000% exactly should be valid
        assert result.close_valid is True

    def test_just_over_1000_percent_is_spike(self, validator):
        """Just over 1000% increase should be detected as spike."""
        previous = {"close": 100}
        # 1001% increase: 100 -> 1101
        price = {"open": 1101, "high": 1150, "low": 1050, "close": 1101}
        result = validator.validate_price(price, previous, [])
        assert result.close_valid is False
        assert result.reason == "spike_detected"

    # =========================================================================
    # Crash Detection Tests (<-90% change)
    # =========================================================================

    def test_crash_detected_under_minus_90_percent(self, validator):
        """Price drop >90% from previous day is a crash."""
        previous = {"close": 100}
        # 95% drop: 100 -> 5
        price = {"open": 5, "high": 6, "low": 4, "close": 5}
        result = validator.validate_price(price, previous, [])
        assert result.close_valid is False
        assert result.reason == "crash_detected"

    def test_exactly_90_percent_drop_is_valid(self, validator):
        """Exactly 90% drop should be valid (boundary test)."""
        previous = {"close": 100}
        # Exactly 90% drop: 100 -> 10
        price = {"open": 10, "high": 12, "low": 9, "close": 10}
        result = validator.validate_price(price, previous, [])
        assert result.close_valid is True

    def test_just_over_90_percent_drop_is_crash(self, validator):
        """Just over 90% drop should be detected as crash."""
        previous = {"close": 100}
        # 90.1% drop: 100 -> 9.9
        price = {"open": 9.9, "high": 10, "low": 9, "close": 9.9}
        result = validator.validate_price(price, previous, [])
        assert result.close_valid is False
        assert result.reason == "crash_detected"

    # =========================================================================
    # Average-Based Outlier Detection Tests
    # =========================================================================

    def test_price_too_high_vs_average(self, validator):
        """Price >10x average is flagged as too high."""
        context = [{"close": 100} for _ in range(30)]  # Avg = 100
        price = {"open": 1100, "high": 1150, "low": 1050, "close": 1100}  # 11x avg
        result = validator.validate_price(price, None, context)
        assert result.close_valid is False
        assert result.reason == "price_too_high"

    def test_price_at_10x_average_is_valid(self, validator):
        """Price exactly 10x average should be valid (boundary)."""
        context = [{"close": 100} for _ in range(30)]  # Avg = 100
        price = {"open": 1000, "high": 1050, "low": 950, "close": 1000}  # 10x avg
        result = validator.validate_price(price, None, context)
        # Exactly at threshold should be valid
        assert result.close_valid is True

    def test_price_too_low_vs_average(self, validator):
        """Price <0.1x average is flagged as too low."""
        context = [{"close": 100} for _ in range(30)]  # Avg = 100
        price = {"open": 9, "high": 10, "low": 8, "close": 9}  # 0.09x avg
        result = validator.validate_price(price, None, context)
        assert result.close_valid is False
        assert result.reason == "price_too_low"

    def test_price_at_0_1x_average_is_valid(self, validator):
        """Price exactly 0.1x average should be valid (boundary)."""
        context = [{"close": 100} for _ in range(30)]  # Avg = 100
        price = {"open": 10, "high": 12, "low": 9, "close": 10}  # 0.1x avg
        result = validator.validate_price(price, None, context)
        assert result.close_valid is True

    def test_no_context_skips_average_check(self, validator):
        """Without context data, average-based check is skipped."""
        price = {"open": 1, "high": 2, "low": 0.5, "close": 1}
        result = validator.validate_price(price, None, [])
        assert result.close_valid is True  # Can't determine if abnormal

    # =========================================================================
    # Edge Cases
    # =========================================================================

    def test_missing_ohlc_components_use_close(self, validator):
        """Missing O/H/L components should default to close for validation."""
        price = {"close": 100}  # Missing open, high, low
        result = validator.validate_price(price, None, [])
        assert result.all_valid() is True

    def test_previous_price_with_zero_close_skips_change_check(self, validator):
        """Previous price with close=0 should skip day-over-day check."""
        previous = {"close": 0}
        price = {"open": 100, "high": 105, "low": 95, "close": 100}
        result = validator.validate_price(price, previous, [])
        assert result.all_valid() is True


class TestPriceInterpolation:
    """Tests for price interpolation logic."""

    @pytest.fixture
    def validator(self):
        return PriceValidator()

    # =========================================================================
    # Full Interpolation (when Close is invalid)
    # =========================================================================

    def test_linear_interpolation_with_before_and_after(self, validator):
        """With both before and after prices, use linear interpolation."""
        price = {"open": 0, "high": 0, "low": 0, "close": 0, "date": "2024-01-02"}
        validation = OHLCValidation(close_valid=False)
        before = [{"close": 100, "open": 98, "high": 105, "low": 95}]
        after = [{"close": 110, "open": 108, "high": 115, "low": 105}]

        result, method = validator.interpolate_price(price, validation, before, after)

        assert method == "linear"
        # Close should be midpoint: (100 + 110) / 2 = 105
        assert result["close"] == 105.0

    def test_forward_fill_when_no_after(self, validator):
        """Without after prices, use forward fill from before."""
        price = {"open": 0, "high": 0, "low": 0, "close": 0}
        validation = OHLCValidation(close_valid=False)
        before = [{"close": 100, "open": 98, "high": 105, "low": 95}]
        after = []

        result, method = validator.interpolate_price(price, validation, before, after)

        assert method == "forward_fill"
        assert result["close"] == 100
        assert result["open"] == 98
        assert result["high"] == 105
        assert result["low"] == 95

    def test_backward_fill_when_no_before(self, validator):
        """Without before prices, use backward fill from after."""
        price = {"open": 0, "high": 0, "low": 0, "close": 0}
        validation = OHLCValidation(close_valid=False)
        before = []
        after = [{"close": 110, "open": 108, "high": 115, "low": 105}]

        result, method = validator.interpolate_price(price, validation, before, after)

        assert method == "backward_fill"
        assert result["close"] == 110

    def test_no_interpolation_when_no_context(self, validator):
        """Without any context, can't interpolate."""
        price = {"open": 0, "high": 0, "low": 0, "close": 0}
        validation = OHLCValidation(close_valid=False)

        result, method = validator.interpolate_price(price, validation, [], [])

        assert method == "no_interpolation"

    # =========================================================================
    # Selective Interpolation (when Close is valid but others invalid)
    # =========================================================================

    def test_selective_interpolation_fixes_high_only(self, validator):
        """Selective interpolation fixes only invalid components."""
        price = {"open": 100, "high": 90, "low": 95, "close": 100}  # high is wrong
        validation = OHLCValidation(high_valid=False, reason="high_below_close")
        before = [{"close": 98, "high": 103}]  # ratio = 103/98 ≈ 1.051
        after = []

        result, method = validator.interpolate_price(price, validation, before, after)

        assert method == "selective"
        assert result["close"] == 100  # Unchanged
        # High should be recalculated based on typical ratio
        assert result["high"] >= result["close"]

    def test_selective_interpolation_fixes_low_only(self, validator):
        """Selective interpolation fixes only the low component."""
        price = {"open": 100, "high": 105, "low": 102, "close": 98}  # low > close
        validation = OHLCValidation(low_valid=False, reason="low_above_close")
        before = [{"close": 100, "low": 97}]  # ratio = 97/100 = 0.97
        after = []

        result, method = validator.interpolate_price(price, validation, before, after)

        assert method == "selective"
        assert result["close"] == 98  # Unchanged
        assert result["low"] <= result["close"]

    def test_selective_interpolation_fixes_open(self, validator):
        """Open is interpolated from previous close."""
        price = {"open": 200, "high": 105, "low": 95, "close": 100}  # open seems wrong
        validation = OHLCValidation(open_valid=False)
        before = [{"close": 99}]
        after = []

        result, method = validator.interpolate_price(price, validation, before, after)

        assert method == "selective"
        assert result["open"] == 99  # Previous close

    # =========================================================================
    # OHLC Consistency After Interpolation
    # =========================================================================

    def test_interpolation_ensures_ohlc_consistency(self, validator):
        """Interpolated prices must have valid OHLC relationships."""
        price = {"open": 100, "high": 90, "low": 110, "close": 100}  # All wrong
        validation = OHLCValidation(high_valid=False, low_valid=False)
        before = [{"close": 100, "high": 105, "low": 95}]
        after = []

        result, method = validator.interpolate_price(price, validation, before, after)

        # After interpolation, OHLC must be consistent
        assert result["high"] >= result["low"]
        assert result["high"] >= result["open"]
        assert result["high"] >= result["close"]
        assert result["low"] <= result["open"]
        assert result["low"] <= result["close"]


class TestValidateAndInterpolate:
    """Tests for the full validate_and_interpolate pipeline."""

    @pytest.fixture
    def validator(self):
        return PriceValidator()

    def test_valid_prices_pass_through_unchanged(self, validator):
        """Valid prices should pass through without modification."""
        prices = [
            {"date": "2024-01-01", "open": 100, "high": 105, "low": 95, "close": 102},
            {"date": "2024-01-02", "open": 102, "high": 108, "low": 100, "close": 106},
            {"date": "2024-01-03", "open": 106, "high": 110, "low": 104, "close": 108},
        ]
        result = validator.validate_and_interpolate(prices)

        assert len(result) == 3
        assert result[0]["close"] == 102
        assert result[1]["close"] == 106
        assert result[2]["close"] == 108

    def test_spike_in_middle_is_interpolated(self, validator):
        """A spike in the middle of the series should be interpolated."""
        prices = [
            {"date": "2024-01-01", "open": 100, "high": 105, "low": 95, "close": 100},
            {"date": "2024-01-02", "open": 100000, "high": 100000, "low": 100000, "close": 100000},  # Spike!
            {"date": "2024-01-03", "open": 102, "high": 108, "low": 100, "close": 102},
        ]
        result = validator.validate_and_interpolate(prices)

        assert len(result) == 3
        # The spike should be interpolated to something reasonable
        assert result[1]["close"] < 1000  # Not 100000
        assert result[1]["close"] > 50  # Reasonable range

    def test_crash_in_middle_is_interpolated(self, validator):
        """A crash in the middle should be interpolated."""
        prices = [
            {"date": "2024-01-01", "open": 100, "high": 105, "low": 95, "close": 100},
            {"date": "2024-01-02", "open": 1, "high": 1, "low": 1, "close": 1},  # 99% crash
            {"date": "2024-01-03", "open": 102, "high": 108, "low": 100, "close": 102},
        ]
        result = validator.validate_and_interpolate(prices)

        # The crash should be interpolated
        assert result[1]["close"] > 50  # Not 1

    def test_empty_prices_returns_empty(self, validator):
        """Empty input should return empty output."""
        result = validator.validate_and_interpolate([])
        assert result == []

    def test_single_valid_price_passes(self, validator):
        """Single valid price should pass through."""
        prices = [{"date": "2024-01-01", "open": 100, "high": 105, "low": 95, "close": 100}]
        result = validator.validate_and_interpolate(prices)
        assert len(result) == 1
        assert result[0]["close"] == 100

    def test_first_price_invalid_uses_backward_fill(self, validator):
        """First price being invalid should use backward fill."""
        prices = [
            {"date": "2024-01-01", "open": 0, "high": 0, "low": 0, "close": 0},  # Invalid
            {"date": "2024-01-02", "open": 100, "high": 105, "low": 95, "close": 100},
        ]
        result = validator.validate_and_interpolate(prices)

        assert len(result) == 2
        # First price should be filled from second
        assert result[0]["close"] == 100


class TestTradeBlocking:
    """Tests for trade blocking logic."""

    def test_normal_price_allows_trade(self):
        """Normal price within range allows trading."""
        current = 100
        history = [100 + i * 0.5 for i in range(30)]  # Slight uptrend around 100
        allow, reason = check_trade_blocking(current, history)
        assert allow is True
        assert reason == ""

    def test_high_anomaly_blocks_trade(self):
        """Price >10x average blocks trading."""
        current = 1100  # 11x average of 100
        history = [100.0] * 30
        allow, reason = check_trade_blocking(current, history)
        assert allow is False
        assert "high price anomaly" in reason

    def test_low_anomaly_allows_trade(self):
        """Price <0.1x average still allows trading (might be opportunity)."""
        current = 5  # 0.05x average of 100
        history = [100.0] * 30
        allow, reason = check_trade_blocking(current, history)
        # Low anomaly allows trades per the design (might be genuine crash)
        assert allow is True

    def test_insufficient_history_allows_trade(self):
        """Less than 30 days of history allows trading."""
        current = 1000
        history = [100.0] * 20  # Only 20 days
        allow, reason = check_trade_blocking(current, history)
        assert allow is True

    def test_zero_current_price_blocks_trade(self):
        """Zero current price blocks trading."""
        allow, reason = check_trade_blocking(0, [100] * 30)
        assert allow is False
        assert "zero or negative" in reason

    def test_negative_current_price_blocks_trade(self):
        """Negative current price blocks trading."""
        allow, reason = check_trade_blocking(-10, [100] * 30)
        assert allow is False


class TestPriceAnomalyWarning:
    """Tests for price anomaly warning messages."""

    def test_no_warning_for_normal_price(self):
        """Normal price returns no warning."""
        warning = get_price_anomaly_warning(100, [100] * 30)
        assert warning is None

    def test_warning_for_spike(self):
        """Price spike returns warning with details."""
        warning = get_price_anomaly_warning(1100, [100] * 30)
        assert warning is not None
        assert "spike" in warning.lower()
        assert "blocked" in warning.lower()

    def test_warning_for_crash(self):
        """Price crash returns warning (but trades not blocked)."""
        warning = get_price_anomaly_warning(5, [100] * 30)
        assert warning is not None
        assert "crash" in warning.lower()
        assert "verify" in warning.lower()

    def test_warning_for_zero_price(self):
        """Zero price returns warning."""
        warning = get_price_anomaly_warning(0, [100] * 30)
        assert warning is not None
        assert "zero or negative" in warning.lower()

    def test_no_warning_insufficient_history(self):
        """Insufficient history returns no warning."""
        warning = get_price_anomaly_warning(1000, [100] * 10)
        assert warning is None
