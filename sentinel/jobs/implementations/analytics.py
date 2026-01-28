"""Analytics job implementations."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta

from sentinel.jobs.types import BaseJob, MarketTiming

logger = logging.getLogger(__name__)


@dataclass
class RegimeJob(BaseJob):
    """Train HMM regime detection model."""

    _detector: object = field(default=None, repr=False)
    _db: object = field(default=None, repr=False)

    def __init__(self, detector, db):
        super().__init__(
            _id="analytics:regime",
            _job_type="analytics:regime",
            _timeout=timedelta(minutes=30),
            _market_timing=MarketTiming.ALL_MARKETS_CLOSED,
        )
        self._detector = detector
        self._db = db

    async def execute(self) -> None:
        """Execute regime model training."""
        securities = await self._db.get_all_securities(active_only=True)
        symbols = [s["symbol"] for s in securities]

        if len(symbols) < 3:
            logger.warning("Not enough securities for regime detection")
            return

        model = await self._detector.train_model(symbols)
        if model:
            logger.info(f"Regime model trained on {len(symbols)} securities")
