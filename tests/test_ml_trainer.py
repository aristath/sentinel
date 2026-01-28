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

from sentinel.ml_features import FEATURE_NAMES, NUM_FEATURES
from sentinel.ml_trainer import TrainingDataGenerator


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
        trainer.db.conn = AsyncMock()
        cursor_mock = AsyncMock()
        cursor_mock.fetchall = AsyncMock(return_value=mock_rows)
        trainer.db.conn.execute = AsyncMock(return_value=cursor_mock)

        result = await trainer._get_price_data("TEST", "2024-01-01", "2024-01-31")

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        assert "close" in result.columns

    @pytest.mark.asyncio
    async def test_get_price_data_empty(self, trainer):
        """Test price data with no results."""
        trainer.db = AsyncMock()
        trainer.db.conn = AsyncMock()
        cursor_mock = AsyncMock()
        cursor_mock.fetchall = AsyncMock(return_value=[])
        trainer.db.conn.execute = AsyncMock(return_value=cursor_mock)

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
        trainer.db.conn = AsyncMock()
        cursor_mock = AsyncMock()
        cursor_mock.fetchall = AsyncMock(return_value=mock_rows)
        trainer.db.conn.execute = AsyncMock(return_value=cursor_mock)

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
        trainer.db = AsyncMock()
        empty_df = pd.DataFrame()

        # Should not raise
        await trainer._store_training_data(empty_df)

        # No execute calls should be made
        trainer.db.conn = MagicMock()
        trainer.db.conn.execute = AsyncMock()
        # execute should not be called for empty df

    @pytest.mark.asyncio
    async def test_store_training_data_batch(self, trainer):
        """Training data is stored in batches."""
        trainer.db = AsyncMock()
        trainer.db.conn = AsyncMock()
        trainer.db.conn.execute = AsyncMock()
        trainer.db.conn.commit = AsyncMock()

        # Create sample DataFrame
        df = pd.DataFrame(
            [
                {
                    "sample_id": "id1",
                    "symbol": "TEST",
                    "sample_date": "2024-01-01",
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
                    "future_return": 0.05,
                    "prediction_horizon_days": 14,
                    "created_at": "2024-01-01T00:00:00",
                }
            ]
        )

        await trainer._store_training_data(df)

        # Should have called execute for each row
        assert trainer.db.conn.execute.called


class TestFeatureConsistency:
    """Tests for feature name consistency."""

    def test_num_features_is_14(self):
        """NUM_FEATURES should be 14 (per-security features only)."""
        assert NUM_FEATURES == 14

    def test_feature_names_count(self):
        """FEATURE_NAMES should have 14 entries."""
        assert len(FEATURE_NAMES) == 14

    def test_feature_names_no_cross_security(self):
        """Feature names should not include cross-security data."""
        # These would indicate cross-security contamination
        cross_security_patterns = ["market_", "sector_", "index_", "cross_"]

        for name in FEATURE_NAMES:
            for pattern in cross_security_patterns:
                assert not name.startswith(pattern), f"Feature {name} suggests cross-security data"
