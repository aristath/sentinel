"""Settings API endpoints."""

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.infrastructure.cache import cache
from app.infrastructure.dependencies import (
    CalculationsRepositoryDep,
    DatabaseManagerDep,
    SettingsRepositoryDep,
)

router = APIRouter()


# Default values for all configurable settings
# NOTE: Score weights (score_weight_*, sell_weight_*) have been removed.
# The optimizer now handles portfolio-level allocation. Per-stock scoring
# uses fixed weights defined in app/domain/scoring/stock_scorer.py and sell.py.
SETTING_DEFAULTS = {
    # Core trading constraints
    "min_hold_days": 90,  # Minimum days before selling
    "sell_cooldown_days": 180,  # Days between sells of same stock
    "max_loss_threshold": -0.20,  # Don't sell if loss exceeds this (as decimal)
    "min_stock_score": 0.5,  # Minimum score for stock to be recommended (0-1)
    "target_annual_return": 0.11,  # Optimal CAGR for scoring (11%)
    "market_avg_pe": 22.0,  # Reference P/E for valuation
    # Trading mode
    "trading_mode": "research",  # "live" or "research" - blocks trades in research mode
    # Portfolio Optimizer settings
    "optimizer_blend": 0.5,  # 0.0 = pure Mean-Variance, 1.0 = pure HRP
    "optimizer_target_return": 0.11,  # Target annual return for MV component
    # Transaction costs (Freedom24) - replaces min_trade_size for smarter filtering
    "transaction_cost_fixed": 2.0,  # Fixed cost per trade in EUR
    "transaction_cost_percent": 0.002,  # Variable cost as fraction (0.2%)
    # Cash management
    "min_cash_reserve": 500.0,  # Minimum cash to keep (never fully deploy)
    # Holistic Planner settings
    "max_plan_depth": 5.0,  # Maximum depth for holistic planner sequences (1-10)
    "max_opportunities_per_category": 5.0,  # Max opportunities per category to consider (1-20)
    "enable_combinatorial_generation": 1.0,  # Enable combinatorial generation (1.0 = enabled, 0.0 = disabled)
    "priority_threshold_for_combinations": 0.3,  # Min priority for combinations (0.0-1.0)
    # Combinatorial generation settings
    "combinatorial_max_combinations_per_depth": 50.0,  # Max combinatorial sequences per depth (10-500)
    "combinatorial_max_sells": 4.0,  # Max sells in combinations (1-10)
    "combinatorial_max_buys": 4.0,  # Max buys in combinations (1-10)
    "combinatorial_max_candidates": 12.0,  # Max candidates considered for combinations (5-30)
    # Enhanced scenario exploration settings
    "beam_width": 10.0,  # Beam search width - number of top sequences to maintain (1-50)
    "enable_diverse_selection": 1.0,  # Enable diverse opportunity selection (1.0 = enabled, 0.0 = disabled)
    "diversity_weight": 0.3,  # Weight for diversity vs priority in selection (0.0-1.0)
    "cost_penalty_factor": 0.1,  # Transaction cost penalty factor for scoring (0.0-1.0)
    "enable_multi_objective": 0.0,  # Enable multi-objective optimization with Pareto frontier (1.0 = enabled, 0.0 = disabled)
    "enable_stochastic_scenarios": 0.0,  # Enable stochastic price scenarios for uncertainty evaluation (1.0 = enabled, 0.0 = disabled)
    "risk_profile": "balanced",  # Risk profile: "conservative", "balanced", or "aggressive"
    "enable_market_regime_scenarios": 0.0,  # Enable market regime-aware scenario generation (1.0 = enabled, 0.0 = disabled)
    "enable_correlation_aware": 0.0,  # Enable correlation-aware sequence filtering (1.0 = enabled, 0.0 = disabled)
    "enable_partial_execution": 0.0,  # Enable partial execution scenarios (first N actions only) (1.0 = enabled, 0.0 = disabled)
    "enable_constraint_relaxation": 0.0,  # Enable constraint relaxation scenarios (1.0 = enabled, 0.0 = disabled)
    "enable_monte_carlo_paths": 0.0,  # Enable Monte Carlo price path evaluation (1.0 = enabled, 0.0 = disabled)
    "monte_carlo_path_count": 100,  # Number of Monte Carlo paths to simulate (10-500)
    "enable_multi_timeframe": 0.0,  # Enable multi-timeframe optimization (short/medium/long-term) (1.0 = enabled, 0.0 = disabled)
    # Incremental Planner settings
    "incremental_planner_enabled": 1.0,  # Enable incremental planner mode (1.0 = enabled, 0.0 = disabled)
    # LED Matrix settings
    "ticker_speed": 50.0,  # Ticker scroll speed in ms per frame (lower = faster)
    "led_brightness": 150.0,  # LED brightness (0-255)
    # Ticker display options (1.0 = show, 0.0 = hide)
    "ticker_show_value": 1.0,  # Show portfolio value
    "ticker_show_cash": 1.0,  # Show cash balance
    "ticker_show_actions": 1.0,  # Show next actions (BUY/SELL)
    "ticker_show_amounts": 1.0,  # Show amounts for actions
    "ticker_max_actions": 3.0,  # Max recommendations to show (buy + sell)
    # Job scheduling intervals (simplified to 3 configurable settings)
    "job_sync_cycle_minutes": 15.0,  # Unified sync cycle interval (trades, prices, recommendations)
    "job_maintenance_hour": 3.0,  # Daily maintenance hour (0-23)
    "job_auto_deploy_minutes": 5.0,  # Auto-deploy check interval (minutes)
    # Universe Pruning settings
    "universe_pruning_enabled": 1.0,  # 1.0 = enabled, 0.0 = disabled
    "universe_pruning_score_threshold": 0.50,  # Minimum average score to keep stock (0-1)
    "universe_pruning_months": 3.0,  # Number of months to look back for scores
    "universe_pruning_min_samples": 2.0,  # Minimum number of score samples required
    "universe_pruning_check_delisted": 1.0,  # 1.0 = check for delisted stocks, 0.0 = skip
    # Event-Driven Rebalancing settings
    "event_driven_rebalancing_enabled": 1.0,  # 1.0 = enabled, 0.0 = disabled
    "rebalance_position_drift_threshold": 0.05,  # Position drift threshold (0.05 = 5%)
    "rebalance_cash_threshold_multiplier": 2.0,  # Cash threshold = multiplier × min_trade_size
    # Trade Frequency Limits settings
    "trade_frequency_limits_enabled": 1.0,  # 1.0 = enabled, 0.0 = disabled
    "min_time_between_trades_minutes": 60.0,  # Minimum minutes between any trades
    "max_trades_per_day": 4.0,  # Maximum trades per calendar day
    "max_trades_per_week": 10.0,  # Maximum trades per rolling 7-day window
    # Stock Discovery settings
    "stock_discovery_enabled": 1.0,  # 1.0 = enabled, 0.0 = disabled
    "stock_discovery_score_threshold": 0.75,  # Minimum score to add stock (0-1)
    "stock_discovery_max_per_month": 2.0,  # Maximum stocks to add per month
    "stock_discovery_require_manual_review": 0.0,  # 1.0 = require review, 0.0 = auto-add
    "stock_discovery_geographies": "EU,US,ASIA",  # Comma-separated geography list
    "stock_discovery_exchanges": "usa,europe",  # Comma-separated exchange list
    "stock_discovery_min_volume": 1000000.0,  # Minimum daily volume for liquidity
    "stock_discovery_fetch_limit": 50.0,  # Maximum candidates to fetch from API
    # Market Regime Detection settings
    "market_regime_detection_enabled": 1.0,  # 1.0 = enabled, 0.0 = disabled
    "market_regime_bull_cash_reserve": 0.02,  # Cash reserve percentage in bull market (2%)
    "market_regime_bear_cash_reserve": 0.05,  # Cash reserve percentage in bear market (5%)
    "market_regime_sideways_cash_reserve": 0.03,  # Cash reserve percentage in sideways market (3%)
    "market_regime_bull_threshold": 0.05,  # Threshold for bull market (5% above MA)
    "market_regime_bear_threshold": -0.05,  # Threshold for bear market (-5% below MA)
}


