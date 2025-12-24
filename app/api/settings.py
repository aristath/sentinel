"""Settings API endpoints."""

import aiosqlite
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.infrastructure.cache import cache

router = APIRouter()


# Default values for all configurable settings
SETTING_DEFAULTS = {
    "min_trade_size": 400.0,        # Minimum EUR for a trade
    "min_hold_days": 90,            # Minimum days before selling
    "sell_cooldown_days": 180,      # Days between sells of same stock
    "max_loss_threshold": -0.20,    # Don't sell if loss exceeds this (as decimal)
    "min_sell_value": 100.0,        # Minimum EUR value to sell
    "target_annual_return": 0.11,   # Optimal CAGR for scoring (11%)
    "market_avg_pe": 22.0,          # Reference P/E for valuation
}


class SettingUpdate(BaseModel):
    value: float


async def get_setting(key: str, default: str = None) -> str | None:
    """Get a setting value from the database."""
    async with aiosqlite.connect(settings.database_path) as db:
        cursor = await db.execute(
            "SELECT value FROM settings WHERE key = ?",
            (key,)
        )
        row = await cursor.fetchone()
        return row[0] if row else default


async def set_setting(key: str, value: str) -> None:
    """Set a setting value in the database."""
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(
            """
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value)
        )
        await db.commit()


async def get_setting_value(key: str) -> float:
    """Get a setting value, falling back to default."""
    db_value = await get_setting(key)
    if db_value:
        return float(db_value)
    return SETTING_DEFAULTS.get(key, 0)


@router.get("")
async def get_all_settings():
    """Get all configurable settings."""
    result = {}
    for key, default in SETTING_DEFAULTS.items():
        db_value = await get_setting(key)
        result[key] = float(db_value) if db_value else default
    return result


@router.put("/{key}")
async def update_setting_value(key: str, data: SettingUpdate):
    """Update a setting value."""
    if key not in SETTING_DEFAULTS:
        raise HTTPException(status_code=400, detail=f"Unknown setting: {key}")

    await set_setting(key, str(data.value))
    return {key: data.value}


@router.post("/restart")
async def restart_system():
    """Trigger system reboot."""
    import subprocess
    subprocess.Popen(["sudo", "reboot"])
    return {"status": "rebooting"}


@router.post("/reset-cache")
async def reset_cache():
    """Clear all cached data."""
    cache.clear()
    return {"status": "ok", "message": "All caches cleared"}
