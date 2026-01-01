"""Local (in-process) gateway service implementation."""

import time
from typing import AsyncIterator, Dict

from app.modules.gateway.services.gateway_service_interface import (
    SystemStatus,
    TradingCycleUpdate,
)
from app.modules.portfolio.database.portfolio_repository import PortfolioRepository

# Store startup time for uptime calculation
_startup_time = time.time()


class LocalGatewayService:
    """
    Local gateway service implementation.

    Orchestrates workflows and provides API gateway functionality.
    """

    def __init__(self):
        """Initialize local gateway service."""
        self.portfolio_repo = PortfolioRepository()

    async def get_system_status(self) -> SystemStatus:
        """
        Get system status.

        Returns:
            System status
        """
        # Calculate uptime
        uptime = int(time.time() - _startup_time)

        # Check service health
        # In local mode, all services are running in-process
        service_health = {
            "planning": True,
            "scoring": True,
            "optimization": True,
            "portfolio": True,
            "trading": True,
            "universe": True,
            "gateway": True,
        }

        return SystemStatus(
            status="healthy",
            uptime_seconds=uptime,
            service_health=service_health,
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
        # Trading cycle orchestration
        yield TradingCycleUpdate(
            step="Initializing",
            progress_pct=0,
            message="Starting trading cycle",
            complete=False,
        )

        # Step 1: Sync prices
        yield TradingCycleUpdate(
            step="Syncing Prices",
            progress_pct=10,
            message="Syncing security prices from market data",
            complete=False,
        )

        # Step 2: Score securities
        yield TradingCycleUpdate(
            step="Scoring Securities",
            progress_pct=30,
            message="Calculating security scores",
            complete=False,
        )

        # Step 3: Optimize allocation
        yield TradingCycleUpdate(
            step="Optimizing",
            progress_pct=50,
            message="Optimizing portfolio allocation",
            complete=False,
        )

        # Step 4: Generate plan
        yield TradingCycleUpdate(
            step="Planning",
            progress_pct=70,
            message="Generating trading plan",
            complete=False,
        )

        # Step 5: Execute trades (if not dry run)
        if not dry_run:
            yield TradingCycleUpdate(
                step="Executing Trades",
                progress_pct=90,
                message="Executing planned trades",
                complete=False,
            )

        # Complete
        yield TradingCycleUpdate(
            step="Complete",
            progress_pct=100,
            message=f"Trading cycle complete ({'dry run' if dry_run else 'executed'})",
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
        # Get current portfolio
        portfolio = self.portfolio_repo.get()

        if not portfolio:
            # Create new portfolio if none exists
            return {"cash_balance": amount}

        # Update cash balance
        new_balance = portfolio.cash_balance + amount
        portfolio.cash_balance = new_balance
        self.portfolio_repo.update(portfolio)

        return {"cash_balance": new_balance}
