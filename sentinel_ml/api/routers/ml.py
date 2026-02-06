"""Machine Learning API routes for Sentinel ML service."""

import asyncio
import bisect
import json
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from typing_extensions import Annotated

from sentinel_ml.adapters import MonolithSettingsAdapter
from sentinel_ml.api.dependencies import CommonDependencies, get_common_deps
from sentinel_ml.database.ml import MODEL_TYPES
from sentinel_ml.ml_monitor import MLMonitor
from sentinel_ml.ml_reset import MLResetManager, get_reset_status, is_reset_in_progress, set_active_reset
from sentinel_ml.ml_retrainer import MLRetrainer
from sentinel_ml.ml_trainer import TrainingDataGenerator
from sentinel_ml.utils.weights import compute_weighted_blend

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ml", tags=["ml"])
_OVERLAY_CACHE: dict[str, object] = {"key": None, "value": None}


def _as_int(value: Any, default: int) -> int:
    """Convert dynamic setting values to int with a safe default."""
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        return default


@router.get("/status")
async def get_ml_status(deps: Annotated[CommonDependencies, Depends(get_common_deps)]) -> dict:
    ml_securities = await deps.monolith.get_ml_enabled_securities()

    cursor = await deps.ml_db.conn.execute("SELECT COUNT(*) as count FROM ml_training_samples")
    total_samples_row = await cursor.fetchone()
    total_samples = total_samples_row["count"] if total_samples_row else 0

    all_model_status = await deps.ml_db.get_all_model_status()
    symbols_with_models = set()
    per_model_metrics = {}
    for mt in MODEL_TYPES:
        models = all_model_status.get(mt, [])
        for m in models:
            symbols_with_models.add(m["symbol"])
        if models:
            per_model_metrics[mt] = {
                "symbols": len(models),
                "avg_validation_rmse": sum(m["validation_rmse"] or 0 for m in models) / len(models),
                "avg_validation_mae": sum(m["validation_mae"] or 0 for m in models) / len(models),
                "avg_validation_r2": sum(m["validation_r2"] or 0 for m in models) / len(models),
            }

    return {
        "securities_ml_enabled": len(ml_securities),
        "symbols_with_models": len(symbols_with_models),
        "total_training_samples": total_samples,
        "per_model_metrics": per_model_metrics,
        "ml_securities": [
            {"symbol": row["symbol"], "blend_ratio": row.get("ml_blend_ratio", 0.5)} for row in ml_securities
        ],
    }


@router.post("/retrain")
async def trigger_retraining(deps: Annotated[CommonDependencies, Depends(get_common_deps)]) -> dict:
    rows = await deps.monolith.get_ml_enabled_securities()
    if not rows:
        return {"status": "skipped", "reason": "No securities have ML enabled"}

    retrainer = MLRetrainer(ml_db=deps.ml_db)
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

    return {"status": "completed", "symbols_trained": trained, "symbols_skipped": skipped, "results": results}


@router.post("/retrain/{symbol}")
async def trigger_retraining_symbol(symbol: str, deps: Annotated[CommonDependencies, Depends(get_common_deps)]) -> dict:
    retrainer = MLRetrainer(ml_db=deps.ml_db)
    result = await retrainer.retrain_symbol(symbol)

    if result is None:
        return {"status": "skipped", "symbol": symbol, "reason": "Insufficient training data"}

    return {"status": "trained", "symbol": symbol, **result}


@router.get("/performance")
async def get_ml_performance(deps: Annotated[CommonDependencies, Depends(get_common_deps)]) -> dict:
    rows = await deps.monolith.get_ml_enabled_securities()

    if not rows:
        return {
            "metrics": {"status": "skipped", "reason": "No securities have ML enabled"},
            "report": "No ML-enabled securities to monitor.",
        }

    monitor = MLMonitor(ml_db=deps.ml_db)
    all_metrics = {}
    for row in rows:
        symbol = row["symbol"]
        result = await monitor.track_symbol_performance(symbol)
        if result:
            all_metrics[symbol] = result

    report = await monitor.generate_report()
    return {"metrics": all_metrics, "report": report}


