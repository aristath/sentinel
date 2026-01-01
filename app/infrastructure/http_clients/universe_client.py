"""HTTP client for Universe service."""

from typing import List, Optional

from app.infrastructure.http_clients.base import BaseHTTPClient


class UniverseHTTPClient(BaseHTTPClient):
    """HTTP client for Universe service."""

    async def get_securities(self, tradable_only: bool = True) -> dict:
        """
        Get all securities.

        Args:
            tradable_only: Only return tradable securities

        Returns:
            Securities list with total count
        """
        response = await self.get(
            "/universe/securities",
            params={"tradable_only": tradable_only},
        )
        return response.json()

    async def get_security(self, isin: str) -> dict:
        """
        Get a specific security.

        Args:
            isin: Security ISIN

        Returns:
            Security details
        """
        response = await self.get(f"/universe/securities/{isin}")
        return response.json()

    async def search_securities(self, query: str, limit: int = 50) -> dict:
        """
        Search securities.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            Matching securities
        """
        response = await self.get(
            "/universe/search",
            params={"q": query, "limit": limit},
        )
        return response.json()

    async def sync_prices(self, isins: Optional[List[str]] = None) -> dict:
        """
        Sync security prices.

        Args:
            isins: List of ISINs to sync (None for all)

        Returns:
            Sync result
        """
        response = await self.post(
            "/universe/sync/prices",
            json={"isins": isins or []},
        )
        return response.json()

    async def add_security(
        self,
        isin: str,
        symbol: str,
        name: str,
        exchange: Optional[str] = None,
    ) -> dict:
        """
        Add a new security.

        Args:
            isin: Security ISIN
            symbol: Trading symbol
            name: Security name
            exchange: Exchange name

        Returns:
            Operation result
        """
        response = await self.post(
            "/universe/securities",
            json={
                "isin": isin,
                "symbol": symbol,
                "name": name,
                "exchange": exchange,
            },
        )
        return response.json()

    async def remove_security(self, isin: str) -> dict:
        """
        Remove a security.

        Args:
            isin: Security ISIN

        Returns:
            Operation result
        """
        response = await self.delete(f"/universe/securities/{isin}")
        return response.json()

    async def health_check(self) -> dict:
        """
        Check service health.

        Returns:
            Health status
        """
        response = await self.get("/universe/health")
        return response.json()
