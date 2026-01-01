"""HTTP client for Trading service."""

from typing import List, Optional

from app.infrastructure.http_clients.base import BaseHTTPClient


class TradingHTTPClient(BaseHTTPClient):
    """HTTP client for Trading service."""

    async def execute_trade(
        self,
        symbol: str,
        side: str,
        quantity: int,
        account_id: str = "default",
        isin: Optional[str] = None,
        limit_price: Optional[float] = None,
    ) -> dict:
        """
        Execute a single trade.

        Args:
            symbol: Trading symbol
            side: BUY or SELL
            quantity: Number of shares
            account_id: Account identifier
            isin: Optional ISIN
            limit_price: Optional limit price

        Returns:
            Trade execution result
        """
        response = await self.post(
            "/trading/execute",
            json={
                "account_id": account_id,
                "isin": isin,
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "limit_price": limit_price,
            },
        )
        return response.json()

    async def batch_execute_trades(self, trades: List[dict]) -> dict:
        """
        Execute multiple trades.

        Args:
            trades: List of trade requests

        Returns:
            Batch execution results
        """
        response = await self.post(
            "/trading/execute/batch",
            json={"trades": trades},
        )
        return response.json()

    async def get_trade_status(self, trade_id: str) -> dict:
        """
        Get trade status.

        Args:
            trade_id: Trade identifier

        Returns:
            Trade status
        """
        response = await self.get(f"/trading/status/{trade_id}")
        return response.json()

    async def get_trade_history(
        self,
        account_id: str = "default",
        limit: int = 100,
    ) -> dict:
        """
        Get trade history.

        Args:
            account_id: Account identifier
            limit: Maximum number of trades

        Returns:
            Trade history
        """
        response = await self.get(
            "/trading/history",
            params={"account_id": account_id, "limit": limit},
        )
        return response.json()

    async def cancel_trade(self, trade_id: str) -> dict:
        """
        Cancel a pending trade.

        Args:
            trade_id: Trade identifier

        Returns:
            Cancellation result
        """
        response = await self.post(f"/trading/cancel/{trade_id}")
        return response.json()

    async def validate_trade(
        self,
        symbol: str,
        side: str,
        quantity: int,
        account_id: str = "default",
        isin: Optional[str] = None,
        limit_price: Optional[float] = None,
    ) -> dict:
        """
        Validate a trade before execution.

        Args:
            symbol: Trading symbol
            side: BUY or SELL
            quantity: Number of shares
            account_id: Account identifier
            isin: Optional ISIN
            limit_price: Optional limit price

        Returns:
            Validation result
        """
        response = await self.post(
            "/trading/validate",
            json={
                "account_id": account_id,
                "isin": isin,
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "limit_price": limit_price,
            },
        )
        return response.json()

    async def health_check(self) -> dict:
        """
        Check service health.

        Returns:
            Health status
        """
        response = await self.get("/trading/health")
        return response.json()
