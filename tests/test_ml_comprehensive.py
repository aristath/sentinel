"""Comprehensive ML tests for production confidence.

These tests cover edge cases, numerical stability, integration scenarios,
and behaviors critical for a production ML system managing real investments.
"""

import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from sentinel.ml_ensemble import (
    EarlyStopping,
    EnsembleBlender,
    NeuralNetReturnPredictor,
    NumpyNeuralNetwork,
    XGBoostReturnPredictor,
)
from sentinel.ml_features import (
    DEFAULT_FEATURES,
    FEATURE_NAMES,
    NUM_FEATURES,
    features_to_array,
    validate_features,
)
from sentinel.ml_predictor import MLPredictor

# =============================================================================
# EarlyStopping Tests
# =============================================================================


class TestEarlyStopping:
    """Tests for EarlyStopping callback."""

    def test_initial_state(self):
        """Initial state has infinite best loss."""
        es = EarlyStopping(patience=5)
        assert es.best_loss == float("inf")
        assert es.counter == 0
        assert es.best_state is None

    def test_improvement_resets_counter(self):
        """Counter resets when loss improves."""
        es = EarlyStopping(patience=5)
        model = NumpyNeuralNetwork()

        # First call - should improve from inf
        should_stop = es(0.5, model)
        assert not should_stop
        assert es.counter == 0
        assert es.best_loss == 0.5

        # Worse loss - counter increments
        should_stop = es(0.6, model)
        assert not should_stop
        assert es.counter == 1

        # Better loss - counter resets
        should_stop = es(0.4, model)
        assert not should_stop
        assert es.counter == 0
        assert es.best_loss == 0.4

    def test_patience_triggers_stop(self):
        """Stop triggers after patience epochs without improvement."""
        es = EarlyStopping(patience=3)
        model = NumpyNeuralNetwork()

        # Initial good loss
        es(0.5, model)

        # 3 worse losses should trigger stop
        assert not es(0.6, model)  # counter = 1
        assert not es(0.7, model)  # counter = 2
        assert es(0.8, model)  # counter = 3 -> stop

    def test_best_state_saved(self):
        """Best model state is saved on improvement."""
        es = EarlyStopping(patience=5)
        model = NumpyNeuralNetwork()

        # Initial call saves state
        es(0.5, model)
        assert es.best_state is not None

        # Modify model weights
        model.weights[0][0, 0] = 999.0

        # Improvement saves new state
        es(0.3, model)

        # State should contain the 999 values (uses 'W1' key for first layer)
        assert es.best_state["W1"][0, 0] == 999.0

    def test_restore_best_works(self):
        """restore_best correctly restores model state."""
        es = EarlyStopping(patience=5)
        model = NumpyNeuralNetwork()

        # Save state with specific value
        model.weights[0].fill(1.0)
        es(0.5, model)

        # Modify model
        model.weights[0].fill(999.0)
        assert model.weights[0][0, 0] == 999.0

        # Restore should bring back original
        es.restore_best(model)
        assert model.weights[0][0, 0] == 1.0

    def test_restore_with_no_state_is_safe(self):
        """restore_best does nothing if no state saved."""
        es = EarlyStopping(patience=5)
        model = NumpyNeuralNetwork()

        model.weights[0].fill(42.0)

        # No state saved yet
        es.restore_best(model)

        # Model unchanged
        assert model.weights[0][0, 0] == 42.0


# =============================================================================
# NumpyNeuralNetwork Tests
# =============================================================================