class SettingUpdate(BaseModel):
    value: float


async def get_setting(
    key: str, settings_repo: SettingsRepositoryDep, default: Optional[str] = None
) -> str | None:
    """Get a setting value from the database."""
    value = await settings_repo.get(key)
    return str(value) if value is not None else default


async def get_settings_batch(
    keys: list[str], settings_repo: SettingsRepositoryDep
) -> dict[str, str]:
    """Get multiple settings in a single database query (cached 3s)."""
    cache_key = "settings:all"
    cached = cache.get(cache_key)
    if cached is not None:
        # Return only requested keys from cached data
        return {k: v for k, v in cached.items() if k in keys}

    # Fetch all settings from DB
    all_settings = await settings_repo.get_all()

    # Cache for 3 seconds
    cache.set(cache_key, all_settings, ttl_seconds=3)

    return {k: v for k, v in all_settings.items() if k in keys}


async def set_setting(
    key: str, value: str, settings_repo: SettingsRepositoryDep
) -> None:
    """Set a setting value in the database."""
    await settings_repo.set_float(key, float(value))
    # Invalidate settings cache
    cache.invalidate("settings:all")


async def get_setting_value(key: str, settings_repo: SettingsRepositoryDep) -> float:
    """Get a setting value, falling back to default."""
    db_value = await get_setting(key, settings_repo)
    if db_value:
        return float(db_value)
    default_val = SETTING_DEFAULTS.get(key, 0)
    return float(default_val) if isinstance(default_val, (int, float)) else 0.0


