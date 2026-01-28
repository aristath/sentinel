"""Tests for ML feature extraction.

These tests verify the intended behavior of the FeatureExtractor:
1. Correct calculation of returns over various periods
2. Proper normalization of price position
3. Accurate volatility calculations
4. Volume metrics
5. Technical indicators (RSI, MACD, Bollinger)
6. Handling of edge cases and missing data
"""

import numpy as np
import pandas as pd
import pytest

from sentinel.ml_features import (
    DEFAULT_FEATURES,
    FEATURE_NAMES,
    NUM_FEATURES,
    FeatureExtractor,
    features_to_array,
    validate_features,
)


class TestFeatureDefinitions:
    """Tests for feature name definitions and constants."""

    def test_feature_count_is_14(self):
        """There should be exactly 14 features."""
        assert NUM_FEATURES == 14
        assert len(FEATURE_NAMES) == 14

    def test_all_features_have_defaults(self):
        """Every feature must have a default value."""
        for name in FEATURE_NAMES:
            assert name in DEFAULT_FEATURES, f"Missing default for {name}"

    def test_feature_names_are_unique(self):
        """Feature names must be unique."""
        assert len(FEATURE_NAMES) == len(set(FEATURE_NAMES))

    def test_default_features_are_reasonable(self):
        """Default feature values should be sensible neutral values."""
        # Returns should default to 0 (no change)
        assert DEFAULT_FEATURES["return_1d"] == 0.0
        assert DEFAULT_FEATURES["return_5d"] == 0.0
        assert DEFAULT_FEATURES["return_20d"] == 0.0
        assert DEFAULT_FEATURES["return_60d"] == 0.0

        # Price normalized to MA should be 0 (at average)
        assert DEFAULT_FEATURES["price_normalized"] == 0.0

        # Volatility should be reasonable small positive
        assert DEFAULT_FEATURES["volatility_10d"] > 0
        assert DEFAULT_FEATURES["volatility_30d"] > 0

        # RSI should be neutral (0.5 = 50)
        assert DEFAULT_FEATURES["rsi_14"] == 0.5

        # Sentiment should be neutral
        assert DEFAULT_FEATURES["sentiment_score"] == 0.5


class TestFeaturesToArray:
    """Tests for features_to_array conversion."""

    def test_converts_to_correct_shape(self):
        """Output should be 1D array of NUM_FEATURES length."""
        arr = features_to_array(DEFAULT_FEATURES)
        assert arr.shape == (NUM_FEATURES,)

    def test_preserves_feature_order(self):
        """Features must be in the exact order defined in FEATURE_NAMES."""
        features = {name: float(i) for i, name in enumerate(FEATURE_NAMES)}
        arr = features_to_array(features)
        for i, name in enumerate(FEATURE_NAMES):
            assert arr[i] == float(i), f"Feature {name} at wrong position"

    def test_missing_features_use_defaults(self):
        """Missing features should use default values."""
        partial = {"return_1d": 0.05, "rsi_14": 0.7}
        arr = features_to_array(partial)

        # Check specified values are correct
        return_1d_idx = FEATURE_NAMES.index("return_1d")
        rsi_idx = FEATURE_NAMES.index("rsi_14")
        assert arr[return_1d_idx] == 0.05
        assert arr[rsi_idx] == 0.7

        # Check unspecified use defaults
        vol_10d_idx = FEATURE_NAMES.index("volatility_10d")
        assert arr[vol_10d_idx] == DEFAULT_FEATURES["volatility_10d"]

    def test_empty_dict_uses_all_defaults(self):
        """Empty dict should produce array of all defaults."""
        arr = features_to_array({})
        expected = features_to_array(DEFAULT_FEATURES)
        np.testing.assert_array_equal(arr, expected)