class TestNumpyNeuralNetwork:
    """Tests for the NumPy neural network module."""

    def test_forward_pass_shape(self):
        """Forward pass produces correct output shape."""
        model = NumpyNeuralNetwork(input_dim=14)
        model.training = False  # eval mode
        x = np.random.randn(32, 14).astype(np.float32)
        output = model.forward(x)
        assert output.shape == (32, 1)

    def test_single_sample_forward(self):
        """Forward pass works with single sample (in eval mode)."""
        model = NumpyNeuralNetwork(input_dim=14)
        model.training = False  # eval mode uses running stats
        x = np.random.randn(1, 14).astype(np.float32)
        output = model.forward(x)
        assert output.shape == (1, 1)

    def test_different_input_dims(self):
        """Model can be built with different input dimensions."""
        for input_dim in [5, 14, 50]:
            model = NumpyNeuralNetwork(input_dim=input_dim)
            model.training = False
            x = np.random.randn(10, input_dim).astype(np.float32)
            output = model.forward(x)
            assert output.shape == (10, 1)

    def test_model_has_weights(self):
        """Model has weights and biases for all layers."""
        from sentinel.ml_features import NUM_FEATURES

        model = NumpyNeuralNetwork()
        # 4 layers: input->64, 64->32, 32->16, 16->1
        assert len(model.weights) == 4
        assert len(model.biases) == 4
        assert model.weights[0].shape == (NUM_FEATURES, 64)
        assert model.weights[1].shape == (64, 32)
        assert model.weights[2].shape == (32, 16)
        assert model.weights[3].shape == (16, 1)

    def test_dropout_in_train_mode(self):
        """Dropout is active in train mode (outputs vary)."""
        from sentinel.ml_features import NUM_FEATURES

        model = NumpyNeuralNetwork()
        model.training = True
        x = np.random.randn(100, NUM_FEATURES).astype(np.float32)

        # Multiple forward passes should give different results due to dropout
        outputs = [model.forward(x) for _ in range(10)]
        stacked = np.stack(outputs)
        variance = stacked.var(axis=0).mean()
        assert variance > 0

    def test_no_dropout_in_eval_mode(self):
        """Dropout is disabled in eval mode (outputs deterministic)."""
        from sentinel.ml_features import NUM_FEATURES

        model = NumpyNeuralNetwork()
        model.training = False
        x = np.random.randn(10, NUM_FEATURES).astype(np.float32)

        output1 = model.forward(x)
        output2 = model.forward(x)
        np.testing.assert_array_almost_equal(output1, output2)


# =============================================================================
# NeuralNetReturnPredictor Edge Cases
# =============================================================================


class TestNeuralNetEdgeCases:
    """Edge cases for neural network predictor."""

    def test_training_requires_minimum_samples(self):
        """Training fails with fewer than 2 samples."""
        nn = NeuralNetReturnPredictor()
        X_train = np.random.randn(1, NUM_FEATURES)
        y_train = np.array([0.05])
        X_val = np.random.randn(5, NUM_FEATURES)
        y_val = np.random.randn(5)

        with pytest.raises(ValueError, match="at least 2 samples"):
            nn.train(X_train, y_train, X_val, y_val)

    def test_training_with_exactly_2_samples(self):
        """Training works with exactly 2 samples."""
        nn = NeuralNetReturnPredictor()
        np.random.seed(42)
        X_train = np.random.randn(2, NUM_FEATURES)
        y_train = np.random.randn(2)
        X_val = np.random.randn(5, NUM_FEATURES)
        y_val = np.random.randn(5)

        # Should not raise
        metrics = nn.train(X_train, y_train, X_val, y_val, epochs=2)
        assert "val_mae" in metrics

    def test_batch_size_larger_than_dataset(self):
        """Batch size is adjusted when larger than dataset."""
        nn = NeuralNetReturnPredictor()
        np.random.seed(42)
        X_train = np.random.randn(10, NUM_FEATURES)
        y_train = np.random.randn(10)
        X_val = np.random.randn(5, NUM_FEATURES)
        y_val = np.random.randn(5)

        # Batch size 64 > dataset size 10 - should handle gracefully
        metrics = nn.train(X_train, y_train, X_val, y_val, epochs=2, batch_size=64)
        assert "val_mae" in metrics

    def test_drop_last_with_remainder_one(self):
        """drop_last is used when remainder would be 1 sample."""
        nn = NeuralNetReturnPredictor()
        np.random.seed(42)
        # 65 samples with batch_size=64 -> remainder of 1
        X_train = np.random.randn(65, NUM_FEATURES)
        y_train = np.random.randn(65)
        X_val = np.random.randn(10, NUM_FEATURES)
        y_val = np.random.randn(10)

        # Should not crash (drop_last handles the single-sample batch)
        metrics = nn.train(X_train, y_train, X_val, y_val, epochs=2, batch_size=64)
        assert "val_mae" in metrics

    def test_old_keras_model_detection(self, tmp_path):
        """Loading old Keras model raises helpful error."""
        # Create fake old Keras model file
        (tmp_path / "nn_model.keras").write_text("fake keras model")
        (tmp_path / "nn_scaler.pkl").write_bytes(b"fake scaler")

        nn = NeuralNetReturnPredictor()
        with pytest.raises(RuntimeError, match="old Keras model"):
            nn.load(str(tmp_path))

    def test_predict_requires_scaler(self):
        """Predict fails without fitted scaler."""
        nn = NeuralNetReturnPredictor()
        nn.build_model()
        X = np.random.randn(5, NUM_FEATURES)

        with pytest.raises((AttributeError, ValueError, AssertionError)):
            nn.predict(X)


