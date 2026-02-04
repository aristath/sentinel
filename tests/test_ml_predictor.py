"""Test ML predictor module - per-symbol models."""

import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
import pytest_asyncio

from sentinel.database import Database
from sentinel.ml_features import DEFAULT_FEATURES, FEATURE_NAMES, NUM_FEATURES
from sentinel.ml_predictor import MLPredictor


@pytest_asyncio.fixture
async def temp_db():
    """Create a temporary database for testing (used by store_prediction test)."""
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
    """Verify feature names match expected count (20 features: 14 core + 6 aggregate)."""
    assert len(FEATURE_NAMES) == NUM_FEATURES
    assert NUM_FEATURES == 20


def test_default_features_complete():
    """Verify all features have defaults."""
    for name in FEATURE_NAMES:
        assert name in DEFAULT_FEATURES, f"Missing default for {name}"


@pytest.mark.asyncio
async def test_predict_and_blend_with_quote_data_predicted_at_skip_cache(predictor, sample_features):
    """With quote_data, predicted_at_ts, skip_cache=True: no cache read/write; _store_prediction with correct args."""
    predictor.db = AsyncMock()
    predictor.db.connect = AsyncMock()
    predictor.db.cache_get = AsyncMock(return_value=None)
    predictor.db.cache_set = AsyncMock()
    predictor.db.conn = AsyncMock()
    predictor.db.conn.execute = AsyncMock()
    predictor.db.conn.commit = AsyncMock()

    mock_ensemble = MagicMock()
    mock_ensemble.predict = MagicMock(return_value=np.array([0.04]))
    predictor._models["SYM"] = mock_ensemble
    predictor._load_times["SYM"] = float("inf")

    quote_data = {"chg5": 1.0, "chg22": 2.0, "chg110": 3.0, "chg220": 4.0, "ltp": 100.0, "x_max": 110.0, "x_min": 90.0}
    predicted_at_ts = 1738000000  # fixed for test
    date_str = "2025-01-27"

    store_calls = []

    async def capture_store(*args, **kwargs):
        store_calls.append((args, kwargs))

    predictor._store_prediction = AsyncMock(side_effect=capture_store)

    with patch(
        "sentinel.ml_predictor.get_regime_adjusted_return",
        new_callable=AsyncMock,
        return_value=(0.03, 0.7, 0.85),  # adjusted_return, regime_score, dampening
    ):
        result = await predictor.predict_and_blend(
            symbol="SYM",
            date=date_str,
            wavelet_score=0.5,
            ml_enabled=True,
            ml_blend_ratio=0.4,
            features=sample_features,
            quote_data=quote_data,
            predicted_at_ts=predicted_at_ts,
            skip_cache=True,
        )

    # skip_cache: cache_set should not have been called
    predictor.db.cache_set.assert_not_called()
    # _store_prediction called once with correct predicted_at_ts, prediction_id, regime_score, regime_dampening
    assert len(store_calls) == 1
    args, kwargs = store_calls[0]
    assert kwargs.get("predicted_at_ts") == predicted_at_ts
    assert kwargs.get("prediction_id") == f"SYM_{predicted_at_ts}"
    assert kwargs.get("regime_score") == 0.7
    assert kwargs.get("regime_dampening") == 0.85
    assert result["regime_score"] == 0.7
    assert result["regime_dampening"] == 0.85


@pytest.mark.asyncio
async def test_predict_and_blend_default_predicted_at_uses_current_time(predictor, sample_features):
    """With predicted_at_ts=None, _store_prediction uses current time and generated prediction_id."""
    predictor.db = AsyncMock()
    predictor.db.connect = AsyncMock()
    predictor.db.cache_get = AsyncMock(return_value=None)
    predictor.db.cache_set = AsyncMock()
    predictor.db.conn = AsyncMock()
    predictor.db.conn.execute = AsyncMock()
    predictor.db.conn.commit = AsyncMock()

    mock_ensemble = MagicMock()
    mock_ensemble.predict = MagicMock(return_value=np.array([0.02]))
    predictor._models["T"] = mock_ensemble
    predictor._load_times["T"] = float("inf")

    store_calls = []

    async def capture_store(*args, **kwargs):
        store_calls.append((args, kwargs))

    predictor._store_prediction = AsyncMock(side_effect=capture_store)

    with patch(
        "sentinel.ml_predictor.get_regime_adjusted_return",
        new_callable=AsyncMock,
        return_value=(0.02, 0.5, 1.0),
    ):
        await predictor.predict_and_blend(
            symbol="T",
            date="2025-01-28",
            wavelet_score=0.6,
            ml_enabled=True,
            ml_blend_ratio=0.3,
            features=sample_features,
        )

    assert len(store_calls) == 1
    _, kwargs = store_calls[0]
    assert kwargs.get("predicted_at_ts") is None
    assert kwargs.get("prediction_id") is None
    # _store_prediction will derive predicted_at_ts and prediction_id internally


@pytest.mark.asyncio
async def test_store_prediction_includes_regime_score_regime_dampening(temp_db):
    """After storing a prediction, row in ml_predictions has regime_score and regime_dampening set."""
    db = temp_db
    predictor = MLPredictor(db=db)
    await predictor.db.connect()

    await predictor._store_prediction(
        symbol="X",
        features={"rsi_14": 0.5},
        predicted_return=0.03,
        ml_score=0.65,
        wavelet_score=0.6,
        blend_ratio=0.4,
        final_score=0.63,
        inference_time_ms=5.0,
        regime_score=0.72,
        regime_dampening=0.88,
        predicted_at_ts=1738100000,
        prediction_id="X_1738100000",
    )

    cursor = await db.conn.execute(
        "SELECT prediction_id, symbol, predicted_at, regime_score, regime_dampening "
        "FROM ml_predictions WHERE symbol = ?",
        ("X",),
    )
    row = await cursor.fetchone()
    assert row is not None
    assert dict(row)["prediction_id"] == "X_1738100000"
    assert dict(row)["predicted_at"] == 1738100000
    assert dict(row)["regime_score"] == 0.72
    assert dict(row)["regime_dampening"] == 0.88
