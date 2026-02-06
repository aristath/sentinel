"""ML performance monitoring and drift detection - per-model tracking."""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Optional

import numpy as np

from sentinel_ml.adapters import MonolithDBAdapter, MonolithSettingsAdapter
from sentinel_ml.clients.monolith_client import MonolithDataClient
from sentinel_ml.database.ml import MODEL_TYPES, MLDatabase
from sentinel_ml.price_validator import PriceValidator

logger = logging.getLogger(__name__)


class MLMonitor:
    """Monitor ML prediction performance per model type and per symbol."""

    def __init__(self, db=None, ml_db=None, settings=None):
        client = MonolithDataClient()
        self.db = db or MonolithDBAdapter(client)
        self.ml_db = ml_db or MLDatabase()
        self.settings = settings or MonolithSettingsAdapter(client)

    async def track_performance(self) -> Dict:
        """
        Track ML predictions vs actual returns for each symbol, per model type.

        Returns:
            {
                'status': 'success',
                'symbols_evaluated': int,
                'total_predictions_evaluated': int,
                'drift_detected': List[str],
                'per_model_metrics': {model_type: {symbol: metrics}}
            }
        """
        await self.db.connect()
        await self.ml_db.connect()

        horizon_days = int(await self.settings.get("ml_prediction_horizon_days", 14) or 14)

        # Cutoff timestamps
        now_ts = int(time.time())
        start_ts = now_ts - (2 * horizon_days * 86400)
        end_ts = now_ts - (horizon_days * 86400)

        per_model_metrics = {}
        all_symbols_evaluated = set()
        total_evaluated = 0
        drift_detected = []

        for mt in MODEL_TYPES:
            # Get symbols with predictions in the evaluation window
            cursor = await self.ml_db.conn.execute(
                f"SELECT DISTINCT symbol FROM ml_predictions_{mt} "  # noqa: S608
                "WHERE predicted_at >= ? AND predicted_at <= ? ORDER BY symbol",
                (start_ts, end_ts),
            )
            rows = await cursor.fetchall()
            symbols = [row["symbol"] for row in rows]

            mt_metrics = {}
            for symbol in symbols:
                metrics = await self._evaluate_model_symbol(mt, symbol, start_ts, end_ts, horizon_days)
                if metrics and metrics["predictions_evaluated"] > 0:
                    mt_metrics[symbol] = metrics
                    all_symbols_evaluated.add(symbol)
                    total_evaluated += metrics["predictions_evaluated"]

                    # Store performance and check drift
                    tracked_at = int(time.time())
                    await self.ml_db.store_performance_metrics(mt, symbol, tracked_at, metrics)

                    is_drifting = await self._check_symbol_drift(mt, symbol, metrics["mean_absolute_error"])
                    if is_drifting:
                        metrics["drift_detected"] = True
                        drift_detected.append(f"{mt}:{symbol}")
                    else:
                        metrics["drift_detected"] = False

            per_model_metrics[mt] = mt_metrics

        logger.info(f"Performance tracked: {len(all_symbols_evaluated)} symbols, {total_evaluated} predictions")
        if drift_detected:
            logger.warning(f"Drift detected in: {', '.join(drift_detected)}")

        return {
            "status": "success",
            "symbols_evaluated": len(all_symbols_evaluated),
            "total_predictions_evaluated": total_evaluated,
            "drift_detected": drift_detected,
            "per_model_metrics": per_model_metrics,
        }

    async def _evaluate_model_symbol(
        self, model_type: str, symbol: str, start_ts: int, end_ts: int, horizon_days: int
    ) -> Optional[Dict]:
        """Evaluate predictions for a single model type and symbol."""
        cursor = await self.ml_db.conn.execute(
            f"SELECT symbol, predicted_at, predicted_return FROM ml_predictions_{model_type} "  # noqa: S608
            "WHERE symbol = ? AND predicted_at >= ? AND predicted_at <= ? ORDER BY predicted_at",
            (symbol, start_ts, end_ts),
        )
        predictions = list(await cursor.fetchall())

        if not predictions:
            return None

        errors = []
        for pred_row in predictions:
            predicted_return = pred_row["predicted_return"]
            if predicted_return is None:
                continue

            predicted_at_ts = pred_row["predicted_at"]
            actual_return = await self._get_actual_return(symbol, predicted_at_ts, horizon_days)

            if actual_return is not None:
                errors.append(predicted_return - actual_return)

        if not errors:
            return None

        errors = np.array(errors)
        return {
            "mean_absolute_error": float(np.mean(np.abs(errors))),
            "root_mean_squared_error": float(np.sqrt(np.mean(errors**2))),
            "prediction_bias": float(np.mean(errors)),
            "predictions_evaluated": len(errors),
        }

    async def _get_actual_return(self, symbol: str, predicted_at_ts: int, horizon_days: int) -> Optional[float]:
        """Get actual return for a prediction using validated prices."""
        pred_dt = datetime.fromtimestamp(predicted_at_ts)
        future_dt = pred_dt + timedelta(days=horizon_days)

        end_date = (future_dt + timedelta(days=7)).strftime("%Y-%m-%d")
        prices = await self.db.get_prices(symbol, days=horizon_days + 30, end_date=end_date)
        if not prices:
            return None

        validator = PriceValidator()
        validated = validator.validate_and_interpolate(list(reversed(prices)))
        if not validated:
            return None

        price_map = {p["date"]: p["close"] for p in validated}

        pred_price = None
        for offset in range(8):
            d = (pred_dt + timedelta(days=offset)).strftime("%Y-%m-%d")
            if d in price_map:
                pred_price = price_map[d]
                break
        if pred_price is None or pred_price <= 0:
            return None

        future_price = None
        for offset in range(8):
            d = (future_dt + timedelta(days=offset)).strftime("%Y-%m-%d")
            if d in price_map:
                future_price = price_map[d]
                break
        if future_price is None or future_price <= 0:
            return None

        return float((future_price / pred_price) - 1.0)

    async def _check_symbol_drift(self, model_type: str, symbol: str, current_mae: float) -> bool:
        """Check for model drift. Drift if current MAE > baseline + 2sigma."""
        cursor = await self.ml_db.conn.execute(
            f"SELECT mean_absolute_error FROM ml_performance_{model_type} "  # noqa: S608
            "WHERE symbol = ? ORDER BY tracked_at DESC LIMIT 30",
            (symbol,),
        )
        historical = list(await cursor.fetchall())

        if len(historical) < 5:
            return False

        historical_mae = [row["mean_absolute_error"] for row in historical if row["mean_absolute_error"] is not None]
        if len(historical_mae) < 5:
            return False

        baseline = np.mean(historical_mae)
        std = np.std(historical_mae)

        if std < 1e-10:
            return False

        return bool(current_mae > baseline + 2 * std)

    async def track_symbol_performance(self, symbol: str) -> Optional[Dict]:
        """Track performance for a single symbol across all model types."""
        await self.db.connect()
        await self.ml_db.connect()

        horizon_days = int(await self.settings.get("ml_prediction_horizon_days", 14) or 14)
        now_ts = int(time.time())
        start_ts = now_ts - (2 * horizon_days * 86400)
        end_ts = now_ts - (horizon_days * 86400)

        per_model = {}
        for mt in MODEL_TYPES:
            metrics = await self._evaluate_model_symbol(mt, symbol, start_ts, end_ts, horizon_days)
            if metrics and metrics["predictions_evaluated"] > 0:
                tracked_at = int(time.time())
                await self.ml_db.store_performance_metrics(mt, symbol, tracked_at, metrics)
                per_model[mt] = metrics

        if not per_model:
            return None

        return per_model

    async def generate_report(self) -> str:
        """Generate performance report across all model types."""
        await self.ml_db.connect()

        lines = ["ML Performance Report (Per-Model)", "=" * 70, ""]

        for mt in MODEL_TYPES:
            cursor = await self.ml_db.conn.execute(
                f"SELECT COUNT(DISTINCT symbol) as symbols, "  # noqa: S608
                f"AVG(mean_absolute_error) as avg_mae, "
                f"AVG(root_mean_squared_error) as avg_rmse, "
                f"AVG(prediction_bias) as avg_bias, "
                f"SUM(predictions_evaluated) as total_preds "
                f"FROM ml_performance_{mt}"
            )
            agg = await cursor.fetchone()

            if not agg or not agg["symbols"]:
                lines.append(f"{mt}: No data")
                continue

            lines.append(
                f"{mt}: {agg['symbols']} symbols, "
                f"MAE={agg['avg_mae'] or 0:.4f}, "
                f"RMSE={agg['avg_rmse'] or 0:.4f}, "
                f"Bias={agg['avg_bias'] or 0:.4f}, "
                f"Preds={agg['total_preds'] or 0}"
            )

        return "\n".join(lines)
