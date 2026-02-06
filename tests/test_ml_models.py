"""Tests for new ML model implementations: Ridge, RF, SVR, XGBoost, EnsembleBlender."""

import shutil

import numpy as np
import pytest

# These will be imported after Phase 2 implementation
from sentinel_ml.ml_ensemble import (
    EnsembleBlender,
    RandomForestReturnPredictor,
    RidgeReturnPredictor,
    SVRReturnPredictor,
    XGBoostReturnPredictor,
)
from sentinel_ml.ml_features import NUM_FEATURES

MODEL_TYPES = ["xgboost", "ridge", "rf", "svr"]


@pytest.fixture
def dummy_data():
    """Generate dummy training and validation data."""
    np.random.seed(42)
    X = np.random.randn(200, NUM_FEATURES).astype(np.float32)
    y = (X[:, 0] * 0.02 + np.random.randn(200) * 0.01).astype(np.float32)
    return X[:160], y[:160], X[160:], y[160:]


class TestRidgeReturnPredictor:
    def test_train_returns_metrics(self, dummy_data):
        X_train, y_train, X_val, y_val = dummy_data
        predictor = RidgeReturnPredictor()
        metrics = predictor.train(X_train, y_train, X_val, y_val)
        assert "val_mae" in metrics
        assert "val_rmse" in metrics
        assert "val_r2" in metrics
        assert metrics["val_mae"] > 0

    def test_predict_correct_shape(self, dummy_data):
        X_train, y_train, X_val, y_val = dummy_data
        predictor = RidgeReturnPredictor()
        predictor.train(X_train, y_train, X_val, y_val)
        preds = predictor.predict(X_val)
        assert preds.shape == (len(X_val),)

    def test_save_load_roundtrip(self, dummy_data, tmp_path):
        X_train, y_train, X_val, y_val = dummy_data
        predictor = RidgeReturnPredictor()
        predictor.train(X_train, y_train, X_val, y_val)
        predictor.save(tmp_path)

        predictor2 = RidgeReturnPredictor()
        predictor2.load(tmp_path)
        preds1 = predictor.predict(X_val)
        preds2 = predictor2.predict(X_val)
        np.testing.assert_array_almost_equal(preds1, preds2, decimal=5)

    def test_files_exist(self, dummy_data, tmp_path):
        X_train, y_train, X_val, y_val = dummy_data
        predictor = RidgeReturnPredictor()
        predictor.train(X_train, y_train, X_val, y_val)
        predictor.save(tmp_path)
        assert RidgeReturnPredictor.files_exist(tmp_path)
        assert not RidgeReturnPredictor.files_exist(tmp_path / "nonexistent")

    def test_predict_single_sample(self, dummy_data):
        X_train, y_train, X_val, y_val = dummy_data
        predictor = RidgeReturnPredictor()
        predictor.train(X_train, y_train, X_val, y_val)
        preds = predictor.predict(X_val[:1])
        assert preds.shape == (1,)


class TestRandomForestReturnPredictor:
    def test_train_returns_metrics(self, dummy_data):
        X_train, y_train, X_val, y_val = dummy_data
        predictor = RandomForestReturnPredictor()
        metrics = predictor.train(X_train, y_train, X_val, y_val)
        assert "val_mae" in metrics
        assert "val_rmse" in metrics
        assert "val_r2" in metrics

    def test_predict_correct_shape(self, dummy_data):
        X_train, y_train, X_val, y_val = dummy_data
        predictor = RandomForestReturnPredictor()
        predictor.train(X_train, y_train, X_val, y_val)
        preds = predictor.predict(X_val)
        assert preds.shape == (len(X_val),)

    def test_save_load_roundtrip(self, dummy_data, tmp_path):
        X_train, y_train, X_val, y_val = dummy_data
        predictor = RandomForestReturnPredictor()
        predictor.train(X_train, y_train, X_val, y_val)
        predictor.save(tmp_path)

        predictor2 = RandomForestReturnPredictor()
        predictor2.load(tmp_path)
        preds1 = predictor.predict(X_val)
        preds2 = predictor2.predict(X_val)
        np.testing.assert_array_almost_equal(preds1, preds2, decimal=5)

    def test_no_scaler_needed(self, dummy_data):
        """RF is tree-based, no scaler."""
        X_train, y_train, X_val, y_val = dummy_data
        predictor = RandomForestReturnPredictor()
        predictor.train(X_train, y_train, X_val, y_val)
        assert predictor.scaler is None


