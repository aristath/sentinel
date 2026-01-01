"""Local (in-process) gateway service implementation."""

from typing import AsyncIterator, Dict

from app.modules.gateway.services.gateway_service_interface import (
    SystemStatus,
    TradingCycleUpdate,
)


class LocalGatewayService:
    """
    Local gateway service implementation.

    Orchestrates workflows and provides API gateway functionality.
    """

    def __init__(self):
        """Initialize local gateway service."""
        pass

    async def get_system_status(self) -> SystemStatus:
        """
        Get system status.

        Returns:
            System status
        """
        # TODO: Implement system status collection
        return SystemStatus(
            status="healthy",
            uptime_seconds=0,
            service_health={},
        )

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
        # TODO: Implement trading cycle orchestration
        yield TradingCycleUpdate(
            step="Initializing",
            progress_pct=0,
            message="Trading cycle logic to be implemented",
            complete=False,
        )

        yield TradingCycleUpdate(
            step="Complete",
            progress_pct=100,
            message="Stub implementation",
            complete=True,
        )

    async def process_deposit(self, amount: float) -> Dict[str, float]:
        """
        Process a deposit.

        Args:
            amount: Deposit amount

        Returns:
            Dictionary with new cash balance
        """
        # TODO: Implement deposit processing
        return {"cash_balance": 0.0}
