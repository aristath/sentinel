"""Test ML training data generator module.

These tests verify the intended behavior of TrainingDataGenerator:
1. Price data fetching and validation
2. Training sample creation
3. Universe symbol retrieval
4. Data storage
"""

from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pandas as pd
import pytest

from sentinel_ml.ml_features import FEATURE_NAMES, NUM_FEATURES
from sentinel_ml.ml_trainer import TrainingDataGenerator


@pytest.fixture
def trainer():
    """Create trainer instance."""
    return TrainingDataGenerator()


@pytest.fixture
def sample_price_data():
    """Generate sample price data (250 days)."""
    np.random.seed(42)
    n = 250
    dates = pd.date_range(start="2024-01-01", periods=n, freq="D")

    # Random walk prices
    returns = np.random.randn(n) * 0.02
    prices = 100 * np.exp(np.cumsum(returns))

    return pd.DataFrame(
        {
            "date": dates.strftime("%Y-%m-%d"),
            "open": prices * (1 + np.random.randn(n) * 0.005),
            "high": prices * (1 + abs(np.random.randn(n) * 0.01)),
            "low": prices * (1 - abs(np.random.randn(n) * 0.01)),
            "close": prices,
            "volume": np.random.randint(100000, 1000000, n),
        }
    )


class TestPriceDataFetching:
    """Tests for price data retrieval."""

    @pytest.mark.asyncio
    async def test_get_price_data(self, trainer):
        """Test price data fetching."""
        trainer.db = AsyncMock()

        mock_rows = [
            {"date": "2024-01-01", "open": 100, "high": 101, "low": 99, "close": 100.5, "volume": 1000},
            {"date": "2024-01-02", "open": 100.5, "high": 102, "low": 100, "close": 101, "volume": 1100},
        ]
        trainer.db.get_prices = AsyncMock(return_value=list(reversed(mock_rows)))

        result = await trainer._get_price_data("TEST", "2024-01-01", "2024-01-31")

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        assert "close" in result.columns

    @pytest.mark.asyncio
    async def test_get_price_data_empty(self, trainer):
        """Test price data with no results."""
        trainer.db = AsyncMock()
        trainer.db.get_prices = AsyncMock(return_value=[])

        result = await trainer._get_price_data("TEST", "2024-01-01", "2024-01-31")

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_get_price_data_converts_types(self, trainer):
        """Test that price data is converted to correct types."""
        trainer.db = AsyncMock()

        # String values that should be converted to float
        mock_rows = [
            {"date": "2024-01-01", "open": "100.5", "high": "101", "low": "99", "close": "100.5", "volume": "1000"},
        ]
        trainer.db.get_prices = AsyncMock(return_value=list(reversed(mock_rows)))

        result = await trainer._get_price_data("TEST", "2024-01-01", "2024-01-31")

        assert isinstance(result["close"].iloc[0], float)


class TestUniverseSymbols:
    """Tests for universe symbol retrieval."""

    @pytest.mark.asyncio
    async def test_get_universe_symbols(self, trainer):
        """Test universe symbols fetching."""
        trainer.db = AsyncMock()
        trainer.db.get_all_securities = AsyncMock(
            return_value=[
                {"symbol": "SYM1"},
                {"symbol": "SYM2"},
            ]
        )

        result = await trainer._get_universe_symbols()

        assert result == ["SYM1", "SYM2"]

    @pytest.mark.asyncio
    async def test_get_universe_symbols_empty(self, trainer):
        """Test universe symbols with no securities."""
        trainer.db = AsyncMock()
        trainer.db.get_all_securities = AsyncMock(return_value=[])

        result = await trainer._get_universe_symbols()

        assert result == []


