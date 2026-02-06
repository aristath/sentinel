"""HTTP client for reading data from Sentinel monolith internal ML endpoints."""

from __future__ import annotations

import os
from typing import Any

import httpx

_MONOLITH_BASE_URL: str | None = None


def _normalize_url(url: str) -> str:
    return url.rstrip("/")


def get_monolith_base_url() -> str:
    if _MONOLITH_BASE_URL:
        return _MONOLITH_BASE_URL
    return _normalize_url(os.getenv("MONOLITH_BASE_URL", "http://localhost:8000"))


def set_monolith_base_url(url: str | None) -> None:
    global _MONOLITH_BASE_URL
    if url is None:
        _MONOLITH_BASE_URL = None
        return
    _MONOLITH_BASE_URL = _normalize_url(url)


class MonolithDataClient:
    def __init__(self, base_url: str | None = None, timeout: float = 30.0):
        self.base_url = _normalize_url(base_url) if base_url else None
        self.timeout = timeout

    def _resolved_base_url(self) -> str:
        return self.base_url or get_monolith_base_url()

    async def _get_json(self, path: str, params: dict[str, Any] | None = None):
        url = f"{self._resolved_base_url()}{path}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()

    async def get_securities(self, active_only: bool = True, ml_enabled_only: bool = False) -> list[dict]:
        return await self._get_json(
            "/api/internal/ml/securities", params={"active_only": active_only, "ml_enabled_only": ml_enabled_only}
        )

    async def get_ml_enabled_securities(self) -> list[dict]:
        return await self._get_json("/api/internal/ml/ml-enabled-securities")

    async def get_prices(
        self,
        symbol: str,
        days: int = 3650,
        end_date: str | None = None,
        start_date: str | None = None,
    ) -> list[dict]:
        params: dict[str, Any] = {"days": days}
        if end_date:
            params["end_date"] = end_date
        if start_date:
            params["start_date"] = start_date
        return await self._get_json(f"/api/internal/ml/prices/{symbol}", params=params)

    async def get_security(self, symbol: str) -> dict | None:
        try:
            return await self._get_json(f"/api/internal/ml/security/{symbol}")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            raise

    async def get_settings(self, keys: list[str]) -> dict:
        return await self._get_json("/api/internal/ml/settings", params={"keys": ",".join(keys)})

    async def get_quotes(self, symbols: list[str]) -> dict:
        if not symbols:
            return {}
        return await self._get_json("/api/internal/ml/quotes", params={"symbols": ",".join(symbols)})

    async def get_scores(self, symbols: list[str], as_of_ts: int | None = None) -> dict[str, float]:
        params: dict[str, Any] = {"symbols": ",".join(symbols)}
        if as_of_ts is not None:
            params["as_of_ts"] = as_of_ts
        return await self._get_json("/api/internal/ml/scores", params=params)

    async def get_scores_history(self, symbols: list[str], since_ts: int | None = None) -> dict[str, list[dict]]:
        params: dict[str, Any] = {"symbols": ",".join(symbols)}
        if since_ts is not None:
            params["since_ts"] = since_ts
        return await self._get_json("/api/internal/ml/scores-history", params=params)

    async def get_portfolio_snapshots(self, days: int = 365) -> list[dict]:
        return await self._get_json("/api/internal/ml/portfolio-snapshots", params={"days": days})

    async def get_portfolio_pnl_history(self) -> dict:
        return await self._get_json("/api/portfolio/pnl-history")

    async def delete_aggregates(self) -> int:
        url = f"{self._resolved_base_url()}/api/internal/ml/aggregates/delete"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url)
            response.raise_for_status()
            payload = response.json()
            return int(payload.get("deleted", 0))

    async def recompute_aggregates(self) -> dict:
        url = f"{self._resolved_base_url()}/api/internal/ml/aggregates/recompute"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url)
            response.raise_for_status()
            return response.json()