class TestSVRReturnPredictor:
    def test_train_returns_metrics(self, dummy_data):
        X_train, y_train, X_val, y_val = dummy_data
        predictor = SVRReturnPredictor()
        metrics = predictor.train(X_train, y_train, X_val, y_val)
        assert "val_mae" in metrics
        assert "val_rmse" in metrics
        assert "val_r2" in metrics

    def test_predict_correct_shape(self, dummy_data):
        X_train, y_train, X_val, y_val = dummy_data
        predictor = SVRReturnPredictor()
        predictor.train(X_train, y_train, X_val, y_val)
        preds = predictor.predict(X_val)
        assert preds.shape == (len(X_val),)

    def test_save_load_roundtrip(self, dummy_data, tmp_path):
        X_train, y_train, X_val, y_val = dummy_data
        predictor = SVRReturnPredictor()
        predictor.train(X_train, y_train, X_val, y_val)
        predictor.save(tmp_path)

        predictor2 = SVRReturnPredictor()
        predictor2.load(tmp_path)
        preds1 = predictor.predict(X_val)
        preds2 = predictor2.predict(X_val)
        np.testing.assert_array_almost_equal(preds1, preds2, decimal=5)


class TestXGBoostReturnPredictor:
    def test_train_returns_metrics(self, dummy_data):
        X_train, y_train, X_val, y_val = dummy_data
        predictor = XGBoostReturnPredictor()
        metrics = predictor.train(X_train, y_train, X_val, y_val)
        assert "val_mae" in metrics
        assert "val_rmse" in metrics
        assert "val_r2" in metrics

    def test_no_scaler(self, dummy_data):
        """XGBoost is tree-based, no scaler in new version."""
        X_train, y_train, X_val, y_val = dummy_data
        predictor = XGBoostReturnPredictor()
        predictor.train(X_train, y_train, X_val, y_val)
        assert predictor.scaler is None

    def test_save_load_roundtrip(self, dummy_data, tmp_path):
        X_train, y_train, X_val, y_val = dummy_data
        predictor = XGBoostReturnPredictor()
        predictor.train(X_train, y_train, X_val, y_val)
        predictor.save(tmp_path)

        predictor2 = XGBoostReturnPredictor()
        predictor2.load(tmp_path)
        preds1 = predictor.predict(X_val)
        preds2 = predictor2.predict(X_val)
        np.testing.assert_array_almost_equal(preds1, preds2, decimal=5)


class TestEnsembleBlender:
    def test_train_trains_all_4_models(self, dummy_data):
        X_train, y_train, X_val, y_val = dummy_data
        X = np.vstack([X_train, X_val])
        y = np.concatenate([y_train, y_val])
        ensemble = EnsembleBlender()
        metrics = ensemble.train(X, y, validation_split=0.2)
        for mt in MODEL_TYPES:
            assert f"{mt}_metrics" in metrics

    def test_predict_returns_dict_with_all_4(self, dummy_data):
        X_train, y_train, X_val, y_val = dummy_data
        X = np.vstack([X_train, X_val])
        y = np.concatenate([y_train, y_val])
        ensemble = EnsembleBlender()
        ensemble.train(X, y)
        result = ensemble.predict(X_val)
        assert isinstance(result, dict)
        for mt in MODEL_TYPES:
            assert mt in result
            assert result[mt].shape == (len(X_val),)

    def test_save_load_roundtrip(self, dummy_data):
        X_train, y_train, X_val, y_val = dummy_data
        X = np.vstack([X_train, X_val])
        y = np.concatenate([y_train, y_val])
        symbol = "TEST_ENSEMBLE_NEW"
        ensemble = EnsembleBlender()
        ensemble.train(X, y)
        ensemble.save(symbol)

        ensemble2 = EnsembleBlender()
        ensemble2.load(symbol)
        result1 = ensemble.predict(X_val)
        result2 = ensemble2.predict(X_val)
        for mt in MODEL_TYPES:
            np.testing.assert_array_almost_equal(result1[mt], result2[mt], decimal=5)

        # Cleanup
        from sentinel.paths import DATA_DIR

        path = DATA_DIR / "ml_models" / symbol
        if path.exists():
            shutil.rmtree(path)

    def test_model_exists(self, dummy_data):
        X_train, y_train, X_val, y_val = dummy_data
        X = np.vstack([X_train, X_val])
        y = np.concatenate([y_train, y_val])
        symbol = "TEST_EXISTS_NEW"
        assert not EnsembleBlender.model_exists(symbol)

        ensemble = EnsembleBlender()
        ensemble.train(X, y)
        ensemble.save(symbol)
        assert EnsembleBlender.model_exists(symbol)

        # Cleanup
        from sentinel.paths import DATA_DIR

        path = DATA_DIR / "ml_models" / symbol
        if path.exists():
            shutil.rmtree(path)