@router.get("/models")
async def list_ml_models(deps: Annotated[CommonDependencies, Depends(get_common_deps)]) -> dict:
    all_status = await deps.ml_db.get_all_model_status()
    return {"models": all_status}


@router.get("/models/{symbol}")
async def get_ml_model(symbol: str, deps: Annotated[CommonDependencies, Depends(get_common_deps)]) -> dict:
    from sentinel_ml.ml_ensemble import EnsembleBlender

    per_model = {}
    found_any = False
    for mt in MODEL_TYPES:
        status_rows = await deps.ml_db.get_model_status(mt)
        row = next((r for r in status_rows if r["symbol"] == symbol), None)
        if row is not None:
            per_model[mt] = row
            found_any = True
        else:
            per_model[mt] = None

    if not found_any:
        return {"error": f"No model found for {symbol}"}

    model_exists = EnsembleBlender.model_exists(symbol)
    sample_count = await deps.ml_db.get_sample_count(symbol)

    return {
        "symbol": symbol,
        "per_model": per_model,
        "model_files_exist": model_exists,
        "available_samples": sample_count,
    }


@router.get("/latest-scores")
async def get_latest_scores(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
    symbols: str,
    as_of_ts: int | None = None,
) -> dict:
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    if not symbol_list:
        return {"scores": {}}

    settings = await deps.monolith.get_settings([f"ml_weight_{mt}" for mt in MODEL_TYPES] + ["ml_weight_wavelet"])
    weights = {mt: float(settings.get(f"ml_weight_{mt}", 0.25) or 0.25) for mt in MODEL_TYPES}
    weights["wavelet"] = float(settings.get("ml_weight_wavelet", 0.25) or 0.25)
    wavelet_scores = await deps.monolith.get_scores(symbol_list, as_of_ts=as_of_ts)

    scores: dict[str, dict] = {}
    for symbol in symbol_list:
        per_model: dict[str, dict] = {}
        score_components: dict[str, float | None] = {"wavelet": wavelet_scores.get(symbol)}
        return_components: dict[str, float | None] = {"wavelet": wavelet_scores.get(symbol)}

        for mt in MODEL_TYPES:
            if as_of_ts is not None:
                row = await deps.ml_db.get_prediction_as_of(mt, symbol, as_of_ts)
            else:
                row = await deps.ml_db.get_latest_prediction(mt, symbol)
            if not row:
                continue

            ml_score = row.get("ml_score")
            predicted_return = row.get("predicted_return")
            if ml_score is None or predicted_return is None:
                continue

            score_components[mt] = float(ml_score)
            return_components[mt] = float(predicted_return)
            per_model[mt] = {
                "ml_score": float(ml_score),
                "predicted_return": float(predicted_return),
                "predicted_at": int(row.get("predicted_at") or 0),
            }

        blended_score = compute_weighted_blend(score_components, weights)
        blended_return = compute_weighted_blend(return_components, weights)
        if blended_score is not None and blended_return is not None:
            scores[symbol] = {
                "ml_score": blended_score,
                "predicted_return": blended_return,
                "final_score": blended_score,
                "per_model": per_model,
            }

    return {"scores": scores}


