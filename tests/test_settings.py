"""Tests for application settings management.

These tests verify the intended behavior of the Settings class:
1. Getting settings with defaults
2. Setting and persisting values
3. Default initialization
4. Type handling
"""

import os
import tempfile

import pytest
import pytest_asyncio

from sentinel.database import Database
from sentinel.settings import DEFAULTS, Settings


@pytest_asyncio.fixture
async def temp_settings():
    """Create settings backed by temporary database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    # Create database and connect
    db = Database(db_path)
    await db.connect()

    # Create settings instance using this database
    settings = Settings()
    settings._db = db

    yield settings

    # Cleanup
    await db.close()
    db.remove_from_cache()
    if os.path.exists(db_path):
        os.unlink(db_path)
    for ext in ["-wal", "-shm"]:
        wal_path = db_path + ext
        if os.path.exists(wal_path):
            os.unlink(wal_path)


class TestSettingsDefaults:
    """Tests for default settings."""

    def test_defaults_has_required_keys(self):
        """DEFAULTS contains all required configuration keys."""
        required_keys = [
            "trading_mode",
            "transaction_fee_fixed",
            "transaction_fee_percent",
            "max_position_pct",
            "min_position_pct",
            "min_cash_buffer",
            "simulated_cash_eur",
        ]
        for key in required_keys:
            assert key in DEFAULTS, f"Missing required default: {key}"

    def test_defaults_trading_mode_is_research(self):
        """Default trading mode should be 'research' for safety."""
        assert DEFAULTS["trading_mode"] == "research"

    def test_defaults_simulated_cash_is_none(self):
        """Simulated cash default should be None (disabled)."""
        assert DEFAULTS["simulated_cash_eur"] is None

    def test_defaults_transaction_fees_positive(self):
        """Transaction fees should be positive."""
        assert DEFAULTS["transaction_fee_fixed"] > 0
        assert DEFAULTS["transaction_fee_percent"] > 0

    def test_defaults_position_limits_valid(self):
        """Position limits should be valid percentages."""
        assert 0 < DEFAULTS["min_position_pct"] < DEFAULTS["max_position_pct"]
        assert DEFAULTS["max_position_pct"] <= 100

    def test_defaults_strategy_settings_exist(self):
        """Strategy-related settings should have defaults."""
        strategy_keys = [
            "strategy_core_target_pct",
            "strategy_opportunity_target_pct",
            "strategy_opportunity_target_max_pct",
            "strategy_min_opp_score",
            "strategy_entry_t1_dd",
            "strategy_entry_t2_dd",
            "strategy_entry_t3_dd",
            "strategy_entry_memory_days",
            "strategy_memory_max_boost",
            "strategy_opportunity_addon_threshold",
            "strategy_max_opportunity_buys_per_cycle",
            "strategy_max_new_opportunity_buys_per_cycle",
            "strategy_lot_standard_max_pct",
            "strategy_lot_coarse_max_pct",
            "strategy_coarse_max_new_lots_per_cycle",
            "strategy_core_floor_pct",
            "strategy_core_new_min_score",
            "strategy_core_new_min_dip_score",
            "strategy_max_funding_sells_per_cycle",
            "strategy_max_funding_turnover_pct",
            "strategy_funding_conviction_bias",
        ]
        for key in strategy_keys:
            assert key in DEFAULTS, f"Missing strategy default: {key}"

    def test_defaults_strategy_targets_sum_to_hundred(self):
        """Core + opportunity sleeves should target full investment."""
        total = DEFAULTS["strategy_core_target_pct"] + DEFAULTS["strategy_opportunity_target_pct"]
        assert abs(total - 100.0) < 0.01


class TestSettingsGet:
    """Tests for getting settings."""

    @pytest.mark.asyncio
    async def test_get_returns_default_when_not_set(self, temp_settings):
        """Getting unset setting returns default from DEFAULTS."""
        # Don't set the value, just get with default
        result = await temp_settings.get("trading_mode")
        assert result == DEFAULTS["trading_mode"]

    @pytest.mark.asyncio
    async def test_get_with_explicit_default(self, temp_settings):
        """Getting unset setting with explicit default uses that default."""
        result = await temp_settings.get("nonexistent_key", "my_default")
        assert result == "my_default"

    @pytest.mark.asyncio
    async def test_get_returns_stored_value(self, temp_settings):
        """Getting set setting returns stored value."""
        await temp_settings.set("custom_key", "custom_value")
        result = await temp_settings.get("custom_key")
        assert result == "custom_value"

    @pytest.mark.asyncio
    async def test_get_stored_overrides_default(self, temp_settings):
        """Stored value overrides DEFAULTS."""
        await temp_settings.set("trading_mode", "live")
        result = await temp_settings.get("trading_mode")
        assert result == "live"


class TestSettingsSet:
    """Tests for setting values."""

    @pytest.mark.asyncio
    async def test_set_string(self, temp_settings):
        """Set and retrieve string value."""
        await temp_settings.set("test_string", "hello")
        result = await temp_settings.get("test_string")
        assert result == "hello"

    @pytest.mark.asyncio
    async def test_set_integer(self, temp_settings):
        """Set and retrieve integer value."""
        await temp_settings.set("test_int", 42)
        result = await temp_settings.get("test_int")
        assert result == 42

    @pytest.mark.asyncio
    async def test_set_float(self, temp_settings):
        """Set and retrieve float value."""
        await temp_settings.set("test_float", 3.14159)
        result = await temp_settings.get("test_float")
        assert abs(result - 3.14159) < 0.00001

    @pytest.mark.asyncio
    async def test_set_boolean(self, temp_settings):
        """Set and retrieve boolean values."""
        await temp_settings.set("test_true", True)
        await temp_settings.set("test_false", False)

        assert await temp_settings.get("test_true") is True
        assert await temp_settings.get("test_false") is False

    @pytest.mark.asyncio
    async def test_set_list(self, temp_settings):
        """Set and retrieve list value."""
        await temp_settings.set("test_list", [1, 2, 3, "four"])
        result = await temp_settings.get("test_list")
        assert result == [1, 2, 3, "four"]

    @pytest.mark.asyncio
    async def test_set_dict(self, temp_settings):
        """Set and retrieve dict value."""
        await temp_settings.set("test_dict", {"a": 1, "b": [2, 3]})
        result = await temp_settings.get("test_dict")
        assert result == {"a": 1, "b": [2, 3]}

    @pytest.mark.asyncio
    async def test_set_overwrites(self, temp_settings):
        """Setting existing key overwrites previous value."""
        await temp_settings.set("overwrite_key", "old")
        await temp_settings.set("overwrite_key", "new")
        result = await temp_settings.get("overwrite_key")
        assert result == "new"


class TestSettingsAll:
    """Tests for getting all settings."""

    @pytest.mark.asyncio
    async def test_all_includes_defaults(self, temp_settings):
        """all() returns defaults for unset keys."""
        result = await temp_settings.all()

        # Should include all DEFAULTS keys
        for key in DEFAULTS:
            assert key in result

    @pytest.mark.asyncio
    async def test_all_includes_stored_values(self, temp_settings):
        """all() includes stored values."""
        await temp_settings.set("custom_key", "custom_value")
        result = await temp_settings.all()

        assert result["custom_key"] == "custom_value"

    @pytest.mark.asyncio
    async def test_all_stored_overrides_defaults(self, temp_settings):
        """all() shows stored values over defaults."""
        await temp_settings.set("trading_mode", "live")
        result = await temp_settings.all()

        assert result["trading_mode"] == "live"


class TestSettingsInitDefaults:
    """Tests for initializing default settings."""

    @pytest.mark.asyncio
    async def test_init_defaults_creates_missing(self, temp_settings):
        """init_defaults() creates settings that don't exist."""
        # Nothing stored yet
        await temp_settings.init_defaults()

        # Now all defaults should be stored
        for key, expected in DEFAULTS.items():
            stored = await temp_settings._db.get_setting(key)
            assert stored == expected, f"Default not initialized for {key}"

    @pytest.mark.asyncio
    async def test_init_defaults_preserves_existing(self, temp_settings):
        """init_defaults() doesn't overwrite existing values."""
        # Set a custom value
        await temp_settings.set("trading_mode", "live")

        # Initialize defaults
        await temp_settings.init_defaults()

        # Custom value should be preserved
        result = await temp_settings.get("trading_mode")
        assert result == "live"


