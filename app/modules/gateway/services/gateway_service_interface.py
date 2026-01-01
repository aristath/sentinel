"""Gateway service interface."""

from dataclasses import dataclass
from typing import AsyncIterator, Dict, Optional, Protocol


@dataclass
class SystemStatus:
    """System status data class."""

    status: str  # "healthy", "degraded", "down"
    uptime_seconds: int
    service_health: Dict[str, bool]


@dataclass
class TradingCycleUpdate:
    """Trading cycle progress update."""

    step: str
    progress_pct: int
    message: str
    complete: bool
    error: Optional[str] = None


class GatewayServiceInterface(Protocol):
    """Gateway service interface."""

    async def get_system_status(self) -> SystemStatus:
        """
        Get system status.

        Returns:
            System status
        """
        ...

    async def trigger_trading_cycle(
        self, dry_run: bool = False
    ) -> AsyncIterator[TradingCycleUpdate]:
        """
        Trigger full trading cycle.

        Args:
            dry_run: Whether to run in dry-run mode

        Yields:
            Progress updates
        """
        ...

    async def process_deposit(self, amount: float) -> Dict[str, float]:
        """
        Process a deposit.

        Args:
            amount: Deposit amount

        Returns:
            Dictionary with new cash balance
        """
        ...
