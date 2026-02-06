"""ML model retraining pipeline - per-symbol, 4 model types."""

import logging
from typing import Any, Dict, Optional

import numpy as np

from sentinel_ml.adapters import MonolithDBAdapter, MonolithSettingsAdapter
from sentinel_ml.clients.monolith_client import MonolithDataClient
from sentinel_ml.database.ml import MODEL_TYPES, MLDatabase
from sentinel_ml.ml_ensemble import EnsembleBlender
from sentinel_ml.ml_trainer import TrainingDataGenerator

logger = logging.getLogger(__name__)


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        return default


class MLRetrainer:
    """Per-symbol ML retraining pipeline using 4 model types."""

    def __init__(self, progress_callback=None, db=None, ml_db=None, settings=None):
        """Initialize retrainer.

        Args:
            progress_callback: Optional callback(current, total, symbol) for progress updates
            db: Optional Database instance (defaults to new Database())
            ml_db: Optional MLDatabase instance (defaults to new MLDatabase())
            settings: Optional Settings instance (defaults to new Settings())
        """
        client = MonolithDataClient()
        self.db = db or MonolithDBAdapter(client)
        self.ml_db = ml_db or MLDatabase()
        self.settings = settings or MonolithSettingsAdapter(client)
        self.trainer = TrainingDataGenerator(db=self.db, ml_db=self.ml_db, settings=self.settings)
        self.progress_callback = progress_callback

    async def retrain(self) -> Dict:
        """
        Execute weekly retraining for all symbols.

        Process:
        [1/4] Generate new training samples from recent data
        [2/4] Get symbols with sufficient training data
        [3/4] Train model for each symbol
        [4/4] Update database

        Returns:
            {
                'status': 'completed',
                'symbols_trained': int,
                'symbols_skipped': int,
                'results': {symbol: metrics}
            }
        """
        await self.db.connect()
        await self.ml_db.connect()

        logger.info("[1/4] Generating new training samples from recent data...")
        new_samples = await self._generate_new_samples()
        logger.info(f"      Generated {new_samples} new samples")

        logger.info("[2/4] Finding symbols with sufficient training data...")
        min_samples = _as_int(await self.settings.get("ml_min_samples_per_symbol", 100), 100)
        symbols_with_data = await self.ml_db.get_symbols_with_sufficient_data(min_samples)
        logger.info(f"      Found {len(symbols_with_data)} symbols with >= {min_samples} samples")

        if not symbols_with_data:
            return {
                "status": "skipped",
                "reason": "No symbols with sufficient training data",
                "symbols_trained": 0,
                "symbols_skipped": 0,
            }

        logger.info("[3/4] Training models per symbol...")
        results = {}
        symbols_trained = 0
        symbols_skipped = 0
        total_symbols = len(symbols_with_data)

        for i, (symbol, sample_count) in enumerate(symbols_with_data.items()):
            logger.info(f"      [{i + 1}/{total_symbols}] {symbol} ({sample_count} samples)...")

            if self.progress_callback:
                self.progress_callback(i + 1, total_symbols, symbol)

            try:
                metrics = await self._train_symbol(symbol)
                if metrics:
                    results[symbol] = metrics
                    symbols_trained += 1
                else:
                    symbols_skipped += 1
            except Exception as e:
                logger.error(f"      {symbol}: Training failed: {e}")
                symbols_skipped += 1

        logger.info("[4/4] Retraining complete")
        logger.info(f"      Trained: {symbols_trained}, Skipped: {symbols_skipped}")

        return {
            "status": "completed",
            "symbols_trained": symbols_trained,
            "symbols_skipped": symbols_skipped,
            "results": results,
        }

    async def retrain_symbol(self, symbol: str) -> Optional[Dict]:
        """Retrain model for a single symbol."""
        await self.db.connect()
        await self.ml_db.connect()

        min_samples = _as_int(await self.settings.get("ml_min_samples_per_symbol", 100), 100)
        sample_count = await self.ml_db.get_sample_count(symbol)

        if sample_count < min_samples:
            logger.warning(f"{symbol}: Insufficient samples ({sample_count} < {min_samples})")
            return None

        return await self._train_symbol(symbol)

    async def _train_symbol(self, symbol: str) -> Optional[Dict]:
        """Train all 4 models for a single symbol."""
        X, y = await self.ml_db.load_training_data(symbol)

        if len(X) == 0:
            logger.warning(f"{symbol}: No valid training data")
            return None

        # Train ensemble (all 4 models)
        ensemble = EnsembleBlender()
        all_metrics = ensemble.train(X, y, validation_split=0.2)

        # Save model files (overwrites existing)
        ensemble.save(symbol)

        # Update model record in each per-model table
        for mt in MODEL_TYPES:
            mt_metrics = all_metrics.get(f"{mt}_metrics", {})
            await self.ml_db.update_model_record(
                model_type=mt,
                symbol=symbol,
                training_samples=len(X),
                metrics={
                    "validation_rmse": mt_metrics.get("val_rmse", 0.0),
                    "validation_mae": mt_metrics.get("val_mae", 0.0),
                    "validation_r2": mt_metrics.get("val_r2", 0.0),
                },
            )

        # Return summary (average across models)
        avg_rmse = np.mean([all_metrics[f"{mt}_metrics"]["val_rmse"] for mt in MODEL_TYPES])
        avg_mae = np.mean([all_metrics[f"{mt}_metrics"]["val_mae"] for mt in MODEL_TYPES])
        avg_r2 = np.mean([all_metrics[f"{mt}_metrics"]["val_r2"] for mt in MODEL_TYPES])

        return {
            "validation_rmse": float(avg_rmse),
            "validation_mae": float(avg_mae),
            "validation_r2": float(avg_r2),
            "training_samples": len(X),
            "per_model": {mt: all_metrics[f"{mt}_metrics"] for mt in MODEL_TYPES},
        }

    async def _generate_new_samples(self) -> int:
        """Generate training samples from recent data."""
        horizon_days = _as_int(await self.settings.get("ml_prediction_horizon_days", 14), 14)
        lookback_years = _as_int(await self.settings.get("ml_training_lookback_years", 8), 8)
        feature_lookback_days = _as_int(await self.settings.get("ml_training_feature_lookback_days", 365), 365)

        df = await self.trainer.generate_incremental_samples(
            lookback_days=feature_lookback_days,
            prediction_horizon_days=horizon_days,
            backfill_years=lookback_years,
        )

        return len(df) if df is not None else 0

    async def get_model_status(self) -> Dict:
        """Get status of all trained models across all model types."""
        await self.ml_db.connect()
        all_status = await self.ml_db.get_all_model_status()

        total_models = sum(len(models) for models in all_status.values())

        return {
            "total_models": total_models,
            "per_type": all_status,
        }
