"""Machine Learning API routes for ML models and predictions."""

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from typing_extensions import Annotated

from sentinel.api.dependencies import CommonDependencies, get_common_deps

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ml", tags=["ml"])
regime_router = APIRouter(prefix="/analytics/regime", tags=["analytics"])
backup_router = APIRouter(prefix="/backup", tags=["backup"])


@router.get("/status")
async def get_ml_status(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict:
    """Get ML system status."""
    # Count securities with ML enabled
    cursor = await deps.db.conn.execute("SELECT COUNT(*) as count FROM securities WHERE ml_enabled = 1 AND active = 1")
    enabled_row = await cursor.fetchone()
    securities_ml_enabled = enabled_row["count"] if enabled_row else 0

    # Count symbols with trained models
    cursor = await deps.db.conn.execute("SELECT COUNT(*) as count FROM ml_models")
    total_models_row = await cursor.fetchone()
    symbols_with_models = total_models_row["count"] if total_models_row else 0

    # Count total training samples
    cursor = await deps.db.conn.execute("SELECT COUNT(*) as count FROM ml_training_samples")
    total_samples_row = await cursor.fetchone()
    total_samples = total_samples_row["count"] if total_samples_row else 0

    # Get aggregate metrics across all models
    cursor = await deps.db.conn.execute(
        """SELECT AVG(validation_rmse) as avg_rmse,
                  AVG(validation_mae) as avg_mae,
                  AVG(validation_r2) as avg_r2,
                  SUM(training_samples) as total_trained_samples
           FROM ml_models"""
    )
    metrics_row = await cursor.fetchone()

    aggregate_metrics = None
    if metrics_row and metrics_row["avg_rmse"] is not None:
        aggregate_metrics = {
            "avg_validation_rmse": metrics_row["avg_rmse"],
            "avg_validation_mae": metrics_row["avg_mae"],
            "avg_validation_r2": metrics_row["avg_r2"],
            "total_trained_samples": metrics_row["total_trained_samples"],
        }

    # Get list of ML-enabled securities with their settings
    cursor = await deps.db.conn.execute(
        """SELECT symbol, ml_blend_ratio FROM securities
           WHERE ml_enabled = 1 AND active = 1"""
    )
    ml_securities = await cursor.fetchall()

    return {
        "securities_ml_enabled": securities_ml_enabled,
        "symbols_with_models": symbols_with_models,
        "total_training_samples": total_samples,
        "aggregate_metrics": aggregate_metrics,
        "ml_securities": [{"symbol": row["symbol"], "blend_ratio": row["ml_blend_ratio"]} for row in ml_securities],
    }


@router.post("/retrain")
async def trigger_retraining(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict:
    """Manually trigger ML model retraining for all ML-enabled symbols."""
    from sentinel.ml_retrainer import MLRetrainer

    # Get symbols with ML enabled
    cursor = await deps.db.conn.execute("SELECT symbol FROM securities WHERE ml_enabled = 1 AND active = 1")
    rows = await cursor.fetchall()

    if not rows:
        return {"status": "skipped", "reason": "No securities have ML enabled"}

    retrainer = MLRetrainer()
    results = {}
    trained = 0
    skipped = 0

    for row in rows:
        symbol = row["symbol"]
        result = await retrainer.retrain_symbol(symbol)
        if result:
            results[symbol] = result
            trained += 1
        else:
            results[symbol] = {"status": "skipped", "reason": "Insufficient data"}
            skipped += 1

    return {
        "status": "completed",
        "symbols_trained": trained,
        "symbols_skipped": skipped,
        "results": results,
    }


@router.post("/retrain/{symbol}")
async def trigger_retraining_symbol(symbol: str) -> dict:
    """Manually trigger ML model retraining for a specific symbol."""
    from sentinel.ml_retrainer import MLRetrainer

    retrainer = MLRetrainer()
    result = await retrainer.retrain_symbol(symbol)

    if result is None:
        return {"status": "skipped", "symbol": symbol, "reason": "Insufficient training data"}

    return {"status": "trained", "symbol": symbol, **result}


@router.get("/performance")
async def get_ml_performance(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict:
    """Get ML model performance metrics and report for ML-enabled securities."""
    from sentinel.ml_monitor import MLMonitor

    # Get symbols with ML enabled
    cursor = await deps.db.conn.execute("SELECT symbol FROM securities WHERE ml_enabled = 1 AND active = 1")
    rows = await cursor.fetchall()

    if not rows:
        return {
            "metrics": {"status": "skipped", "reason": "No securities have ML enabled"},
            "report": "No ML-enabled securities to monitor.",
        }

    monitor = MLMonitor()
    all_metrics = {}

    for row in rows:
        symbol = row["symbol"]
        result = await monitor.track_symbol_performance(symbol)
        if result:
            all_metrics[symbol] = result

    report = await monitor.generate_report()

    return {
        "metrics": all_metrics,
        "report": report,
    }


@router.get("/models")
async def list_ml_models(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict:
    """List all per-symbol ML models."""
    query = """
        SELECT symbol, training_samples, validation_rmse,
               validation_mae, validation_r2, last_trained_at
        FROM ml_models
        ORDER BY last_trained_at DESC
    """
    cursor = await deps.db.conn.execute(query)
    models = await cursor.fetchall()

    return {
        "models": [
            {
                "symbol": m["symbol"],
                "training_samples": m["training_samples"],
                "validation_rmse": m["validation_rmse"],
                "validation_mae": m["validation_mae"],
                "validation_r2": m["validation_r2"],
                "last_trained_at": m["last_trained_at"],
            }
            for m in models
        ]
    }


@router.get("/models/{symbol}")
async def get_ml_model(
    symbol: str,
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict:
    """Get ML model details for a specific symbol."""
    from sentinel.ml_ensemble import EnsembleBlender

    # Get model record
    cursor = await deps.db.conn.execute("SELECT * FROM ml_models WHERE symbol = ?", (symbol,))
    model_row = await cursor.fetchone()

    if not model_row:
        return {"error": f"No model found for {symbol}"}

    # Check if model files exist
    model_exists = EnsembleBlender.model_exists(symbol)

    # Get sample count for this symbol
    cursor = await deps.db.conn.execute("SELECT COUNT(*) as count FROM ml_training_samples WHERE symbol = ?", (symbol,))
    sample_row = await cursor.fetchone()

    return {
        "symbol": model_row["symbol"],
        "training_samples": model_row["training_samples"],
        "validation_rmse": model_row["validation_rmse"],
        "validation_mae": model_row["validation_mae"],
        "validation_r2": model_row["validation_r2"],
        "last_trained_at": model_row["last_trained_at"],
        "model_files_exist": model_exists,
        "available_samples": sample_row["count"] if sample_row else 0,
    }


@router.get("/train/{symbol}/stream")
async def train_symbol_stream(symbol: str) -> StreamingResponse:
    """Train ML model for a symbol with SSE progress updates."""
    from sentinel.ml_retrainer import MLRetrainer
    from sentinel.ml_trainer import TrainingDataGenerator

    async def generate():
        db = Database()
        await db.connect()
        settings = Settings()

        try:
            # Step 1: Check if symbol exists
            yield f"data: {json.dumps({'step': 1, 'total': 5, 'message': 'Checking symbol...', 'progress': 0})}\n\n"
            security = await db.get_security(symbol)
            if not security:
                yield f"data: {json.dumps({'error': 'Symbol not found'})}\n\n"
                return

            # Step 2: Generate training samples
            evt = json.dumps({"step": 2, "total": 5, "message": "Generating training samples...", "progress": 20})
            yield f"data: {evt}\n\n"
            trainer = TrainingDataGenerator()
            horizon_days = await settings.get("ml_prediction_horizon_days", 14)
            lookback_years = await settings.get("ml_training_lookback_years", 8)

            samples_df = await trainer.generate_training_data_for_symbol(
                symbol,
                lookback_years=lookback_years,
                prediction_horizon_days=horizon_days,
            )
            sample_count = len(samples_df) if samples_df is not None else 0
            msg = f"Generated {sample_count} samples"
            yield f"data: {json.dumps({'step': 2, 'total': 5, 'message': msg, 'progress': 40})}\n\n"

            # Step 3: Check minimum samples
            evt = json.dumps({"step": 3, "total": 5, "message": "Checking data sufficiency...", "progress": 50})
            yield f"data: {evt}\n\n"
            min_samples = await settings.get("ml_min_samples_per_symbol", 100)
            if sample_count < min_samples:
                err_msg = f"Insufficient samples: {sample_count} < {min_samples} required"
                yield f"data: {json.dumps({'error': err_msg})}\n\n"
                return

            # Step 4: Train model
            evt = json.dumps({"step": 4, "total": 5, "message": "Training neural network + XGBoost...", "progress": 60})
            yield f"data: {evt}\n\n"
            retrainer = MLRetrainer()
            metrics = await retrainer.retrain_symbol(symbol)

            if not metrics:
                yield f"data: {json.dumps({'error': 'Training failed'})}\n\n"
                return

            rmse_msg = f"RMSE: {metrics['validation_rmse']:.4f}"
            evt = json.dumps({"step": 4, "total": 5, "message": rmse_msg, "progress": 90})
            yield f"data: {evt}\n\n"

            # Step 5: Done
            evt = json.dumps(
                {"step": 5, "total": 5, "message": "Model saved", "progress": 100, "complete": True, "metrics": metrics}
            )
            yield f"data: {evt}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.delete("/training-data/{symbol}")
async def delete_training_data(
    symbol: str,
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict:
    """Delete all training data and model for a symbol."""
    import shutil

    from sentinel.paths import DATA_DIR

    # Delete training samples
    await deps.db.conn.execute("DELETE FROM ml_training_samples WHERE symbol = ?", (symbol,))

    # Delete predictions
    await deps.db.conn.execute("DELETE FROM ml_predictions WHERE symbol = ?", (symbol,))

    # Delete model record
    await deps.db.conn.execute("DELETE FROM ml_models WHERE symbol = ?", (symbol,))

    # Delete performance tracking
    await deps.db.conn.execute("DELETE FROM ml_performance_tracking WHERE symbol = ?", (symbol,))

    await deps.db.conn.commit()

    # Delete model files
    model_path = DATA_DIR / "ml_models" / symbol
    if model_path.exists():
        shutil.rmtree(model_path)

    return {"status": "deleted", "symbol": symbol}


@router.get("/training-status/{symbol}")
async def get_training_status(
    symbol: str,
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict:
    """Get ML training status for a symbol."""
    from sentinel.ml_ensemble import EnsembleBlender

    # Get sample count
    cursor = await deps.db.conn.execute("SELECT COUNT(*) as count FROM ml_training_samples WHERE symbol = ?", (symbol,))
    row = await cursor.fetchone()
    sample_count = row["count"] if row else 0

    # Get model info
    cursor = await deps.db.conn.execute("SELECT * FROM ml_models WHERE symbol = ?", (symbol,))
    model_row = await cursor.fetchone()

    # Check if model files exist
    model_exists = EnsembleBlender.model_exists(symbol)

    return {
        "symbol": symbol,
        "sample_count": sample_count,
        "model_exists": model_exists,
        "model_info": dict(model_row) if model_row else None,
    }


@router.post("/reset-and-retrain")
async def reset_and_retrain() -> dict:
    """Reset all ML data and retrain all models from scratch.

    This endpoint:
    1. Deletes all aggregate price series (_AGG_*)
    2. Clears ML training data tables
    3. Removes model files
    4. Recomputes aggregates
    5. Regenerates training samples
    6. Retrains all models

    The operation runs in the background and returns immediately.
    Returns 409 Conflict if a reset is already in progress.
    """
    from sentinel.ml_reset import is_reset_in_progress

    if is_reset_in_progress():
        raise HTTPException(
            status_code=409,
            detail="A reset operation is already in progress",
        )

    asyncio.create_task(_run_reset_and_retrain())
    return {"status": "started", "message": "Reset and retrain started in background"}


@router.get("/reset-status")
async def get_ml_reset_status() -> dict:
    """Get the current status of the ML reset operation.

    Returns:
        - running: bool - whether a reset is in progress
        - current_step: int - current step number (1-6)
        - total_steps: int - total number of steps (6)
        - step_name: str - name of the current step
        - details: str - additional details about current progress
    """
    from sentinel.ml_reset import get_reset_status

    return get_reset_status()


async def _run_reset_and_retrain():
    """Background task to run the full reset and retrain pipeline."""
    from sentinel.ml_reset import MLResetManager, set_active_reset

    manager = MLResetManager()
    set_active_reset(manager)
    try:
        result = await manager.reset_all()
        logger.info(f"ML reset and retrain completed: {result}")
    except Exception as e:
        logger.error(f"ML reset and retrain failed: {e}")
    finally:
        set_active_reset(None)


# Regime router endpoints


@regime_router.get("/{symbol}")
async def get_regime_status(symbol: str) -> dict:
    """Get current regime for a security."""
    from sentinel.regime_hmm import RegimeDetector

    detector = RegimeDetector()
    regime = await detector.detect_current_regime(symbol)
    history = await detector.get_regime_history(symbol, days=90)
    return {"current": regime, "history": history}


@regime_router.get("/all/regimes")
async def get_all_regimes(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict:
    """Get current regimes for all active securities."""
    from sentinel.regime_hmm import RegimeDetector

    detector = RegimeDetector()

    securities = await deps.db.get_all_securities(active_only=True)
    results = {}
    for sec in securities:
        regime = await detector.detect_current_regime(sec["symbol"])
        results[sec["symbol"]] = regime
    return results


# Backup router endpoints


@backup_router.post("/run")
async def run_backup() -> dict:
    """Trigger an immediate R2 backup."""
    from sentinel.jobs import run_now

    result = await run_now("backup:r2")
    return result


@backup_router.get("/status")
async def get_backup_status(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict:
    """List recent backups from R2."""
    account_id = await deps.settings.get("r2_account_id", "")
    access_key = await deps.settings.get("r2_access_key", "")
    secret_key = await deps.settings.get("r2_secret_key", "")
    bucket_name = await deps.settings.get("r2_bucket_name", "")

    if not all([account_id, access_key, secret_key, bucket_name]):
        return {"configured": False, "backups": []}

    try:
        from sentinel.jobs.tasks import _get_r2_client

        client = _get_r2_client(account_id, access_key, secret_key)
        response = client.list_objects_v2(Bucket=bucket_name, Prefix="backups/")
        contents = response.get("Contents", [])

        backups = sorted(
            [
                {
                    "key": obj["Key"],
                    "size_bytes": obj.get("Size", 0),
                    "last_modified": obj["LastModified"].isoformat() if obj.get("LastModified") else None,
                }
                for obj in contents
            ],
            key=lambda x: x["last_modified"] or "",
            reverse=True,
        )

        return {"configured": True, "backups": backups}
    except Exception as e:
        return {"configured": True, "backups": [], "error": str(e)}


# Import here to avoid circular imports
def Database():
    from sentinel.database import Database

    return Database()


def Settings():
    from sentinel.settings import Settings

    return Settings()