async def get_trading_mode(settings_repo: SettingsRepositoryDep) -> str:
    """Get trading mode setting (returns "live" or "research")."""
    db_value = await get_setting("trading_mode", settings_repo)
    if db_value in ("live", "research"):
        return db_value
    return str(SETTING_DEFAULTS.get("trading_mode", "research"))


async def set_trading_mode(mode: str, settings_repo: SettingsRepositoryDep) -> None:
    """Set trading mode setting (must be "live" or "research")."""
    if mode not in ("live", "research"):
        raise ValueError(f"Invalid trading mode: {mode}. Must be 'live' or 'research'")
    await settings_repo.set("trading_mode", mode, "Trading mode: 'live' or 'research'")
    # Invalidate settings cache
    cache.invalidate("settings:all")


async def get_job_settings(settings_repo: SettingsRepositoryDep) -> dict[str, float]:
    """Get all job scheduling settings in one query."""
    job_keys = [k for k in SETTING_DEFAULTS if k.startswith("job_")]
    db_values = await get_settings_batch(job_keys, settings_repo)
    result = {}
    for key in job_keys:
        if key in db_values:
            val = db_values[key]
            result[key] = float(val) if isinstance(val, (int, float, str)) else 0.0
        else:
            default_val = SETTING_DEFAULTS[key]
            result[key] = (
                float(default_val) if isinstance(default_val, (int, float)) else 0.0
            )
    return result


@router.get("")
async def get_all_settings(settings_repo: SettingsRepositoryDep):
    """Get all configurable settings."""
    # Get all settings in a single query
    keys = list(SETTING_DEFAULTS.keys())
    db_values = await get_settings_batch(keys, settings_repo)

    # String settings that should be returned as strings
    string_settings = {
        "trading_mode",
        "stock_discovery_geographies",
        "stock_discovery_exchanges",
        "risk_profile",
    }

    result: dict[str, Any] = {}
    for key, default in SETTING_DEFAULTS.items():
        if key in db_values:
            if key in string_settings:
                result[key] = str(db_values[key])
            else:
                val = db_values[key]
                result[key] = float(val) if isinstance(val, (int, float, str)) else 0.0
        else:
            if key in string_settings:
                result[key] = str(default) if default is not None else ""
            else:
                default_val = default if isinstance(default, (int, float)) else 0.0
                result[key] = float(default_val)
    return result


