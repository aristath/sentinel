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
    "max_position_pct": 20,  # Max 20% of portfolio in one position
    "min_position_pct": 2,  # Min 2% position size
    "min_trade_value": 100.0,  # Minimum trade value (EUR)
    # Cash management
    "min_cash_buffer": 0.005,  # Keep 0.5% cash minimum
    "target_cash_pct": 5,  # Target 5% cash
    "simulated_cash_eur": None,  # Override cash in research mode (None = use real)
    # Scoring
    "score_lookback_years": 10,  # Years of history for scoring
    # Rebalancing
    "rebalance_threshold_pct": 5,  # Rebalance when 5% off target
    # Diversification
    "diversification_impact_pct": 10,  # Max ±10% score adjustment for diversification
    # Dividend reinvestment
    "max_dividend_reinvestment_boost": 0.15,  # Max score boost for uninvested dividends
    # Trade cool-off
    "trade_cooloff_days": 30,  # Days to wait before opposite action after trade
    # API
    "tradernet_api_key": "",
    "tradernet_api_secret": "",
    # Advanced Analytics
    "use_regime_adjustment": False,
    # Regime Detection
    "regime_n_states": 3,
    "regime_lookback_days": 504,
    "regime_weight_adjustment": 0.2,  # ±20% weight adjustments
    # LED Display (Arduino UNO Q orbital visualization)
    "led_display_enabled": False,  # Disabled by default for dev environments
    "led_brightness": 200,  # Global LED brightness 0-255
    # Cloudflare R2 Backup
    "r2_account_id": "",
    "r2_access_key": "",
    "r2_secret_key": "",
    "r2_bucket_name": "",
    "r2_backup_retention_days": 30,
    # ML Per-Security Prediction (per-security settings in securities table)
    "ml_ensemble_nn_weight": 0.5,
    "ml_ensemble_xgb_weight": 0.5,
    "ml_prediction_horizon_days": 21,  # Predict 21 days ahead (~1 month)
    "ml_training_lookback_years": 8,
    "ml_validation_split": 0.2,
    "ml_min_samples_per_symbol": 100,  # Min samples to train a model for a symbol
}


@singleton
class Settings:
    """Single source of truth for application settings."""

    _db: "Database"

    def __init__(self):
        self._db = Database()

    async def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
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
        result = DEFAULTS.copy()
        result.update(stored)
        return result

    async def init_defaults(self) -> None:
        """Initialize default settings if not already set."""
        for key, value in DEFAULTS.items():
            existing = await self._db.get_setting(key)
            if existing is None:
                await self._db.set_setting(key, value)
