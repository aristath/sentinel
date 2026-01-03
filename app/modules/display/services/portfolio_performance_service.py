"""Portfolio performance calculation service for display visualization.

Calculates weighted performance metrics:
- Trailing 12-month annualized return
- Since-inception CAGR
- Weighted combination for display purposes
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class PortfolioPerformanceService:
    """Calculate portfolio performance metrics for display visualization."""

    def __init__(self, portfolio_repo, settings_repo) -> None:
        """Initialize performance service.

        Args:
            portfolio_repo: Portfolio repository for historical snapshots
            settings_repo: Settings repository for weights and targets
        """
        self._portfolio_repo = portfolio_repo
        self._settings_repo = settings_repo

    async def calculate_weighted_performance(self) -> Optional[float]:
        """Calculate weighted portfolio performance vs target.

        Returns weighted combination of:
        - Trailing 12-month annualized return (70% default)
        - Since-inception CAGR (30% default)

        Returns:
            Weighted performance as decimal (e.g., 0.12 = 12%), or None if insufficient data
        """
        # Get weights from settings
        trailing_weight = await self._settings_repo.get_float(
            "display_performance_trailing12mo_weight", 0.70
        )
        inception_weight = await self._settings_repo.get_float(
            "display_performance_inception_weight", 0.30
        )

        # Calculate both metrics
        trailing_12mo = await self.calculate_trailing_12mo_return()
        since_inception = await self.calculate_since_inception_cagr()

        if trailing_12mo is None and since_inception is None:
            logger.warning("Insufficient data for performance calculation")
            return None

        # Handle partial data availability
        if trailing_12mo is None:
            logger.debug("No trailing 12mo data, using inception CAGR only")
            return since_inception

        if since_inception is None:
            logger.debug("No inception data, using trailing 12mo only")
            return trailing_12mo

        # Weighted combination
        weighted = (trailing_12mo * trailing_weight) + (
            since_inception * inception_weight
        )
        logger.debug(
            f"Weighted performance: {weighted:.4f} "
            f"(trailing: {trailing_12mo:.4f} × {trailing_weight}, "
            f"inception: {since_inception:.4f} × {inception_weight})"
        )
        return weighted

    async def calculate_trailing_12mo_return(self) -> Optional[float]:
        """Calculate trailing 12-month annualized return from portfolio snapshots.

        Uses portfolio value change over last 12 months, annualized.

        Returns:
            Annualized return as decimal (e.g., 0.12 = 12%), or None if insufficient data
        """
        # Get snapshot from 12 months ago
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")

        # Get snapshots in range
        snapshots = await self._portfolio_repo.get_range(start_date_str, end_date_str)

        if not snapshots or len(snapshots) < 2:
            logger.debug("Insufficient snapshots for trailing 12mo calculation")
            return None

        # Use first and last snapshot
        start_snapshot = snapshots[0]
        end_snapshot = snapshots[-1]

        start_value = start_snapshot.total_value
        end_value = end_snapshot.total_value

        if not start_value or start_value <= 0:
            logger.warning("Invalid start value for trailing 12mo calculation")
            return None

        # Calculate days between snapshots
        start_dt = datetime.strptime(start_snapshot.date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_snapshot.date, "%Y-%m-%d")
        days = (end_dt - start_dt).days

        if days < 30:
            logger.debug("Insufficient time period for trailing 12mo calculation")
            return None

        # Calculate annualized return
        # For periods close to 1 year, use simple return
        # For shorter periods, annualize: (end/start)^(365/days) - 1
        years = days / 365.0

        if years >= 0.25:
            # Use CAGR formula for periods >= 3 months
            annualized_return = ((end_value / start_value) ** (1 / years)) - 1
        else:
            # Simple return for very short periods
            annualized_return = (end_value / start_value) - 1

        logger.debug(
            f"Trailing 12mo return: {annualized_return:.4f} "
            f"(from {start_value:.2f} to {end_value:.2f} over {days} days)"
        )
        return annualized_return

    async def calculate_since_inception_cagr(self) -> Optional[float]:
        """Calculate since-inception CAGR from first to latest portfolio snapshot.

        Returns:
            CAGR as decimal (e.g., 0.11 = 11%), or None if insufficient data
        """
        # Get all snapshots (ordered by date ascending from get_range)
        # We'll get from very early date to now
        start_date_str = "2020-01-01"  # Far enough back to catch first snapshot
        end_date_str = datetime.now().strftime("%Y-%m-%d")

        snapshots = await self._portfolio_repo.get_range(start_date_str, end_date_str)

        if not snapshots or len(snapshots) < 2:
            logger.debug("Insufficient snapshots for inception CAGR calculation")
            return None

        # Use first and last snapshot
        first_snapshot = snapshots[0]
        latest_snapshot = snapshots[-1]

        first_value = first_snapshot.total_value
        latest_value = latest_snapshot.total_value

        if not first_value or first_value <= 0:
            logger.warning("Invalid first value for inception CAGR calculation")
            return None

        # Calculate years between snapshots
        first_dt = datetime.strptime(first_snapshot.date, "%Y-%m-%d")
        latest_dt = datetime.strptime(latest_snapshot.date, "%Y-%m-%d")
        days = (latest_dt - first_dt).days
        years = days / 365.0

        if years < 0.25:
            # Too short for meaningful CAGR
            logger.debug("Insufficient time period for inception CAGR calculation")
            return None

        # Calculate CAGR: (ending/beginning)^(1/years) - 1
        cagr = ((latest_value / first_value) ** (1 / years)) - 1

        logger.debug(
            f"Since-inception CAGR: {cagr:.4f} "
            f"(from {first_value:.2f} to {latest_value:.2f} over {years:.2f} years)"
        )
        return cagr

    async def get_performance_vs_target(self) -> Optional[float]:
        """Get performance difference vs target annual return.

        Returns:
            Difference from target (e.g., 0.03 = 3% above target), or None if no data
        """
        weighted_perf = await self.calculate_weighted_performance()
        if weighted_perf is None:
            return None

        target = await self._settings_repo.get_float("target_annual_return", 0.11)
        difference = weighted_perf - target

        logger.debug(
            f"Performance vs target: {difference:+.4f} "
            f"(weighted: {weighted_perf:.4f}, target: {target:.4f})"
        )
        return difference
