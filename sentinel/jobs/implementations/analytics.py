"""Analytics job implementations."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta

from sentinel.jobs.types import BaseJob, MarketTiming

logger = logging.getLogger(__name__)


@dataclass
class CorrelationJob(BaseJob):
    """Update correlation matrices using RMT."""

    _cleaner: object = field(default=None, repr=False)
    _db: object = field(default=None, repr=False)

    def __init__(self, cleaner, db):
        super().__init__(
            _id='analytics:correlation',
            _job_type='analytics:correlation',
            _timeout=timedelta(minutes=30),
            _market_timing=MarketTiming.ALL_MARKETS_CLOSED,
        )
        self._cleaner = cleaner
        self._db = db

    async def execute(self) -> None:
        """Execute correlation calculation."""
        securities = await self._db.get_all_securities(active_only=True)
        symbols = [s['symbol'] for s in securities]

        if len(symbols) < 2:
            logger.warning("Not enough securities for correlation")
            return

        raw_corr, valid_symbols = await self._cleaner.calculate_raw_correlation(
            symbols, days=504
        )
        if raw_corr is not None:
            cleaned_corr = await self._cleaner.clean_correlation(raw_corr)
            await self._cleaner.store_matrices(raw_corr, cleaned_corr, valid_symbols)
            logger.info(
                f"Correlation matrices updated for {len(valid_symbols)} securities"
            )


@dataclass
class RegimeJob(BaseJob):
    """Train HMM regime detection model."""

    _detector: object = field(default=None, repr=False)
    _db: object = field(default=None, repr=False)

    def __init__(self, detector, db):
        super().__init__(
            _id='analytics:regime',
            _job_type='analytics:regime',
            _timeout=timedelta(minutes=30),
            _market_timing=MarketTiming.ALL_MARKETS_CLOSED,
        )
        self._detector = detector
        self._db = db

    async def execute(self) -> None:
        """Execute regime model training."""
        securities = await self._db.get_all_securities(active_only=True)
        symbols = [s['symbol'] for s in securities]

        if len(symbols) < 3:
            logger.warning("Not enough securities for regime detection")
            return

        model = await self._detector.train_model(symbols)
        if model:
            logger.info(f"Regime model trained on {len(symbols)} securities")


@dataclass
class TransferEntropyJob(BaseJob):
    """Calculate transfer entropy matrix."""

    _te_analyzer: object = field(default=None, repr=False)
    _db: object = field(default=None, repr=False)

    def __init__(self, te_analyzer, db):
        super().__init__(
            _id='analytics:transfer_entropy',
            _job_type='analytics:transfer_entropy',
            _timeout=timedelta(minutes=30),
            _market_timing=MarketTiming.ALL_MARKETS_CLOSED,
        )
        self._te_analyzer = te_analyzer
        self._db = db

    async def execute(self) -> None:
        """Execute transfer entropy calculation."""
        securities = await self._db.get_all_securities(active_only=True)
        symbols = [s['symbol'] for s in securities]

        if len(symbols) < 2:
            logger.warning("Not enough securities for transfer entropy")
            return

        await self._te_analyzer.calculate_matrix(symbols)
        logger.info(f"Transfer entropy calculated for {len(symbols)} securities")
