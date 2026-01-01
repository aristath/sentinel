"""HTTP client for Optimization service."""

from typing import List

from app.infrastructure.http_clients.base import BaseHTTPClient


class OptimizationHTTPClient(BaseHTTPClient):
    """HTTP client for Optimization service."""

    async def optimize_allocation(
        self,
        current_positions: List[dict],
        target_allocations: List[dict],
        available_cash: float,
    ) -> dict:
        """
        Optimize portfolio allocation.

        Args:
            current_positions: Current positions
            target_allocations: Target allocations
            available_cash: Available cash

        Returns:
            Allocation optimization result
        """
        response = await self.post(
            "/optimization/allocation",
            json={
                "current_positions": current_positions,
                "target_allocations": target_allocations,
                "available_cash": available_cash,
            },
        )
        return response.json()

    async def optimize_execution(self, trades: List[dict]) -> dict:
        """
        Optimize trade execution.

        Args:
            trades: List of trades to optimize

        Returns:
            Execution plans
        """
        response = await self.post(
            "/optimization/execution",
            json={"trades": trades},
        )
        return response.json()

    async def calculate_rebalancing(
        self,
        target_allocations: List[dict],
        available_cash: float,
    ) -> dict:
        """
        Calculate rebalancing needs.

        Args:
            target_allocations: Target allocations
            available_cash: Available cash

        Returns:
            Rebalancing recommendations
        """
        response = await self.post(
            "/optimization/rebalancing",
            json={
                "target_allocations": target_allocations,
                "available_cash": available_cash,
            },
        )
        return response.json()

    async def health_check(self) -> dict:
        """
        Check service health.

        Returns:
            Health status
        """
        response = await self.get("/optimization/health")
        return response.json()
