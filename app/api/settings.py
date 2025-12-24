"""Settings API endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.infrastructure.cache import cache
from app.repositories import SettingsRepository
from app.domain.scoring.cache import get_score_cache

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
    "recommendation_depth": 1.0,    # Number of steps in multi-step recommendations (1-5)
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
    # Buy Score Group Weights (relative - normalized at scoring time)
    "score_weight_long_term": 0.20,         # CAGR, Sortino, Sharpe
    "score_weight_fundamentals": 0.15,      # Financial strength, Consistency
    "score_weight_opportunity": 0.15,       # 52W high, P/E ratio
    "score_weight_dividends": 0.12,         # Yield, Dividend consistency
    "score_weight_short_term": 0.10,        # Recent momentum, Drawdown
    "score_weight_technicals": 0.10,        # RSI, Bollinger, EMA
    "score_weight_opinion": 0.10,           # Analyst recs, Price targets
    "score_weight_diversification": 0.08,   # Geography, Industry, Averaging
    # Sell Score Weights (relative - normalized at scoring time)
    "sell_weight_underperformance": 0.35,   # Return vs target
    "sell_weight_time_held": 0.18,          # Position age
    "sell_weight_portfolio_balance": 0.18,  # Overweight detection
    "sell_weight_instability": 0.14,        # Bubble/volatility
    "sell_weight_drawdown": 0.15,           # PyFolio drawdown
}


class SettingUpdate(BaseModel):
    value: float


async def get_setting(key: str, default: str = None) -> str | None:
    """Get a setting value from the database."""
    settings_repo = SettingsRepository()
    value = await settings_repo.get(key)
    return str(value) if value is not None else default


async def get_settings_batch(keys: list[str]) -> dict[str, str]:
    """Get multiple settings in a single database query (cached 3s)."""
    cache_key = "settings:all"
    cached = cache.get(cache_key)
    if cached is not None:
        # Return only requested keys from cached data
        return {k: v for k, v in cached.items() if k in keys}

    # Fetch all settings from DB
    settings_repo = SettingsRepository()
    all_settings = await settings_repo.get_all()

    # Cache for 3 seconds
    cache.set(cache_key, all_settings, ttl_seconds=3)

    return {k: v for k, v in all_settings.items() if k in keys}


async def set_setting(key: str, value: str) -> None:
    """Set a setting value in the database."""
    settings_repo = SettingsRepository()
    await settings_repo.set_float(key, float(value))
    # Invalidate settings cache
    cache.invalidate("settings:all")


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


async def get_buy_score_weights() -> dict[str, float]:
    """Get buy score group weights (8 groups, normalized at scoring time)."""
    weight_keys = [k for k in SETTING_DEFAULTS if k.startswith("score_weight_")]
    db_values = await get_settings_batch(weight_keys)
    result = {}
    for key in weight_keys:
        # Extract group name from key (e.g., "score_weight_long_term" -> "long_term")
        group = key.replace("score_weight_", "")
        if key in db_values:
            result[group] = float(db_values[key])
        else:
            result[group] = SETTING_DEFAULTS[key]
    return result


async def get_sell_score_weights() -> dict[str, float]:
    """Get sell score weights (5 groups, normalized at scoring time)."""
    weight_keys = [k for k in SETTING_DEFAULTS if k.startswith("sell_weight_")]
    db_values = await get_settings_batch(weight_keys)
    result = {}
    for key in weight_keys:
        # Extract group name from key (e.g., "sell_weight_underperformance" -> "underperformance")
        group = key.replace("sell_weight_", "")
        if key in db_values:
            result[group] = float(db_values[key])
        else:
            result[group] = SETTING_DEFAULTS[key]
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
    """Clear all cached data including score cache."""
    # Clear simple cache
    cache.clear()

    # Clear score cache
    score_cache = get_score_cache()
    if score_cache:
        await score_cache.invalidate_all()

    return {"status": "ok", "message": "All caches cleared (including score cache)"}


@router.get("/cache-stats")
async def get_cache_stats():
    """Get cache statistics."""
    score_cache = get_score_cache()
    score_stats = await score_cache.get_stats() if score_cache else {}

    return {
        "simple_cache": {
            "entries": len(cache._cache) if hasattr(cache, '_cache') else 0,
        },
        "score_cache": score_stats,
    }


@router.post("/reschedule-jobs")
async def reschedule_jobs():
    """Reschedule all jobs with current settings values."""
    from app.jobs.scheduler import reschedule_all_jobs

    await reschedule_all_jobs()
    return {"status": "ok", "message": "Jobs rescheduled"}
