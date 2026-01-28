"""ML performance monitoring and drift detection - per-symbol tracking."""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

from sentinel.database import Database
from sentinel.settings import Settings

logger = logging.getLogger(__name__)


class MLMonitor:
    """Monitor ML prediction performance per symbol."""

    def __init__(self):
        self.db = Database()
        self.settings = Settings()

    async def track_performance(self) -> Dict:
        """
        Track ML predictions vs actual returns for each symbol.

        Process:
        1. Get predictions from 14+ days ago (so we have actual returns)
        2. Group by symbol
        3. For each symbol: calculate error metrics (MAE, RMSE, bias)
        4. Store per-symbol metrics in performance tracking table
        5. Check for per-symbol drift

        Returns:
            {
                'status': 'success',
                'symbols_evaluated': int,
                'total_predictions_evaluated': int,
                'drift_detected': List[str],  # symbols with drift
                'per_symbol_metrics': {symbol: metrics}
            }
        """
        await self.db.connect()

        # Get prediction horizon from settings
        horizon_days = await self.settings.get('ml_prediction_horizon_days', 14)

        # Get predictions from horizon_days to 2*horizon_days ago
        start_date = (datetime.now() - timedelta(days=2 * horizon_days)).isoformat()
        end_date = (datetime.now() - timedelta(days=horizon_days)).isoformat()

        query = """
            SELECT symbol, predicted_at, predicted_return
            FROM ml_predictions
            WHERE predicted_at >= ? AND predicted_at <= ?
            ORDER BY symbol, predicted_at
        """
        cursor = await self.db.conn.execute(query, (start_date, end_date))
        predictions = await cursor.fetchall()

        if len(predictions) == 0:
            logger.info("No predictions to evaluate yet")
            return {
                'status': 'success',
                'symbols_evaluated': 0,
                'total_predictions_evaluated': 0,
                'drift_detected': [],
                'message': 'No predictions to evaluate yet'
            }

        # Group predictions by symbol
        symbol_predictions: Dict[str, List] = {}
        for pred_row in predictions:
            symbol = pred_row['symbol']
            if symbol not in symbol_predictions:
                symbol_predictions[symbol] = []
            symbol_predictions[symbol].append(pred_row)

        # Track metrics per symbol
        tracked_at = datetime.now().isoformat()
        per_symbol_metrics = {}
        drift_detected = []
        total_evaluated = 0

        for symbol, preds in symbol_predictions.items():
            metrics = await self._evaluate_symbol(symbol, preds, horizon_days)

            if metrics and metrics['predictions_evaluated'] > 0:
                per_symbol_metrics[symbol] = metrics
                total_evaluated += metrics['predictions_evaluated']

                # Store metrics
                await self._store_symbol_metrics(symbol, tracked_at, metrics)

                # Check drift for this symbol
                is_drifting = await self._check_symbol_drift(
                    symbol, metrics['mean_absolute_error'], metrics['root_mean_squared_error']
                )

                if is_drifting:
                    drift_detected.append(symbol)
                    logger.warning(f"{symbol}: Drift detected! MAE={metrics['mean_absolute_error']:.4f}")

                    # Update drift flag
                    await self.db.conn.execute(
                        """UPDATE ml_performance_tracking
                           SET drift_detected = 1
                           WHERE symbol = ? AND tracked_at = ?""",
                        (symbol, tracked_at)
                    )
                    await self.db.conn.commit()

        logger.info(f"Performance tracked for {len(per_symbol_metrics)} symbols, {total_evaluated} predictions")
        if drift_detected:
            logger.warning(f"Drift detected in: {', '.join(drift_detected)}")

        return {
            'status': 'success',
            'symbols_evaluated': len(per_symbol_metrics),
            'total_predictions_evaluated': total_evaluated,
            'drift_detected': drift_detected,
            'per_symbol_metrics': per_symbol_metrics,
        }

    async def _evaluate_symbol(
        self, symbol: str, predictions: List, horizon_days: int
    ) -> Optional[Dict]:
        """Evaluate predictions for a single symbol."""
        errors = []

        for pred_row in predictions:
            predicted_at = pred_row['predicted_at']
            predicted_return = pred_row['predicted_return']

            if predicted_return is None:
                continue

            actual_return = await self._get_actual_return(symbol, predicted_at, horizon_days)

            if actual_return is not None:
                error = predicted_return - actual_return
                errors.append(error)

        if len(errors) == 0:
            return None

        errors = np.array(errors)

        mae = float(np.mean(np.abs(errors)))
        rmse = float(np.sqrt(np.mean(errors ** 2)))
        bias = float(np.mean(errors))

        return {
            'mean_absolute_error': mae,
            'root_mean_squared_error': rmse,
            'prediction_bias': bias,
            'predictions_evaluated': len(errors),
        }

    async def _get_actual_return(
        self, symbol: str, prediction_date: str, horizon_days: int
    ) -> Optional[float]:
        """Get actual return for a prediction."""
        try:
            pred_dt = datetime.fromisoformat(prediction_date)
        except (ValueError, TypeError) as e:
            logger.debug(f"Invalid prediction date '{prediction_date}': {e}")
            return None

        # Get price at prediction date
        query_pred = """
            SELECT close FROM prices
            WHERE symbol = ? AND date >= ?
            ORDER BY date ASC LIMIT 1
        """
        cursor = await self.db.conn.execute(
            query_pred, (symbol, pred_dt.strftime('%Y-%m-%d'))
        )
        pred_price_row = await cursor.fetchone()

        if not pred_price_row:
            return None

        pred_price = pred_price_row['close']
        if pred_price is None or pred_price <= 0:
            return None

        # Get price horizon_days later
        future_dt = pred_dt + timedelta(days=horizon_days)
        query_future = """
            SELECT close FROM prices
            WHERE symbol = ? AND date >= ?
            ORDER BY date ASC LIMIT 1
        """
        cursor = await self.db.conn.execute(
            query_future, (symbol, future_dt.strftime('%Y-%m-%d'))
        )
        future_price_row = await cursor.fetchone()

        if not future_price_row:
            return None

        future_price = future_price_row['close']
        if future_price is None or future_price <= 0:
            return None

        actual_return = (future_price / pred_price) - 1.0
        return float(actual_return)

    async def _store_symbol_metrics(self, symbol: str, tracked_at: str, metrics: Dict):
        """Store performance metrics for a symbol."""
        try:
            await self.db.conn.execute(
                """INSERT OR REPLACE INTO ml_performance_tracking
                   (symbol, tracked_at, mean_absolute_error, root_mean_squared_error,
                    prediction_bias, drift_detected, predictions_evaluated)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    symbol, tracked_at,
                    metrics['mean_absolute_error'],
                    metrics['root_mean_squared_error'],
                    metrics['prediction_bias'],
                    0,  # drift_detected - updated later if needed
                    metrics['predictions_evaluated']
                )
            )
            await self.db.conn.commit()
        except Exception as e:
            logger.error(f"Failed to store metrics for {symbol}: {e}")

    async def _check_symbol_drift(
        self, symbol: str, current_mae: float, current_rmse: float
    ) -> bool:
        """
        Check for model drift for a specific symbol.

        Drift detected if current error > baseline + 2σ
        """
        # Get historical metrics for this symbol
        query = """
            SELECT mean_absolute_error, root_mean_squared_error
            FROM ml_performance_tracking
            WHERE symbol = ? AND tracked_at < ?
            ORDER BY tracked_at DESC
            LIMIT 30
        """
        cutoff = datetime.now().isoformat()
        cursor = await self.db.conn.execute(query, (symbol, cutoff))
        historical = await cursor.fetchall()

        if len(historical) < 5:
            logger.debug(f"{symbol}: Not enough historical data for drift detection")
            return False

        historical_mae = [row['mean_absolute_error'] for row in historical if row['mean_absolute_error'] is not None]
        historical_rmse = [row['root_mean_squared_error'] for row in historical if row['root_mean_squared_error'] is not None]

        if len(historical_mae) < 5:
            return False

        baseline_mae = np.mean(historical_mae)
        std_mae = np.std(historical_mae)

        baseline_rmse = np.mean(historical_rmse)
        std_rmse = np.std(historical_rmse)

        # Drift if current > baseline + 2σ
        # Use epsilon threshold to handle floating point precision issues
        epsilon = 1e-10
        drift_mae = current_mae > (baseline_mae + 2 * std_mae) if std_mae > epsilon else False
        drift_rmse = current_rmse > (baseline_rmse + 2 * std_rmse) if std_rmse > epsilon else False

        return drift_mae or drift_rmse

    async def generate_report(self) -> str:
        """Generate performance report for all symbols."""
        await self.db.connect()

        # Get aggregate statistics
        query_agg = """
            SELECT
                COUNT(DISTINCT symbol) as symbols,
                AVG(mean_absolute_error) as avg_mae,
                AVG(root_mean_squared_error) as avg_rmse,
                AVG(prediction_bias) as avg_bias,
                SUM(drift_detected) as drift_count,
                SUM(predictions_evaluated) as total_predictions
            FROM ml_performance_tracking
            WHERE tracked_at >= datetime('now', '-30 days')
        """
        cursor = await self.db.conn.execute(query_agg)
        agg = await cursor.fetchone()

        if not agg or agg['symbols'] is None or agg['symbols'] == 0:
            return "No performance data available yet."

        # Get per-symbol recent metrics
        query_symbols = """
            SELECT symbol,
                   AVG(mean_absolute_error) as avg_mae,
                   AVG(root_mean_squared_error) as avg_rmse,
                   SUM(drift_detected) as drift_count
            FROM ml_performance_tracking
            WHERE tracked_at >= datetime('now', '-30 days')
            GROUP BY symbol
            ORDER BY avg_mae DESC
            LIMIT 10
        """
        cursor = await self.db.conn.execute(query_symbols)
        symbol_stats = await cursor.fetchall()

        # Get symbols with recent drift
        query_drift = """
            SELECT DISTINCT symbol
            FROM ml_performance_tracking
            WHERE drift_detected = 1 AND tracked_at >= datetime('now', '-7 days')
        """
        cursor = await self.db.conn.execute(query_drift)
        drifting = await cursor.fetchall()
        drifting_symbols = [r['symbol'] for r in drifting]

        report = f"""
ML Performance Report (Last 30 Days)
{'='*70}

Aggregate Statistics:
- Symbols tracked: {agg['symbols']}
- Total predictions evaluated: {agg['total_predictions'] or 0}
- Mean MAE: {(agg['avg_mae'] or 0):.4f}
- Mean RMSE: {(agg['avg_rmse'] or 0):.4f}
- Mean Bias: {(agg['avg_bias'] or 0):.4f}
- Drift events: {agg['drift_count'] or 0}

Top 10 Symbols by MAE (worst first):
"""
        for row in symbol_stats:
            drift_flag = " [DRIFT]" if row['drift_count'] and row['drift_count'] > 0 else ""
            report += f"  {row['symbol']}: MAE={row['avg_mae']:.4f}, RMSE={row['avg_rmse']:.4f}{drift_flag}\n"

        if drifting_symbols:
            report += f"\nSymbols with recent drift (last 7 days):\n"
            report += f"  {', '.join(drifting_symbols)}\n"
        else:
            report += f"\nNo drift detected in last 7 days.\n"

        return report

    async def track_symbol_performance(self, symbol: str) -> Optional[Dict]:
        """
        Track ML predictions vs actual returns for a single symbol.

        Returns metrics for this symbol or None if no predictions to evaluate.
        """
        await self.db.connect()

        horizon_days = await self.settings.get('ml_prediction_horizon_days', 14)

        # Get predictions for this symbol from horizon_days to 2*horizon_days ago
        start_date = (datetime.now() - timedelta(days=2 * horizon_days)).isoformat()
        end_date = (datetime.now() - timedelta(days=horizon_days)).isoformat()

        query = """
            SELECT symbol, predicted_at, predicted_return
            FROM ml_predictions
            WHERE symbol = ? AND predicted_at >= ? AND predicted_at <= ?
            ORDER BY predicted_at
        """
        cursor = await self.db.conn.execute(query, (symbol, start_date, end_date))
        predictions = await cursor.fetchall()

        if len(predictions) == 0:
            return None

        # Evaluate predictions
        metrics = await self._evaluate_symbol(symbol, predictions, horizon_days)

        if metrics and metrics['predictions_evaluated'] > 0:
            tracked_at = datetime.now().isoformat()
            await self._store_symbol_metrics(symbol, tracked_at, metrics)

            # Check drift
            is_drifting = await self._check_symbol_drift(
                symbol, metrics['mean_absolute_error'], metrics['root_mean_squared_error']
            )

            if is_drifting:
                metrics['drift_detected'] = True
                await self.db.conn.execute(
                    """UPDATE ml_performance_tracking
                       SET drift_detected = 1
                       WHERE symbol = ? AND tracked_at = ?""",
                    (symbol, tracked_at)
                )
                await self.db.conn.commit()
            else:
                metrics['drift_detected'] = False

        return metrics

    async def get_symbol_history(self, symbol: str, days: int = 30) -> List[Dict]:
        """Get performance history for a specific symbol."""
        await self.db.connect()

        query = """
            SELECT tracked_at, mean_absolute_error, root_mean_squared_error,
                   prediction_bias, drift_detected, predictions_evaluated
            FROM ml_performance_tracking
            WHERE symbol = ? AND tracked_at >= datetime('now', ? || ' days')
            ORDER BY tracked_at DESC
        """
        cursor = await self.db.conn.execute(query, (symbol, f'-{days}'))
        rows = await cursor.fetchall()

        return [dict(row) for row in rows]
