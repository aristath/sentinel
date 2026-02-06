"""ML ensemble models for per-security return prediction.

Four model types: XGBoost, Ridge, Random Forest, SVR.
"""

import json
import logging
import pickle
from pathlib import Path
from typing import Dict, Optional, Protocol

import numpy as np
import xgboost as xgb
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR

from sentinel_ml.database.ml import MODEL_TYPES
from sentinel_ml.ml_features import FEATURE_NAMES, NUM_FEATURES

logger = logging.getLogger(__name__)


class _PredictorProtocol(Protocol):
    def train(self, X_train: np.ndarray, y_train: np.ndarray, X_val: np.ndarray, y_val: np.ndarray) -> Dict: ...
    def predict(self, X: np.ndarray) -> np.ndarray: ...
    def save(self, path: Path) -> None: ...
    def load(self, path: Path) -> None: ...


def _compute_regression_metrics(predictions: np.ndarray, labels: np.ndarray) -> tuple[float, float, float]:
    """Compute MAE, RMSE, and R² for regression predictions."""
    mae = float(np.mean(np.abs(predictions - labels)))
    rmse = float(np.sqrt(np.mean((predictions - labels) ** 2)))
    ss_res = np.sum((labels - predictions) ** 2)
    ss_tot = np.sum((labels - np.mean(labels)) ** 2)
    r2 = float(1 - (ss_res / ss_tot)) if ss_tot > 0 else 0.0
    return mae, rmse, r2


# =============================================================================
# XGBoost
# =============================================================================