class TestValidateFeatures:
    """Tests for feature validation and cleaning."""

    def test_valid_features_pass_through(self):
        """Valid features should pass through unchanged."""
        features = DEFAULT_FEATURES.copy()
        features["return_1d"] = 0.05
        cleaned, warnings = validate_features(features)
        assert cleaned["return_1d"] == 0.05
        assert len(warnings) == 0

    def test_nan_replaced_with_default(self):
        """NaN values should be replaced with defaults."""
        features = DEFAULT_FEATURES.copy()
        features["return_1d"] = float("nan")
        cleaned, warnings = validate_features(features)
        assert cleaned["return_1d"] == DEFAULT_FEATURES["return_1d"]
        assert any("return_1d" in w for w in warnings)

    def test_inf_replaced_with_default(self):
        """Infinite values should be replaced with defaults."""
        features = DEFAULT_FEATURES.copy()
        features["volatility_10d"] = float("inf")
        cleaned, warnings = validate_features(features)
        assert cleaned["volatility_10d"] == DEFAULT_FEATURES["volatility_10d"]
        assert any("volatility_10d" in w for w in warnings)

    def test_negative_inf_replaced_with_default(self):
        """Negative infinite values should be replaced with defaults."""
        features = DEFAULT_FEATURES.copy()
        features["return_5d"] = float("-inf")
        cleaned, warnings = validate_features(features)
        assert cleaned["return_5d"] == DEFAULT_FEATURES["return_5d"]

    def test_extreme_return_passes_through(self):
        """Extreme returns pass through - model should see real market data."""
        features = DEFAULT_FEATURES.copy()
        features["return_20d"] = 2.5  # 250% return
        cleaned, warnings = validate_features(features)
        assert cleaned["return_20d"] == 2.5  # Passes through unchanged
        assert len(warnings) == 0

    def test_extreme_negative_return_passes_through(self):
        """Extreme negative returns pass through - no artificial clipping."""
        features = DEFAULT_FEATURES.copy()
        features["return_60d"] = -0.8  # -80% return
        cleaned, warnings = validate_features(features)
        assert cleaned["return_60d"] == -0.8  # Passes through unchanged

    def test_high_volume_passes_through(self):
        """High volume values pass through - only physical constraint is >=0."""
        features = DEFAULT_FEATURES.copy()
        features["volume_normalized"] = 15.0  # High volume spike
        cleaned, warnings = validate_features(features)
        assert cleaned["volume_normalized"] == 15.0  # Passes through unchanged

    def test_negative_normalized_clipped_to_zero(self):
        """Negative normalized values should be clipped to 0."""
        features = DEFAULT_FEATURES.copy()
        features["volume_normalized"] = -2.0
        cleaned, warnings = validate_features(features)
        assert cleaned["volume_normalized"] == 0.0


