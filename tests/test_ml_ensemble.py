"""Test ML ensemble models."""

import numpy as np
import pytest
from sklearn.model_selection import train_test_split

from sentinel.ml_ensemble import (
    EnsembleBlender,
    NeuralNetReturnPredictor,
    XGBoostReturnPredictor,
)
from sentinel.ml_features import FEATURE_NAMES, NUM_FEATURES


def test_feature_count():
    """Verify feature count is correct (20 features: 14 core + 6 aggregate)."""
    assert NUM_FEATURES == 20
    assert len(FEATURE_NAMES) == 20


def test_nn_build_train_predict():
    """Test NN model building, training, and prediction."""
    nn = NeuralNetReturnPredictor()

    # Build model with correct number of features
    model = nn.build_model(input_dim=NUM_FEATURES)
    assert model is not None
    # NumPy model has weights for each layer
    assert len(model.weights) > 0

    # Generate dummy data
    np.random.seed(42)
    X = np.random.randn(1000, NUM_FEATURES)
    y = np.random.randn(1000) * 0.05  # Returns -5% to +5%

    # Split data (new API requires pre-split data)
    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)

    # Train with new API
    metrics = nn.train(X_train, y_train, X_val, y_val, epochs=5, batch_size=64)
    assert "val_mae" in metrics
    assert "val_rmse" in metrics
    assert metrics["val_mae"] > 0

    # Predict
    preds = nn.predict(X[:10])
    assert len(preds) == 10
    assert all(isinstance(p, (float, np.floating)) for p in preds)


def test_xgb_train_predict():
    """Test XGBoost model training and prediction."""
    xgb_model = XGBoostReturnPredictor()

    # Generate dummy data
    np.random.seed(42)
    X = np.random.randn(1000, NUM_FEATURES)
    y = np.random.randn(1000) * 0.05

    # Split data (new API requires pre-split data)
    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)

    # Train with new API
    metrics = xgb_model.train(X_train, y_train, X_val, y_val)
    assert "val_mae" in metrics
    assert "val_rmse" in metrics
    assert metrics["val_mae"] > 0

    # Check feature importance is extracted
    assert "feature_importance" in metrics
    assert isinstance(metrics["feature_importance"], dict)
    assert len(metrics["feature_importance"]) == NUM_FEATURES

    # Predict
    preds = xgb_model.predict(X[:10])
    assert len(preds) == 10
    assert all(isinstance(p, (float, np.floating)) for p in preds)


def test_ensemble_blending():
    """Test 50-50 ensemble blending."""
    ensemble = EnsembleBlender(nn_weight=0.5, xgb_weight=0.5)

    # Generate dummy data
    np.random.seed(42)
    X = np.random.randn(1000, NUM_FEATURES)
    y = np.random.randn(1000) * 0.05

    # Train (EnsembleBlender.train() handles the split internally)
    metrics = ensemble.train(X, y, validation_split=0.2)
    assert "ensemble_val_mae" in metrics
    assert "ensemble_val_rmse" in metrics
    assert "nn_metrics" in metrics
    assert "xgb_metrics" in metrics

    # Predict
    preds = ensemble.predict(X[:10])
    assert len(preds) == 10
    assert all(isinstance(p, (float, np.floating)) for p in preds)


def test_ensemble_consistent_validation():
    """Test that ensemble uses consistent validation set for all metrics."""
    ensemble = EnsembleBlender(nn_weight=0.5, xgb_weight=0.5)

    # Generate dummy data with a pattern
    np.random.seed(42)
    X = np.random.randn(500, NUM_FEATURES)
    # Create y with some correlation to X
    y = X[:, 0] * 0.02 + np.random.randn(500) * 0.01

    metrics = ensemble.train(X, y, validation_split=0.2)

    # All validation metrics should be computed on the same set
    # So ensemble metrics should be a blend of individual metrics
    # (not exactly, but reasonable relationship)
    assert metrics["nn_metrics"]["val_rmse"] > 0
    assert metrics["xgb_metrics"]["val_rmse"] > 0
    assert metrics["ensemble_val_rmse"] > 0

    # Ensemble should generally not be worse than the worst individual model
    # (though not guaranteed with small noisy data)
    max_individual_rmse = max(metrics["nn_metrics"]["val_rmse"], metrics["xgb_metrics"]["val_rmse"])
    # Allow some tolerance for noise
    assert metrics["ensemble_val_rmse"] < max_individual_rmse * 1.5


