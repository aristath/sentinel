"""HTTP client for the model-agnostic forecasting service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


class ForecastingClientError(RuntimeError):
    """Raised when the forecasting service request fails."""


@dataclass(frozen=True)
class ForecastingClient:
    """Small async client for the external forecasting process."""

    base_url: str
    timeout_seconds: float = 300.0

    async def health(self) -> dict[str, Any]:
        async with httpx.AsyncClient(base_url=self.base_url.rstrip("/"), timeout=15.0) as client:
            response = await client.get("/health")
            response.raise_for_status()
            return response.json()

    async def forecast(
        self,
        *,
        provider: str,
        model_id: str,
        horizon_steps: int,
        batches: list[dict[str, Any]],
    ) -> dict[str, Any]:
        payload = {
            "provider": provider,
            "model_id": model_id,
            "horizon_steps": horizon_steps,
            "batches": batches,
        }
        try:
            async with httpx.AsyncClient(base_url=self.base_url.rstrip("/"), timeout=self.timeout_seconds) as client:
                response = await client.post("/forecast", json=payload)
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException as exc:
            raise ForecastingClientError(f"Forecasting service timed out after {self.timeout_seconds:g}s") from exc
        except httpx.HTTPError as exc:
            message = str(exc) or exc.__class__.__name__
            raise ForecastingClientError(message) from exc
