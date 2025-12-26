"""Calculations repository - operations for pre-computed raw metrics database."""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from app.domain.scoring.constants import DEFAULT_METRIC_TTL, METRIC_TTL
from app.infrastructure.database import get_db_manager

logger = logging.getLogger(__name__)


class CalculationsRepository:
    """Repository for pre-computed raw metrics stored in calculations.db."""

    def __init__(self):
        self._db_manager = get_db_manager()

    def _get_ttl_for_metric(self, metric: str) -> int:
        """Get TTL in seconds for a metric."""
        return METRIC_TTL.get(metric, DEFAULT_METRIC_TTL)

    async def get_metric(self, symbol: str, metric: str) -> Optional[float]:
        """
        Get latest metric value if not expired.

        Args:
            symbol: Stock symbol
            metric: Metric name (e.g., 'RSI_14', 'SHARPE', 'CAGR_5Y')

        Returns:
            Metric value or None if not found/expired
        """
        db = self._db_manager.calculations
        now = datetime.now().isoformat()

        row = await db.fetchone(
            """SELECT value, expires_at FROM calculated_metrics
               WHERE symbol = ? AND metric = ? AND (expires_at IS NULL OR expires_at > ?)""",
            (symbol.upper(), metric, now),
        )

        if row:
            return float(row["value"])

        return None

    async def set_metric(
        self,
        symbol: str,
        metric: str,
        value: float,
        ttl_override: Optional[int] = None,
        source: str = "calculated",
    ) -> None:
        """
        Store or update a metric value with automatic TTL.

        Args:
            symbol: Stock symbol
            metric: Metric name
            value: Metric value
            ttl_override: Optional TTL in seconds (overrides automatic lookup)
            source: Source of the metric ('calculated', 'yahoo', 'pyfolio')
        """
        db = self._db_manager.calculations
        now = datetime.now()

        # Get TTL (use override if provided, otherwise lookup)
        ttl_seconds = (
            ttl_override
            if ttl_override is not None
            else self._get_ttl_for_metric(metric)
        )
        expires_at = (now + timedelta(seconds=ttl_seconds)).isoformat()

        await db.execute(
            """INSERT OR REPLACE INTO calculated_metrics
               (symbol, metric, value, calculated_at, expires_at, source)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (symbol.upper(), metric, value, now.isoformat(), expires_at, source),
        )
        await db.commit()

        logger.debug(
            f"Stored metric {metric} for {symbol}: {value} (TTL: {ttl_seconds}s)"
        )

    async def get_metrics(
        self, symbol: str, metrics: List[str]
    ) -> Dict[str, Optional[float]]:
        """
        Batch get multiple metrics for a symbol.

        Args:
            symbol: Stock symbol
            metrics: List of metric names

        Returns:
            Dict mapping metric name to value (None if not found/expired)
        """
        db = self._db_manager.calculations
        now = datetime.now().isoformat()

        # Build query with placeholders
        placeholders = ",".join(["?"] * len(metrics))
        query = f"""SELECT metric, value FROM calculated_metrics
                    WHERE symbol = ? AND metric IN ({placeholders})
                    AND (expires_at IS NULL OR expires_at > ?)"""

        rows = await db.fetchall(query, (symbol.upper(), *metrics, now))

        # Build result dict
        result = {metric: None for metric in metrics}
        for row in rows:
            result[row["metric"]] = float(row["value"])

        return result

    async def set_metrics(
        self,
        symbol: str,
        metrics: Dict[str, float],
        ttl_override: Optional[int] = None,
        source: str = "calculated",
    ) -> None:
        """
        Batch set multiple metrics with per-metric TTL.

        Args:
            symbol: Stock symbol
            metrics: Dict mapping metric name to value
            ttl_override: Optional TTL in seconds (applies to all metrics)
            source: Source of the metrics
        """
        db = self._db_manager.calculations
        now = datetime.now()

        async with db.transaction():
            for metric, value in metrics.items():
                # Get TTL for this specific metric (unless override provided)
                ttl_seconds = (
                    ttl_override
                    if ttl_override is not None
                    else self._get_ttl_for_metric(metric)
                )
                expires_at = (now + timedelta(seconds=ttl_seconds)).isoformat()

                await db.execute(
                    """INSERT OR REPLACE INTO calculated_metrics
                       (symbol, metric, value, calculated_at, expires_at, source)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        symbol.upper(),
                        metric,
                        value,
                        now.isoformat(),
                        expires_at,
                        source,
                    ),
                )

        await db.commit()
        logger.debug(f"Stored {len(metrics)} metrics for {symbol}")

    async def get_all_metrics(self, symbol: str) -> Dict[str, float]:
        """
        Get all non-expired metrics for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Dict mapping metric name to value
        """
        db = self._db_manager.calculations
        now = datetime.now().isoformat()

        rows = await db.fetchall(
            """SELECT metric, value FROM calculated_metrics
               WHERE symbol = ? AND (expires_at IS NULL OR expires_at > ?)""",
            (symbol.upper(), now),
        )

        return {row["metric"]: float(row["value"]) for row in rows}

    async def delete_expired(self) -> int:
        """
        Delete expired metric entries.

        Returns:
            Number of entries deleted
        """
        db = self._db_manager.calculations
        now = datetime.now().isoformat()

        cursor = await db.execute(
            "DELETE FROM calculated_metrics WHERE expires_at IS NOT NULL AND expires_at < ?",
            (now,),
        )
        await db.commit()

        count = cursor.rowcount
        if count > 0:
            logger.info(f"Deleted {count} expired metric entries")
        return count

    def get_ttl_for_metric(self, metric: str) -> int:
        """
        Get TTL for a metric (from METRIC_TTL or default).

        Args:
            metric: Metric name

        Returns:
            TTL in seconds
        """
        return self._get_ttl_for_metric(metric)
