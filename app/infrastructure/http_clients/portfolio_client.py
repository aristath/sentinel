"""HTTP client for Portfolio service."""

from typing import Optional

from app.infrastructure.http_clients.base import BaseHTTPClient


class PortfolioHTTPClient(BaseHTTPClient):
    """HTTP client for Portfolio service."""

    async def get_positions(self, account_id: str = "default") -> dict:
        """
        Get all positions.

        Args:
            account_id: Account identifier

        Returns:
            Positions list with total count
        """
        response = await self.get(
            "/portfolio/positions",
            params={"account_id": account_id},
        )
        return response.json()

    async def get_position(
        self,
        symbol: str,
        account_id: str = "default",
        isin: Optional[str] = None,
    ) -> dict:
        """
        Get a specific position.

        Args:
            symbol: Trading symbol
            account_id: Account identifier
            isin: Optional ISIN filter

        Returns:
            Position details
        """
        params = {"account_id": account_id}
        if isin:
            params["isin"] = isin

        response = await self.get(f"/portfolio/positions/{symbol}", params=params)
        return response.json()

    async def get_summary(self, account_id: str = "default") -> dict:
        """
        Get portfolio summary.

        Args:
            account_id: Account identifier

        Returns:
            Portfolio summary
        """
        response = await self.get(
            "/portfolio/summary",
            params={"account_id": account_id},
        )
        return response.json()

    async def get_performance(
        self,
        account_id: str = "default",
        days: int = 30,
    ) -> dict:
        """
        Get portfolio performance.

        Args:
            account_id: Account identifier
            days: Number of days of history

        Returns:
            Performance data
        """
        response = await self.get(
            "/portfolio/performance",
            params={"account_id": account_id, "days": days},
        )
        return response.json()

    async def get_cash_balance(self, account_id: str = "default") -> dict:
        """
        Get cash balance.

        Args:
            account_id: Account identifier

        Returns:
            Cash balance details
        """
        response = await self.get(
            "/portfolio/cash",
            params={"account_id": account_id},
        )
        return response.json()

    async def sync_positions(self, account_id: str = "default") -> dict:
        """
        Sync positions from broker.

        Args:
            account_id: Account identifier

        Returns:
            Sync result
        """
        response = await self.post(
            "/portfolio/positions/sync",
            params={"account_id": account_id},
        )
        return response.json()

    async def health_check(self) -> dict:
        """
        Check service health.

        Returns:
            Health status
        """
        response = await self.get("/portfolio/health")
        return response.json()
