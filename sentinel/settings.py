"""
Settings - Single source of truth for application configuration.

Usage:
    settings = Settings()
    fee = await settings.get('transaction_fee_fixed', default=2.0)
    await settings.set('transaction_fee_fixed', 2.5)
    all_settings = await settings.all()

All settings are stored in the database and editable via the web UI.
No hardcoded magic numbers.
"""

from typing import Any

from sentinel.database import Database
from sentinel.utils.decorators import singleton

# Default settings - applied on first run, then configurable via UI
DEFAULTS = {
    # Trading mode: 'research' or 'live'
    # In research mode, no actual trades are executed
    "trading_mode": "research",
    # Transaction costs
    "transaction_fee_fixed": 2.0,  # Fixed fee per trade (EUR)
    "transaction_fee_percent": 0.2,  # Percentage fee (0.2%)
    # Position limits (for planner)
    "max_position_pct": 25,  # Hard cap per security
    "min_position_pct": 2,  # Min 2% position size
    "min_trade_value": 400.0,  # Minimum trade value (EUR)
    # Cash management
    "min_cash_buffer": 0.005,  # Keep 0.5% cash minimum
    "target_cash_pct": 0,  # Fully invested strategy
    "simulated_cash_eur": None,  # Override cash in research mode (None = use real)
    # Rebalancing
    "rebalance_threshold_pct": 5,  # Rebalance when 5% off target
    # Performance chart benchmark: trailing-1Y return overlaid on the portfolio's
    # rolling TWR line. VWCE.EU (FTSE All-World ETF) = the "plain index" yardstick.
    "performance_benchmark_symbol": "VWCE.EU",
    # Dividend reinvestment
    "max_dividend_reinvestment_boost": 0.15,  # Max score boost for uninvested dividends
    # API
    "tradernet_api_key": "",
    "tradernet_api_secret": "",
    # Freedom24 web-session login (needed for PRAAMS portfolio-structure data
    # which is only served on the authenticated web UI, not the public API).
    "freedom24_login": "",
    "freedom24_password": "",
    # Contrarian strategy
    "strategy_min_opp_score": 0.55,
    "strategy_ideal_qualifying_threshold": 0.65,
    "strategy_entry_t1_dd": -0.10,
    "strategy_entry_t2_dd": -0.16,
    "strategy_entry_t3_dd": -0.22,
    "strategy_entry_memory_days": 45,
    "strategy_memory_max_boost": 0.12,
    "strategy_opportunity_addon_threshold": 0.75,
    "strategy_max_opportunity_buys_per_cycle": 1,
    "strategy_max_new_opportunity_buys_per_cycle": 1,
    "strategy_lot_standard_max_pct": 0.08,
    "strategy_lot_coarse_max_pct": 0.30,
    "strategy_coarse_max_new_lots_per_cycle": 1,
    "cooldown_enabled": True,
    "strategy_opportunity_cooloff_days": 7,
    "strategy_core_cooloff_days": 21,
    "strategy_same_side_cooloff_days": 15,
    "strategy_rotation_time_stop_days": 90,
    "strategy_core_timing_min_score": 0.30,
    "strategy_core_timing_min_dip_score": 0.20,
    # When every executable target is poorly timed, wait this long before one
    # convergence buy. The clock persists across restarts and resets after a buy.
    "strategy_fallback_wait_days": 30,
    "strategy_max_funding_sells_per_cycle": 2,
    "strategy_max_funding_turnover_pct": 0.12,
    "strategy_funding_conviction_bias": 1.0,
    # Model-agnostic time-series forecasting layer. The first provider is Toto
    # 2.0, but planner/database/API names stay provider-neutral.
    "forecasting_enabled": True,
    "forecasting_service_url": "http://127.0.0.1:8010",
    "forecasting_provider": "toto2",
    "forecasting_model_id": "Datadog/Toto-2.0-1B",
    "forecasting_horizon_weeks": 4,
    "forecasting_context_weeks": 520,
    "forecasting_min_history_weeks": 104,
    "forecasting_max_group_variates": 32,
    "forecasting_stale_after_days": 21,
    "forecasting_max_missing_ratio": 0.25,
    "forecasting_score_max_age_days": 14,
    "forecasting_timing_weight": 0.15,
    # User-conviction target. The stored `user_multiplier` slider value defines
    # long-term relative weights and decays toward neutral (0.5) by
    # `user_multiplier_decay_factor` every
    # `user_multiplier_decay_interval_days` days via a scheduled job, so an
    # untouched rating gracefully fades out over ~52 weeks at defaults.
    "clara_preference_strength": 5.0,
    "user_multiplier_decay_factor": 0.90,
    "user_multiplier_decay_interval_days": 7,
    # LED Display (Arduino UNO Q orbital visualization)
    "led_display_enabled": False,  # Disabled by default for dev environments
    "led_brightness": 200,  # Global LED brightness 0-255
    # Cloudflare R2 Backup
    "r2_account_id": "",
    "r2_access_key": "",
    "r2_secret_key": "",
    "r2_bucket_name": "",
    "r2_backup_retention_days": 30,
}

REMOVED_SETTINGS = {
    "planner_forecast_months",
    "strategy_core_target_pct",
    "strategy_core_floor_pct",
    "strategy_core_new_min_dip_score",
    "strategy_core_new_min_score",
    "strategy_opportunity_target_max_pct",
    "strategy_opportunity_target_pct",
    "strategy_projection_months",
    "strategy_priority_contrarian_weight_pct",
    "strategy_reserve_margin_pct",
    "strategy_reserve_max_months",
    "strategy_reserve_great_opp_score",
    "strategy_reserve_great_conviction_pct",
    "strategy_rotation_threshold",
    "strategy_strategic_buy_threshold",
    "user_multiplier_blend_pct",
}


@singleton
class Settings:
    """Single source of truth for application settings."""

    _db: "Database"

    def __init__(self):
        self._db = Database()

    async def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        if key in REMOVED_SETTINGS:
            return default
        value = await self._db.get_setting(key)
        if value is None:
            return default if default is not None else DEFAULTS.get(key)
        return value

    async def set(self, key: str, value: Any) -> None:
        """Set a setting value."""
        await self._db.set_setting(key, value)

    async def all(self) -> dict:
        """Get all settings with defaults applied."""
        stored = await self._db.get_all_settings()
        for key in REMOVED_SETTINGS:
            stored.pop(key, None)
        result = DEFAULTS.copy()
        result.update(stored)
        return result

    async def init_defaults(self) -> None:
        """Initialize default settings if not already set."""
        for key in REMOVED_SETTINGS:
            await self._db.delete_setting(key)
        for key, value in DEFAULTS.items():
            existing = await self._db.get_setting(key)
            if existing is None:
                await self._db.set_setting(key, value)