class TestFeatureExtractor:
    """Tests for the FeatureExtractor class."""

    @pytest.fixture
    def extractor(self):
        return FeatureExtractor()

    @pytest.fixture
    def sample_price_data(self):
        """Generate 250 days of sample price data."""
        np.random.seed(42)
        n = 250
        dates = pd.date_range(start="2023-06-01", periods=n, freq="B")

        # Start at 100, random walk with slight upward drift
        returns = np.random.normal(0.0005, 0.02, n)
        prices = 100 * np.cumprod(1 + returns)

        # Generate OHLC - ensure all arrays have same length
        open_prices = prices * (1 + np.random.uniform(-0.01, 0.01, n))
        high_prices = prices * (1 + np.random.uniform(0, 0.02, n))
        low_prices = prices * (1 - np.random.uniform(0, 0.02, n))
        volumes = np.random.uniform(1e6, 5e6, n)

        df = pd.DataFrame(
            {
                "date": [d.strftime("%Y-%m-%d") for d in dates],
                "open": open_prices,
                "high": high_prices,
                "low": low_prices,
                "close": prices,
                "volume": volumes,
            }
        )

        # Ensure OHLC consistency
        df["high"] = df[["open", "high", "low", "close"]].max(axis=1)
        df["low"] = df[["open", "high", "low", "close"]].min(axis=1)

        return df

    # =========================================================================
    # Insufficient Data Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_insufficient_data_returns_defaults(self, extractor):
        """Less than 200 rows should return default features."""
        n = 50
        dates = pd.date_range(start="2023-06-01", periods=n, freq="B")
        small_df = pd.DataFrame(
            {
                "date": [d.strftime("%Y-%m-%d") for d in dates],
                "close": np.random.uniform(95, 105, n),
                "volume": np.random.uniform(1e6, 5e6, n),
            }
        )

        features = await extractor.extract_features("TEST", "2024-06-01", small_df)

        # Should return defaults
        assert features == DEFAULT_FEATURES

    # =========================================================================
    # Return Calculation Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_return_1d_calculation(self, extractor, sample_price_data):
        """1-day return should be (today - yesterday) / yesterday."""
        features = await extractor.extract_features("TEST", "2024-06-01", sample_price_data)

        # Calculate expected 1-day return
        closes = sample_price_data["close"]
        expected = (closes.iloc[-1] / closes.iloc[-2]) - 1.0

        assert abs(features["return_1d"] - expected) < 0.0001

    @pytest.mark.asyncio
    async def test_return_5d_calculation(self, extractor, sample_price_data):
        """5-day return should be (today - 5 days ago) / 5 days ago."""
        features = await extractor.extract_features("TEST", "2024-06-01", sample_price_data)

        closes = sample_price_data["close"]
        expected = (closes.iloc[-1] / closes.iloc[-6]) - 1.0

        assert abs(features["return_5d"] - expected) < 0.0001

    @pytest.mark.asyncio
    async def test_return_20d_calculation(self, extractor, sample_price_data):
        """20-day return calculation."""
        features = await extractor.extract_features("TEST", "2024-06-01", sample_price_data)

        closes = sample_price_data["close"]
        expected = (closes.iloc[-1] / closes.iloc[-21]) - 1.0

        assert abs(features["return_20d"] - expected) < 0.0001

    @pytest.mark.asyncio
    async def test_return_60d_calculation(self, extractor, sample_price_data):
        """60-day return calculation."""
        features = await extractor.extract_features("TEST", "2024-06-01", sample_price_data)

        closes = sample_price_data["close"]
        expected = (closes.iloc[-1] / closes.iloc[-61]) - 1.0

        assert abs(features["return_60d"] - expected) < 0.0001

    # =========================================================================
    # Price Position Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_price_normalized_above_ma(self, extractor):
        """Price above 200-day MA should have positive normalized value."""
        # Create uptrend: start at 50, end at 150
        # 200-day MA will be around 100, current price 150 -> normalized > 0
        prices = [50 + (100 * i / 249) for i in range(250)]  # Linear from 50 to 150
        df = pd.DataFrame(
            {
                "date": [d.strftime("%Y-%m-%d") for d in pd.date_range(start="2023-06-01", periods=250, freq="B")],
                "close": prices,
                "volume": [1e6] * 250,
            }
        )

        features = await extractor.extract_features("TEST", "2024-06-01", df)

        # Current price (~150) is above 200-day MA (~100), so normalized should be positive
        assert features["price_normalized"] > 0

    @pytest.mark.asyncio
    async def test_price_normalized_below_ma(self, extractor):
        """Price below 200-day MA should have negative normalized value."""
        # Create downtrend: start at 150, end at 50
        # 200-day MA will be around 100, current price 50 -> normalized should be ~ -0.5
        prices = [150 - (100 * i / 249) for i in range(250)]  # Linear from 150 to 50
        df = pd.DataFrame(
            {
                "date": [d.strftime("%Y-%m-%d") for d in pd.date_range(start="2023-06-01", periods=250, freq="B")],
                "close": prices,
                "volume": [1e6] * 250,
            }
        )

        features = await extractor.extract_features("TEST", "2024-06-01", df)

        # Current price (~50) is below 200-day MA (~100), so normalized should be negative
        assert features["price_normalized"] < 0

    # =========================================================================
    # Volatility Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_volatility_positive(self, extractor, sample_price_data):
        """Volatility measures should be positive."""
        features = await extractor.extract_features("TEST", "2024-06-01", sample_price_data)

        assert features["volatility_10d"] > 0
        assert features["volatility_30d"] > 0
        assert features["atr_14d"] > 0

    @pytest.mark.asyncio
    async def test_high_volatility_detected(self, extractor):
        """High volatility in data should produce high volatility features."""
        np.random.seed(42)
        # Create very volatile data
        returns = np.random.normal(0, 0.10, 250)  # 10% daily volatility
        prices = 100 * np.cumprod(1 + returns)

        df = pd.DataFrame(
            {
                "date": [d.strftime("%Y-%m-%d") for d in pd.date_range(start="2023-06-01", periods=250, freq="B")],
                "open": prices * 0.98,
                "high": prices * 1.05,
                "low": prices * 0.95,
                "close": prices,
                "volume": [1e6] * 250,
            }
        )

        features = await extractor.extract_features("TEST", "2024-06-01", df)

        # 10% daily volatility should show up as ~0.10
        assert features["volatility_10d"] > 0.05

    @pytest.mark.asyncio
    async def test_low_volatility_detected(self, extractor):
        """Low volatility data should produce low volatility features."""
        # Create nearly constant prices
        prices = [100 + 0.01 * i for i in range(250)]  # Tiny trend, almost no volatility

        df = pd.DataFrame(
            {
                "date": [d.strftime("%Y-%m-%d") for d in pd.date_range(start="2023-06-01", periods=250, freq="B")],
                "open": prices,
                "high": [p * 1.001 for p in prices],
                "low": [p * 0.999 for p in prices],
                "close": prices,
                "volume": [1e6] * 250,
            }
        )

        features = await extractor.extract_features("TEST", "2024-06-01", df)

        # Very low volatility
        assert features["volatility_10d"] < 0.01

    # =========================================================================
    # Volume Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_volume_normalized_around_one_for_average(self, extractor, sample_price_data):
        """Average volume should produce normalized value around 1."""
        features = await extractor.extract_features("TEST", "2024-06-01", sample_price_data)

        # Should be reasonably close to 1.0
        assert 0.2 < features["volume_normalized"] < 5.0

    @pytest.mark.asyncio
    async def test_high_volume_spike_detected(self, extractor):
        """Volume spike should produce high normalized volume."""
        volumes = [1e6] * 249 + [10e6]  # Last day has 10x volume

        df = pd.DataFrame(
            {
                "date": [d.strftime("%Y-%m-%d") for d in pd.date_range(start="2023-06-01", periods=250, freq="B")],
                "close": [100] * 250,
                "volume": volumes,
            }
        )

        features = await extractor.extract_features("TEST", "2024-06-01", df)

        # Should detect the volume spike
        assert features["volume_normalized"] > 5.0

    @pytest.mark.asyncio
    async def test_volume_trend_positive_for_increasing(self, extractor):
        """Increasing volume trend should be positive."""
        # Volume increasing over time
        volumes = [1e6 * (1 + 0.01 * i) for i in range(250)]

        df = pd.DataFrame(
            {
                "date": [d.strftime("%Y-%m-%d") for d in pd.date_range(start="2023-06-01", periods=250, freq="B")],
                "close": [100] * 250,
                "volume": volumes,
            }
        )

        features = await extractor.extract_features("TEST", "2024-06-01", df)

        assert features["volume_trend"] > 0

    @pytest.mark.asyncio
    async def test_missing_volume_uses_defaults(self, extractor):
        """Missing volume data should use default values."""
        df = pd.DataFrame(
            {
                "date": [d.strftime("%Y-%m-%d") for d in pd.date_range(start="2023-06-01", periods=250, freq="B")],
                "close": [100] * 250,
                # No volume column
            }
        )

        features = await extractor.extract_features("TEST", "2024-06-01", df)

        assert features["volume_normalized"] == DEFAULT_FEATURES["volume_normalized"]
        assert features["volume_trend"] == DEFAULT_FEATURES["volume_trend"]

    # =========================================================================
    # Technical Indicator Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_rsi_oversold(self, extractor):
        """RSI should be low (oversold) after sustained drops."""
        # 250 days of steady decline
        prices = [100 * (0.995**i) for i in range(250)]  # -0.5% per day

        df = pd.DataFrame(
            {
                "date": [d.strftime("%Y-%m-%d") for d in pd.date_range(start="2023-06-01", periods=250, freq="B")],
                "close": prices,
                "volume": [1e6] * 250,
            }
        )

        features = await extractor.extract_features("TEST", "2024-06-01", df)

        # RSI should be very low (normalized to 0-1, so < 0.3)
        assert features["rsi_14"] < 0.3

    @pytest.mark.asyncio
    async def test_rsi_overbought(self, extractor):
        """RSI should be high (overbought) after sustained rises."""
        # 250 days of steady increase
        prices = [100 * (1.005**i) for i in range(250)]  # +0.5% per day

        df = pd.DataFrame(
            {
                "date": [d.strftime("%Y-%m-%d") for d in pd.date_range(start="2023-06-01", periods=250, freq="B")],
                "close": prices,
                "volume": [1e6] * 250,
            }
        )

        features = await extractor.extract_features("TEST", "2024-06-01", df)

        # RSI should be very high (normalized to 0-1, so > 0.7)
        assert features["rsi_14"] > 0.7

    @pytest.mark.asyncio
    async def test_bollinger_at_upper_band(self, extractor):
        """Price at upper Bollinger band should have position near 1."""
        # Create data where price spikes at end to upper band
        prices = [100] * 230 + [100 + i * 2 for i in range(20)]  # Sharp rise at end

        df = pd.DataFrame(
            {
                "date": [d.strftime("%Y-%m-%d") for d in pd.date_range(start="2023-06-01", periods=250, freq="B")],
                "close": prices,
                "volume": [1e6] * 250,
            }
        )

        features = await extractor.extract_features("TEST", "2024-06-01", df)

        # Should be near upper band
        assert features["bollinger_position"] > 0.7

    @pytest.mark.asyncio
    async def test_bollinger_at_lower_band(self, extractor):
        """Price at lower Bollinger band should have position near 0."""
        # Create data where price drops at end to lower band
        prices = [100] * 230 + [100 - i * 2 for i in range(20)]  # Sharp drop at end

        df = pd.DataFrame(
            {
                "date": [d.strftime("%Y-%m-%d") for d in pd.date_range(start="2023-06-01", periods=250, freq="B")],
                "close": prices,
                "volume": [1e6] * 250,
            }
        )

        features = await extractor.extract_features("TEST", "2024-06-01", df)

        # Should be near lower band
        assert features["bollinger_position"] < 0.3

    # =========================================================================
    # Sentiment Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_sentiment_passed_through(self, extractor, sample_price_data):
        """Explicit sentiment score should be used."""
        features = await extractor.extract_features("TEST", "2024-06-01", sample_price_data, sentiment_score=0.8)
        assert features["sentiment_score"] == 0.8

    @pytest.mark.asyncio
    async def test_sentiment_clipped_to_range(self, extractor, sample_price_data):
        """Sentiment outside 0-1 should be clipped."""
        features = await extractor.extract_features("TEST", "2024-06-01", sample_price_data, sentiment_score=1.5)
        assert features["sentiment_score"] == 1.0

    @pytest.mark.asyncio
    async def test_no_sentiment_uses_default(self, extractor, sample_price_data):
        """No sentiment provided should use default (0.5 = neutral)."""
        features = await extractor.extract_features("TEST", "2024-06-01", sample_price_data)
        assert features["sentiment_score"] == 0.5

    # =========================================================================
    # Edge Cases
    # =========================================================================

    @pytest.mark.asyncio
    async def test_all_features_present(self, extractor, sample_price_data):
        """All 14 features should be present in output."""
        features = await extractor.extract_features("TEST", "2024-06-01", sample_price_data)

        for name in FEATURE_NAMES:
            assert name in features, f"Missing feature: {name}"

    @pytest.mark.asyncio
    async def test_no_nan_in_output(self, extractor, sample_price_data):
        """Output should never contain NaN values."""
        features = await extractor.extract_features("TEST", "2024-06-01", sample_price_data)

        for name, value in features.items():
            assert not np.isnan(value), f"NaN in {name}"

    @pytest.mark.asyncio
    async def test_no_inf_in_output(self, extractor, sample_price_data):
        """Output should never contain infinite values."""
        features = await extractor.extract_features("TEST", "2024-06-01", sample_price_data)

        for name, value in features.items():
            assert np.isfinite(value), f"Infinite value in {name}"


