"""Test ML predictor module - per-symbol, per-model predictions."""

import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
import pytest_asyncio

from sentinel.database import Database
from sentinel_ml.database.ml import MODEL_TYPES, MLDatabase
from sentinel_ml.ml_features import DEFAULT_FEATURES, FEATURE_NAMES, NUM_FEATURES
from sentinel_ml.ml_predictor import MLPredictor


@pytest_asyncio.fixture
async def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    db = Database(db_path)
    await db.connect()
    yield db
    await db.close()
    db.remove_from_cache()
    if os.path.exists(db_path):
        os.unlink(db_path)
    for ext in ["-wal", "-shm"]:
        wal_path = db_path + ext
        if os.path.exists(wal_path):
            os.unlink(wal_path)


@pytest_asyncio.fixture
async def temp_ml_db():
    """Create a temporary ML database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    ml_db = MLDatabase(db_path)
    await ml_db.connect()
    yield ml_db
    await ml_db.close()
    ml_db.remove_from_cache()
    if os.path.exists(db_path):
        os.unlink(db_path)
    for ext in ["-wal", "-shm"]:
        wal_path = db_path + ext
        if os.path.exists(wal_path):
            os.unlink(wal_path)


@pytest.fixture
def predictor():
    """Create predictor instance with mocked dbs."""
    p = MLPredictor()
    p.settings = AsyncMock()
    p.settings.get = AsyncMock(return_value=0.25)
    return p


@pytest.fixture
def sample_features():
    """Generate sample features dict."""
    return {name: np.random.randn() * 0.1 for name in FEATURE_NAMES}


def test_normalize_return_to_score():
    """Test return to score normalization."""
    predictor = MLPredictor()

    assert predictor._normalize_return_to_score(-0.10) == 0.0
    assert predictor._normalize_return_to_score(0.0) == 0.5
    assert predictor._normalize_return_to_score(0.10) == 1.0
    assert predictor._normalize_return_to_score(0.05) == 0.75
    assert predictor._normalize_return_to_score(-0.05) == 0.25
    assert predictor._normalize_return_to_score(0.50) == 1.0
    assert predictor._normalize_return_to_score(-0.50) == 0.0


def test_fallback_to_wavelet():
    """Test fallback returns correct structure with empty predictions."""
    predictor = MLPredictor()
    wavelet_score = 0.7

    result = predictor._fallback_to_wavelet(wavelet_score)

    assert result["predictions"] == {}
    assert result["final_score"] == wavelet_score
    assert result["regime_score"] == 0.0
    assert result["wavelet_score"] == wavelet_score


@pytest.mark.asyncio
async def test_predict_and_blend_ml_disabled(predictor):
    """Test prediction when ML is disabled returns wavelet fallback."""
    predictor.db = AsyncMock()
    predictor.db.connect = AsyncMock()

    wavelet_score = 0.6
    result = await predictor.predict_and_blend(
        symbol="TEST",
        date="2025-01-27",
        wavelet_score=wavelet_score,
        ml_enabled=False,
        ml_blend_ratio=0.5,
    )

    assert result["predictions"] == {}
    assert result["wavelet_score"] == wavelet_score


@pytest.mark.asyncio
async def test_predict_and_blend_no_model(predictor):
    """Test prediction when no model exists falls back to wavelet."""
    predictor.db = AsyncMock()
    predictor.db.connect = AsyncMock()
    predictor.db.cache_get = AsyncMock(return_value=None)

    with patch("sentinel_ml.ml_predictor.EnsembleBlender.model_exists", return_value=False):
        wavelet_score = 0.6
        result = await predictor.predict_and_blend(
            symbol="TEST",
            date="2025-01-27",
            wavelet_score=wavelet_score,
            ml_enabled=True,
            ml_blend_ratio=0.3,
        )

    assert result["predictions"] == {}
    assert result["wavelet_score"] == wavelet_score


@pytest.mark.asyncio
async def test_predict_and_blend_returns_all_4_models(predictor, sample_features):
    """Test prediction returns per-model results for all 4 model types."""
    predictor.db = AsyncMock()
    predictor.db.connect = AsyncMock()
    predictor.db.cache_get = AsyncMock(return_value=None)
    predictor.db.cache_set = AsyncMock()
    predictor.db.get_security = AsyncMock(return_value=None)

    predictor.ml_db = AsyncMock()
    predictor.ml_db.connect = AsyncMock()
    predictor.ml_db.store_prediction = AsyncMock()

    # Mock ensemble returning dict of per-model predictions
    mock_ensemble = MagicMock()
    mock_ensemble.predict = MagicMock(
        return_value={
            "xgboost": np.array([0.05]),
            "ridge": np.array([0.03]),
            "rf": np.array([0.04]),
            "svr": np.array([0.02]),
        }
    )
    predictor._models["TEST"] = mock_ensemble
    predictor._load_times["TEST"] = float("inf")

    with patch(
        "sentinel_ml.ml_predictor.get_regime_adjusted_return",
        new_callable=AsyncMock,
        return_value=(0.04, 0.5, 0.1),
    ):
        result = await predictor.predict_and_blend(
            symbol="TEST",
            date="2025-01-27",
            wavelet_score=0.6,
            ml_enabled=True,
            ml_blend_ratio=0.3,
            features=sample_features,
        )

    assert "predictions" in result
    for mt in MODEL_TYPES:
        assert mt in result["predictions"]
        pred = result["predictions"][mt]
        assert "predicted_return" in pred
        assert "ml_score" in pred
        assert "regime_score" in pred
        assert "regime_dampening" in pred

    assert result["regime_score"] == 0.5
    assert result["wavelet_score"] == 0.6


@pytest.mark.asyncio
async def test_predict_stores_to_all_4_tables(predictor, sample_features):
    """Test that prediction stores to all 4 per-model prediction tables."""
    predictor.db = AsyncMock()
    predictor.db.connect = AsyncMock()
    predictor.db.cache_get = AsyncMock(return_value=None)
    predictor.db.cache_set = AsyncMock()
    predictor.db.get_security = AsyncMock(return_value=None)

    predictor.ml_db = AsyncMock()
    predictor.ml_db.connect = AsyncMock()
    predictor.ml_db.store_prediction = AsyncMock()

    mock_ensemble = MagicMock()
    mock_ensemble.predict = MagicMock(
        return_value={
            "xgboost": np.array([0.05]),
            "ridge": np.array([0.03]),
            "rf": np.array([0.04]),
            "svr": np.array([0.02]),
        }
    )
    predictor._models["TEST"] = mock_ensemble
    predictor._load_times["TEST"] = float("inf")

    with patch(
        "sentinel_ml.ml_predictor.get_regime_adjusted_return",
        new_callable=AsyncMock,
        return_value=(0.04, 0.5, 0.1),
    ):
        await predictor.predict_and_blend(
            symbol="TEST",
            date="2025-01-27",
            wavelet_score=0.6,
            ml_enabled=True,
            ml_blend_ratio=0.3,
            features=sample_features,
        )

    # Should have stored 4 predictions (one per model type)
    assert predictor.ml_db.store_prediction.call_count == 4
    stored_types = [call.kwargs["model_type"] for call in predictor.ml_db.store_prediction.call_args_list]
    assert set(stored_types) == set(MODEL_TYPES)


@pytest.mark.asyncio
async def test_predict_regime_dampening_per_model(predictor, sample_features):
    """Test regime dampening is applied independently per model."""
    predictor.db = AsyncMock()
    predictor.db.connect = AsyncMock()
    predictor.db.cache_get = AsyncMock(return_value=None)
    predictor.db.cache_set = AsyncMock()

    predictor.ml_db = AsyncMock()
    predictor.ml_db.connect = AsyncMock()
    predictor.ml_db.store_prediction = AsyncMock()

    mock_ensemble = MagicMock()
    mock_ensemble.predict = MagicMock(
        return_value={
            "xgboost": np.array([0.10]),  # Strong bullish
            "ridge": np.array([-0.05]),  # Bearish
            "rf": np.array([0.02]),
            "svr": np.array([0.00]),
        }
    )
    predictor._models["TEST"] = mock_ensemble
    predictor._load_times["TEST"] = float("inf")

    # Track calls to get_regime_adjusted_return
    regime_calls = []

    async def mock_regime(symbol, ml_return, db, quote_data=None):
        regime_calls.append(ml_return)
        # Different dampening for different returns
        if ml_return > 0:
            return ml_return * 0.8, -0.5, 0.2
        return ml_return, -0.5, 0.0

    with patch("sentinel_ml.ml_predictor.get_regime_adjusted_return", side_effect=mock_regime):
        result = await predictor.predict_and_blend(
            symbol="TEST",
            date="2025-01-27",
            wavelet_score=0.5,
            ml_enabled=True,
            ml_blend_ratio=0.5,
            features=sample_features,
        )

    # Regime adjustment called once per model
    assert len(regime_calls) == 4
    # XGBoost: 0.10 -> 0.08 (dampened)
    assert abs(result["predictions"]["xgboost"]["predicted_return"] - 0.08) < 0.001
    # Ridge: -0.05 -> -0.05 (not dampened, bearish aligns with bearish regime)
    assert abs(result["predictions"]["ridge"]["predicted_return"] - (-0.05)) < 0.001


@pytest.mark.asyncio
async def test_predict_skip_cache(predictor, sample_features):
    """Test skip_cache prevents cache read/write."""
    predictor.db = AsyncMock()
    predictor.db.connect = AsyncMock()
    predictor.db.cache_get = AsyncMock(return_value=None)
    predictor.db.cache_set = AsyncMock()

    predictor.ml_db = AsyncMock()
    predictor.ml_db.connect = AsyncMock()
    predictor.ml_db.store_prediction = AsyncMock()

    mock_ensemble = MagicMock()
    mock_ensemble.predict = MagicMock(return_value={mt: np.array([0.03]) for mt in MODEL_TYPES})
    predictor._models["SYM"] = mock_ensemble
    predictor._load_times["SYM"] = float("inf")

    with patch(
        "sentinel_ml.ml_predictor.get_regime_adjusted_return",
        new_callable=AsyncMock,
        return_value=(0.03, 0.5, 0.0),
    ):
        await predictor.predict_and_blend(
            symbol="SYM",
            date="2025-01-27",
            wavelet_score=0.5,
            ml_enabled=True,
            ml_blend_ratio=0.4,
            features=sample_features,
            skip_cache=True,
        )

    predictor.db.cache_get.assert_not_called()
    predictor.db.cache_set.assert_not_called()


@pytest.mark.asyncio
async def test_store_prediction_writes_to_ml_db(temp_ml_db, temp_db):
    """Test _store_prediction actually writes to ml.db per-model table."""
    predictor = MLPredictor(db=temp_db, ml_db=temp_ml_db)

    await predictor._store_prediction(
        model_type="xgboost",
        prediction_id="X_xgboost_1738100000",
        symbol="X",
        features={"rsi_14": 0.5},
        predicted_return=0.03,
        ml_score=0.65,
        regime_score=0.72,
        regime_dampening=0.88,
        inference_time_ms=5.0,
        predicted_at_ts=1738100000,
    )

    cursor = await temp_ml_db.conn.execute("SELECT * FROM ml_predictions_xgboost WHERE symbol = ?", ("X",))
    row = await cursor.fetchone()
    assert row is not None
    row_dict = dict(row)
    assert row_dict["prediction_id"] == "X_xgboost_1738100000"
    assert row_dict["predicted_at"] == 1738100000
    assert row_dict["regime_score"] == 0.72
    assert row_dict["regime_dampening"] == 0.88


def test_clear_cache_single_symbol(predictor):
    """Test clearing cache for a single symbol."""
    predictor._models["AAPL"] = MagicMock()
    predictor._models["MSFT"] = MagicMock()
    predictor._load_times["AAPL"] = 12345
    predictor._load_times["MSFT"] = 12345

    predictor.clear_cache("AAPL")

    assert "AAPL" not in predictor._models
    assert "MSFT" in predictor._models


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
    """Verify feature names match expected count (20 features: 14 core + 6 aggregate)."""
    assert len(FEATURE_NAMES) == NUM_FEATURES
    assert NUM_FEATURES == 20


def test_default_features_complete():
    """Verify all features have defaults."""
    for name in FEATURE_NAMES:
        assert name in DEFAULT_FEATURES, f"Missing default for {name}"
