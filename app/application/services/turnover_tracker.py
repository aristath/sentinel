"""Portfolio turnover tracking service.

Calculates annual portfolio turnover rate from trade history.
Turnover = (total_buy_value + total_sell_value) / 2 / average_portfolio_value
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from app.core.database.manager import get_db_manager

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
        # Use next day for end_date to include all trades on end_date
        end_date_next = (end_dt + timedelta(days=1)).strftime("%Y-%m-%d")

        # Get all trades in the 365-day window
        trades = await self._db_manager.ledger.fetchall(
            """
            SELECT side, quantity, price, currency, currency_rate, value_eur
            FROM trades
            WHERE executed_at >= ? AND executed_at < ?
            ORDER BY executed_at
            """,
            (start_date, end_date_next),
        )

        if not trades:
            logger.debug("No trades found for turnover calculation")
            return None

        # Calculate total buy and sell values in EUR
        total_buy_value = 0.0
        total_sell_value = 0.0

        for trade in trades:
            # Convert Row to dict if needed
            if hasattr(trade, "keys"):
                trade_dict = {key: trade[key] for key in trade.keys()}
            else:
                trade_dict = trade

            side = trade_dict["side"].upper()

            # Use value_eur if available (more accurate), otherwise calculate
            value_eur = trade_dict.get("value_eur")
            if value_eur and value_eur > 0:
                trade_value_eur = value_eur
            else:
                # Fallback: calculate from quantity * price * currency_rate
                quantity = trade_dict["quantity"]
                price = trade_dict["price"]
                currency_rate = trade_dict.get("currency_rate") or 1.0
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
        # Convert Row objects to dicts if needed
        snapshot_values = []
        for s in snapshots:
            if hasattr(s, "keys"):
                snapshot_dict = {key: s[key] for key in s.keys()}
            else:
                snapshot_dict = s
            snapshot_values.append(snapshot_dict["total_value"])

        total_value_sum = sum(snapshot_values)
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
