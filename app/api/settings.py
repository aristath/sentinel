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
    # LED Matrix settings
    "ticker_speed": 50.0,           # Ticker scroll speed in ms per frame (lower = faster)
    "led_brightness": 150.0,        # LED brightness (0-255)
    # Ticker display options (1.0 = show, 0.0 = hide)
    "ticker_show_value": 1.0,       # Show portfolio value
    "ticker_show_cash": 1.0,        # Show cash balance
    "ticker_show_actions": 1.0,     # Show next actions (BUY/SELL)
    "ticker_show_amounts": 1.0,     # Show amounts for actions
    "ticker_max_actions": 3.0,      # Max recommendations to show (buy + sell)
    # Job scheduling intervals
    "job_portfolio_sync_minutes": 2.0,      # Portfolio sync interval
    "job_trade_sync_minutes": 4.0,          # Trade sync interval
    "job_price_sync_minutes": 7.0,          # Price sync interval
    "job_score_refresh_minutes": 10.0,      # Score refresh interval
    "job_rebalance_check_minutes": 15.0,    # Rebalance check interval
    "job_cash_flow_sync_hour": 1.0,         # Cash flow sync hour (0-23)
    "job_historical_sync_hour": 20.0,       # Historical sync hour (0-23)
    "job_maintenance_hour": 3.0,            # Daily maintenance hour (0-23)
}


class SettingUpdate(BaseModel):
    value: float


async def get_setting(key: str, default: str = None) -> str | None:
    """Get a setting value from the database."""
    from app.database import get_db_connection
    async with get_db_connection() as db:
        cursor = await db.execute(
            "SELECT value FROM settings WHERE key = ?",
            (key,)
        )
        row = await cursor.fetchone()
        return row[0] if row else default


async def get_settings_batch(keys: list[str]) -> dict[str, str]:
    """Get multiple settings in a single database query."""
    from app.database import get_db_connection
    async with get_db_connection() as db:
        placeholders = ",".join("?" * len(keys))
        cursor = await db.execute(
            f"SELECT key, value FROM settings WHERE key IN ({placeholders})",
            keys
        )
        rows = await cursor.fetchall()
        return {row[0]: row[1] for row in rows}


async def set_setting(key: str, value: str) -> None:
    """Set a setting value in the database."""
    from app.database import get_db_connection
    async with get_db_connection() as db:
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


async def get_job_settings() -> dict[str, float]:
    """Get all job scheduling settings in one query."""
    job_keys = [k for k in SETTING_DEFAULTS if k.startswith("job_")]
    db_values = await get_settings_batch(job_keys)
    result = {}
    for key in job_keys:
        if key in db_values:
            result[key] = float(db_values[key])
        else:
            result[key] = SETTING_DEFAULTS[key]
    return result


@router.get("")
async def get_all_settings():
    """Get all configurable settings."""
    # Get all settings in a single query
    keys = list(SETTING_DEFAULTS.keys())
    db_values = await get_settings_batch(keys)

    result = {}
    for key, default in SETTING_DEFAULTS.items():
        if key in db_values:
            result[key] = float(db_values[key])
        else:
            result[key] = default
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


@router.post("/reschedule-jobs")
async def reschedule_jobs():
    """Reschedule all jobs with current settings values."""
    from app.jobs.scheduler import reschedule_all_jobs

    await reschedule_all_jobs()
    return {"status": "ok", "message": "Jobs rescheduled"}
