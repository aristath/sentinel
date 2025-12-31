"""Trade frequency limit service.

Enforces minimum time between trades and daily/weekly trade count limits
to prevent excessive trading in long-term retirement funds.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple

from app.domain.repositories.protocols import ISettingsRepository, ITradeRepository

logger = logging.getLogger(__name__)


class TradeFrequencyService:
    """Service to check and enforce trade frequency limits."""

    def __init__(
        self,
        trade_repo: ITradeRepository,
        settings_repo: ISettingsRepository,
    ):
        """Initialize trade frequency service.

        Args:
            trade_repo: Trade repository for querying trade history
            settings_repo: Settings repository for getting limit configuration
        """
        self._trade_repo = trade_repo
        self._settings_repo = settings_repo

    async def can_execute_trade(self) -> Tuple[bool, Optional[str]]:
        """
        Check if a trade can be executed based on frequency limits.

        Returns:
            Tuple of (allowed: bool, reason: Optional[str])
            If allowed is False, reason explains why
        """
        try:
            # Check if frequency limits are enabled
            enabled = await self._settings_repo.get_float(
                "trade_frequency_limits_enabled", 1.0
            )
            if enabled == 0.0:
                return True, None

            # Check minimum time between trades
            min_time_minutes = await self._settings_repo.get_float(
                "min_time_between_trades_minutes", 60.0
            )
            last_trade_time = await self._trade_repo.get_last_trade_timestamp()

            if last_trade_time:
                time_since_last = datetime.now() - last_trade_time
                minutes_since_last = time_since_last.total_seconds() / 60.0

                if minutes_since_last < min_time_minutes:
                    remaining_minutes = int(min_time_minutes - minutes_since_last)
                    return (
                        False,
                        f"Minimum {int(min_time_minutes)} minutes between trades. "
                        f"{remaining_minutes} minutes remaining.",
                    )

            # Check daily trade limit
            max_per_day = int(
                await self._settings_repo.get_float("max_trades_per_day", 4.0)
            )
            trades_today = await self._trade_repo.get_trade_count_today()

            if trades_today >= max_per_day:
                return (
                    False,
                    f"Daily trade limit reached ({trades_today}/{max_per_day} trades today)",
                )

            # Check weekly trade limit
            max_per_week = int(
                await self._settings_repo.get_float("max_trades_per_week", 10.0)
            )
            trades_this_week = await self._trade_repo.get_trade_count_this_week()

            if trades_this_week >= max_per_week:
                return (
                    False,
                    f"Weekly trade limit reached ({trades_this_week}/{max_per_week} trades this week)",
                )

            return True, None
        except Exception as e:
            logger.warning(f"Error checking trade frequency limits: {e}")
            # On error, be conservative and block the trade
            return False, f"Error checking trade frequency limits: {str(e)}"

    async def get_frequency_status(self) -> dict:
        """
        Get current trade frequency status.

        Returns:
            Dict with current counts, limits, and next allowed time
        """
        enabled = await self._settings_repo.get_float(
            "trade_frequency_limits_enabled", 1.0
        )
        min_time_minutes = await self._settings_repo.get_float(
            "min_time_between_trades_minutes", 60.0
        )
        max_per_day = int(
            await self._settings_repo.get_float("max_trades_per_day", 4.0)
        )
        max_per_week = int(
            await self._settings_repo.get_float("max_trades_per_week", 10.0)
        )

        last_trade_time = await self._trade_repo.get_last_trade_timestamp()
        trades_today = await self._trade_repo.get_trade_count_today()
        trades_this_week = await self._trade_repo.get_trade_count_this_week()

        # Calculate next allowed time
        next_allowed_time = None
        if last_trade_time:
            next_allowed = last_trade_time + timedelta(minutes=min_time_minutes)
            if next_allowed > datetime.now():
                next_allowed_time = next_allowed.isoformat()

        return {
            "enabled": enabled == 1.0,
            "min_time_between_trades_minutes": int(min_time_minutes),
            "max_trades_per_day": max_per_day,
            "max_trades_per_week": max_per_week,
            "trades_today": trades_today,
            "trades_this_week": trades_this_week,
            "last_trade_time": last_trade_time.isoformat() if last_trade_time else None,
            "next_allowed_time": next_allowed_time,
            "can_trade": (
                enabled == 0.0
                or (
                    (not last_trade_time or next_allowed_time is None)
                    and trades_today < max_per_day
                    and trades_this_week < max_per_week
                )
            ),
        }
