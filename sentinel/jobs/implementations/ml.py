"""ML job implementations."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta

from sentinel.jobs.types import BaseJob, MarketTiming

logger = logging.getLogger(__name__)


@dataclass
class MLRetrainJob(BaseJob):
    """Retrain ML model for a specific symbol."""

    _symbol: str = ""
    _retrainer: object = field(default=None, repr=False)

    def __init__(self, symbol: str, retrainer):
        super().__init__(
            _id=f'ml:retrain:{symbol}',
            _job_type='ml:retrain',
            _timeout=timedelta(minutes=30),
            _market_timing=MarketTiming.ALL_MARKETS_CLOSED,
            _subject=symbol,
        )
        self._symbol = symbol
        self._retrainer = retrainer

    async def execute(self) -> None:
        """Execute ML retraining."""
        result = await self._retrainer.retrain_symbol(self._symbol)

        if result:
            logger.info(
                f"ML retraining complete for {self._symbol}: "
                f"RMSE={result.get('validation_rmse', 0):.4f}, "
                f"samples={result.get('training_samples', 0)}"
            )
        else:
            logger.info(f"ML retraining skipped for {self._symbol}: insufficient data")


@dataclass
class MLMonitorJob(BaseJob):
    """Monitor ML model performance for a specific symbol."""

    _symbol: str = ""
    _monitor: object = field(default=None, repr=False)

    def __init__(self, symbol: str, monitor):
        super().__init__(
            _id=f'ml:monitor:{symbol}',
            _job_type='ml:monitor',
            _timeout=timedelta(minutes=10),
            _market_timing=MarketTiming.ANY_TIME,
            _subject=symbol,
        )
        self._symbol = symbol
        self._monitor = monitor

    async def execute(self) -> None:
        """Execute ML performance monitoring."""
        result = await self._monitor.track_symbol_performance(self._symbol)

        if result and result.get('predictions_evaluated', 0) > 0:
            logger.info(
                f"ML performance for {self._symbol}: "
                f"MAE={result.get('mean_absolute_error', 0):.4f}, "
                f"RMSE={result.get('root_mean_squared_error', 0):.4f}, "
                f"N={result['predictions_evaluated']}"
            )

            if result.get('drift_detected'):
                logger.warning(f"ML DRIFT DETECTED for {self._symbol}!")
        else:
            logger.info(
                f"ML monitoring for {self._symbol}: no predictions to evaluate"
            )
