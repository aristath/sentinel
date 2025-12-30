"""Portfolio turnover tracking service.

Calculates annual portfolio turnover rate from trade history.
Turnover = (total_buy_value + total_sell_value) / 2 / average_portfolio_value
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from app.infrastructure.database.manager import get_db_manager

logger = logging.getLogger(__name__)


class TurnoverTracker:
    """Track and calculate portfolio turnover rate."""

    def __init__(self, db_manager=None):
        """Initialize turnover tracker.

        Args:
            db_manager: Optional database manager (uses get_db_manager() if None)
        """
        self._db_manager = db_manager or get_db_manager()

    async def calculate_annual_turnover(
        self, end_date: Optional[str] = None
    ) -> Optional[float]:
        """
        Calculate annual portfolio turnover for the last 365 days.

        Turnover = (total_buy_value + total_sell_value) / 2 / average_portfolio_value

        Args:
            end_date: End date for calculation (YYYY-MM-DD). Defaults to today.

        Returns:
            Annual turnover rate as decimal (e.g., 0.50 = 50%), or None if insufficient data
        """
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")

        # Calculate start date (365 days ago)
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        start_dt = end_dt - timedelta(days=365)
        start_date = start_dt.strftime("%Y-%m-%d")

        # Get all trades in the 365-day window
        trades = await self._db_manager.ledger.fetchall(
            """
            SELECT side, quantity, price, currency, currency_rate
            FROM trades
            WHERE executed_at >= ? AND executed_at <= ?
            ORDER BY executed_at
            """,
            (start_date, end_date),
        )

        if not trades:
            logger.debug("No trades found for turnover calculation")
            return None

        # Calculate total buy and sell values in EUR
        total_buy_value = 0.0
        total_sell_value = 0.0

        for trade in trades:
            side = trade["side"].upper()
            quantity = trade["quantity"]
            price = trade["price"]
            currency_rate = trade.get("currency_rate") or 1.0

            # Calculate trade value in EUR
            trade_value_eur = quantity * price * currency_rate

            if side == "BUY":
                total_buy_value += trade_value_eur
            elif side == "SELL":
                total_sell_value += trade_value_eur

        # Calculate average portfolio value from snapshots
        snapshots = await self._db_manager.snapshots.fetchall(
            """
            SELECT total_value, date
            FROM portfolio_snapshots
            WHERE date >= ? AND date <= ?
            ORDER BY date
            """,
            (start_date, end_date),
        )

        if not snapshots:
            logger.debug("No portfolio snapshots found for turnover calculation")
            return None

        # Calculate average portfolio value
        total_value_sum = sum(s["total_value"] for s in snapshots)
        average_portfolio_value = total_value_sum / len(snapshots)

        if average_portfolio_value <= 0:
            logger.warning("Average portfolio value is zero or negative")
            return None

        # Calculate turnover: (buys + sells) / 2 / average_value
        turnover = (total_buy_value + total_sell_value) / 2.0 / average_portfolio_value

        logger.debug(
            f"Turnover calculation: buys={total_buy_value:.2f} EUR, "
            f"sells={total_sell_value:.2f} EUR, "
            f"avg_value={average_portfolio_value:.2f} EUR, "
            f"turnover={turnover*100:.2f}%"
        )

        return turnover

    async def get_turnover_status(self, turnover: Optional[float]) -> dict:
        """
        Get turnover status with alerts.

        Args:
            turnover: Annual turnover rate (0.0-1.0) or None

        Returns:
            Dict with turnover, status, and alert info
        """
        if turnover is None:
            return {
                "turnover": None,
                "turnover_display": "N/A",
                "status": "unknown",
                "alert": None,
                "reason": "Insufficient data to calculate turnover",
            }

        # Alert thresholds
        WARNING_THRESHOLD = 0.50  # 50% annual turnover
        CRITICAL_THRESHOLD = 1.00  # 100% annual turnover

        if turnover >= CRITICAL_THRESHOLD:
            status = "critical"
            alert = "critical"
            reason = f"Very high turnover: {turnover*100:.1f}% (exceeds {CRITICAL_THRESHOLD*100:.0f}% threshold)"
        elif turnover >= WARNING_THRESHOLD:
            status = "warning"
            alert = "warning"
            reason = f"High turnover: {turnover*100:.1f}% (exceeds {WARNING_THRESHOLD*100:.0f}% threshold)"
        else:
            status = "normal"
            alert = None
            reason = f"Normal turnover: {turnover*100:.1f}%"

        return {
            "turnover": turnover,
            "turnover_display": f"{turnover*100:.2f}%",
            "status": status,
            "alert": alert,
            "reason": reason,
        }
