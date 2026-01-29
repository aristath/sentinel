"""ML ensemble models for per-security return prediction.

Neural network implemented in pure NumPy for lightweight deployment.
"""

import json
import logging
import pickle
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from sentinel.ml_features import FEATURE_NAMES, NUM_FEATURES

logger = logging.getLogger(__name__)


def _compute_regression_metrics(predictions: np.ndarray, labels: np.ndarray) -> tuple[float, float, float]:
    """Compute MAE, RMSE, and R² for regression predictions.

    Returns:
        Tuple of (mae, rmse, r2)
    """
    mae = float(np.mean(np.abs(predictions - labels)))
    rmse = float(np.sqrt(np.mean((predictions - labels) ** 2)))
    ss_res = np.sum((labels - predictions) ** 2)
    ss_tot = np.sum((labels - np.mean(labels)) ** 2)
    r2 = float(1 - (ss_res / ss_tot)) if ss_tot > 0 else 0.0
    return mae, rmse, r2


# =============================================================================
# NumPy Neural Network Implementation
# =============================================================================


class NumpyNeuralNetwork:
    """
    Neural network implemented in pure NumPy.

    Architecture (matches original PyTorch):
    - Input: 14 features
    - Hidden 1: 64 neurons, BatchNorm, ReLU, Dropout(0.3)
    - Hidden 2: 32 neurons, BatchNorm, ReLU, Dropout(0.2)
    - Hidden 3: 16 neurons, ReLU, Dropout(0.1)
    - Output: 1 neuron (predicted return)
    """

    def __init__(self, input_dim: int = NUM_FEATURES):
        self.input_dim = input_dim

        # Layer dimensions
        self.dims = [input_dim, 64, 32, 16, 1]

        # Dropout rates (0 = no dropout)
        self.dropout_rates = [0.0, 0.3, 0.2, 0.1, 0.0]

        # Initialize weights using Xavier initialization
        self._init_weights()

        # BatchNorm parameters for layers 1 and 2
        self._init_batchnorm()

        # Training mode flag
        self.training = True

    def _init_weights(self):
        """Initialize weights using Xavier initialization."""
        np.random.seed(42)  # For reproducibility

        self.weights = []
        self.biases = []

        for i in range(len(self.dims) - 1):
            # Xavier initialization: sqrt(2 / (fan_in + fan_out))
            fan_in, fan_out = self.dims[i], self.dims[i + 1]
            std = np.sqrt(2.0 / (fan_in + fan_out))
            W = np.random.randn(fan_in, fan_out).astype(np.float32) * std
            b = np.zeros(fan_out, dtype=np.float32)
            self.weights.append(W)
            self.biases.append(b)

    def _init_batchnorm(self):
        """Initialize BatchNorm parameters for layers 1 and 2."""
        # BatchNorm for layer 1 (64 neurons)
        self.bn1_gamma = np.ones(64, dtype=np.float32)
        self.bn1_beta = np.zeros(64, dtype=np.float32)
        self.bn1_running_mean = np.zeros(64, dtype=np.float32)
        self.bn1_running_var = np.ones(64, dtype=np.float32)

        # BatchNorm for layer 2 (32 neurons)
        self.bn2_gamma = np.ones(32, dtype=np.float32)
        self.bn2_beta = np.zeros(32, dtype=np.float32)
        self.bn2_running_mean = np.zeros(32, dtype=np.float32)
        self.bn2_running_var = np.ones(32, dtype=np.float32)

        # Momentum for running statistics
        self.bn_momentum = 0.1
        self.bn_eps = 1e-5

    def _batchnorm_forward(
        self,
        x: np.ndarray,
        gamma: np.ndarray,
        beta: np.ndarray,
        running_mean: np.ndarray,
        running_var: np.ndarray,
    ) -> Tuple[np.ndarray, Optional[Dict]]:
        """
        BatchNorm forward pass.

        Returns:
            Tuple of (output, cache for backward pass)
        """
        if self.training:
            # Calculate batch statistics
            batch_mean = np.mean(x, axis=0)
            batch_var = np.var(x, axis=0)

            # Update running statistics
            running_mean[:] = (1 - self.bn_momentum) * running_mean + self.bn_momentum * batch_mean
            running_var[:] = (1 - self.bn_momentum) * running_var + self.bn_momentum * batch_var

            # Normalize
            x_norm = (x - batch_mean) / np.sqrt(batch_var + self.bn_eps)

            # Cache for backward pass
            cache = {
                "x": x,
                "x_norm": x_norm,
                "mean": batch_mean,
                "var": batch_var,
                "gamma": gamma,
            }
        else:
            # Use running statistics for inference
            x_norm = (x - running_mean) / np.sqrt(running_var + self.bn_eps)
            cache = None

        # Scale and shift
        out = gamma * x_norm + beta
        return out, cache

    def _batchnorm_backward(
        self,
        dout: np.ndarray,
        cache: Dict,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        BatchNorm backward pass.

        Returns:
            Tuple of (dx, dgamma, dbeta)
        """
        x, x_norm, mean, var, gamma = cache["x"], cache["x_norm"], cache["mean"], cache["var"], cache["gamma"]
        N = x.shape[0]

        # Gradients
        dgamma = np.sum(dout * x_norm, axis=0)
        dbeta = np.sum(dout, axis=0)

        # Gradient w.r.t. normalized x
        dx_norm = dout * gamma

        # Gradient w.r.t. variance
        std_inv = 1.0 / np.sqrt(var + self.bn_eps)
        dvar = np.sum(dx_norm * (x - mean) * -0.5 * std_inv**3, axis=0)

        # Gradient w.r.t. mean
        dmean = np.sum(dx_norm * -std_inv, axis=0) + dvar * np.mean(-2.0 * (x - mean), axis=0)

        # Gradient w.r.t. input
        dx = dx_norm * std_inv + dvar * 2.0 * (x - mean) / N + dmean / N

        return dx, dgamma, dbeta

    def _relu(self, x: np.ndarray) -> np.ndarray:
        """ReLU activation."""
        return np.maximum(0, x)

    def _relu_backward(self, dout: np.ndarray, x: np.ndarray) -> np.ndarray:
        """ReLU backward pass."""
        return dout * (x > 0).astype(np.float32)

    def _dropout(self, x: np.ndarray, rate: float) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        """
        Dropout forward pass.

        Returns:
            Tuple of (output, mask for backward pass)
        """
        if self.training and rate > 0:
            mask = (np.random.rand(*x.shape) > rate).astype(np.float32)
            # Scale by 1/(1-rate) during training so we don't need to scale during inference
            return x * mask / (1 - rate), mask
        return x, None

    def _dropout_backward(self, dout: np.ndarray, mask: np.ndarray, rate: float) -> np.ndarray:
        """Dropout backward pass."""
        if mask is not None:
            return dout * mask / (1 - rate)
        return dout

    def forward(self, X: np.ndarray) -> np.ndarray:
        """
        Forward pass through the network.

        Args:
            X: Input features (batch_size, input_dim)

        Returns:
            Predictions (batch_size, 1)
        """
        self.cache = {}  # Store values for backward pass

        # Layer 1: Linear -> BatchNorm -> ReLU -> Dropout
        z1 = X @ self.weights[0] + self.biases[0]
        self.cache["z1_pre"] = z1
        bn1_out, self.cache["bn1"] = self._batchnorm_forward(
            z1, self.bn1_gamma, self.bn1_beta, self.bn1_running_mean, self.bn1_running_var
        )
        a1 = self._relu(bn1_out)
        self.cache["a1_pre_dropout"] = a1
        a1, self.cache["dropout1_mask"] = self._dropout(a1, self.dropout_rates[1])
        self.cache["a1"] = a1

        # Layer 2: Linear -> BatchNorm -> ReLU -> Dropout
        z2 = a1 @ self.weights[1] + self.biases[1]
        self.cache["z2_pre"] = z2
        bn2_out, self.cache["bn2"] = self._batchnorm_forward(
            z2, self.bn2_gamma, self.bn2_beta, self.bn2_running_mean, self.bn2_running_var
        )
        a2 = self._relu(bn2_out)
        self.cache["a2_pre_dropout"] = a2
        a2, self.cache["dropout2_mask"] = self._dropout(a2, self.dropout_rates[2])
        self.cache["a2"] = a2

        # Layer 3: Linear -> ReLU -> Dropout (no BatchNorm)
        z3 = a2 @ self.weights[2] + self.biases[2]
        self.cache["z3"] = z3
        a3 = self._relu(z3)
        self.cache["a3_pre_dropout"] = a3
        a3, self.cache["dropout3_mask"] = self._dropout(a3, self.dropout_rates[3])
        self.cache["a3"] = a3

        # Output layer: Linear (no activation)
        output = a3 @ self.weights[3] + self.biases[3]

        return output

    def backward(self, X: np.ndarray, y: np.ndarray, predictions: np.ndarray) -> Dict:
        """
        Backward pass to compute gradients.

        Args:
            X: Input features
            y: True labels
            predictions: Model predictions

        Returns:
            Dictionary of gradients
        """
        batch_size = X.shape[0]
        gradients = {}

        # Output layer gradient (MSE loss derivative)
        dout = 2 * (predictions - y.reshape(-1, 1)) / batch_size

        # Layer 4 (output) gradients
        gradients["W4"] = self.cache["a3"].T @ dout
        gradients["b4"] = np.sum(dout, axis=0)
        da3 = dout @ self.weights[3].T

        # Dropout 3 backward
        da3 = self._dropout_backward(da3, self.cache["dropout3_mask"], self.dropout_rates[3])

        # ReLU 3 backward
        dz3 = self._relu_backward(da3, self.cache["z3"])

        # Layer 3 gradients
        gradients["W3"] = self.cache["a2"].T @ dz3
        gradients["b3"] = np.sum(dz3, axis=0)
        da2 = dz3 @ self.weights[2].T

        # Dropout 2 backward
        da2 = self._dropout_backward(da2, self.cache["dropout2_mask"], self.dropout_rates[2])

        # ReLU 2 backward
        dbn2 = self._relu_backward(da2, self.cache["z2_pre"])

        # BatchNorm 2 backward
        if self.cache["bn2"] is not None:
            dz2, gradients["bn2_gamma"], gradients["bn2_beta"] = self._batchnorm_backward(dbn2, self.cache["bn2"])
        else:
            dz2 = dbn2
            gradients["bn2_gamma"] = np.zeros_like(self.bn2_gamma)
            gradients["bn2_beta"] = np.zeros_like(self.bn2_beta)

        # Layer 2 gradients
        gradients["W2"] = self.cache["a1"].T @ dz2
        gradients["b2"] = np.sum(dz2, axis=0)
        da1 = dz2 @ self.weights[1].T

        # Dropout 1 backward
        da1 = self._dropout_backward(da1, self.cache["dropout1_mask"], self.dropout_rates[1])

        # ReLU 1 backward
        dbn1 = self._relu_backward(da1, self.cache["z1_pre"])

        # BatchNorm 1 backward
        if self.cache["bn1"] is not None:
            dz1, gradients["bn1_gamma"], gradients["bn1_beta"] = self._batchnorm_backward(dbn1, self.cache["bn1"])
        else:
            dz1 = dbn1
            gradients["bn1_gamma"] = np.zeros_like(self.bn1_gamma)
            gradients["bn1_beta"] = np.zeros_like(self.bn1_beta)

        # Layer 1 gradients
        gradients["W1"] = X.T @ dz1
        gradients["b1"] = np.sum(dz1, axis=0)

        return gradients

    def train_mode(self):
        """Set network to training mode."""
        self.training = True

    def eval_mode(self):
        """Set network to evaluation mode."""
        self.training = False

    def get_state(self) -> Dict:
        """Get all model parameters as a dictionary."""
        return {
            "W1": self.weights[0],
            "b1": self.biases[0],
            "W2": self.weights[1],
            "b2": self.biases[1],
            "W3": self.weights[2],
            "b3": self.biases[2],
            "W4": self.weights[3],
            "b4": self.biases[3],
            "bn1_gamma": self.bn1_gamma,
            "bn1_beta": self.bn1_beta,
            "bn1_running_mean": self.bn1_running_mean,
            "bn1_running_var": self.bn1_running_var,
            "bn2_gamma": self.bn2_gamma,
            "bn2_beta": self.bn2_beta,
            "bn2_running_mean": self.bn2_running_mean,
            "bn2_running_var": self.bn2_running_var,
        }

    def set_state(self, state: Dict):
        """Load model parameters from a dictionary."""
        self.weights[0] = state["W1"]
        self.biases[0] = state["b1"]
        self.weights[1] = state["W2"]
        self.biases[1] = state["b2"]
        self.weights[2] = state["W3"]
        self.biases[2] = state["b3"]
        self.weights[3] = state["W4"]
        self.biases[3] = state["b4"]
        self.bn1_gamma = state["bn1_gamma"]
        self.bn1_beta = state["bn1_beta"]
        self.bn1_running_mean = state["bn1_running_mean"]
        self.bn1_running_var = state["bn1_running_var"]
        self.bn2_gamma = state["bn2_gamma"]
        self.bn2_beta = state["bn2_beta"]
        self.bn2_running_mean = state["bn2_running_mean"]
        self.bn2_running_var = state["bn2_running_var"]

    def copy_state(self) -> Dict:
        """Create a deep copy of the current state."""
        state = self.get_state()
        return {k: v.copy() for k, v in state.items()}


class EarlyStopping:
    """Early stopping to prevent overfitting."""

    def __init__(self, patience: int = 10):
        self.patience = patience
        self.counter = 0
        self.best_loss = float("inf")
        self.best_state = None

    def __call__(self, val_loss: float, model: NumpyNeuralNetwork) -> bool:
        if val_loss < self.best_loss:
            self.best_loss = val_loss
            self.best_state = model.copy_state()
            self.counter = 0
        else:
            self.counter += 1
        return self.counter >= self.patience

    def restore_best(self, model: NumpyNeuralNetwork):
        if self.best_state:
            model.set_state(self.best_state)


class NeuralNetReturnPredictor:
    """Neural network for predicting security returns (NumPy implementation)."""

    def __init__(self):
        self.model: Optional[NumpyNeuralNetwork] = None
        self.scaler: Optional[StandardScaler] = None
        self.input_dim: int = NUM_FEATURES

    def build_model(self, input_dim: int = NUM_FEATURES) -> NumpyNeuralNetwork:
        """
        Build neural network for return prediction.

        Architecture:
        - Input: 14 features (NUM_FEATURES) - per-security, no cross-security data
        - Hidden: 64 → 32 → 16 neurons with BatchNorm, ReLU, Dropout
        - Output: 1 (predicted return %)
        """
        self.input_dim = input_dim
        self.model = NumpyNeuralNetwork(input_dim=input_dim)
        return self.model

    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
        epochs: int = 100,
        batch_size: int = 64,
        learning_rate: float = 0.001,
    ) -> Dict:
        """
        Train neural network using mini-batch gradient descent with Adam optimizer.

        Args:
            X_train: Training features (N, NUM_FEATURES) - raw, unscaled
            y_train: Training labels (N,) - actual returns
            X_val: Validation features - raw, unscaled
            y_val: Validation labels
            epochs: Max training epochs
            batch_size: Batch size
            learning_rate: Learning rate for Adam

        Returns:
            Training history and metrics
        """
        # Scale features (fit on training data only)
        self.scaler = StandardScaler()
        X_train_scaled = self.scaler.fit_transform(X_train).astype(np.float32)  # type: ignore[union-attr]
        X_val_scaled = self.scaler.transform(X_val).astype(np.float32)  # type: ignore[union-attr]
        y_train = y_train.astype(np.float32)
        y_val = y_val.astype(np.float32)

        # Build model if not exists
        if self.model is None:
            self.build_model(input_dim=X_train.shape[1])

        # Assert model is built
        assert self.model is not None

        # Check minimum samples for BatchNorm
        n_train = len(X_train_scaled)
        if n_train < 2:
            raise ValueError(
                f"Training requires at least 2 samples, got {n_train}. BatchNorm cannot operate on single samples."
            )

        # Adam optimizer state
        adam_state = self._init_adam()

        # Early stopping
        early_stop = EarlyStopping(patience=10)

        # Training history
        history = {"loss": [], "val_loss": []}

        effective_batch_size = min(batch_size, n_train)

        for epoch in range(epochs):
            # Shuffle training data
            indices = np.random.permutation(n_train)
            X_shuffled = X_train_scaled[indices]
            y_shuffled = y_train[indices]

            # Training phase
            self.model.train_mode()
            epoch_loss = 0.0
            samples_processed = 0

            for i in range(0, n_train, effective_batch_size):
                # Get batch
                X_batch = X_shuffled[i : i + effective_batch_size]
                y_batch = y_shuffled[i : i + effective_batch_size]

                # Skip batch if too small (BatchNorm needs >= 2)
                if len(X_batch) < 2:
                    continue

                # Forward pass
                predictions = self.model.forward(X_batch)

                # Compute loss (MSE)
                batch_loss = np.mean((predictions.flatten() - y_batch) ** 2)
                epoch_loss += batch_loss * len(X_batch)
                samples_processed += len(X_batch)

                # Backward pass
                gradients = self.model.backward(X_batch, y_batch, predictions)

                # Update weights with Adam
                self._adam_update(gradients, adam_state, learning_rate, epoch + 1)

            if samples_processed > 0:
                epoch_loss /= samples_processed
            history["loss"].append(epoch_loss)

            # Validation phase
            self.model.eval_mode()
            val_predictions = self.model.forward(X_val_scaled)
            val_loss = float(np.mean((val_predictions.flatten() - y_val) ** 2))
            history["val_loss"].append(val_loss)

            # Early stopping check
            if early_stop(val_loss, self.model):
                early_stop.restore_best(self.model)
                break

        # Calculate metrics on validation set
        self.model.eval_mode()
        val_predictions = self.model.forward(X_val_scaled).flatten()

        val_mae, val_rmse, val_r2 = _compute_regression_metrics(val_predictions, y_val)

        return {
            "history": history,
            "val_mae": val_mae,
            "val_rmse": val_rmse,
            "val_r2": val_r2,
            "epochs_trained": len(history["loss"]),
        }

    def _init_adam(self) -> Dict:
        """Initialize Adam optimizer state."""
        state = {
            "m": {},  # First moment
            "v": {},  # Second moment
        }
        param_names = ["W1", "b1", "W2", "b2", "W3", "b3", "W4", "b4", "bn1_gamma", "bn1_beta", "bn2_gamma", "bn2_beta"]
        for name in param_names:
            state["m"][name] = 0
            state["v"][name] = 0
        return state

    def _adam_update(
        self,
        gradients: Dict,
        state: Dict,
        lr: float,
        t: int,
        beta1: float = 0.9,
        beta2: float = 0.999,
        eps: float = 1e-8,
    ):
        """Apply Adam optimizer update."""
        assert self.model is not None
        # Map gradient names to model attributes
        param_map = {
            "W1": (self.model.weights, 0),
            "b1": (self.model.biases, 0),
            "W2": (self.model.weights, 1),
            "b2": (self.model.biases, 1),
            "W3": (self.model.weights, 2),
            "b3": (self.model.biases, 2),
            "W4": (self.model.weights, 3),
            "b4": (self.model.biases, 3),
        }

        # Update weights and biases
        for name, (container, idx) in param_map.items():
            if name in gradients:
                g = gradients[name]
                state["m"][name] = beta1 * state["m"][name] + (1 - beta1) * g
                state["v"][name] = beta2 * state["v"][name] + (1 - beta2) * (g**2)
                m_hat = state["m"][name] / (1 - beta1**t)
                v_hat = state["v"][name] / (1 - beta2**t)
                container[idx] -= lr * m_hat / (np.sqrt(v_hat) + eps)

        # Update BatchNorm parameters
        bn_params = [
            ("bn1_gamma", "bn1_gamma"),
            ("bn1_beta", "bn1_beta"),
            ("bn2_gamma", "bn2_gamma"),
            ("bn2_beta", "bn2_beta"),
        ]
        for grad_name, attr_name in bn_params:
            if grad_name in gradients:
                g = gradients[grad_name]
                state["m"][grad_name] = beta1 * state["m"][grad_name] + (1 - beta1) * g
                state["v"][grad_name] = beta2 * state["v"][grad_name] + (1 - beta2) * (g**2)
                m_hat = state["m"][grad_name] / (1 - beta1**t)
                v_hat = state["v"][grad_name] / (1 - beta2**t)
                current = getattr(self.model, attr_name)
                setattr(self.model, attr_name, current - lr * m_hat / (np.sqrt(v_hat) + eps))

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Predict returns.

        Args:
            X: Features (N, NUM_FEATURES)

        Returns:
            Predicted returns (N,)
        """
        assert self.model is not None and self.scaler is not None
        X_scaled = self.scaler.transform(X).astype(np.float32)  # type: ignore[union-attr]
        self.model.eval_mode()
        predictions = self.model.forward(X_scaled).flatten()
        return predictions

    def save(self, path: str):
        """Save model, scaler, metadata."""
        assert self.model is not None
        save_path = Path(path)
        save_path.mkdir(parents=True, exist_ok=True)

        # Save model state as NumPy archive
        state = self.model.get_state()
        np.savez(save_path / "nn_model.npz", **state)

        # Save scaler
        with open(save_path / "nn_scaler.pkl", "wb") as f:
            pickle.dump(self.scaler, f)

        # Save metadata
        metadata = {
            "model_type": "numpy_neural_network",
            "input_dim": self.input_dim,
            "architecture": [self.input_dim, 64, 32, 16, 1],
        }
        with open(save_path / "nn_metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

    def load(self, path: str):
        """Load model, scaler, metadata."""
        load_path = Path(path)

        # Check for old PyTorch format
        if (load_path / "nn_model.pt").exists() and not (load_path / "nn_model.npz").exists():
            raise RuntimeError(
                f"Found old PyTorch model at {load_path / 'nn_model.pt'}. "
                "This format is no longer supported after NumPy migration. "
                "Delete the old model files and retrain."
            )

        # Check for old Keras format
        if (load_path / "nn_model.keras").exists():
            raise RuntimeError(
                f"Found old Keras model at {load_path / 'nn_model.keras'}. "
                "This format is no longer supported. Delete and retrain."
            )

        # Load metadata to get input_dim
        with open(load_path / "nn_metadata.json", "r") as f:
            metadata = json.load(f)
            self.input_dim = metadata.get("input_dim", NUM_FEATURES)

        # Validate input dimension matches current feature count
        if self.input_dim != NUM_FEATURES:
            raise RuntimeError(
                f"Model at {load_path} was trained with {self.input_dim} features, "
                f"but current system expects {NUM_FEATURES} features. "
                "Delete the old model files and retrain with the new feature set."
            )

        # Rebuild model with correct input dim
        self.build_model(input_dim=self.input_dim)
        assert self.model is not None

        # Load model state from NumPy archive
        with np.load(load_path / "nn_model.npz") as data:
            state = {key: data[key] for key in data.files}
        self.model.set_state(state)
        self.model.eval_mode()

        # Load scaler
        with open(load_path / "nn_scaler.pkl", "rb") as f:
            self.scaler = pickle.load(f)  # noqa: S301


class XGBoostReturnPredictor:
    """XGBoost for predicting security returns."""

    def __init__(self):
        self.model: Optional[xgb.XGBRegressor] = None
        self.scaler: Optional[StandardScaler] = None
        self.feature_importance: Optional[Dict[str, float]] = None

    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
    ) -> Dict:
        """
        Train XGBoost model.

        Args:
            X_train: Training features (N, NUM_FEATURES) - raw, unscaled
            y_train: Training labels (N,) - actual returns
            X_val: Validation features - raw, unscaled
            y_val: Validation labels

        Returns:
            Training metrics including feature importance
        """
        # Scale features (fit on training data only)
        self.scaler = StandardScaler()
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_val_scaled = self.scaler.transform(X_val)

        # Build and train model
        self.model = xgb.XGBRegressor(
            n_estimators=150,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            objective="reg:squarederror",
            random_state=42,
        )

        self.model.fit(
            X_train_scaled,
            y_train,
            eval_set=[(X_val_scaled, y_val)],
            verbose=False,
        )

        # Calculate metrics on validation set
        val_predictions = self.model.predict(X_val_scaled)
        val_mae, val_rmse, val_r2 = _compute_regression_metrics(val_predictions, y_val)

        # Extract feature importance
        self.feature_importance = self._extract_feature_importance()

        # Log top features
        if self.feature_importance:
            sorted_features = sorted(self.feature_importance.items(), key=lambda x: x[1], reverse=True)
            logger.info("XGBoost feature importance (top 5):")
            for name, importance in sorted_features[:5]:
                logger.info(f"  {name}: {importance:.4f}")

        return {
            "val_mae": float(val_mae),
            "val_rmse": float(val_rmse),
            "val_r2": float(val_r2),
            "feature_importance": self.feature_importance,
        }

    def _extract_feature_importance(self) -> Dict[str, float]:
        """Extract and return feature importance from trained model."""
        if self.model is None:
            return {}

        importance = self.model.feature_importances_

        # Map to feature names
        feature_importance = {}
        for i, name in enumerate(FEATURE_NAMES):
            if i < len(importance):
                feature_importance[name] = float(importance[i])

        return feature_importance

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Predict returns.

        Args:
            X: Features (N, NUM_FEATURES)

        Returns:
            Predicted returns (N,)
        """
        assert self.model is not None and self.scaler is not None
        X_scaled = self.scaler.transform(X)
        predictions = self.model.predict(X_scaled)
        return predictions

    def save(self, path: str):
        """Save model, scaler, metadata, and feature importance."""
        assert self.model is not None
        save_path = Path(path)
        save_path.mkdir(parents=True, exist_ok=True)

        # Save model
        self.model.save_model(str(save_path / "xgb_model.json"))

        # Save scaler
        with open(save_path / "xgb_scaler.pkl", "wb") as f:
            pickle.dump(self.scaler, f)

        # Save metadata with feature importance
        n_estimators = self.model.n_estimators if self.model.n_estimators is not None else 150
        max_depth = self.model.max_depth if self.model.max_depth is not None else 4
        metadata = {
            "model_type": "xgboost",
            "input_dim": NUM_FEATURES,
            "n_estimators": int(n_estimators),
            "max_depth": int(max_depth),
            "feature_importance": self.feature_importance or {},
        }
        with open(save_path / "xgb_metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

    def load(self, path: str):
        """Load model, scaler, metadata, and feature importance."""
        load_path = Path(path)

        # Load metadata first to validate input_dim
        metadata_path = load_path / "xgb_metadata.json"
        if metadata_path.exists():
            with open(metadata_path, "r") as f:
                metadata = json.load(f)
                self.feature_importance = metadata.get("feature_importance", {})

                # Validate input dimension if present
                saved_input_dim = metadata.get("input_dim")
                if saved_input_dim is not None and saved_input_dim != NUM_FEATURES:
                    raise RuntimeError(
                        f"XGBoost model at {load_path} was trained with {saved_input_dim} features, "
                        f"but current system expects {NUM_FEATURES} features. "
                        "Delete the old model files and retrain with the new feature set."
                    )

        # Load model
        self.model = xgb.XGBRegressor()
        self.model.load_model(str(load_path / "xgb_model.json"))

        # Load scaler
        with open(load_path / "xgb_scaler.pkl", "rb") as f:
            self.scaler = pickle.load(f)  # noqa: S301


class EnsembleBlender:
    """Blend Neural Network and XGBoost predictions 50-50."""

    def __init__(self, nn_weight: float = 0.5, xgb_weight: float = 0.5):
        """
        Initialize ensemble.

        Args:
            nn_weight: Weight for neural network (default 0.5)
            xgb_weight: Weight for XGBoost (default 0.5)
        """
        if abs(nn_weight + xgb_weight - 1.0) >= 1e-6:
            raise ValueError("Weights must sum to 1.0")

        self.nn_weight = nn_weight
        self.xgb_weight = xgb_weight

        self.nn_predictor = NeuralNetReturnPredictor()
        self.xgb_predictor = XGBoostReturnPredictor()

    def train(
        self,
        X: np.ndarray,
        y: np.ndarray,
        validation_split: float = 0.2,
    ) -> Dict:
        """
        Train both models using the same train/validation split.

        Args:
            X: Features (N, NUM_FEATURES)
            y: Labels (N,) - actual returns
            validation_split: Fraction of data to use for validation

        Returns:
            Combined training metrics (all computed on the same validation set)
        """
        # Split data ONCE - both models use the same split
        X_train_split, X_val_split, y_train_split, y_val_split = train_test_split(
            X, y, test_size=validation_split, random_state=42
        )
        # Ensure numpy arrays for type safety
        X_train_arr: np.ndarray = np.asarray(X_train_split)
        X_val_arr: np.ndarray = np.asarray(X_val_split)
        y_train_arr: np.ndarray = np.asarray(y_train_split)
        y_val_arr: np.ndarray = np.asarray(y_val_split)

        logger.info(f"Training data: {len(X_train_arr)} samples, Validation: {len(X_val_arr)} samples")

        logger.info("Training Neural Network...")
        nn_metrics = self.nn_predictor.train(X_train_arr, y_train_arr, X_val_arr, y_val_arr)

        logger.info("Training XGBoost...")
        xgb_metrics = self.xgb_predictor.train(X_train_arr, y_train_arr, X_val_arr, y_val_arr)

        # Calculate ensemble validation metrics on the SAME validation set
        nn_preds = self.nn_predictor.predict(X_val_arr)
        xgb_preds = self.xgb_predictor.predict(X_val_arr)

        ensemble_preds = self.nn_weight * nn_preds + self.xgb_weight * xgb_preds

        ensemble_mae, ensemble_rmse, ensemble_r2 = _compute_regression_metrics(ensemble_preds, y_val_arr)

        logger.info(f"Ensemble validation: MAE={ensemble_mae:.4f}, RMSE={ensemble_rmse:.4f}, R²={ensemble_r2:.4f}")

        return {
            "nn_metrics": nn_metrics,
            "xgb_metrics": xgb_metrics,
            "ensemble_val_mae": float(ensemble_mae),
            "ensemble_val_rmse": float(ensemble_rmse),
            "ensemble_val_r2": float(ensemble_r2),
        }

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Predict using 50-50 ensemble.

        Args:
            X: Features (N, NUM_FEATURES)

        Returns:
            Predicted returns (N,)
        """
        nn_preds = self.nn_predictor.predict(X)
        xgb_preds = self.xgb_predictor.predict(X)

        ensemble_preds = self.nn_weight * nn_preds + self.xgb_weight * xgb_preds
        return ensemble_preds

    def validate_before_save(self) -> bool:
        """
        Validate model produces finite predictions before saving.

        Returns:
            True if valid, raises ValueError if invalid.
        """
        # Test with various inputs
        test_inputs = [
            np.zeros((1, NUM_FEATURES)),  # All zeros
            np.ones((1, NUM_FEATURES)),  # All ones
            np.random.randn(5, NUM_FEATURES),  # Random normal
            np.random.randn(5, NUM_FEATURES) * 10,  # Larger values
        ]

        for i, test_X in enumerate(test_inputs):
            test_X = test_X.astype(np.float32)
            try:
                preds = self.predict(test_X)
                if not np.all(np.isfinite(preds)):
                    raise ValueError(f"Model produces non-finite predictions (NaN/Inf) for test case {i + 1}")
            except Exception as e:
                raise ValueError(f"Model prediction failed: {e}") from e

        return True

    def save(self, symbol: str):
        """
        Save both models for a symbol.

        Args:
            symbol: Security ticker (e.g., 'AAPL')

        Raises:
            ValueError: If model validation fails
        """
        # Validate model before saving
        self.validate_before_save()

        from sentinel.paths import DATA_DIR

        path = DATA_DIR / "ml_models" / symbol
        path.mkdir(parents=True, exist_ok=True)

        # Save both models
        self.nn_predictor.save(str(path))
        self.xgb_predictor.save(str(path))

        # Save ensemble metadata
        metadata = {
            "symbol": symbol,
            "nn_weight": self.nn_weight,
            "xgb_weight": self.xgb_weight,
            "ensemble_type": "numpy_nn_xgb_blend",
            "saved_at": datetime.now().isoformat(),
        }
        with open(path / "ensemble_metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

    def load(self, symbol: str):
        """
        Load both models for a symbol.

        Args:
            symbol: Security ticker
        """
        from sentinel.paths import DATA_DIR

        path = DATA_DIR / "ml_models" / symbol

        # Load both models
        self.nn_predictor.load(str(path))
        self.xgb_predictor.load(str(path))

        # Load ensemble metadata
        with open(path / "ensemble_metadata.json", "r") as f:
            metadata = json.load(f)
            self.nn_weight = metadata["nn_weight"]
            self.xgb_weight = metadata["xgb_weight"]

    @staticmethod
    def model_exists(symbol: str) -> bool:
        """Check if a trained model exists for a symbol."""
        from sentinel.paths import DATA_DIR

        path = DATA_DIR / "ml_models" / symbol
        # Check for all required files (NumPy format)
        required_files = [
            "ensemble_metadata.json",
            "nn_model.npz",  # Changed from .pt to .npz
            "nn_scaler.pkl",
            "nn_metadata.json",
            "xgb_model.json",
            "xgb_scaler.pkl",
            "xgb_metadata.json",
        ]
        return all((path / f).exists() for f in required_files)