@router.get("/train/{symbol}/stream")
async def train_symbol_stream(
    symbol: str, deps: Annotated[CommonDependencies, Depends(get_common_deps)]
) -> StreamingResponse:
    def _sse(payload: dict) -> str:
        return f"data: {json.dumps(payload)}\n\n"

    async def generate():
        settings = MonolithSettingsAdapter(deps.monolith)

        try:
            yield _sse({"step": 1, "total": 5, "message": "Checking symbol...", "progress": 0})
            security = await deps.monolith.get_security(symbol)
            if not security:
                yield _sse({"error": "Symbol not found"})
                return

            yield _sse({"step": 2, "total": 5, "message": "Generating training samples...", "progress": 20})
            trainer = TrainingDataGenerator(ml_db=deps.ml_db)
            horizon_days = _as_int(await settings.get("ml_prediction_horizon_days", 14), 14)
            lookback_years = _as_int(await settings.get("ml_training_lookback_years", 8), 8)
            samples_df = await trainer.generate_training_data_for_symbol(
                symbol,
                lookback_years=lookback_years,
                prediction_horizon_days=horizon_days,
            )
            sample_count = len(samples_df) if samples_df is not None else 0
            yield _sse({"step": 2, "total": 5, "message": f"Generated {sample_count} samples", "progress": 40})

            yield _sse({"step": 3, "total": 5, "message": "Checking data sufficiency...", "progress": 50})
            min_samples = _as_int(await settings.get("ml_min_samples_per_symbol", 100), 100)
            if sample_count < min_samples:
                err_msg = f"Insufficient samples: {sample_count} < {min_samples} required"
                yield _sse({"error": err_msg})
                return

            yield _sse(
                {
                    "step": 4,
                    "total": 5,
                    "message": "Training XGBoost + Ridge + RF + SVR...",
                    "progress": 60,
                }
            )
            retrainer = MLRetrainer(ml_db=deps.ml_db)
            metrics = await retrainer.retrain_symbol(symbol)

            if not metrics:
                yield _sse({"error": "Training failed"})
                return

            yield _sse(
                {
                    "step": 4,
                    "total": 5,
                    "message": f"RMSE: {metrics['validation_rmse']:.4f}",
                    "progress": 90,
                }
            )
            yield _sse(
                {
                    "step": 5,
                    "total": 5,
                    "message": "Models saved",
                    "progress": 100,
                    "complete": True,
                    "metrics": metrics,
                }
            )
        except Exception as e:  # noqa: BLE001
            yield _sse({"error": str(e)})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.delete("/training-data/{symbol}")
async def delete_training_data(symbol: str, deps: Annotated[CommonDependencies, Depends(get_common_deps)]) -> dict:
    import shutil

    from sentinel_ml.paths import DATA_DIR

    await deps.ml_db.delete_symbol_data(symbol)

    model_path = DATA_DIR / "ml_models" / symbol
    if model_path.exists():
        shutil.rmtree(model_path)

    return {"status": "deleted", "symbol": symbol}


@router.get("/training-status/{symbol}")
async def get_training_status(symbol: str, deps: Annotated[CommonDependencies, Depends(get_common_deps)]) -> dict:
    from sentinel_ml.ml_ensemble import EnsembleBlender

    sample_count = await deps.ml_db.get_sample_count(symbol)
    per_model = {}
    for mt in MODEL_TYPES:
        status_rows = await deps.ml_db.get_model_status(mt)
        row = next((r for r in status_rows if r["symbol"] == symbol), None)
        per_model[mt] = row

    model_exists = EnsembleBlender.model_exists(symbol)
    return {
        "symbol": symbol,
        "sample_count": sample_count,
        "model_exists": model_exists,
        "per_model": per_model,
    }


@router.post("/reset-and-retrain")
async def reset_and_retrain() -> dict:
    if is_reset_in_progress():
        raise HTTPException(status_code=409, detail="A reset operation is already in progress")

    asyncio.create_task(_run_reset_and_retrain())
    return {"status": "started", "message": "Reset and retrain started in background"}


@router.get("/reset-status")
async def get_ml_reset_status() -> dict:
    return get_reset_status()


