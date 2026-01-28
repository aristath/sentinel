"""Test ML predictor module - per-symbol models."""

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from sentinel.ml_features import DEFAULT_FEATURES, FEATURE_NAMES, NUM_FEATURES
from sentinel.ml_predictor import MLPredictor


@pytest.fixture
def predictor():
    """Create predictor instance."""
    return MLPredictor()


@pytest.fixture
def sample_features():
    """Generate sample features dict."""
    return {name: np.random.randn() * 0.1 for name in FEATURE_NAMES}


def test_normalize_return_to_score():
    """Test return to score normalization."""
    predictor = MLPredictor()

    # -10% return -> 0.0 score
    assert predictor._normalize_return_to_score(-0.10) == 0.0

    # 0% return -> 0.5 score
    assert predictor._normalize_return_to_score(0.0) == 0.5

    # +10% return -> 1.0 score
    assert predictor._normalize_return_to_score(0.10) == 1.0

    # +5% return -> 0.75 score
    assert predictor._normalize_return_to_score(0.05) == 0.75

    # -5% return -> 0.25 score
    assert predictor._normalize_return_to_score(-0.05) == 0.25

    # Extreme values should clip
    assert predictor._normalize_return_to_score(0.50) == 1.0
    assert predictor._normalize_return_to_score(-0.50) == 0.0


def test_fallback_to_wavelet():
    """Test fallback returns correct structure."""
    predictor = MLPredictor()
    wavelet_score = 0.7

    result = predictor._fallback_to_wavelet(wavelet_score)

    assert result["ml_predicted_return"] == 0.0
    assert result["ml_score"] == wavelet_score
    assert result["wavelet_score"] == wavelet_score
    assert result["blend_ratio"] == 0.0
    assert result["final_score"] == wavelet_score


@pytest.mark.asyncio
async def test_predict_and_blend_ml_disabled(predictor):
    """Test prediction when ML is disabled for this security."""
    predictor.db = AsyncMock()
    predictor.db.connect = AsyncMock()

    wavelet_score = 0.6
    result = await predictor.predict_and_blend(
        symbol="TEST",
        date="2025-01-27",
        wavelet_score=wavelet_score,
        ml_enabled=False,  # ML disabled for this security
        ml_blend_ratio=0.5,
    )

    assert result["final_score"] == wavelet_score
    assert result["blend_ratio"] == 0.0


@pytest.mark.asyncio
async def test_predict_and_blend_no_model(predictor):
    """Test prediction when no model exists for symbol."""
    predictor.db = AsyncMock()
    predictor.db.connect = AsyncMock()
    predictor.db.cache_get = AsyncMock(return_value=None)

    # Mock EnsembleBlender.model_exists to return False
    with patch("sentinel.ml_predictor.EnsembleBlender.model_exists", return_value=False):
        wavelet_score = 0.6
        result = await predictor.predict_and_blend(
            symbol="TEST",
            date="2025-01-27",
            wavelet_score=wavelet_score,
            ml_enabled=True,
            ml_blend_ratio=0.3,
        )

    # Should fallback to wavelet (no model available)
    assert result["final_score"] == wavelet_score
    assert result["blend_ratio"] == 0.0


@pytest.mark.asyncio
async def test_predict_and_blend_with_model(predictor, sample_features):
    """Test prediction with trained model for symbol."""
    predictor.db = AsyncMock()
    predictor.db.connect = AsyncMock()
    predictor.db.cache_get = AsyncMock(return_value=None)
    predictor.db.cache_set = AsyncMock()
    predictor.db.conn = AsyncMock()
    predictor.db.conn.execute = AsyncMock()
    predictor.db.conn.commit = AsyncMock()
    # Mock get_security to return None (no quote data for regime adjustment)
    predictor.db.get_security = AsyncMock(return_value=None)

    # Mock ensemble for this symbol
    mock_ensemble = MagicMock()
    mock_ensemble.predict = MagicMock(return_value=np.array([0.05]))  # 5% predicted return
    predictor._models["TEST"] = mock_ensemble
    predictor._load_times["TEST"] = float("inf")  # Skip reload

    wavelet_score = 0.6
    ml_blend_ratio = 0.3
    result = await predictor.predict_and_blend(
        symbol="TEST",
        date="2025-01-27",
        wavelet_score=wavelet_score,
        ml_enabled=True,
        ml_blend_ratio=ml_blend_ratio,
        features=sample_features,
    )

    assert "ml_predicted_return" in result
    assert "ml_score" in result
    assert "final_score" in result
    assert result["blend_ratio"] == ml_blend_ratio

    # 5% return -> 0.75 ml_score
    # final = 0.7 * 0.6 + 0.3 * 0.75 = 0.42 + 0.225 = 0.645
    expected_ml_score = 0.75
    expected_final = (1 - ml_blend_ratio) * wavelet_score + ml_blend_ratio * expected_ml_score
    assert abs(result["ml_score"] - expected_ml_score) < 0.01
    assert abs(result["final_score"] - expected_final) < 0.01


def test_clear_cache_single_symbol(predictor):
    """Test clearing cache for a single symbol."""
    predictor._models["AAPL"] = MagicMock()
    predictor._models["MSFT"] = MagicMock()
    predictor._load_times["AAPL"] = 12345
    predictor._load_times["MSFT"] = 12345

    predictor.clear_cache("AAPL")

    assert "AAPL" not in predictor._models
    assert "MSFT" in predictor._models
    assert "AAPL" not in predictor._load_times
    assert "MSFT" in predictor._load_times


def test_clear_cache_all(predictor):
    """Test clearing entire cache."""
    predictor._models["AAPL"] = MagicMock()
    predictor._models["MSFT"] = MagicMock()
    predictor._load_times["AAPL"] = 12345
    predictor._load_times["MSFT"] = 12345

    predictor.clear_cache()

    assert len(predictor._models) == 0
    assert len(predictor._load_times) == 0


def test_feature_names_consistency():
    """Verify feature names match expected count (14 features per security)."""
    assert len(FEATURE_NAMES) == NUM_FEATURES
    assert NUM_FEATURES == 14


def test_default_features_complete():
    """Verify all features have defaults."""
    for name in FEATURE_NAMES:
        assert name in DEFAULT_FEATURES, f"Missing default for {name}"