@router.put("/{key}")
async def update_setting_value(
    key: str, data: SettingUpdate, settings_repo: SettingsRepositoryDep
):
    """Update a setting value."""
    if key not in SETTING_DEFAULTS:
        raise HTTPException(status_code=400, detail=f"Unknown setting: {key}")

    # Special handling for string settings
    if key == "trading_mode":
        mode = str(data.value).lower()
        if mode not in ("live", "research"):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid trading mode: {mode}. Must be 'live' or 'research'",
            )
        await set_trading_mode(mode, settings_repo)
        return {key: mode}
    elif key in ("stock_discovery_geographies", "stock_discovery_exchanges"):
        # Store as string for comma-separated lists
        await settings_repo.set(key, str(data.value))
        cache.invalidate("settings:all")
        return {key: str(data.value)}
    elif key in (
        "market_regime_bull_cash_reserve",
        "market_regime_bear_cash_reserve",
        "market_regime_sideways_cash_reserve",
    ):
        # Validate percentage range (1% to 40%)
        if data.value < 0.01 or data.value > 0.40:
            raise HTTPException(
                status_code=400,
                detail=f"{key} must be between 1% (0.01) and 40% (0.40)",
            )
        await set_setting(key, str(data.value), settings_repo)
        return {key: data.value}
    elif key == "max_plan_depth":
        # Validate range (1-10)
        if data.value < 1 or data.value > 10:
            raise HTTPException(
                status_code=400,
                detail=f"{key} must be between 1 and 10",
            )
        await set_setting(key, str(int(data.value)), settings_repo)
        return {key: int(data.value)}
    elif key == "max_opportunities_per_category":
        # Validate range (1-20)
        if data.value < 1 or data.value > 20:
            raise HTTPException(
                status_code=400,
                detail=f"{key} must be between 1 and 20",
            )
        await set_setting(key, str(int(data.value)), settings_repo)
        return {key: int(data.value)}
    elif key == "enable_combinatorial_generation":
        # Validate boolean-like (0.0 or 1.0)
        if data.value not in (0.0, 1.0):
            raise HTTPException(
                status_code=400,
                detail=f"{key} must be 0.0 (disabled) or 1.0 (enabled)",
            )
        await set_setting(key, str(data.value), settings_repo)
        return {key: data.value}
    elif key == "priority_threshold_for_combinations":
        # Validate range (0.0-1.0)
        if data.value < 0.0 or data.value > 1.0:
            raise HTTPException(
                status_code=400,
                detail=f"{key} must be between 0.0 and 1.0",
            )
        await set_setting(key, str(data.value), settings_repo)
        return {key: data.value}
    elif key == "combinatorial_max_combinations_per_depth":
        # Validate range (10-500)
        if data.value < 10 or data.value > 500:
            raise HTTPException(
                status_code=400,
                detail=f"{key} must be between 10 and 500",
            )
        await set_setting(key, str(int(data.value)), settings_repo)
        return {key: int(data.value)}
    elif key == "combinatorial_max_sells":
        # Validate range (1-10)
        if data.value < 1 or data.value > 10:
            raise HTTPException(
                status_code=400,
                detail=f"{key} must be between 1 and 10",
            )
        await set_setting(key, str(int(data.value)), settings_repo)
        return {key: int(data.value)}
    elif key == "combinatorial_max_buys":
        # Validate range (1-10)
        if data.value < 1 or data.value > 10:
            raise HTTPException(
                status_code=400,
                detail=f"{key} must be between 1 and 10",
            )
        await set_setting(key, str(int(data.value)), settings_repo)
        return {key: int(data.value)}
    elif key == "combinatorial_max_candidates":
        # Validate range (5-30)
        if data.value < 5 or data.value > 30:
            raise HTTPException(
                status_code=400,
                detail=f"{key} must be between 5 and 30",
            )
        await set_setting(key, str(int(data.value)), settings_repo)
        return {key: int(data.value)}
    elif key == "beam_width":
        # Validate range (1-50)
        if data.value < 1 or data.value > 50:
            raise HTTPException(
                status_code=400,
                detail=f"{key} must be between 1 and 50",
            )
        await set_setting(key, str(int(data.value)), settings_repo)
        return {key: int(data.value)}
    elif key == "enable_diverse_selection":
        # Validate boolean-like (0.0 or 1.0)
        if data.value not in (0.0, 1.0):
            raise HTTPException(
                status_code=400,
                detail=f"{key} must be 0.0 (disabled) or 1.0 (enabled)",
            )
        await set_setting(key, str(data.value), settings_repo)
        return {key: data.value}
    elif key == "diversity_weight":
        # Validate range (0.0-1.0)
        if data.value < 0.0 or data.value > 1.0:
            raise HTTPException(
                status_code=400,
                detail=f"{key} must be between 0.0 and 1.0",
            )
        await set_setting(key, str(data.value), settings_repo)
        return {key: data.value}
    elif key == "cost_penalty_factor":
        # Validate range (0.0-1.0)
        if data.value < 0.0 or data.value > 1.0:
            raise HTTPException(
                status_code=400,
                detail=f"{key} must be between 0.0 and 1.0",
            )
        await set_setting(key, str(data.value), settings_repo)
        return {key: data.value}
    elif key == "enable_multi_objective":
        # Validate boolean-like (0.0 or 1.0)
        if data.value not in (0.0, 1.0):
            raise HTTPException(
                status_code=400,
                detail=f"{key} must be 0.0 (disabled) or 1.0 (enabled)",
            )
        await set_setting(key, str(data.value), settings_repo)
        return {key: data.value}
    elif key == "enable_stochastic_scenarios":
        # Validate boolean-like (0.0 or 1.0)
        if data.value not in (0.0, 1.0):
            raise HTTPException(
                status_code=400,
                detail=f"{key} must be 0.0 (disabled) or 1.0 (enabled)",
            )
        await set_setting(key, str(data.value), settings_repo)
        return {key: data.value}
    elif key == "risk_profile":
        # Validate risk profile string
        profile = str(data.value).lower()
        if profile not in ("conservative", "balanced", "aggressive"):
            raise HTTPException(
                status_code=400,
                detail=f"{key} must be 'conservative', 'balanced', or 'aggressive'",
            )
        await settings_repo.set(key, profile)
        cache.invalidate("settings:all")
        return {key: profile}
    elif key == "enable_market_regime_scenarios":
        # Validate boolean-like (0.0 or 1.0)
        if data.value not in (0.0, 1.0):
            raise HTTPException(
                status_code=400,
                detail=f"{key} must be 0.0 (disabled) or 1.0 (enabled)",
            )
        await set_setting(key, str(data.value), settings_repo)
        return {key: data.value}
    elif key == "enable_correlation_aware":
        # Validate boolean-like (0.0 or 1.0)
        if data.value not in (0.0, 1.0):
            raise HTTPException(
                status_code=400,
                detail=f"{key} must be 0.0 (disabled) or 1.0 (enabled)",
            )
        await set_setting(key, str(data.value), settings_repo)
        return {key: data.value}
    elif key == "enable_partial_execution":
        # Validate boolean-like (0.0 or 1.0)
        if data.value not in (0.0, 1.0):
            raise HTTPException(
                status_code=400,
                detail=f"{key} must be 0.0 (disabled) or 1.0 (enabled)",
            )
        await set_setting(key, str(data.value), settings_repo)
        return {key: data.value}
    elif key == "enable_constraint_relaxation":
        # Validate boolean-like (0.0 or 1.0)
        if data.value not in (0.0, 1.0):
            raise HTTPException(
                status_code=400,
                detail=f"{key} must be 0.0 (disabled) or 1.0 (enabled)",
            )
        await set_setting(key, str(data.value), settings_repo)
        return {key: data.value}
    elif key == "enable_monte_carlo_paths":
        # Validate boolean-like (0.0 or 1.0)
        if data.value not in (0.0, 1.0):
            raise HTTPException(
                status_code=400,
                detail=f"{key} must be 0.0 (disabled) or 1.0 (enabled)",
            )
        await set_setting(key, str(data.value), settings_repo)
        return {key: data.value}
    elif key == "monte_carlo_path_count":
        # Validate integer (10-500)
        if not isinstance(data.value, (int, float)):
            raise HTTPException(status_code=400, detail=f"{key} must be a number")
        count = int(data.value)
        if count < 10 or count > 500:
            raise HTTPException(
                status_code=400,
                detail=f"{key} must be between 10 and 500",
            )
        await set_setting(key, str(count), settings_repo)
        return {key: count}
    elif key == "incremental_planner_enabled":
        # Validate boolean-like (0.0 or 1.0)
        if data.value not in (0.0, 1.0):
            raise HTTPException(
                status_code=400,
                detail=f"{key} must be 0.0 (disabled) or 1.0 (enabled)",
            )
        await set_setting(key, str(data.value), settings_repo)
        # Invalidate cache when toggling incremental mode
        from app.infrastructure.recommendation_cache import get_recommendation_cache

        rec_cache = get_recommendation_cache()
        await rec_cache.invalidate_all_recommendations()
        cache.invalidate_prefix("recommendations")
        return {key: data.value}

    await set_setting(key, str(data.value), settings_repo)

    # Invalidate recommendation caches when recommendation-affecting settings change
    # Note: optimizer settings (optimizer_blend, optimizer_target_return) also affect recommendations
    recommendation_settings = {
        "min_stock_score",
        "min_hold_days",
        "sell_cooldown_days",
        "max_loss_threshold",
        "target_annual_return",
        "optimizer_blend",
        "optimizer_target_return",
        "transaction_cost_fixed",
        "transaction_cost_percent",
        "min_cash_reserve",
        "max_plan_depth",
        "max_opportunities_per_category",
        "enable_combinatorial_generation",
        "priority_threshold_for_combinations",
        "combinatorial_max_combinations_per_depth",
        "combinatorial_max_sells",
        "combinatorial_max_buys",
        "combinatorial_max_candidates",
        "beam_width",
        "enable_diverse_selection",
        "diversity_weight",
        "cost_penalty_factor",
        "enable_multi_objective",
        "enable_stochastic_scenarios",
        "risk_profile",
        "enable_market_regime_scenarios",
        "enable_correlation_aware",
        "enable_partial_execution",
        "enable_constraint_relaxation",
        "enable_monte_carlo_paths",
        "monte_carlo_path_count",
        "enable_multi_timeframe",
        "incremental_planner_enabled",
    }
    if key in recommendation_settings:
        from app.infrastructure.recommendation_cache import get_recommendation_cache

        # Invalidate SQLite recommendation cache
        rec_cache = get_recommendation_cache()
        await rec_cache.invalidate_all_recommendations()

        # Invalidate in-memory caches
        cache.invalidate_prefix("recommendations")  # Unified recommendations cache

    return {key: data.value}