@router.get("/portfolio-overlays")
async def get_portfolio_overlays(deps: Annotated[CommonDependencies, Depends(get_common_deps)]) -> dict:
    """Return ML model overlay series keyed by portfolio pnl-history dates."""
    pnl_history = await deps.monolith.get_portfolio_pnl_history()
    points = pnl_history.get("snapshots", [])
    if not points:
        return {"snapshots": []}

    last_date = points[-1]["date"]
    max_pred_ts = 0
    for mt in MODEL_TYPES:
        cursor = await deps.ml_db.conn.execute(f"SELECT MAX(predicted_at) AS max_ts FROM ml_predictions_{mt}")  # noqa: S608
        row = await cursor.fetchone()
        max_pred_ts = max(max_pred_ts, int((row["max_ts"] if row is not None else 0) or 0))
    cache_key = f"{last_date}:{len(points)}:{max_pred_ts}"
    if _OVERLAY_CACHE.get("key") == cache_key and isinstance(_OVERLAY_CACHE.get("value"), dict):
        return _OVERLAY_CACHE["value"]  # type: ignore[return-value]

    # Load raw snapshots to compute per-date portfolio-weighted ML prediction returns.
    raw_snaps = await deps.monolith.get_portfolio_snapshots(days=730)

    # Preload model prediction histories from ml.db.
    ml_per_model: dict[str, dict[str, list[tuple[int, float]]]] = {}
    for mt in MODEL_TYPES:
        ml_per_model[mt] = {}
        rows = await deps.ml_db.get_all_predictions_history(mt)
        for row in rows:
            pr = row.get("predicted_return")
            if pr is None:
                continue
            symbol = row["symbol"]
            ml_per_model[mt].setdefault(symbol, []).append((int(row["predicted_at"]), float(pr)))
        for symbol in ml_per_model[mt]:
            ml_per_model[mt][symbol].sort(key=lambda x: x[0])

    # Compute weighted per-model predicted returns for each snapshot date.
    pred_by_date: dict[str, dict[str, float | None]] = {}
    for snap in raw_snaps:
        date_ts = int(snap["date"])
        iso_date = datetime.utcfromtimestamp(date_ts).strftime("%Y-%m-%d")
        eod_ts = int(datetime.strptime(iso_date + " 23:59:59", "%Y-%m-%d %H:%M:%S").timestamp())

        positions = (snap.get("data") or {}).get("positions", {})
        positions_value = sum((p.get("value_eur", 0) or 0) for p in positions.values())
        model_vals: dict[str, float | None] = {f"ml_{mt}": None for mt in MODEL_TYPES}
        if positions_value <= 0:
            pred_by_date[iso_date] = model_vals
            continue

        for mt in MODEL_TYPES:
            m_sum = 0.0
            m_total = 0.0
            for symbol, pos in positions.items():
                pos_val = float(pos.get("value_eur", 0) or 0)
                if pos_val <= 0:
                    continue
                pm_list = ml_per_model[mt].get(symbol, [])
                if not pm_list:
                    continue
                idx = bisect.bisect_right(pm_list, (eod_ts, float("inf"))) - 1
                if idx >= 0:
                    m_sum += pm_list[idx][1] * pos_val
                    m_total += pos_val
            model_vals[f"ml_{mt}"] = (m_sum / m_total) if m_total > 0 else None

        pred_by_date[iso_date] = model_vals

    # Build final overlay aligned with monolith pnl-history points.
    offset = 14
    overlays = []
    for i, point in enumerate(points):
        row = {"date": point["date"], "ml_xgboost": None, "ml_ridge": None, "ml_rf": None, "ml_svr": None}
        past_i = i - offset
        if past_i >= 0:
            past = points[past_i]
            past_date = past["date"]
            past_actual = past.get("actual_ann_return")
            preds = pred_by_date.get(past_date, {})
            if past_actual is not None:
                for mt in MODEL_TYPES:
                    p = preds.get(f"ml_{mt}")
                    if p is not None:
                        row[f"ml_{mt}"] = round(float(past_actual) + float(p) * 100.0, 2)
        overlays.append(row)

    payload = {"snapshots": overlays}
    _OVERLAY_CACHE["key"] = cache_key
    _OVERLAY_CACHE["value"] = payload
    return payload


async def _run_reset_and_retrain():
    manager = MLResetManager()
    set_active_reset(manager)
    try:
        result = await manager.reset_all()
        logger.info("ML reset and retrain completed: %s", result)
    except Exception as e:  # noqa: BLE001
        logger.error("ML reset and retrain failed: %s", e)
    finally:
        set_active_reset(None)
