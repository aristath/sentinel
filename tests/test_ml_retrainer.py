"""Test ML retrainer module - per-symbol, 4 model types."""

from unittest.mock import AsyncMock, patch

import numpy as np
import pandas as pd
import pytest

from sentinel_ml.database.ml import MODEL_TYPES
from sentinel_ml.ml_features import NUM_FEATURES
from sentinel_ml.ml_retrainer import MLRetrainer


@pytest.fixture
def retrainer():
    """Create retrainer instance with mocked dbs."""
    r = MLRetrainer()
    r.db = AsyncMock()
    r.db.connect = AsyncMock()
    r.ml_db = AsyncMock()
    r.ml_db.connect = AsyncMock()
    return r


@pytest.mark.asyncio
async def test_retrain_trains_all_4_models(retrainer):
    """Test that _train_symbol trains all 4 model types and stores metrics."""
    n = 200
    np.random.seed(42)
    X = np.random.randn(n, NUM_FEATURES).astype(np.float32)
    y = (X[:, 0] * 0.02 + np.random.randn(n) * 0.01).astype(np.float32)

    retrainer.ml_db.load_training_data = AsyncMock(return_value=(X, y))
    retrainer.ml_db.update_model_record = AsyncMock()

    with patch("sentinel_ml.ml_retrainer.EnsembleBlender") as MockBlender:
        instance = MockBlender.return_value
        instance.train.return_value = {
            f"{mt}_metrics": {"val_mae": 0.01, "val_rmse": 0.02, "val_r2": 0.5} for mt in MODEL_TYPES
        }
        instance.save.return_value = None

        result = await retrainer._train_symbol("TEST")

    assert result is not None
    assert "validation_rmse" in result
    assert "per_model" in result
    for mt in MODEL_TYPES:
        assert mt in result["per_model"]

    # Should update model record for all 4 types
    assert retrainer.ml_db.update_model_record.call_count == 4
    stored_types = [call.kwargs["model_type"] for call in retrainer.ml_db.update_model_record.call_args_list]
    assert set(stored_types) == set(MODEL_TYPES)


@pytest.mark.asyncio
async def test_retrain_no_symbols(retrainer):
    """Test retraining when no symbols have sufficient data."""
    retrainer.settings = AsyncMock()
    retrainer.settings.get = AsyncMock(return_value=100)
    retrainer.trainer = AsyncMock()
    retrainer.trainer.generate_incremental_samples = AsyncMock(return_value=pd.DataFrame())
    retrainer.ml_db.get_symbols_with_sufficient_data = AsyncMock(return_value={})

    result = await retrainer.retrain()

    assert result["status"] == "skipped"
    assert "No symbols with sufficient training data" in result["reason"]


@pytest.mark.asyncio
async def test_retrain_symbol_insufficient_data(retrainer):
    """Test retraining a single symbol with insufficient data."""
    retrainer.settings = AsyncMock()
    retrainer.settings.get = AsyncMock(return_value=100)
    retrainer.ml_db.get_sample_count = AsyncMock(return_value=50)

    result = await retrainer.retrain_symbol("TEST")

    assert result is None


@pytest.mark.asyncio
async def test_train_symbol_empty_data(retrainer):
    """Test _train_symbol with no valid training data."""
    retrainer.ml_db.load_training_data = AsyncMock(return_value=(np.array([]), np.array([])))

    result = await retrainer._train_symbol("TEST")

    assert result is None


@pytest.mark.asyncio
async def test_get_model_status(retrainer):
    """Test getting status of all trained models across all types."""
    retrainer.ml_db.get_all_model_status = AsyncMock(
        return_value={
            "xgboost": [{"symbol": "AAPL", "training_samples": 500}],
            "ridge": [{"symbol": "AAPL", "training_samples": 500}],
            "rf": [{"symbol": "AAPL", "training_samples": 500}],
            "svr": [{"symbol": "AAPL", "training_samples": 500}],
        }
    )

    result = await retrainer.get_model_status()

    assert result["total_models"] == 4
    assert "per_type" in result
    for mt in MODEL_TYPES:
        assert mt in result["per_type"]
