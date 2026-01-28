"""Scoring job implementations."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta

from sentinel.jobs.types import BaseJob, MarketTiming

logger = logging.getLogger(__name__)


@dataclass
class CalculateScoresJob(BaseJob):
    """Calculate scores for all securities."""

    _analyzer: object = field(default=None, repr=False)

    def __init__(self, analyzer):
        super().__init__(
            _id="scoring:calculate",
            _job_type="scoring:calculate",
            _timeout=timedelta(minutes=30),
            _market_timing=MarketTiming.ANY_TIME,
        )
        self._analyzer = analyzer

    async def execute(self) -> None:
        """Execute score calculation."""
        count = await self._analyzer.update_scores()
        logger.info(f"Calculated scores for {count} securities")