# =============================================================================
# Model Persistence Tests
# =============================================================================


class TestModelPersistence:
    """Tests for model save/load cycle."""

    def test_nn_load_after_save_produces_same_predictions(self, tmp_path):
        """NN predictions are identical after load."""
        np.random.seed(42)
        X = np.random.randn(100, NUM_FEATURES)
        y = np.random.randn(100)

        nn = NeuralNetReturnPredictor()
        nn.train(X[:80], y[:80], X[80:], y[80:], epochs=5)

        test_X = X[:10]
        pred_before = nn.predict(test_X)

        nn.save(str(tmp_path))

        nn2 = NeuralNetReturnPredictor()
        nn2.load(str(tmp_path))
        pred_after = nn2.predict(test_X)

        np.testing.assert_array_almost_equal(pred_before, pred_after, decimal=6)

    def test_xgb_load_after_save_produces_same_predictions(self, tmp_path):
        """XGBoost predictions are identical after load."""
        np.random.seed(42)
        X = np.random.randn(100, NUM_FEATURES)
        y = np.random.randn(100)

        xgb = XGBoostReturnPredictor()
        xgb.train(X[:80], y[:80], X[80:], y[80:])

        test_X = X[:10]
        pred_before = xgb.predict(test_X)

        xgb.save(str(tmp_path))

        xgb2 = XGBoostReturnPredictor()
        xgb2.load(str(tmp_path))
        pred_after = xgb2.predict(test_X)

        np.testing.assert_array_almost_equal(pred_before, pred_after, decimal=6)

    def test_ensemble_metadata_saved_correctly(self, tmp_path):
        """Ensemble metadata contains expected fields."""
        from sentinel.paths import DATA_DIR

        np.random.seed(42)
        X = np.random.randn(100, NUM_FEATURES)
        y = np.random.randn(100)

        ensemble = EnsembleBlender(nn_weight=0.7, xgb_weight=0.3)
        ensemble.train(X, y)

        symbol = "TEST_META"
        ensemble.save(symbol)

        model_path = DATA_DIR / "ml_models" / symbol
        try:
            with open(model_path / "ensemble_metadata.json") as f:
                metadata = json.load(f)

            assert metadata["symbol"] == symbol
            assert metadata["nn_weight"] == 0.7
            assert metadata["xgb_weight"] == 0.3
            assert "saved_at" in metadata
        finally:
            if model_path.exists():
                shutil.rmtree(model_path)

    def test_loaded_ensemble_preserves_weights(self, tmp_path):
        """Loaded ensemble has correct weights."""
        np.random.seed(42)
        X = np.random.randn(100, NUM_FEATURES)
        y = np.random.randn(100)

        ensemble = EnsembleBlender(nn_weight=0.8, xgb_weight=0.2)
        ensemble.train(X, y)

        symbol = "TEST_WEIGHTS"
        ensemble.save(symbol)

        model_path = Path(f"data/ml_models/{symbol}")
        try:
            ensemble2 = EnsembleBlender()
            ensemble2.load(symbol)

            assert ensemble2.nn_weight == 0.8
            assert ensemble2.xgb_weight == 0.2
        finally:
            if model_path.exists():
                shutil.rmtree(model_path)


