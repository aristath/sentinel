"""Async HTTP client for the Sentinel API."""

from __future__ import annotations

import httpx


class SentinelAPI:
    """Thin async wrapper around the Sentinel REST API."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url
        self._client = httpx.AsyncClient(base_url=base_url, timeout=10.0)

    async def close(self) -> None:
        await self._client.aclose()

    # -- endpoints -----------------------------------------------------------

    async def health(self) -> dict:
        resp = await self._client.get("/api/health")
        resp.raise_for_status()
        return resp.json()

    async def portfolio(self) -> dict:
        resp = await self._client.get("/api/portfolio")
        resp.raise_for_status()
        return resp.json()

    async def unified(self) -> list[dict]:
        resp = await self._client.get("/api/unified")
        resp.raise_for_status()
        return resp.json()
