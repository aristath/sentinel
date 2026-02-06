"""ML system reset and retrain operations.

This module provides functionality to completely reset the ML system,
including deleting all training data, model files, and aggregate price series,
then regenerating everything from scratch.
"""

import logging
import shutil
from datetime import datetime
from typing import Optional

from sentinel_ml.adapters import MonolithDBAdapter, MonolithSettingsAdapter
from sentinel_ml.clients.monolith_client import MonolithDataClient
from sentinel_ml.database.ml import MLDatabase
from sentinel_ml.paths import DATA_DIR

logger = logging.getLogger(__name__)

# Global state for tracking active reset operation
_active_reset: Optional["MLResetManager"] = None

# Step definitions for progress tracking
RESET_STEPS = [
    (1, "Preparing reset", "Preparing ML reset..."),
    (2, "Deleting ML data", "Deleting ML training data..."),
    (3, "Deleting model files", "Deleting model files..."),
    (4, "Computing aggregates", "Recomputing aggregates..."),
    (5, "Generating training data", "Regenerating training data..."),
    (6, "Training models", "Retraining all models..."),
]
TOTAL_STEPS = len(RESET_STEPS)


def get_active_reset() -> Optional["MLResetManager"]:
    """Get the currently active reset operation, if any."""
    global _active_reset
    return _active_reset


def set_active_reset(reset: Optional["MLResetManager"]) -> None:
    """Set or clear the active reset operation."""
    global _active_reset
    _active_reset = reset


def is_reset_in_progress() -> bool:
    """Check if a reset operation is currently in progress."""
    return _active_reset is not None


def get_reset_status() -> dict:
    """Get the current status of the reset operation."""
    if _active_reset is None:
        return {"running": False}

    status = {
        "running": True,
        "current_step": _active_reset.current_step,
        "total_steps": TOTAL_STEPS,
        "step_name": _active_reset.step_name,
        "details": _active_reset.step_details,
    }

    if _active_reset.current_step == 6 and _active_reset.models_total > 0:
        status["models_current"] = _active_reset.models_current
        status["models_total"] = _active_reset.models_total
        status["current_symbol"] = _active_reset.current_symbol

    return status


class MLResetManager:
    """Manages full ML system reset and retrain operations."""

    def __init__(self, db=None, ml_db: MLDatabase | None = None, monolith_client: MonolithDataClient | None = None):
        """Initialize reset manager.

        Args:
            db: Optional Database instance (creates one if not provided)
            ml_db: Optional MLDatabase instance (creates one if not provided)
            monolith_client: Optional monolith data client for endpoint calls
        """
        self._monolith_client = monolith_client or MonolithDataClient()
        self.db = db or MonolithDBAdapter(self._monolith_client)
        self.ml_db = ml_db or MLDatabase()
        self._settings = MonolithSettingsAdapter(self._monolith_client)
        self.current_step = 0
        self.step_name = ""
        self.step_details = ""
        self.models_current = 0
        self.models_total = 0
        self.current_symbol = ""

    def _set_step(self, step: int, details: str = "") -> None:
        """Update current step progress."""
        self.current_step = step
        self.step_name = RESET_STEPS[step - 1][1]
        self.step_details = details
        if step != 6:
            self.models_current = 0
            self.models_total = 0
            self.current_symbol = ""
        logger.info(f"[{step}/{TOTAL_STEPS}] {RESET_STEPS[step - 1][2]}")

    def _on_model_progress(self, current: int, total: int, symbol: str) -> None:
        """Callback for model training progress."""
        self.models_current = current
        self.models_total = total
        self.current_symbol = symbol
        self.step_details = f"Training {symbol} ({current}/{total})"

    async def reset_all(self) -> dict:
        """Execute full reset and retrain pipeline."""
        await self.db.connect()
        await self.ml_db.connect()

        self._set_step(1)
        agg_deleted = await self.delete_aggregates()
        logger.info(f"      Deleted {agg_deleted} aggregate rows")

        self._set_step(2)
        await self.delete_training_data()
        logger.info("      Cleared all ML tables")

        self._set_step(3)
        await self.delete_model_files()
        logger.info("      Removed model directory contents")

        self._set_step(4)
        agg_result = await self._recompute_aggregates()
        logger.info(f"      Computed {agg_result.get('country', 0)} country, {agg_result.get('industry', 0)} industry")

        self._set_step(5)
        samples_count = await self._regenerate_training_data()
        logger.info(f"      Generated {samples_count} training samples")

        self._set_step(6)
        retrain_result = await self._retrain_all_models()
        logger.info(f"      Trained {retrain_result.get('symbols_trained', 0)} models")

        logger.info("Reset and retrain complete!")

        return {
            "status": "completed",
            "aggregates_deleted": agg_deleted,
            "aggregates_computed": agg_result,
            "training_samples_generated": samples_count,
            "models_trained": retrain_result.get("symbols_trained", 0),
            "models_skipped": retrain_result.get("symbols_skipped", 0),
        }

    async def delete_aggregates(self) -> int:
        """Delete all aggregate series via monolith-owned endpoint."""
        return await self._monolith_client.delete_aggregates()

    async def delete_training_data(self) -> None:
        """Delete all ML data from ml.db (all 13 tables)."""
        await self.ml_db.connect()
        await self.ml_db.delete_all_data()

    async def delete_model_files(self) -> None:
        """Delete all model files from data/ml_models/ directory."""
        model_dir = DATA_DIR / "ml_models"

        if model_dir.exists():
            shutil.rmtree(model_dir)

        model_dir.mkdir(exist_ok=True)

    async def _recompute_aggregates(self) -> dict:
        """Recompute all aggregate series via monolith-owned endpoint."""
        return await self._monolith_client.recompute_aggregates()

    async def _regenerate_training_data(self) -> int:
        """Regenerate all training samples."""
        from sentinel_ml.ml_trainer import TrainingDataGenerator

        generator = TrainingDataGenerator(db=self.db, ml_db=self.ml_db)

        horizon_days = await self._settings.get("ml_prediction_horizon_days", 14)
        lookback_years = await self._settings.get("ml_training_lookback_years", 8)

        current_year = datetime.now().year
        df = await generator.generate_training_data(
            start_date=f"{current_year - lookback_years}-01-01",
            prediction_horizon_days=horizon_days,
        )

        return len(df) if df is not None else 0

    async def _retrain_all_models(self) -> dict:
        """Retrain all ML models."""
        from sentinel_ml.ml_retrainer import MLRetrainer

        retrainer = MLRetrainer(progress_callback=self._on_model_progress, db=self.db, ml_db=self.ml_db)
        return await retrainer.retrain()
