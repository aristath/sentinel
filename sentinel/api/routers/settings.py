"""Settings and LED API routes."""

import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from typing_extensions import Annotated

from sentinel.api.dependencies import CommonDependencies, get_common_deps
from sentinel.broker import Broker
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
LED_BRIDGE_HEALTH_KEY = "led_bridge_health"
LED_BRIDGE_STALE_AFTER_SEC = 600


def set_led_controller(controller: LEDController | None) -> None:
    """Set the global LED controller reference."""
    global _led_controller
    _led_controller = controller


def _to_iso_utc(ts: int | None) -> str | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _to_int(value: Any, default: int | None = None, minimum: int | None = None) -> int | None:
    if value is None:
        return default
    if isinstance(value, bool):
        return default
    if isinstance(value, int | float):
        parsed = int(value)
    elif isinstance(value, str):
        try:
            parsed = int(value.strip())
        except ValueError:
            return default
    else:
        return default
    if minimum is not None and parsed < minimum:
        return minimum
    return parsed


def _normalize_led_bridge_health(raw: Any) -> dict[str, Any]:
    now_ts = int(time.time())
    data = raw if isinstance(raw, dict) else {}

    last_attempt_ts = _to_int(data.get("last_attempt_ts"))
    last_success_ts = _to_int(data.get("last_success_ts"))
    last_error_ts = _to_int(data.get("last_error_ts"))
    updated_at_ts = _to_int(data.get("updated_at_ts"))
    consecutive_failures = _to_int(data.get("consecutive_failures"), default=0, minimum=0) or 0
    bridge_ok = bool(data.get("bridge_ok", False))
    last_error = data.get("last_error")
    watchdog_action = data.get("watchdog_action")
    app_instance = data.get("app_instance")

    stale_seconds: int | None = None
    if last_success_ts is not None:
        stale_seconds = max(0, now_ts - last_success_ts)

    is_stale = stale_seconds is None or stale_seconds > LED_BRIDGE_STALE_AFTER_SEC

    return {
        "bridge_ok": bridge_ok,
        "consecutive_failures": consecutive_failures,
        "last_attempt_ts": last_attempt_ts,
        "last_attempt_at": _to_iso_utc(last_attempt_ts),
        "last_success_ts": last_success_ts,
        "last_success_at": _to_iso_utc(last_success_ts),
        "last_error_ts": last_error_ts,
        "last_error_at": _to_iso_utc(last_error_ts),
        "last_error": str(last_error) if last_error else None,
        "watchdog_action": str(watchdog_action) if watchdog_action else None,
        "app_instance": str(app_instance) if app_instance else None,
        "updated_at_ts": updated_at_ts,
        "updated_at": _to_iso_utc(updated_at_ts),
        "stale_seconds": stale_seconds,
        "stale_threshold_seconds": LED_BRIDGE_STALE_AFTER_SEC,
        "is_stale": is_stale,
    }


async def _get_led_bridge_health() -> dict[str, Any]:
    from sentinel.settings import Settings

    settings = Settings()
    raw = await settings.get(LED_BRIDGE_HEALTH_KEY, {})
    return _normalize_led_bridge_health(raw)


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
    broker = Broker()
    bridge_health = await _get_led_bridge_health()
    return {
        "enabled": enabled,
        "running": _led_controller.is_running if _led_controller else False,
        "trade_count": _led_controller.trade_count if _led_controller else 0,
        "broker_connected": broker.connected,
        "bridge": bridge_health,
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


@led_router.get("/bridge/health")
async def get_led_bridge_health() -> dict[str, Any]:
    """Get health telemetry for the UNO Q hm.u bridge."""
    return await _get_led_bridge_health()


@led_router.post("/bridge/health")
async def set_led_bridge_health(data: dict[str, Any]) -> dict[str, Any]:
    """Store health telemetry for the UNO Q hm.u bridge."""
    from sentinel.settings import Settings

    settings = Settings()
    normalized = _normalize_led_bridge_health(data)

    stored = {
        "bridge_ok": normalized["bridge_ok"],
        "consecutive_failures": normalized["consecutive_failures"],
        "last_attempt_ts": normalized["last_attempt_ts"],
        "last_success_ts": normalized["last_success_ts"],
        "last_error_ts": normalized["last_error_ts"],
        "last_error": normalized["last_error"],
        "watchdog_action": normalized["watchdog_action"],
        "app_instance": normalized["app_instance"],
        "updated_at_ts": int(time.time()),
    }

    await settings.set(LED_BRIDGE_HEALTH_KEY, stored)
    return _normalize_led_bridge_health(stored)
