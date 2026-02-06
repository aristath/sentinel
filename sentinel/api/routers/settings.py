"""Settings and LED API routes."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from typing_extensions import Annotated

from sentinel.api.dependencies import CommonDependencies, get_common_deps
from sentinel.led import LEDController

router = APIRouter(prefix="/settings", tags=["settings"])
WEIGHT_KEYS = {"ml_weight_wavelet", "ml_weight_xgboost", "ml_weight_ridge", "ml_weight_rf", "ml_weight_svr"}

# Global LED controller reference (set by app lifespan)
_led_controller: LEDController | None = None


def set_led_controller(controller: LEDController | None) -> None:
    """Set the global LED controller reference."""
    global _led_controller
    _led_controller = controller


@router.get("")
async def get_settings(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict[str, Any]:
    """Get all settings."""
    return await deps.settings.all()


@router.put("/{key}")
async def set_setting(
    key: str,
    value: dict,
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict[str, str]:
    """Set a setting value."""
    await deps.settings.set(key, value.get("value"))
    return {"status": "ok"}


@router.put("")
async def set_settings_batch(
    payload: dict,
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict[str, str]:
    """Set multiple settings atomically.

    For this endpoint, payload must contain all ML weight keys so validation can
    enforce domain/range constraints and prevent partial inconsistent updates.
    """
    values = payload.get("values")
    if not isinstance(values, dict):
        raise HTTPException(status_code=400, detail="Payload must include object field 'values'")

    keys = set(values.keys())
    if keys != WEIGHT_KEYS:
        raise HTTPException(status_code=400, detail=f"Batch update requires exactly these keys: {sorted(WEIGHT_KEYS)}")

    parsed_weights: dict[str, float] = {}
    for key in WEIGHT_KEYS:
        raw = values.get(key)
        if isinstance(raw, bool) or not isinstance(raw, int | float):
            raise HTTPException(status_code=400, detail=f"Setting '{key}' must be a number")
        value = float(raw)
        if value < 0.0 or value > 1.0:
            raise HTTPException(status_code=400, detail=f"Setting '{key}' must be in [0, 1]")
        parsed_weights[key] = value

    if sum(parsed_weights.values()) <= 0.0:
        raise HTTPException(status_code=400, detail="At least one weight must be greater than zero")

    await deps.db.set_settings_batch({key: parsed_weights[key] for key in sorted(WEIGHT_KEYS)})

    return {"status": "ok"}


# LED endpoints are under /api/led, not /api/settings
led_router = APIRouter(prefix="/led", tags=["led"])


@led_router.get("/status")
async def get_led_status() -> dict[str, Any]:
    """Get LED display status and settings."""
    from sentinel.settings import Settings

    settings = Settings()
    enabled = await settings.get("led_display_enabled", False)
    return {
        "enabled": enabled,
        "running": _led_controller.is_running if _led_controller else False,
        "trade_count": _led_controller.trade_count if _led_controller else 0,
    }


@led_router.put("/enabled")
async def set_led_enabled(data: dict) -> dict[str, bool]:
    """Enable or disable LED display."""
    from sentinel.settings import Settings

    settings = Settings()
    enabled = data.get("enabled", False)
    await settings.set("led_display_enabled", enabled)
    return {"enabled": enabled}


@led_router.post("/refresh")
async def refresh_led_display() -> dict[str, Any]:
    """Force an immediate LED display refresh."""
    if not _led_controller or not _led_controller.is_running:
        return {"status": "not_running"}
    await _led_controller.force_refresh()
    return {"status": "refreshed", "trade_count": _led_controller.trade_count}
