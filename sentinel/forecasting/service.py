"""Standalone model-agnostic forecasting service.

Run separately from Sentinel's trading process, for example:

    uvicorn sentinel.forecasting.service:app --host 127.0.0.1 --port 8010

The public API is deliberately model-neutral. Toto is one provider behind this
boundary, not the service identity.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Protocol, cast

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

QUANTILE_LEVELS = ["0.1", "0.2", "0.3", "0.4", "0.5", "0.6", "0.7", "0.8", "0.9"]
TOTO2_PATCH_SIZE = 32


class ForecastBatch(BaseModel):
    scope: str = Field(pattern="^(solo|grouped)$")
    symbols: list[str] = Field(min_length=1)
    values: list[list[float]] = Field(min_length=1)
    masks: list[list[bool]] = Field(min_length=1)


class ForecastRequest(BaseModel):
    provider: str = "toto2"
    model_id: str = "Datadog/Toto-2.0-1B"
    horizon_steps: int = Field(default=4, ge=1, le=256)
    batches: list[ForecastBatch] = Field(min_length=1)


class Provider(Protocol):
    provider: str
    model_id: str
    model_version: str

    def forecast(self, request: ForecastRequest) -> dict[str, Any]:
        """Return model-agnostic quantile forecasts."""
        ...


class NaiveProvider:
    """Deterministic fallback provider for local development and tests."""

    provider = "naive"
    model_version = "local"

    def __init__(self, model_id: str):
        self.model_id = model_id

    def forecast(self, request: ForecastRequest) -> dict[str, Any]:
        batches = []
        for batch in request.batches:
            forecasts: dict[str, list[dict[str, Any]]] = {}
            for symbol, values, masks in zip(batch.symbols, batch.values, batch.masks, strict=False):
                observed = [v for v, mask in zip(values, masks, strict=False) if mask]
                recent = observed[-13:] if observed else [0.0]
                drift = sum(recent) / len(recent)
                spread = max(0.01, min(0.08, _stdev(recent) * 2.0))
                rows = []
                for step in range(1, request.horizon_steps + 1):
                    rows.append(
                        {
                            "step": step,
                            "quantiles": {level: drift + ((float(level) - 0.5) * spread) for level in QUANTILE_LEVELS},
                        }
                    )
                forecasts[symbol] = rows
            batches.append({"scope": batch.scope, "forecasts": forecasts})
        return _response(self.provider, self.model_id, self.model_version, batches)


class Toto2Provider:
    """Toto 2.0 provider loaded lazily inside the forecasting process."""

    provider = "toto2"

    def __init__(self, model_id: str):
        import torch as torch_module  # pyright: ignore[reportMissingImports]
        from toto2 import Toto2Model  # pyright: ignore[reportMissingImports]

        torch = cast(Any, torch_module)
        self._torch = torch
        self.model_id = model_id
        self.model_version = model_id
        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._model = Toto2Model.from_pretrained(model_id).to(self._device).eval()

    def forecast(self, request: ForecastRequest) -> dict[str, Any]:
        torch = self._torch
        batches = []
        for batch in request.batches:
            if len(batch.symbols) != len(batch.values) or len(batch.symbols) != len(batch.masks):
                raise HTTPException(status_code=400, detail="Batch symbols, values, and masks must have equal length")
            values, masks = _prepare_toto2_batch(batch.values, batch.masks)

            target = torch.tensor([values], dtype=torch.float32, device=self._device)
            target_mask = torch.tensor([masks], dtype=torch.bool, device=self._device)
            series_ids = torch.tensor(
                _toto2_series_ids(len(batch.symbols)),
                dtype=torch.long,
                device=self._device,
            )
            has_missing = not bool(target_mask.all().item())

            with torch.inference_mode():
                quantiles = self._model.forecast(
                    {"target": target, "target_mask": target_mask, "series_ids": series_ids},
                    horizon=request.horizon_steps,
                    decode_block_size=768,
                    has_missing_values=has_missing,
                )
            quantiles = quantiles.detach().cpu().tolist()

            forecasts: dict[str, list[dict[str, Any]]] = {}
            for variate_idx, symbol in enumerate(batch.symbols):
                rows = []
                for step_idx in range(request.horizon_steps):
                    rows.append(
                        {
                            "step": step_idx + 1,
                            "quantiles": {
                                level: float(quantiles[q_idx][0][variate_idx][step_idx])
                                for q_idx, level in enumerate(QUANTILE_LEVELS)
                            },
                        }
                    )
                forecasts[symbol] = rows
            batches.append({"scope": batch.scope, "forecasts": forecasts})
        return _response(self.provider, self.model_id, self.model_version, batches)


def _stdev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return (sum((v - mean) ** 2 for v in values) / len(values)) ** 0.5


def _prepare_toto2_batch(
    values: list[list[float]],
    masks: list[list[bool]],
) -> tuple[list[list[float]], list[list[bool]]]:
    """Return a rectangular Toto-compatible context window.

    Toto 2.0 patches the time axis in chunks of 32. Sentinel's natural default
    context is 520 weekly returns, so keep the newest observations and discard
    only the oldest excess values when the context is not patch-aligned.
    """

    lengths = {len(row) for row in values}
    lengths.update(len(row) for row in masks)
    if len(lengths) != 1:
        raise HTTPException(status_code=400, detail="All batch value and mask rows must have equal length")

    input_length = lengths.pop()
    if input_length < TOTO2_PATCH_SIZE:
        raise HTTPException(status_code=400, detail=f"Toto 2.0 requires at least {TOTO2_PATCH_SIZE} context steps")

    trim = input_length % TOTO2_PATCH_SIZE
    if trim == 0:
        return values, masks
    trimmed_length = input_length - trim
    if trimmed_length < TOTO2_PATCH_SIZE:
        raise HTTPException(status_code=400, detail=f"Toto 2.0 requires at least {TOTO2_PATCH_SIZE} context steps")
    return [row[trim:] for row in values], [row[trim:] for row in masks]


def _toto2_series_ids(n_symbols: int) -> list[list[int]]:
    """Return Toto series IDs for one multivariate batch.

    Equal IDs allow variate-axis attention inside the batch. Distinct IDs tell
    Toto to mask variates from one another, which makes grouped forecasts behave
    like independent solo forecasts.
    """

    return [[0] * max(0, int(n_symbols))]


def _response(provider: str, model_id: str, model_version: str, batches: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "provider": provider,
        "model_id": model_id,
        "model_version": model_version,
        "quantiles": QUANTILE_LEVELS,
        "batches": batches,
    }


@lru_cache(maxsize=4)
def _provider(provider: str, model_id: str) -> Provider:
    if provider == "naive":
        return NaiveProvider(model_id)
    if provider == "toto2":
        return Toto2Provider(model_id)
    raise HTTPException(status_code=400, detail=f"Unsupported forecasting provider: {provider}")


app = FastAPI(title="Sentinel Forecasting Service")


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "default_provider": os.getenv("FORECASTING_PROVIDER", "toto2"),
        "default_model_id": os.getenv("FORECASTING_MODEL_ID", "Datadog/Toto-2.0-1B"),
    }


@app.post("/forecast")
async def forecast(request: ForecastRequest) -> dict[str, Any]:
    provider = _provider(request.provider, request.model_id)
    return provider.forecast(request)