def test_ensemble_weights_sum_to_one():
    """Test that ensemble weights must sum to 1.0."""
    # Valid weights
    ensemble = EnsembleBlender(nn_weight=0.5, xgb_weight=0.5)
    assert ensemble.nn_weight + ensemble.xgb_weight == 1.0

    # Invalid weights should raise
    with pytest.raises(ValueError):
        EnsembleBlender(nn_weight=0.6, xgb_weight=0.6)


def test_ensemble_save_load(tmp_path):
    """Test ensemble model saving and loading."""
    ensemble = EnsembleBlender(nn_weight=0.5, xgb_weight=0.5)

    # Train with small dataset
    np.random.seed(42)
    X = np.random.randn(100, NUM_FEATURES)
    y = np.random.randn(100) * 0.05
    ensemble.train(X, y, validation_split=0.2)

    # Save (now uses symbol instead of version)
    symbol = "TEST_SYMBOL"
    ensemble.save(symbol)

    # Load
    ensemble2 = EnsembleBlender()
    ensemble2.load(symbol)

    # Compare predictions
    preds1 = ensemble.predict(X[:5])
    preds2 = ensemble2.predict(X[:5])

    np.testing.assert_array_almost_equal(preds1, preds2, decimal=5)

    # Cleanup
    import shutil
    from pathlib import Path

    model_path = Path(f"data/ml_models/{symbol}")
    if model_path.exists():
        shutil.rmtree(model_path)


def test_model_exists():
    """Test model existence check."""
    # Non-existent symbol
    assert EnsembleBlender.model_exists("DEFINITELY_NOT_A_SYMBOL") is False

    # Create a model and check it exists
    ensemble = EnsembleBlender(nn_weight=0.5, xgb_weight=0.5)
    np.random.seed(42)
    X = np.random.randn(100, NUM_FEATURES)
    y = np.random.randn(100) * 0.05
    ensemble.train(X, y, validation_split=0.2)

    symbol = "TEST_EXISTS"
    ensemble.save(symbol)

    assert EnsembleBlender.model_exists(symbol) is True

    # Cleanup
    import shutil
    from pathlib import Path

    model_path = Path(f"data/ml_models/{symbol}")
    if model_path.exists():
        shutil.rmtree(model_path)


class TestNeuralNetArchitecture:
    """Tests for Neural Network model architecture."""

    @pytest.fixture
    def predictor(self):
        return NeuralNetReturnPredictor()

    def test_model_has_correct_layers(self, predictor):
        """Model has expected layer structure (Linear + BatchNorm + Dropout)."""
        model = predictor.build_model()
        # NumPy model has 4 linear layers (weights)
        assert len(model.weights) == 4
        # Has BatchNorm parameters for first two layers
        assert hasattr(model, "bn1_gamma")
        assert hasattr(model, "bn2_gamma")
        # Has dropout rates
        assert len(model.dropout_rates) == 5

    def test_model_single_output_neuron(self, predictor):
        """Output layer has single neuron for return prediction."""
        model = predictor.build_model()
        # Check output layer (last weight matrix) has 1 output feature
        assert model.weights[-1].shape[1] == 1

    def test_model_linear_output_activation(self, predictor):
        """Output layer uses linear activation for unbounded return prediction."""
        # NumPy model's final layer has no activation (linear output)
        # This is verified by the architecture - dims[-1] = 1 with no ReLU
        model = predictor.build_model()
        # Verify the output layer dimensions
        assert model.dims[-1] == 1

    def test_scaler_fit_on_training_data_only(self, predictor):
        """Scaler is fit only on training data, not validation."""
        np.random.seed(42)
        X_train = np.random.randn(100, NUM_FEATURES)
        X_val = np.random.randn(20, NUM_FEATURES) * 10  # Different scale
        y_train = np.random.randn(100)
        y_val = np.random.randn(20)

        predictor.train(X_train, y_train, X_val, y_val, epochs=2)

        # Scaler should be fit on X_train statistics
        # So mean should be close to 0 and std close to 1 for training data
        X_train_scaled = predictor.scaler.transform(X_train)
        assert np.abs(X_train_scaled.mean()) < 0.2
        assert np.abs(X_train_scaled.std() - 1.0) < 0.2


