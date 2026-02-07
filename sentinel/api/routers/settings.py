"""Settings and LED API routes."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from typing_extensions import Annotated

from sentinel.api.dependencies import CommonDependencies, get_common_deps
from sentinel.led import LEDController

router = APIRouter(prefix="/settings", tags=["settings"])
STRATEGY_KEYS = {
    "strategy_core_target_pct",
    "strategy_opportunity_target_pct",
    "strategy_min_opp_score",
    "strategy_core_floor_pct",
}

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

    For this endpoint, payload must contain all strategy tuning keys so validation can
    enforce domain/range constraints and prevent partial inconsistent updates.
    """
    values = payload.get("values")
    if not isinstance(values, dict):
        raise HTTPException(status_code=400, detail="Payload must include object field 'values'")

    keys = set(values.keys())
    if keys != STRATEGY_KEYS:
        raise HTTPException(
            status_code=400,
            detail=f"Batch update requires exactly these keys: {sorted(STRATEGY_KEYS)}",
        )

    parsed_values: dict[str, float] = {}
    for key in STRATEGY_KEYS:
        raw = values.get(key)
        if isinstance(raw, bool) or not isinstance(raw, int | float):
            raise HTTPException(status_code=400, detail=f"Setting '{key}' must be a number")
        value = float(raw)
        parsed_values[key] = value

    if parsed_values["strategy_core_target_pct"] < 0 or parsed_values["strategy_core_target_pct"] > 100:
        raise HTTPException(status_code=400, detail="'strategy_core_target_pct' must be in [0, 100]")
    if parsed_values["strategy_opportunity_target_pct"] < 0 or parsed_values["strategy_opportunity_target_pct"] > 100:
        raise HTTPException(status_code=400, detail="'strategy_opportunity_target_pct' must be in [0, 100]")
    target_sum = parsed_values["strategy_core_target_pct"] + parsed_values["strategy_opportunity_target_pct"]
    if abs(target_sum - 100.0) > 1e-9:
        raise HTTPException(status_code=400, detail="Core and opportunity targets must sum to 100")
    if parsed_values["strategy_min_opp_score"] < 0 or parsed_values["strategy_min_opp_score"] > 1:
        raise HTTPException(status_code=400, detail="'strategy_min_opp_score' must be in [0, 1]")
    if parsed_values["strategy_core_floor_pct"] < 0 or parsed_values["strategy_core_floor_pct"] > 1:
        raise HTTPException(status_code=400, detail="'strategy_core_floor_pct' must be in [0, 1]")

    await deps.db.set_settings_batch({key: parsed_values[key] for key in sorted(STRATEGY_KEYS)})

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
