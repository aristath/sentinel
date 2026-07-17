"""Forecast API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from typing_extensions import Annotated

from sentinel.api.dependencies import CommonDependencies, get_common_deps
from sentinel.forecasting.client import ForecastingClient

router = APIRouter(prefix="/forecasts", tags=["forecasts"])


@router.get("/status")
async def get_forecast_status(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict:
    """Return latest scheduled forecast status and service health."""

    latest = await deps.db.get_latest_forecast_run()
    counts = await deps.db.get_forecast_status_counts()
    service_url = await deps.settings.get("forecasting_service_url", "http://127.0.0.1:8010")
    service_health = None
    service_error = None
    if service_url:
        try:
            service_health = await ForecastingClient(base_url=service_url).health()
        except Exception as exc:  # noqa: BLE001 - endpoint should report, not fail, on service outages.
            service_error = str(exc)

    return {
        "enabled": bool(await deps.settings.get("forecasting_enabled", True)),
        "service_url": service_url,
        "provider": await deps.settings.get("forecasting_provider", "toto2"),
        "model_id": await deps.settings.get("forecasting_model_id", "Datadog/Toto-2.0-1B"),
        "latest_run": latest,
        "run_counts": counts,
        "service_health": service_health,
        "service_error": service_error,
    }


@router.get("/{symbol}")
async def get_symbol_forecast(
    symbol: str,
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict:
    """Return latest forecast path and evaluation summary for one symbol."""

    security = await deps.db.get_security(symbol)
    if not security:
        raise HTTPException(status_code=404, detail="Security not found")

    scores = await deps.db.get_latest_forecast_scores([symbol], scope="combined")
    scope_scores = {}
    for scope in ("solo", "grouped"):
        scope_scores[scope] = (await deps.db.get_latest_forecast_scores([symbol], scope=scope)).get(symbol)

    return {
        "symbol": symbol,
        "score": scores.get(symbol),
        "scope_scores": scope_scores,
        "points": await deps.db.get_latest_forecast_points(symbol),
        "evaluation": await deps.db.get_forecast_evaluation_summary(symbol),
    }