class TestXGBoostModelProperties:
    """Tests for XGBoost model properties."""

    @pytest.fixture
    def trained_predictor(self):
        np.random.seed(42)
        X = np.random.randn(200, NUM_FEATURES)
        y = X[:, 0] * 0.5 + np.random.randn(200) * 0.1
        predictor = XGBoostReturnPredictor()
        predictor.train(X[:160], y[:160], X[160:], y[160:])
        return predictor

    def test_feature_importance_maps_to_feature_names(self, trained_predictor):
        """Feature importance keys match FEATURE_NAMES."""
        importance = trained_predictor.feature_importance
        for name in importance.keys():
            assert name in FEATURE_NAMES

    def test_feature_importance_values_are_positive(self, trained_predictor):
        """All feature importance values are non-negative."""
        importance = trained_predictor.feature_importance
        for value in importance.values():
            assert value >= 0

    def test_model_uses_specified_hyperparameters(self, trained_predictor):
        """Model uses the specified hyperparameters."""
        model = trained_predictor.model
        assert model.n_estimators == 150
        assert model.max_depth == 4


class TestEnsembleBlendingMath:
    """Tests for ensemble blending calculations."""

    @pytest.fixture
    def trained_ensemble(self):
        np.random.seed(42)
        X = np.random.randn(200, NUM_FEATURES)
        y = np.random.randn(200)
        ensemble = EnsembleBlender(nn_weight=0.6, xgb_weight=0.4)
        ensemble.train(X, y, validation_split=0.2)
        return ensemble, X

    def test_custom_weights_applied_correctly(self, trained_ensemble):
        """Custom weights are correctly applied in blending."""
        ensemble, X = trained_ensemble
        test_X = X[:5]

        nn_preds = ensemble.nn_predictor.predict(test_X)
        xgb_preds = ensemble.xgb_predictor.predict(test_X)

        expected = 0.6 * nn_preds + 0.4 * xgb_preds
        actual = ensemble.predict(test_X)

        np.testing.assert_array_almost_equal(expected, actual)

    def test_equal_weights_gives_mean(self):
        """Equal weights (0.5, 0.5) gives arithmetic mean."""
        np.random.seed(42)
        X = np.random.randn(200, NUM_FEATURES)
        y = np.random.randn(200)

        ensemble = EnsembleBlender(nn_weight=0.5, xgb_weight=0.5)
        ensemble.train(X, y, validation_split=0.2)

        test_X = X[:5]
        nn_preds = ensemble.nn_predictor.predict(test_X)
        xgb_preds = ensemble.xgb_predictor.predict(test_X)

        expected_mean = (nn_preds + xgb_preds) / 2
        actual = ensemble.predict(test_X)

        np.testing.assert_array_almost_equal(expected_mean, actual)


class TestMetricsCalculation:
    """Tests for metrics calculation (MAE, RMSE, R^2)."""

    def test_mae_calculation(self):
        """MAE is computed correctly."""
        np.random.seed(42)
        X = np.random.randn(200, NUM_FEATURES)
        y = np.random.randn(200) * 0.1

        predictor = XGBoostReturnPredictor()
        metrics = predictor.train(X[:160], y[:160], X[160:], y[160:])

        # MAE should be positive and reasonable for this data
        assert metrics["val_mae"] > 0
        assert metrics["val_mae"] < 1.0  # Reasonable for normalized returns

    def test_rmse_greater_than_mae(self):
        """RMSE is always >= MAE due to squaring larger errors."""
        np.random.seed(42)
        X = np.random.randn(200, NUM_FEATURES)
        y = np.random.randn(200) * 0.1

        predictor = XGBoostReturnPredictor()
        metrics = predictor.train(X[:160], y[:160], X[160:], y[160:])

        assert metrics["val_rmse"] >= metrics["val_mae"]

    def test_r2_bounded(self):
        """R^2 should be bounded (can be negative for poor fits)."""
        np.random.seed(42)
        X = np.random.randn(200, NUM_FEATURES)
        y = np.random.randn(200) * 0.1

        predictor = XGBoostReturnPredictor()
        metrics = predictor.train(X[:160], y[:160], X[160:], y[160:])

        # R^2 should be less than 1 (perfect fit)
        assert metrics["val_r2"] <= 1.0


