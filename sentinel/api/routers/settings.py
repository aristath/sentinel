"""Settings and LED API routes."""

from typing import Any

from fastapi import APIRouter, Depends
from typing_extensions import Annotated

from sentinel.api.dependencies import CommonDependencies, get_common_deps
from sentinel.led import LEDController

router = APIRouter(prefix="/settings", tags=["settings"])

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
