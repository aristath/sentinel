"""Train initial ML models - one per symbol."""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sentinel.database import Database
from sentinel.ml_ensemble import EnsembleBlender
from sentinel.ml_features import DEFAULT_FEATURES, FEATURE_NAMES
from sentinel.settings import Settings


async def load_training_data_for_symbol(db, symbol: str):
    """Load training data for a specific symbol."""
    query = """
        SELECT * FROM ml_training_samples
        WHERE symbol = ? AND future_return IS NOT NULL
        ORDER BY sample_date DESC
    """
    cursor = await db.conn.execute(query, (symbol,))
    rows = await cursor.fetchall()

    if not rows:
        return None, None

    df = pd.DataFrame([dict(row) for row in rows])

    # Fill missing/NaN values with defaults from FEATURE_NAMES
    for col in FEATURE_NAMES:
        if col not in df.columns:
            default_val = DEFAULT_FEATURES.get(col, 0.0)
            df[col] = default_val
        else:
            default_val = DEFAULT_FEATURES.get(col, 0.0)
            df[col] = df[col].fillna(default_val)

    X = df[FEATURE_NAMES].values.astype(np.float32)
    y = df["future_return"].values.astype(np.float32)

    # Remove invalid rows
    valid_mask = np.all(np.isfinite(X), axis=1) & np.isfinite(y)
    X = X[valid_mask]
    y = y[valid_mask]

    return X, y


async def main():
    print("=" * 70)
    print("Per-Symbol ML Model Training")
    print("=" * 70)

    db = Database()
    await db.connect()
    settings = Settings()

    # Get minimum samples requirement
    min_samples = await settings.get("ml_min_samples_per_symbol", 100)
    print(f"\nMinimum samples per symbol: {min_samples}")

    # Get symbols with sufficient data
    query = """
        SELECT symbol, COUNT(*) as sample_count
        FROM ml_training_samples
        WHERE future_return IS NOT NULL
        GROUP BY symbol
        HAVING sample_count >= ?
        ORDER BY sample_count DESC
    """
    cursor = await db.conn.execute(query, (min_samples,))
    rows = await cursor.fetchall()

    if not rows:
        print("\nERROR: No symbols with sufficient training samples!")
        print("Please run generate_ml_training_data.py first.")
        return

    symbols = [(row["symbol"], row["sample_count"]) for row in rows]
    print(f"\nFound {len(symbols)} symbols with sufficient data:")
    for symbol, count in symbols[:10]:
        print(f"  {symbol}: {count} samples")
    if len(symbols) > 10:
        print(f"  ... and {len(symbols) - 10} more")

    # Train model for each symbol
    print("\n" + "=" * 70)
    print("Training Models")
    print("=" * 70)

    trained = 0
    failed = 0

    for i, (symbol, sample_count) in enumerate(symbols):
        print(f"\n[{i + 1}/{len(symbols)}] {symbol} ({sample_count} samples)")

        X, y = await load_training_data_for_symbol(db, symbol)

        if X is None or len(X) == 0:
            print("  SKIP: No valid training data")
            failed += 1
            continue

        print(f"  Features: {X.shape}, Labels: {y.shape}")
        print(f"  Return stats: mean={y.mean():.4f}, std={y.std():.4f}")

        try:
            # Train ensemble
            ensemble = EnsembleBlender(nn_weight=0.5, xgb_weight=0.5)
            metrics = ensemble.train(X, y, validation_split=0.2)

            # Save model
            ensemble.save(symbol)

            print(f"  NN:  MAE={metrics['nn_metrics']['val_mae']:.4f}, R²={metrics['nn_metrics']['val_r2']:.4f}")
            print(f"  XGB: MAE={metrics['xgb_metrics']['val_mae']:.4f}, R²={metrics['xgb_metrics']['val_r2']:.4f}")
            print(f"  Ensemble: RMSE={metrics['ensemble_val_rmse']:.4f}, R²={metrics['ensemble_val_r2']:.4f}")

            # Register in database
            await db.conn.execute(
                """INSERT OR REPLACE INTO ml_models
                   (symbol, training_samples, validation_rmse, validation_mae,
                    validation_r2, last_trained_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    symbol,
                    len(X),
                    metrics["ensemble_val_rmse"],
                    metrics["ensemble_val_mae"],
                    metrics["ensemble_val_r2"],
                    datetime.now().isoformat(),
                ),
            )
            await db.conn.commit()

            trained += 1

        except Exception as e:
            print(f"  ERROR: {e}")
            failed += 1
            continue

    print("\n" + "=" * 70)
    print("Training Complete!")
    print("=" * 70)
    print(f"\nModels trained: {trained}")
    print(f"Models failed: {failed}")
    print("\nModels saved to: data/ml_models/<symbol>/")

    # Show summary
    cursor = await db.conn.execute("SELECT COUNT(*) as count FROM ml_models")
    row = await cursor.fetchone()
    print(f"Total models in database: {row['count']}")

    print("\nTo enable ML predictions, set:")
    print("  ml_enabled = True")
    print("  ml_wavelet_blend_ratio = 0.3  (or desired ratio)")


if __name__ == "__main__":
    asyncio.run(main())
