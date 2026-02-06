"""Test ML ensemble integration — 4 models working together."""

import numpy as np
import pytest

from sentinel_ml.database.ml import MODEL_TYPES
from sentinel_ml.ml_ensemble import (
    EnsembleBlender,
    RandomForestReturnPredictor,
    RidgeReturnPredictor,
    SVRReturnPredictor,
    XGBoostReturnPredictor,
)


@pytest.fixture
def dummy_data():
    """Generate reproducible dummy training data (20 features)."""
    np.random.seed(42)
    X = np.random.randn(200, 20).astype(np.float32)
    y = (X[:, 0] * 0.5 + X[:, 1] * 0.3 + np.random.randn(200) * 0.1).astype(np.float32)
    return X, y


class TestEnsembleIntegration:
    """Integration tests for the 4-model ensemble."""

    def test_all_model_types_exported(self):
        """MODEL_TYPES should list all 4 model types."""
        assert set(MODEL_TYPES) == {"xgboost", "ridge", "rf", "svr"}

    def test_ensemble_trains_all_models(self, dummy_data):
        """EnsembleBlender.train() produces metrics for all 4 model types."""
        X, y = dummy_data
        ensemble = EnsembleBlender()
        metrics = ensemble.train(X, y)

        for mt in MODEL_TYPES:
            assert f"{mt}_metrics" in metrics
            assert "val_mae" in metrics[f"{mt}_metrics"]
            assert "val_rmse" in metrics[f"{mt}_metrics"]
            assert "val_r2" in metrics[f"{mt}_metrics"]

    def test_ensemble_predict_returns_all_4(self, dummy_data):
        """EnsembleBlender.predict() returns dict with all 4 model arrays."""
        X, y = dummy_data
        ensemble = EnsembleBlender()
        ensemble.train(X, y)

        predictions = ensemble.predict(X[:5])
        assert isinstance(predictions, dict)
        for mt in MODEL_TYPES:
            assert mt in predictions
            assert len(predictions[mt]) == 5

    def test_ensemble_save_load_roundtrip(self, dummy_data):
        """Save and load ensemble, predictions should match."""
        import shutil

        from sentinel.paths import DATA_DIR

        X, y = dummy_data
        symbol = "TEST_ENSEMBLE_CLEANUP"
        ensemble = EnsembleBlender()
        ensemble.train(X, y)
        ensemble.save(symbol)

        try:
            assert EnsembleBlender.model_exists(symbol)

            loaded = EnsembleBlender()
            loaded.load(symbol)

            original_preds = ensemble.predict(X[:3])
            loaded_preds = loaded.predict(X[:3])

            for mt in MODEL_TYPES:
                np.testing.assert_allclose(
                    original_preds[mt], loaded_preds[mt], rtol=1e-5, err_msg=f"Predictions differ after load for {mt}"
                )
        finally:
            path = DATA_DIR / "ml_models" / symbol
            if path.exists():
                shutil.rmtree(path)

    def test_individual_predictors_exist(self):
        """All 4 predictor classes should be importable."""
        assert XGBoostReturnPredictor is not None
        assert RidgeReturnPredictor is not None
        assert RandomForestReturnPredictor is not None
        assert SVRReturnPredictor is not None

    def test_predictions_are_finite(self, dummy_data):
        """All model predictions should be finite values."""
        X, y = dummy_data
        ensemble = EnsembleBlender()
        ensemble.train(X, y)

        preds = ensemble.predict(X)
        for mt in MODEL_TYPES:
            assert np.all(np.isfinite(preds[mt])), f"{mt} has non-finite predictions"