class TestSettingsValidation:
    """Tests for settings value validation (intended behavior)."""

    @pytest.mark.asyncio
    async def test_transaction_fee_fixed_stored_as_number(self, temp_settings):
        """Transaction fee fixed should be stored as number."""
        await temp_settings.set("transaction_fee_fixed", 2.5)
        result = await temp_settings.get("transaction_fee_fixed")
        assert isinstance(result, (int, float))
        assert result == 2.5

    @pytest.mark.asyncio
    async def test_position_pct_stored_correctly(self, temp_settings):
        """Position percentages should be stored correctly."""
        await temp_settings.set("max_position_pct", 25)
        result = await temp_settings.get("max_position_pct")
        assert result == 25

    @pytest.mark.asyncio
    async def test_boolean_settings(self, temp_settings):
        """Boolean settings should work correctly."""
        await temp_settings.set("led_display_enabled", True)
        assert await temp_settings.get("led_display_enabled") is True

        await temp_settings.set("led_display_enabled", False)
        assert await temp_settings.get("led_display_enabled") is False


class TestSettingsEdgeCases:
    """Edge case tests."""

    @pytest.mark.asyncio
    async def test_empty_string_value(self, temp_settings):
        """Empty string is a valid value (not None)."""
        await temp_settings.set("empty_key", "")
        result = await temp_settings.get("empty_key", "default")
        assert result == ""

    @pytest.mark.asyncio
    async def test_zero_value(self, temp_settings):
        """Zero is a valid value (not None)."""
        await temp_settings.set("zero_key", 0)
        result = await temp_settings.get("zero_key", 42)
        assert result == 0

    @pytest.mark.asyncio
    async def test_none_default_falls_back_to_DEFAULTS(self, temp_settings):
        """get() with default=None falls back to DEFAULTS."""
        # Don't set trading_mode
        result = await temp_settings.get("trading_mode", None)
        # Should return DEFAULTS value, not None
        assert result == DEFAULTS["trading_mode"]

    @pytest.mark.asyncio
    async def test_key_not_in_defaults_returns_explicit_default(self, temp_settings):
        """Key not in DEFAULTS returns explicit default."""
        result = await temp_settings.get("completely_unknown", "explicit_default")
        assert result == "explicit_default"

    @pytest.mark.asyncio
    async def test_key_not_in_defaults_no_explicit_default_returns_none(self, temp_settings):
        """Key not in DEFAULTS with no explicit default returns None."""
        result = await temp_settings.get("completely_unknown")
        assert result is None