@router.post("/restart-service")
async def restart_service():
    """Restart the arduino-trader systemd service."""
    import subprocess

    try:
        result = subprocess.run(
            ["sudo", "systemctl", "restart", "arduino-trader"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return {"status": "ok", "message": "Service restart initiated"}
        else:
            return {
                "status": "error",
                "message": f"Failed to restart service: {result.stderr}",
            }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/restart")
async def restart_system():
    """Trigger system reboot."""
    import subprocess

    subprocess.Popen(["sudo", "reboot"])
    return {"status": "rebooting"}


@router.post("/reset-cache")
async def reset_cache():
    """Clear all cached data including score cache."""
    from app.infrastructure.recommendation_cache import get_recommendation_cache

    # Clear simple in-memory cache
    cache.clear()

    # Clear SQLite recommendation cache
    rec_cache = get_recommendation_cache()
    await rec_cache.invalidate_all_recommendations()

    # Metrics expire naturally via TTL, no manual invalidation needed

    return {"status": "ok", "message": "All caches cleared"}


@router.get("/cache-stats")
async def get_cache_stats(
    calc_repo: CalculationsRepositoryDep,
    db_manager: DatabaseManagerDep,
):
    """Get cache statistics."""
    db = db_manager.calculations

    # Get calculations.db stats
    row = await db.fetchone("SELECT COUNT(*) as cnt FROM calculated_metrics")
    calc_count = row["cnt"] if row else 0

    expired_count = await calc_repo.delete_expired()

    return {
        "simple_cache": {
            "entries": len(cache._cache) if hasattr(cache, "_cache") else 0,
        },
        "calculations_db": {
            "entries": calc_count,
            "expired_cleaned": expired_count,
        },
    }


@router.post("/reschedule-jobs")
async def reschedule_jobs():
    """Reschedule all jobs with current settings values."""
    from app.jobs.scheduler import reschedule_all_jobs

    await reschedule_all_jobs()
    return {"status": "ok", "message": "Jobs rescheduled"}


@router.get("/trading-mode")
async def get_trading_mode_endpoint(settings_repo: SettingsRepositoryDep):
    """Get current trading mode."""
    mode = await get_trading_mode(settings_repo)
    return {"trading_mode": mode}


@router.post("/trading-mode")
async def toggle_trading_mode(settings_repo: SettingsRepositoryDep):
    """Toggle trading mode between 'live' and 'research'."""
    current_mode = await get_trading_mode(settings_repo)
    new_mode = "research" if current_mode == "live" else "live"
    await set_trading_mode(new_mode, settings_repo)
    return {"trading_mode": new_mode, "previous_mode": current_mode}