class TestSampleCreation:
    """Tests for training sample creation."""

    @pytest.mark.asyncio
    async def test_create_samples_requires_min_data(self, trainer, sample_price_data):
        """Samples are not created without sufficient data."""
        # Less than 200 days of data
        short_data = sample_price_data.iloc[:100].copy()

        # Mock feature extractor
        trainer.feature_extractor = MagicMock()
        trainer.feature_extractor.extract_features = AsyncMock(
            return_value={
                "return_1d": 0.01,
                "return_5d": 0.02,
                "return_20d": 0.05,
                "return_60d": 0.10,
                "price_normalized": 0.5,
                "volatility_10d": 0.02,
                "volatility_30d": 0.03,
                "atr_14d": 1.5,
                "volume_normalized": 1.0,
                "volume_trend": 0.0,
                "rsi_14": 50.0,
                "macd": 0.0,
                "bollinger_position": 0.5,
                "sentiment_score": 0.0,
            }
        )

        samples = await trainer._create_samples_for_symbol(
            symbol="TEST",
            price_data=short_data,
            prediction_horizon_days=14,
        )

        # With only 100 days, no samples should be created (need 200 minimum)
        assert len(samples) == 0

    @pytest.mark.asyncio
    async def test_create_samples_with_sufficient_data(self, trainer, sample_price_data):
        """Samples are created with sufficient data."""
        # Mock feature extractor
        trainer.feature_extractor = MagicMock()
        trainer.feature_extractor.extract_features = AsyncMock(
            return_value={
                "return_1d": 0.01,
                "return_5d": 0.02,
                "return_20d": 0.05,
                "return_60d": 0.10,
                "price_normalized": 0.5,
                "volatility_10d": 0.02,
                "volatility_30d": 0.03,
                "atr_14d": 1.5,
                "volume_normalized": 1.0,
                "volume_trend": 0.0,
                "rsi_14": 50.0,
                "macd": 0.0,
                "bollinger_position": 0.5,
                "sentiment_score": 0.0,
            }
        )

        samples = await trainer._create_samples_for_symbol(
            symbol="TEST",
            price_data=sample_price_data,
            prediction_horizon_days=14,
        )

        # Should create some samples (step size is 7 days)
        assert len(samples) > 0

    @pytest.mark.asyncio
    async def test_sample_has_required_fields(self, trainer, sample_price_data):
        """Samples contain all required fields."""
        trainer.feature_extractor = MagicMock()
        trainer.feature_extractor.extract_features = AsyncMock(
            return_value={
                "return_1d": 0.01,
                "return_5d": 0.02,
                "return_20d": 0.05,
                "return_60d": 0.10,
                "price_normalized": 0.5,
                "volatility_10d": 0.02,
                "volatility_30d": 0.03,
                "atr_14d": 1.5,
                "volume_normalized": 1.0,
                "volume_trend": 0.0,
                "rsi_14": 50.0,
                "macd": 0.0,
                "bollinger_position": 0.5,
                "sentiment_score": 0.0,
            }
        )

        samples = await trainer._create_samples_for_symbol(
            symbol="TEST",
            price_data=sample_price_data,
            prediction_horizon_days=14,
        )

        if len(samples) > 0:
            sample = samples[0]
            assert "sample_id" in sample
            assert "symbol" in sample
            assert "sample_date" in sample
            assert "future_return" in sample
            assert "prediction_horizon_days" in sample
            assert "created_at" in sample

    @pytest.mark.asyncio
    async def test_sample_calculates_future_return(self, trainer, sample_price_data):
        """Sample future_return is calculated correctly."""
        trainer.feature_extractor = MagicMock()
        trainer.feature_extractor.extract_features = AsyncMock(
            return_value={
                "return_1d": 0.01,
                "return_5d": 0.02,
                "return_20d": 0.05,
                "return_60d": 0.10,
                "price_normalized": 0.5,
                "volatility_10d": 0.02,
                "volatility_30d": 0.03,
                "atr_14d": 1.5,
                "volume_normalized": 1.0,
                "volume_trend": 0.0,
                "rsi_14": 50.0,
                "macd": 0.0,
                "bollinger_position": 0.5,
                "sentiment_score": 0.0,
            }
        )

        samples = await trainer._create_samples_for_symbol(
            symbol="TEST",
            price_data=sample_price_data,
            prediction_horizon_days=14,
        )

        if len(samples) > 0:
            # future_return should be a float between reasonable bounds
            sample = samples[0]
            assert isinstance(sample["future_return"], float)
            # Returns are typically between -50% and +100%
            assert -1.0 < sample["future_return"] < 2.0


class TestDataStorage:
    """Tests for training data storage."""

    @pytest.mark.asyncio
    async def test_store_training_data_empty(self, trainer):
        """Empty DataFrame is handled gracefully."""
        trainer.ml_db = AsyncMock()
        trainer.ml_db.connect = AsyncMock()
        trainer.ml_db.store_training_samples = AsyncMock()
        empty_df = pd.DataFrame()

        # Should not raise
        await trainer._store_training_data(empty_df)

        # store_training_samples should not be called for empty df
        trainer.ml_db.store_training_samples.assert_not_called()

    @pytest.mark.asyncio
    async def test_store_training_data_calls_ml_db(self, trainer):
        """Training data is stored via ml_db.store_training_samples."""
        trainer.ml_db = AsyncMock()
        trainer.ml_db.connect = AsyncMock()
        trainer.ml_db.store_training_samples = AsyncMock()

        # Create sample DataFrame
        df = pd.DataFrame(
            [
                {
                    "sample_id": "id1",
                    "symbol": "TEST",
                    "sample_date": 1704067200,
                    "return_1d": 0.01,
                    "return_5d": 0.02,
                    "return_20d": 0.05,
                    "return_60d": 0.10,
                    "price_normalized": 0.5,
                    "volatility_10d": 0.02,
                    "volatility_30d": 0.03,
                    "atr_14d": 1.5,
                    "volume_normalized": 1.0,
                    "volume_trend": 0.0,
                    "rsi_14": 50.0,
                    "macd": 0.0,
                    "bollinger_position": 0.5,
                    "sentiment_score": 0.0,
                    "country_agg_momentum": 0.0,
                    "country_agg_rsi": 0.0,
                    "country_agg_volatility": 0.0,
                    "industry_agg_momentum": 0.0,
                    "industry_agg_rsi": 0.0,
                    "industry_agg_volatility": 0.0,
                    "future_return": 0.05,
                    "prediction_horizon_days": 14,
                    "created_at": 1704067200,
                }
            ]
        )

        await trainer._store_training_data(df)

        # Should have called ml_db.store_training_samples with the df
        trainer.ml_db.store_training_samples.assert_called_once()


class TestFeatureConsistency:
    """Tests for feature name consistency."""

    def test_num_features_is_20(self):
        """NUM_FEATURES should be 20 (14 core + 6 aggregate market context)."""
        assert NUM_FEATURES == 20

    def test_feature_names_count(self):
        """FEATURE_NAMES should have 20 entries."""
        assert len(FEATURE_NAMES) == 20

    def test_feature_names_structure(self):
        """Feature names should follow expected patterns."""
        # Core features (14)
        core_features = [
            f
            for f in FEATURE_NAMES
            if not f.endswith("_agg_momentum") and not f.endswith("_agg_rsi") and not f.endswith("_agg_volatility")
        ]
        assert len(core_features) == 14

        # Aggregate features (6)
        agg_features = [f for f in FEATURE_NAMES if "agg" in f]
        assert len(agg_features) == 6
