"""HTTP client for Gateway service."""

from typing import Optional

from app.infrastructure.http_clients.base import BaseHTTPClient


class GatewayHTTPClient(BaseHTTPClient):
    """HTTP client for Gateway service."""

    async def get_system_status(self) -> dict:
        """
        Get overall system status.

        Returns:
            System status with all services
        """
        response = await self.get("/gateway/status")
        return response.json()

    async def trigger_trading_cycle(
        self,
        force: bool = False,
        deposit_amount: Optional[float] = None,
    ) -> dict:
        """
        Trigger a trading cycle.

        Args:
            force: Force cycle even if conditions not met
            deposit_amount: Optional deposit amount

        Returns:
            Trading cycle result
        """
        response = await self.post(
            "/gateway/trading-cycle",
            json={
                "force": force,
                "deposit_amount": deposit_amount,
            },
        )
        return response.json()

    async def process_deposit(
        self,
        amount: float,
        account_id: str = "default",
    ) -> dict:
        """
        Process a deposit.

        Args:
            amount: Deposit amount
            account_id: Account identifier

        Returns:
            Deposit processing result
        """
        response = await self.post(
            "/gateway/deposit",
            json={
                "account_id": account_id,
                "amount": amount,
            },
        )
        return response.json()

    async def get_service_health(self, service_name: str) -> dict:
        """
        Get health of a specific service.

        Args:
            service_name: Name of the service

        Returns:
            Service health status
        """
        response = await self.get(f"/gateway/services/{service_name}/health")
        return response.json()

    async def health_check(self) -> dict:
        """
        Check service health.

        Returns:
            Health status
        """
        response = await self.get("/gateway/health")
        return response.json()