class XGBoostReturnPredictor:
    """XGBoost for predicting security returns. No scaler (tree-based)."""

    def __init__(self):
        self.model: Optional[xgb.XGBRegressor] = None
        self.scaler = None  # Tree-based, no scaling needed
        self.feature_importance: Optional[Dict[str, float]] = None

    def train(self, X_train: np.ndarray, y_train: np.ndarray, X_val: np.ndarray, y_val: np.ndarray) -> Dict:
        self.model = xgb.XGBRegressor(
            n_estimators=150,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            objective="reg:squarederror",
            random_state=42,
        )
        self.model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)

        val_predictions = self.model.predict(X_val)
        val_mae, val_rmse, val_r2 = _compute_regression_metrics(val_predictions, y_val)

        self.feature_importance = self._extract_feature_importance()
        return {"val_mae": float(val_mae), "val_rmse": float(val_rmse), "val_r2": float(val_r2)}

    def _extract_feature_importance(self) -> Dict[str, float]:
        if self.model is None:
            return {}
        importance = self.model.feature_importances_
        return {name: float(importance[i]) for i, name in enumerate(FEATURE_NAMES) if i < len(importance)}

    def predict(self, X: np.ndarray) -> np.ndarray:
        assert self.model is not None
        return self.model.predict(X)

    def save(self, path: Path) -> None:
        assert self.model is not None
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        self.model.save_model(str(path / "xgb_model.json"))
        metadata = {
            "model_type": "xgboost",
            "input_dim": NUM_FEATURES,
            "feature_importance": self.feature_importance or {},
        }
        with open(path / "xgb_metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

    def load(self, path: Path) -> None:
        path = Path(path)
        self.model = xgb.XGBRegressor()
        self.model.load_model(str(path / "xgb_model.json"))
        metadata_path = path / "xgb_metadata.json"
        if metadata_path.exists():
            with open(metadata_path) as f:
                metadata = json.load(f)
                self.feature_importance = metadata.get("feature_importance", {})

    @staticmethod
    def files_exist(path: Path) -> bool:
        path = Path(path)
        return (path / "xgb_model.json").exists() and (path / "xgb_metadata.json").exists()


# =============================================================================
# Ridge
# =============================================================================


class RidgeReturnPredictor:
    """Ridge regression with scaling."""

    def __init__(self):
        self.model: Optional[Ridge] = None
        self.scaler: Optional[StandardScaler] = None

    def train(self, X_train: np.ndarray, y_train: np.ndarray, X_val: np.ndarray, y_val: np.ndarray) -> Dict:
        self.scaler = StandardScaler()
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_val_scaled = self.scaler.transform(X_val)

        self.model = Ridge(alpha=1.0)
        self.model.fit(X_train_scaled, y_train)

        val_predictions = self.model.predict(X_val_scaled)
        val_mae, val_rmse, val_r2 = _compute_regression_metrics(val_predictions, y_val)
        return {"val_mae": float(val_mae), "val_rmse": float(val_rmse), "val_r2": float(val_r2)}

    def predict(self, X: np.ndarray) -> np.ndarray:
        assert self.model is not None and self.scaler is not None
        X_scaled = self.scaler.transform(X)
        return self.model.predict(X_scaled)

    def save(self, path: Path) -> None:
        assert self.model is not None
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        with open(path / "ridge_model.pkl", "wb") as f:
            pickle.dump(self.model, f)
        with open(path / "ridge_scaler.pkl", "wb") as f:
            pickle.dump(self.scaler, f)
        metadata = {"model_type": "ridge", "input_dim": NUM_FEATURES}
        with open(path / "ridge_metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

    def load(self, path: Path) -> None:
        path = Path(path)
        with open(path / "ridge_model.pkl", "rb") as f:
            self.model = pickle.load(f)  # noqa: S301
        with open(path / "ridge_scaler.pkl", "rb") as f:
            self.scaler = pickle.load(f)  # noqa: S301

    @staticmethod
    def files_exist(path: Path) -> bool:
        path = Path(path)
        return all((path / f).exists() for f in ["ridge_model.pkl", "ridge_scaler.pkl", "ridge_metadata.json"])


# =============================================================================
# Random Forest
# =============================================================================


class RandomForestReturnPredictor:
    """Random Forest regression. No scaler (tree-based)."""

    def __init__(self):
        self.model: Optional[RandomForestRegressor] = None
        self.scaler = None  # Tree-based, no scaling needed

    def train(self, X_train: np.ndarray, y_train: np.ndarray, X_val: np.ndarray, y_val: np.ndarray) -> Dict:
        self.model = RandomForestRegressor(n_estimators=200, max_depth=6, random_state=42, n_jobs=-1)
        self.model.fit(X_train, y_train)

        val_predictions = self.model.predict(X_val)
        val_mae, val_rmse, val_r2 = _compute_regression_metrics(val_predictions, y_val)
        return {"val_mae": float(val_mae), "val_rmse": float(val_rmse), "val_r2": float(val_r2)}

    def predict(self, X: np.ndarray) -> np.ndarray:
        assert self.model is not None
        return self.model.predict(X)

    def save(self, path: Path) -> None:
        assert self.model is not None
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        with open(path / "rf_model.pkl", "wb") as f:
            pickle.dump(self.model, f)
        metadata = {"model_type": "random_forest", "input_dim": NUM_FEATURES}
        with open(path / "rf_metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

    def load(self, path: Path) -> None:
        path = Path(path)
        with open(path / "rf_model.pkl", "rb") as f:
            self.model = pickle.load(f)  # noqa: S301

    @staticmethod
    def files_exist(path: Path) -> bool:
        path = Path(path)
        return (path / "rf_model.pkl").exists() and (path / "rf_metadata.json").exists()


# =============================================================================
# SVR
# =============================================================================


class SVRReturnPredictor:
    """SVR regression with scaling."""

    def __init__(self):
        self.model: Optional[SVR] = None
        self.scaler: Optional[StandardScaler] = None

    def train(self, X_train: np.ndarray, y_train: np.ndarray, X_val: np.ndarray, y_val: np.ndarray) -> Dict:
        self.scaler = StandardScaler()
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_val_scaled = self.scaler.transform(X_val)

        self.model = SVR(kernel="rbf", C=1.0, epsilon=0.01)
        self.model.fit(X_train_scaled, y_train)

        val_predictions = self.model.predict(X_val_scaled)
        val_mae, val_rmse, val_r2 = _compute_regression_metrics(val_predictions, y_val)
        return {"val_mae": float(val_mae), "val_rmse": float(val_rmse), "val_r2": float(val_r2)}

    def predict(self, X: np.ndarray) -> np.ndarray:
        assert self.model is not None and self.scaler is not None
        X_scaled = self.scaler.transform(X)
        return self.model.predict(X_scaled)

    def save(self, path: Path) -> None:
        assert self.model is not None
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        with open(path / "svr_model.pkl", "wb") as f:
            pickle.dump(self.model, f)
        with open(path / "svr_scaler.pkl", "wb") as f:
            pickle.dump(self.scaler, f)
        metadata = {"model_type": "svr", "input_dim": NUM_FEATURES}
        with open(path / "svr_metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

    def load(self, path: Path) -> None:
        path = Path(path)
        with open(path / "svr_model.pkl", "rb") as f:
            self.model = pickle.load(f)  # noqa: S301
        with open(path / "svr_scaler.pkl", "rb") as f:
            self.scaler = pickle.load(f)  # noqa: S301

    @staticmethod
    def files_exist(path: Path) -> bool:
        path = Path(path)
        return all((path / f).exists() for f in ["svr_model.pkl", "svr_scaler.pkl", "svr_metadata.json"])


# =============================================================================
# Ensemble Blender (4 models)
# =============================================================================

_PREDICTOR_MAP = {
    "xgboost": XGBoostReturnPredictor,
    "ridge": RidgeReturnPredictor,
    "rf": RandomForestReturnPredictor,
    "svr": SVRReturnPredictor,
}


class EnsembleBlender:
    """Blend XGBoost, Ridge, RF, and SVR predictions."""

    def __init__(self):
        self.predictors: Dict[str, _PredictorProtocol] = {mt: _PREDICTOR_MAP[mt]() for mt in MODEL_TYPES}

    def train(self, X: np.ndarray, y: np.ndarray, validation_split: float = 0.2) -> Dict:
        """Train all 4 models on the same train/val split."""
        X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=validation_split, random_state=42)
        X_train = np.asarray(X_train, dtype=np.float32)
        X_val = np.asarray(X_val, dtype=np.float32)
        y_train = np.asarray(y_train, dtype=np.float32)
        y_val = np.asarray(y_val, dtype=np.float32)

        logger.info(f"Training data: {len(X_train)} samples, Validation: {len(X_val)} samples")

        all_metrics = {}
        for mt in MODEL_TYPES:
            logger.info(f"Training {mt}...")
            metrics = self.predictors[mt].train(X_train, y_train, X_val, y_val)
            all_metrics[f"{mt}_metrics"] = metrics
            logger.info(f"  {mt}: MAE={metrics['val_mae']:.4f}, R²={metrics['val_r2']:.4f}")

        return all_metrics

    def predict(self, X: np.ndarray) -> Dict[str, np.ndarray]:
        """Predict using all 4 models. Returns dict of model_type -> predictions."""
        return {mt: self.predictors[mt].predict(X) for mt in MODEL_TYPES}

    def save(self, symbol: str) -> None:
        """Save all 4 models for a symbol."""
        from sentinel_ml.paths import DATA_DIR

        path = DATA_DIR / "ml_models" / symbol
        path.mkdir(parents=True, exist_ok=True)
        for mt in MODEL_TYPES:
            self.predictors[mt].save(path)

    def load(self, symbol: str) -> None:
        """Load all 4 models for a symbol."""
        from sentinel_ml.paths import DATA_DIR

        path = DATA_DIR / "ml_models" / symbol
        for mt in MODEL_TYPES:
            self.predictors[mt].load(path)

    @staticmethod
    def model_exists(symbol: str) -> bool:
        """Check if all 4 trained models exist for a symbol."""
        from sentinel_ml.paths import DATA_DIR

        path = DATA_DIR / "ml_models" / symbol
        return all(_PREDICTOR_MAP[mt].files_exist(path) for mt in MODEL_TYPES)