class TestModelPersistence:
    """Tests for model save/load functionality."""

    def test_nn_save_creates_all_files(self, tmp_path):
        """NN save creates model, scaler, and metadata files."""
        np.random.seed(42)
        X = np.random.randn(100, NUM_FEATURES)
        y = np.random.randn(100)

        predictor = NeuralNetReturnPredictor()
        predictor.train(X[:80], y[:80], X[80:], y[80:], epochs=2)
        predictor.save(str(tmp_path))

        assert (tmp_path / "nn_model.npz").exists()  # NumPy format
        assert (tmp_path / "nn_scaler.pkl").exists()
        assert (tmp_path / "nn_metadata.json").exists()

    def test_xgb_save_creates_all_files(self, tmp_path):
        """XGBoost save creates model, scaler, and metadata files."""
        np.random.seed(42)
        X = np.random.randn(100, NUM_FEATURES)
        y = np.random.randn(100)

        predictor = XGBoostReturnPredictor()
        predictor.train(X[:80], y[:80], X[80:], y[80:])
        predictor.save(str(tmp_path))

        assert (tmp_path / "xgb_model.json").exists()
        assert (tmp_path / "xgb_scaler.pkl").exists()
        assert (tmp_path / "xgb_metadata.json").exists()

    def test_xgb_metadata_contains_feature_importance(self, tmp_path):
        """XGBoost metadata includes feature importance."""
        import json

        np.random.seed(42)
        X = np.random.randn(100, NUM_FEATURES)
        y = np.random.randn(100)

        predictor = XGBoostReturnPredictor()
        predictor.train(X[:80], y[:80], X[80:], y[80:])
        predictor.save(str(tmp_path))

        with open(tmp_path / "xgb_metadata.json", "r") as f:
            metadata = json.load(f)

        assert "feature_importance" in metadata
        assert isinstance(metadata["feature_importance"], dict)


class TestMLEnsembleEdgeCases:
    """Edge case tests for ML ensemble."""

    def test_very_small_dataset(self):
        """Handles very small datasets."""
        np.random.seed(42)
        X = np.random.randn(30, NUM_FEATURES)
        y = np.random.randn(30)

        ensemble = EnsembleBlender()
        # Should not crash
        metrics = ensemble.train(X, y, validation_split=0.3)
        assert metrics is not None

    def test_single_sample_prediction(self):
        """Can predict for a single sample."""
        np.random.seed(42)
        X = np.random.randn(100, NUM_FEATURES)
        y = np.random.randn(100)

        ensemble = EnsembleBlender()
        ensemble.train(X, y, validation_split=0.2)

        single = X[0:1]  # Shape (1, NUM_FEATURES)
        pred = ensemble.predict(single)
        assert pred.shape == (1,)

    def test_batch_prediction(self):
        """Can predict for a batch of samples."""
        np.random.seed(42)
        X = np.random.randn(100, NUM_FEATURES)
        y = np.random.randn(100)

        ensemble = EnsembleBlender()
        ensemble.train(X, y, validation_split=0.2)

        batch = X[:50]
        pred = ensemble.predict(batch)
        assert pred.shape == (50,)

    def test_predictions_are_deterministic(self):
        """Same input produces same output."""
        np.random.seed(42)
        X = np.random.randn(100, NUM_FEATURES)
        y = np.random.randn(100)

        ensemble = EnsembleBlender()
        ensemble.train(X, y, validation_split=0.2)

        test_X = X[:10]
        pred1 = ensemble.predict(test_X)
        pred2 = ensemble.predict(test_X)

        np.testing.assert_array_almost_equal(pred1, pred2)

    def test_constant_target_handling(self):
        """Handles constant target gracefully."""
        np.random.seed(42)
        X = np.random.randn(100, NUM_FEATURES)
        y = np.ones(100) * 0.05  # Constant target

        ensemble = EnsembleBlender()
        # R^2 calculation has division by zero when variance is 0
        # Should still complete without crashing
        metrics = ensemble.train(X, y, validation_split=0.2)
        assert metrics is not None