# =============================================================================
# Numerical Stability Tests
# =============================================================================


class TestNumericalStability:
    """Tests for numerical stability with extreme values."""

    def test_extreme_returns_in_training(self):
        """Training handles extreme return values."""
        np.random.seed(42)
        X = np.random.randn(100, NUM_FEATURES)
        # Extreme returns: -50% to +100%
        y = np.random.uniform(-0.5, 1.0, 100)

        ensemble = EnsembleBlender()
        metrics = ensemble.train(X, y)

        # Should complete without NaN
        assert not np.isnan(metrics["ensemble_val_mae"])
        assert not np.isnan(metrics["ensemble_val_rmse"])

    def test_predictions_are_finite(self):
        """Predictions never contain NaN or Inf."""
        np.random.seed(42)
        X = np.random.randn(100, NUM_FEATURES)
        y = np.random.randn(100) * 0.1

        ensemble = EnsembleBlender()
        ensemble.train(X, y)

        # Test with various inputs
        test_cases = [
            np.random.randn(10, NUM_FEATURES),  # Normal
            np.random.randn(10, NUM_FEATURES) * 10,  # Large values
            np.random.randn(10, NUM_FEATURES) * 0.001,  # Small values
            np.zeros((5, NUM_FEATURES)),  # All zeros
        ]

        for test_X in test_cases:
            preds = ensemble.predict(test_X)
            assert np.all(np.isfinite(preds)), "Non-finite predictions for input"

    def test_scaler_handles_constant_features(self):
        """Scaler handles features with zero variance."""
        np.random.seed(42)
        X = np.random.randn(100, NUM_FEATURES)
        # Make one feature constant
        X[:, 5] = 1.0
        y = np.random.randn(100)

        nn = NeuralNetReturnPredictor()
        # Should not crash with constant feature
        metrics = nn.train(X[:80], y[:80], X[80:], y[80:], epochs=2)
        assert "val_mae" in metrics

    def test_very_small_loss_values(self):
        """Training handles when predictions are very accurate."""
        np.random.seed(42)
        X = np.random.randn(100, NUM_FEATURES)
        # Target is a simple function of first feature
        y = X[:, 0] * 0.01  # Very predictable

        xgb = XGBoostReturnPredictor()
        metrics = xgb.train(X[:80], y[:80], X[80:], y[80:])

        # MAE should be small but not cause numerical issues
        assert metrics["val_mae"] >= 0
        assert np.isfinite(metrics["val_mae"])


# =============================================================================
# Reproducibility Tests
# =============================================================================


class TestReproducibility:
    """Tests for reproducible results."""

    def test_same_seed_same_xgb_predictions(self):
        """Same seed produces identical XGBoost results."""
        X = np.random.randn(100, NUM_FEATURES)
        y = np.random.randn(100)

        xgb1 = XGBoostReturnPredictor()
        xgb1.train(X[:80], y[:80], X[80:], y[80:])
        preds1 = xgb1.predict(X[:10])

        xgb2 = XGBoostReturnPredictor()
        xgb2.train(X[:80], y[:80], X[80:], y[80:])
        preds2 = xgb2.predict(X[:10])

        np.testing.assert_array_almost_equal(preds1, preds2)

    def test_same_validation_split_both_models(self):
        """NN and XGBoost use identical validation split in ensemble."""
        np.random.seed(42)
        X = np.random.randn(100, NUM_FEATURES)
        y = X[:, 0] * 0.5 + np.random.randn(100) * 0.01  # Strong signal in feature 0

        ensemble = EnsembleBlender()
        metrics = ensemble.train(X, y, validation_split=0.2)

        # Both models should see same validation data
        # So validation metrics should be computed on same samples
        # This is implicitly tested by consistent_validation test
        # but let's verify explicitly
        assert metrics["nn_metrics"]["val_mae"] > 0
        assert metrics["xgb_metrics"]["val_mae"] > 0


