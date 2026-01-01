"""HTTP client for Planning service."""

from typing import Dict, List, Optional

from app.infrastructure.http_clients.base import BaseHTTPClient


class PlanningHTTPClient(BaseHTTPClient):
    """HTTP client for Planning service."""

    async def create_plan(
        self,
        portfolio_hash: str,
        available_cash: float,
        positions: List[dict],
        constraints: Optional[Dict[str, str]] = None,
    ) -> dict:
        """
        Create a new plan.

        Args:
            portfolio_hash: Portfolio hash
            available_cash: Available cash
            positions: Current positions
            constraints: Planning constraints

        Returns:
            Created plan
        """
        response = await self.post(
            "/planning/create",
            json={
                "portfolio_hash": portfolio_hash,
                "available_cash": available_cash,
                "positions": positions,
                "constraints": constraints or {},
            },
        )
        return response.json()

    async def get_plan(self, plan_id: str) -> dict:
        """
        Get an existing plan.

        Args:
            plan_id: Plan identifier

        Returns:
            Plan details
        """
        response = await self.get(f"/planning/plans/{plan_id}")
        return response.json()

    async def list_plans(
        self,
        portfolio_hash: str,
        limit: int = 100,
        offset: int = 0,
    ) -> dict:
        """
        List plans for a portfolio.

        Args:
            portfolio_hash: Portfolio hash
            limit: Maximum results
            offset: Results offset

        Returns:
            List of plans
        """
        response = await self.get(
            "/planning/plans",
            params={
                "portfolio_hash": portfolio_hash,
                "limit": limit,
                "offset": offset,
            },
        )
        return response.json()

    async def get_best_result(self, portfolio_hash: str) -> dict:
        """
        Get best plan for portfolio.

        Args:
            portfolio_hash: Portfolio hash

        Returns:
            Best plan
        """
        response = await self.get(
            "/planning/best",
            params={"portfolio_hash": portfolio_hash},
        )
        return response.json()

    async def health_check(self) -> dict:
        """
        Check service health.

        Returns:
            Health status
        """
        response = await self.get("/planning/health")
        return response.json()
