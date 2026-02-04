"""
Clear all ML tables and model files for a fresh backfill.

Clears: ml_training_samples, ml_predictions, ml_models, ml_performance_tracking,
and the data/ml_models/ directory.

Run from repo root with venv active:

    python scripts/clear_ml_data.py

Then regenerate training data, train models, and run backfill:

    python scripts/generate_ml_training_data.py
    python scripts/train_initial_ml_models.py
    python scripts/backfill_ml_predictions.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sentinel.ml_reset import MLResetManager


async def main() -> None:
    manager = MLResetManager()
    await manager.db.connect()
    try:
        await manager.delete_training_data()
        print("Cleared ML tables: ml_training_samples, ml_predictions, ml_models, ml_performance_tracking")
        await manager.delete_model_files()
        print("Removed data/ml_models/ contents")
    finally:
        await manager.db.close()
    print("Done. Next: generate_ml_training_data.py -> train_initial_ml_models.py -> backfill_ml_predictions.py")


if __name__ == "__main__":
    asyncio.run(main())
