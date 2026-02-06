"""Tests for regime detection and ML prediction dampening."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from sentinel_ml.regime_quote import (
    apply_regime_dampening,
    calculate_regime_score,
    get_regime_adjusted_return,
    quote_data_from_prices,
)


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


class TestQuoteDataFromPrices:
    """Tests for quote_data_from_prices (historical OHLCV to quote_data shape)."""

    def test_list_dict_newest_first_returns_ltp_chg_x(self):
        """Given list[dict] newest first, returns ltp, chg5/chg22/chg110/chg220, x_max/x_min."""
        # Row 0 = newest (today), row i = i days ago
        prices = [{"date": f"d{i}", "close": 100.0 - (i * 0.1)} for i in range(300)]
        result = quote_data_from_prices(prices)
        assert "ltp" in result
        assert result["ltp"] == 100.0
        assert "chg5" in result
        assert "chg22" in result
        assert "chg110" in result
        assert "chg220" in result
        assert "x_max" in result
        assert "x_min" in result

    def test_chg5_from_close_delta(self):
        """chg5 is (close - close_5d_ago) / close_5d_ago * 100."""
        # Newest first: row 0 close=110, row 5 close=100
        prices = [{"date": f"d{i}", "close": 110 - i * 2} for i in range(10)]
        result = quote_data_from_prices(prices)
        # Row 0 close=110, row 5 close=100 -> chg5 = (110-100)/100*100 = 10
        assert abs(result["chg5"] - 10.0) < 0.01

    def test_52_week_high_low_from_close(self):
        """x_max/x_min are max/min of close over up to 252 rows."""
        # Newest first: row 0 .. 251 used for 52-week
        prices = [{"date": f"d{i}", "close": 50 + (i % 100)} for i in range(300)]
        result = quote_data_from_prices(prices)
        assert result["x_max"] == 149  # max of 50 + (i % 100) in first 252
        assert result["x_min"] == 50

    def test_fewer_than_252_rows_uses_full_range(self):
        """When fewer than 252 rows, x_max/x_min use full range."""
        prices = [{"date": f"d{i}", "close": 100 + i} for i in range(100)]
        result = quote_data_from_prices(prices)
        assert result["x_min"] == 100
        assert result["x_max"] == 199

    def test_dataframe_input(self):
        """Accepts DataFrame with date, close columns (newest first)."""
        import pandas as pd

        df = pd.DataFrame([{"date": "2024-01-02", "close": 100}, {"date": "2024-01-01", "close": 98}])
        result = quote_data_from_prices(df)
        assert result["ltp"] == 100
        assert "chg5" in result


class TestGetRegimeAdjustedReturnWithQuoteData:
    """Tests for get_regime_adjusted_return with optional quote_data."""

    @pytest.mark.asyncio
    async def test_when_quote_data_provided_no_db_call(self):
        """When quote_data is provided, db.get_security is not called."""
        db = MagicMock()
        db.get_security = AsyncMock()
        quote_data = {"chg5": 2, "chg22": 5, "chg110": 10, "chg220": 15, "ltp": 100, "x_max": 110, "x_min": 90}
        adjusted, regime_score, dampening = await get_regime_adjusted_return("SYM", 0.05, db, quote_data=quote_data)
        db.get_security.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_when_quote_data_provided_returns_from_that_data(self):
        """When quote_data is provided, returns (adjusted_return, regime_score, dampening) from it."""
        db = MagicMock()
        quote_data = {"chg5": -5, "chg22": -10, "chg110": -20, "chg220": -30, "ltp": 80, "x_max": 100, "x_min": 60}
        adjusted, regime_score, dampening = await get_regime_adjusted_return("SYM", 0.08, db, quote_data=quote_data)
        assert regime_score < 0
        assert adjusted < 0.08  # dampened
        assert dampening >= 0

    @pytest.mark.asyncio
    async def test_when_quote_data_none_uses_db(self):
        """When quote_data is None, loads from db.get_security."""
        db = MagicMock()
        db.get_security = AsyncMock(
            return_value={
                "quote_data": (
                    '{"chg5": 0, "chg22": 0, "chg110": 0, "chg220": 0, "ltp": 100, "x_max": 100, "x_min": 100}'
                )
            }
        )
        adjusted, regime_score, dampening = await get_regime_adjusted_return("SYM", 0.05, db)
        db.get_security.assert_awaited_once_with("SYM")
        assert adjusted == 0.05  # neutral regime, no dampening