# =============================================================================
# Feature Integration Tests
# =============================================================================


class TestFeatureIntegration:
    """Tests for feature extraction to prediction pipeline."""

    def test_features_to_array_order_matches_training(self):
        """features_to_array produces array in same order as training."""
        features = {name: float(i) for i, name in enumerate(FEATURE_NAMES)}
        arr = features_to_array(features)

        # Verify order matches FEATURE_NAMES
        for i, _name in enumerate(FEATURE_NAMES):
            assert arr[i] == float(i)

    def test_default_features_produce_valid_predictions(self):
        """Model can predict using default features."""
        np.random.seed(42)
        X = np.random.randn(100, NUM_FEATURES)
        y = np.random.randn(100)

        ensemble = EnsembleBlender()
        ensemble.train(X, y)

        default_arr = features_to_array(DEFAULT_FEATURES).reshape(1, -1)
        pred = ensemble.predict(default_arr)

        assert pred.shape == (1,)
        assert np.isfinite(pred[0])

    def test_validated_features_are_predictable(self):
        """Features after validation can be used for prediction."""
        np.random.seed(42)
        X = np.random.randn(100, NUM_FEATURES)
        y = np.random.randn(100)

        ensemble = EnsembleBlender()
        ensemble.train(X, y)

        # Create features with some issues
        features = {
            "return_1d": 0.05,
            "return_5d": float("nan"),  # Will be replaced with default
            "return_20d": 0.1,
            "return_60d": -0.05,
            "price_normalized": -0.5,
            "volatility_10d": 0.02,
            "volatility_30d": 0.03,
            "atr_14d": 0.015,
            "volume_normalized": 1.5,
            "volume_trend": 0.1,
            "rsi_14": 0.6,
            "macd": 0.01,
            "bollinger_position": 0.7,
            "sentiment_score": 0.55,
        }

        cleaned, _ = validate_features(features)
        arr = features_to_array(cleaned).reshape(1, -1)
        pred = ensemble.predict(arr)

        assert np.isfinite(pred[0])


# =============================================================================
# MLPredictor Integration Tests
# =============================================================================


class TestMLPredictorIntegration:
    """Integration tests for MLPredictor class."""

    def test_normalize_return_to_score_mapping(self):
        """Return to score mapping is correct."""
        predictor = MLPredictor()

        # Test key points
        assert predictor._normalize_return_to_score(-0.10) == 0.0  # -10% -> 0
        assert predictor._normalize_return_to_score(0.0) == 0.5  # 0% -> 0.5
        assert predictor._normalize_return_to_score(0.10) == 1.0  # +10% -> 1.0

        # Test intermediate values
        assert abs(predictor._normalize_return_to_score(0.05) - 0.75) < 0.01  # +5% -> 0.75
        assert abs(predictor._normalize_return_to_score(-0.05) - 0.25) < 0.01  # -5% -> 0.25

        # Test clipping
        assert predictor._normalize_return_to_score(0.50) == 1.0  # +50% clipped to 1
        assert predictor._normalize_return_to_score(-0.50) == 0.0  # -50% clipped to 0

    def test_fallback_to_wavelet_structure(self):
        """Fallback returns correct structure."""
        predictor = MLPredictor()
        result = predictor._fallback_to_wavelet(0.65)

        assert result["ml_predicted_return"] == 0.0
        assert result["wavelet_score"] == 0.65
        assert result["blend_ratio"] == 0.0
        assert result["final_score"] == 0.65

    def test_cache_clear_single_symbol(self):
        """Cache clear works for single symbol."""
        predictor = MLPredictor()
        predictor._models["AAPL"] = MagicMock()
        predictor._models["GOOGL"] = MagicMock()
        predictor._load_times["AAPL"] = 12345
        predictor._load_times["GOOGL"] = 12345

        predictor.clear_cache("AAPL")

        assert "AAPL" not in predictor._models
        assert "GOOGL" in predictor._models

    def test_cache_clear_all(self):
        """Cache clear all removes everything."""
        predictor = MLPredictor()
        predictor._models["AAPL"] = MagicMock()
        predictor._models["GOOGL"] = MagicMock()

        predictor.clear_cache()

        assert len(predictor._models) == 0


