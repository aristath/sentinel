"""ML model retraining pipeline - per-symbol models."""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path
import logging

from sentinel.ml_ensemble import EnsembleBlender
from sentinel.ml_trainer import TrainingDataGenerator
from sentinel.ml_features import FEATURE_NAMES
from sentinel.database import Database
from sentinel.settings import Settings

logger = logging.getLogger(__name__)


class MLRetrainer:
    """Per-symbol ML retraining pipeline."""

    def __init__(self):
        self.db = Database()
        self.settings = Settings()
        self.trainer = TrainingDataGenerator()

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

        logger.info("[1/4] Generating new training samples from recent data...")
        new_samples = await self._generate_new_samples()
        logger.info(f"      Generated {new_samples} new samples")

        logger.info("[2/4] Finding symbols with sufficient training data...")
        min_samples = await self.settings.get('ml_min_samples_per_symbol', 100)
        symbols_with_data = await self._get_symbols_with_sufficient_data(min_samples)
        logger.info(f"      Found {len(symbols_with_data)} symbols with >= {min_samples} samples")

        if not symbols_with_data:
            return {
                'status': 'skipped',
                'reason': 'No symbols with sufficient training data',
                'symbols_trained': 0,
                'symbols_skipped': 0,
            }

        logger.info("[3/4] Training models per symbol...")
        results = {}
        symbols_trained = 0
        symbols_skipped = 0

        for i, (symbol, sample_count) in enumerate(symbols_with_data.items()):
            logger.info(f"      [{i+1}/{len(symbols_with_data)}] {symbol} ({sample_count} samples)...")

            try:
                metrics = await self._train_symbol(symbol)
                if metrics:
                    results[symbol] = metrics
                    symbols_trained += 1
                    logger.info(f"      {symbol}: RMSE={metrics['validation_rmse']:.4f}, R²={metrics['validation_r2']:.4f}")
                else:
                    symbols_skipped += 1
            except Exception as e:
                logger.error(f"      {symbol}: Training failed: {e}")
                symbols_skipped += 1

        logger.info("[4/4] Retraining complete")
        logger.info(f"      Trained: {symbols_trained}, Skipped: {symbols_skipped}")

        return {
            'status': 'completed',
            'symbols_trained': symbols_trained,
            'symbols_skipped': symbols_skipped,
            'results': results,
        }

    async def retrain_symbol(self, symbol: str) -> Optional[Dict]:
        """
        Retrain model for a single symbol.

        Args:
            symbol: Security ticker

        Returns:
            Training metrics or None if failed
        """
        await self.db.connect()

        min_samples = await self.settings.get('ml_min_samples_per_symbol', 100)
        sample_count = await self._get_sample_count(symbol)

        if sample_count < min_samples:
            logger.warning(f"{symbol}: Insufficient samples ({sample_count} < {min_samples})")
            return None

        return await self._train_symbol(symbol)

    async def _train_symbol(self, symbol: str) -> Optional[Dict]:
        """Train model for a single symbol."""
        # Load training data for this symbol
        X, y = await self._load_training_data(symbol)

        if len(X) == 0:
            logger.warning(f"{symbol}: No valid training data")
            return None

        # Train ensemble
        ensemble = EnsembleBlender(nn_weight=0.5, xgb_weight=0.5)
        metrics = ensemble.train(X, y, validation_split=0.2)

        # Save model (overwrites existing)
        ensemble.save(symbol)

        # Update database
        await self._update_model_record(symbol, len(X), metrics)

        return {
            'validation_rmse': metrics['ensemble_val_rmse'],
            'validation_mae': metrics['ensemble_val_mae'],
            'validation_r2': metrics['ensemble_val_r2'],
            'training_samples': len(X),
        }

    async def _generate_new_samples(self) -> int:
        """Generate training samples from recent data."""
        horizon_days = await self.settings.get('ml_prediction_horizon_days', 14)

        df = await self.trainer.generate_incremental_samples(
            lookback_days=90,
            prediction_horizon_days=horizon_days,
        )

        return len(df) if df is not None else 0

    async def _get_symbols_with_sufficient_data(self, min_samples: int) -> Dict[str, int]:
        """Get symbols that have at least min_samples training samples."""
        query = """
            SELECT symbol, COUNT(*) as sample_count
            FROM ml_training_samples
            WHERE future_return IS NOT NULL
            GROUP BY symbol
            HAVING sample_count >= ?
            ORDER BY sample_count DESC
        """
        cursor = await self.db.conn.execute(query, (min_samples,))
        rows = await cursor.fetchall()

        return {row['symbol']: row['sample_count'] for row in rows}

    async def _get_sample_count(self, symbol: str) -> int:
        """Get training sample count for a symbol."""
        query = """
            SELECT COUNT(*) as count
            FROM ml_training_samples
            WHERE symbol = ? AND future_return IS NOT NULL
        """
        cursor = await self.db.conn.execute(query, (symbol,))
        row = await cursor.fetchone()
        return row['count'] if row else 0

    async def _load_training_data(self, symbol: str) -> tuple[np.ndarray, np.ndarray]:
        """Load training data for a specific symbol."""
        query = """
            SELECT * FROM ml_training_samples
            WHERE symbol = ? AND future_return IS NOT NULL
            ORDER BY sample_date DESC
        """
        cursor = await self.db.conn.execute(query, (symbol,))
        rows = await cursor.fetchall()

        if not rows:
            return np.array([]), np.array([])

        df = pd.DataFrame([dict(row) for row in rows])

        # 14 features per security - no cross-security data
        from sentinel.ml_features import FEATURE_NAMES, DEFAULT_FEATURES
        db_feature_columns = FEATURE_NAMES

        # Use default values from centralized definition
        defaults = DEFAULT_FEATURES

        for col in db_feature_columns:
            if col not in df.columns:
                df[col] = defaults.get(col, 0.0)
            else:
                df[col] = df[col].fillna(defaults.get(col, 0.0))

        X = df[db_feature_columns].values.astype(np.float32)
        y = df['future_return'].values.astype(np.float32)

        # Remove any remaining NaN/Inf values
        valid_mask = np.all(np.isfinite(X), axis=1) & np.isfinite(y)
        X = X[valid_mask]
        y = y[valid_mask]

        return X, y

    async def _update_model_record(self, symbol: str, training_samples: int, metrics: Dict):
        """Update or insert model record in database."""
        await self.db.conn.execute(
            """INSERT OR REPLACE INTO ml_models
               (symbol, training_samples, validation_rmse, validation_mae,
                validation_r2, last_trained_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                symbol, training_samples,
                metrics['ensemble_val_rmse'],
                metrics['ensemble_val_mae'],
                metrics['ensemble_val_r2'],
                datetime.now().isoformat()
            )
        )
        await self.db.conn.commit()

    async def get_model_status(self) -> Dict:
        """Get status of all trained models."""
        await self.db.connect()

        query = "SELECT * FROM ml_models ORDER BY last_trained_at DESC"
        cursor = await self.db.conn.execute(query)
        rows = await cursor.fetchall()

        models = [dict(row) for row in rows]

        return {
            'total_models': len(models),
            'models': models,
        }
