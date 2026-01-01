"""HTTP client for Scoring service."""

from typing import List, Optional

from app.infrastructure.http_clients.base import BaseHTTPClient


class ScoringHTTPClient(BaseHTTPClient):
    """HTTP client for Scoring service."""

    async def score_security(
        self,
        symbol: str,
        isin: Optional[str] = None,
    ) -> dict:
        """
        Score a single security.

        Args:
            symbol: Trading symbol
            isin: Optional ISIN

        Returns:
            Security score
        """
        response = await self.post(
            "/scoring/score",
            json={"symbol": symbol, "isin": isin},
        )
        return response.json()

    async def batch_score_securities(self, isins: List[str]) -> dict:
        """
        Score multiple securities.

        Args:
            isins: List of ISINs

        Returns:
            Batch scoring results
        """
        response = await self.post(
            "/scoring/score/batch",
            json={"isins": isins},
        )
        return response.json()

    async def score_portfolio(self, positions: List[dict]) -> dict:
        """
        Score entire portfolio.

        Args:
            positions: Portfolio positions

        Returns:
            Portfolio score
        """
        response = await self.post(
            "/scoring/score/portfolio",
            json={"positions": positions},
        )
        return response.json()

    async def get_score_history(self, isin: str) -> dict:
        """
        Get historical scores.

        Args:
            isin: Security ISIN

        Returns:
            Score history
        """
        response = await self.get(f"/scoring/history/{isin}")
        return response.json()

    async def health_check(self) -> dict:
        """
        Check service health.

        Returns:
            Health status
        """
        response = await self.get("/scoring/health")
        return response.json()