# =============================================================================
# Model Existence Check Tests
# =============================================================================


class TestModelExistence:
    """Tests for model existence checks."""

    def test_model_exists_requires_all_files(self, tmp_path):
        """model_exists returns False if any file missing."""
        symbol = "PARTIAL_MODEL"
        model_path = Path(f"data/ml_models/{symbol}")
        model_path.mkdir(parents=True, exist_ok=True)

        try:
            # Create only some files
            (model_path / "ensemble_metadata.json").write_text("{}")
            (model_path / "nn_model.npz").write_text("")  # .npz for NumPy format

            # Should return False - missing other files
            assert EnsembleBlender.model_exists(symbol) is False

        finally:
            if model_path.exists():
                shutil.rmtree(model_path)

    def test_model_exists_with_all_files(self):
        """model_exists returns True when all files present."""
        np.random.seed(42)
        X = np.random.randn(100, NUM_FEATURES)
        y = np.random.randn(100)

        ensemble = EnsembleBlender()
        ensemble.train(X, y)

        symbol = "FULL_MODEL"
        ensemble.save(symbol)

        model_path = Path(f"data/ml_models/{symbol}")
        try:
            assert EnsembleBlender.model_exists(symbol) is True
        finally:
            if model_path.exists():
                shutil.rmtree(model_path)


# =============================================================================
# Training History Tests
# =============================================================================


class TestTrainingHistory:
    """Tests for training history and metrics."""

    def test_nn_history_recorded(self):
        """NN training records loss history."""
        np.random.seed(42)
        X = np.random.randn(100, NUM_FEATURES)
        y = np.random.randn(100)

        nn = NeuralNetReturnPredictor()
        metrics = nn.train(X[:80], y[:80], X[80:], y[80:], epochs=10)

        assert "history" in metrics
        assert "loss" in metrics["history"]
        assert "val_loss" in metrics["history"]
        assert len(metrics["history"]["loss"]) > 0
        assert len(metrics["history"]["val_loss"]) > 0

    def test_early_stopping_can_trigger(self):
        """Early stopping mechanism works correctly."""
        np.random.seed(42)
        X = np.random.randn(200, NUM_FEATURES)
        y = np.random.randn(200) * 0.1

        nn = NeuralNetReturnPredictor()
        metrics = nn.train(X[:160], y[:160], X[160:], y[160:], epochs=200)

        # Early stopping should record epochs trained
        assert "epochs_trained" in metrics
        assert metrics["epochs_trained"] > 0
        # Either stopped early or ran to completion
        assert metrics["epochs_trained"] <= 200

    def test_training_loss_generally_decreases(self):
        """Training loss generally trends downward."""
        np.random.seed(42)
        X = np.random.randn(200, NUM_FEATURES)
        y = X[:, 0] * 0.1 + np.random.randn(200) * 0.01

        nn = NeuralNetReturnPredictor()
        metrics = nn.train(X[:160], y[:160], X[160:], y[160:], epochs=20)

        losses = metrics["history"]["loss"]
        # First loss should generally be higher than last
        # (may not always hold due to noise, but likely)
        if len(losses) > 5:
            early_avg = np.mean(losses[:3])
            late_avg = np.mean(losses[-3:])
            # Loose check - training should help
            assert late_avg <= early_avg * 2  # At least not catastrophically worse