class TestReturnCalculation:
    """Focused tests for the _calculate_return helper method."""

    @pytest.fixture
    def extractor(self):
        return FeatureExtractor()

    def test_positive_return(self, extractor):
        """Positive price change should produce positive return."""
        df = pd.DataFrame(
            {
                "close": [100, 110]  # 10% increase
            }
        )
        result = extractor._calculate_return(df, periods=1)
        assert abs(result - 0.10) < 0.001

    def test_negative_return(self, extractor):
        """Negative price change should produce negative return."""
        df = pd.DataFrame(
            {
                "close": [100, 90]  # 10% decrease
            }
        )
        result = extractor._calculate_return(df, periods=1)
        assert abs(result - (-0.10)) < 0.001

    def test_zero_return(self, extractor):
        """No price change should produce zero return."""
        df = pd.DataFrame({"close": [100, 100]})
        result = extractor._calculate_return(df, periods=1)
        assert result == 0.0

    def test_insufficient_data_returns_zero(self, extractor):
        """Less data than required periods should return 0."""
        df = pd.DataFrame(
            {
                "close": [100, 110]  # Only 2 rows
            }
        )
        result = extractor._calculate_return(df, periods=5)  # Need 6 rows
        assert result == 0.0

    def test_multi_period_return(self, extractor):
        """Multi-period return calculation."""
        df = pd.DataFrame(
            {
                "close": [100, 105, 110, 115, 120, 125]  # 25% total over 5 periods
            }
        )
        result = extractor._calculate_return(df, periods=5)
        expected = (125 / 100) - 1.0  # 0.25
        assert abs(result - expected) < 0.001
