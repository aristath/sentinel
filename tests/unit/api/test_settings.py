"""Tests for settings API endpoints.

These tests validate the configuration management system, including
trading mode, optimizer settings, and cache management.
Critical for ensuring trading parameters are correctly applied.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.settings import (
    SETTING_DEFAULTS,
    get_job_settings,
    get_setting,
    get_setting_value,
    get_settings_batch,
    get_trading_mode,
    set_setting,
    set_trading_mode,
)


class TestSettingDefaults:
    """Test that default settings are properly defined."""

    def test_has_min_hold_days(self):
        """Test that min_hold_days is defined."""
        assert "min_hold_days" in SETTING_DEFAULTS
        assert SETTING_DEFAULTS["min_hold_days"] == 90

    def test_has_trading_mode(self):
        """Test that trading_mode default is 'research'."""
        assert SETTING_DEFAULTS["trading_mode"] == "research"

    def test_has_optimizer_settings(self):
        """Test that optimizer settings are defined."""
        assert "optimizer_blend" in SETTING_DEFAULTS
        assert "optimizer_target_return" in SETTING_DEFAULTS
        assert 0 <= SETTING_DEFAULTS["optimizer_blend"] <= 1

    def test_has_transaction_cost_settings(self):
        """Test that transaction cost settings are defined."""
        assert "transaction_cost_fixed" in SETTING_DEFAULTS
        assert "transaction_cost_percent" in SETTING_DEFAULTS
        assert SETTING_DEFAULTS["transaction_cost_percent"] < 0.01  # Less than 1%

    def test_has_min_cash_reserve(self):
        """Test that min_cash_reserve is defined."""
        assert "min_cash_reserve" in SETTING_DEFAULTS
        assert SETTING_DEFAULTS["min_cash_reserve"] > 0

    def test_has_job_scheduling_settings(self):
        """Test that job scheduling settings are defined."""
        job_settings = [k for k in SETTING_DEFAULTS if k.startswith("job_")]
        assert len(job_settings) >= 2  # Simplified to sync_cycle and maintenance_hour
        assert "job_sync_cycle_minutes" in SETTING_DEFAULTS
        assert "job_maintenance_hour" in SETTING_DEFAULTS


class TestGetSetting:
    """Test the get_setting function."""

    @pytest.mark.asyncio
    async def test_returns_stored_value(self):
        """Test that stored setting value is returned."""
        mock_repo = AsyncMock()
        mock_repo.get.return_value = "42.5"

        result = await get_setting("min_hold_days", mock_repo)

        assert result == "42.5"

    @pytest.mark.asyncio
    async def test_returns_none_when_not_set(self):
        """Test that None is returned when setting doesn't exist."""
        mock_repo = AsyncMock()
        mock_repo.get.return_value = None

        result = await get_setting("unknown_setting", mock_repo)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_default_when_not_set(self):
        """Test that default is returned when setting doesn't exist."""
        mock_repo = AsyncMock()
        mock_repo.get.return_value = None

        result = await get_setting("unknown_setting", mock_repo, default="default_val")

        assert result == "default_val"


class TestGetSettingsBatch:
    """Test the batch settings retrieval."""

    @pytest.mark.asyncio
    async def test_returns_requested_keys_from_cache(self):
        """Test that cached values are returned for requested keys."""
        mock_repo = AsyncMock()

        with patch("app.api.settings.cache") as mock_cache:
            mock_cache.get.return_value = {
                "key1": "value1",
                "key2": "value2",
                "key3": "value3",
            }

            result = await get_settings_batch(["key1", "key3"], mock_repo)

        assert result == {"key1": "value1", "key3": "value3"}

    @pytest.mark.asyncio
    async def test_fetches_from_db_when_not_cached(self):
        """Test that DB is queried when cache is empty."""
        mock_repo = AsyncMock()
        mock_repo.get_all.return_value = {"key1": "db_value1", "key2": "db_value2"}

        with patch("app.api.settings.cache") as mock_cache:
            mock_cache.get.return_value = None

            result = await get_settings_batch(["key1"], mock_repo)

        assert result == {"key1": "db_value1"}
        mock_repo.get_all.assert_called_once()


class TestSetSetting:
    """Test the set_setting function."""

    @pytest.mark.asyncio
    async def test_sets_value_in_repo(self):
        """Test that value is set in repository."""
        mock_repo = AsyncMock()

        with patch("app.api.settings.cache") as mock_cache:
            await set_setting("min_hold_days", "120", mock_repo)

        mock_repo.set_float.assert_called_once_with("min_hold_days", 120.0)
        mock_cache.invalidate.assert_called_once_with("settings:all")


class TestGetSettingValue:
    """Test the get_setting_value function."""

    @pytest.mark.asyncio
    async def test_returns_db_value_as_float(self):
        """Test that DB value is returned as float."""
        mock_repo = AsyncMock()
        mock_repo.get.return_value = "150.5"

        result = await get_setting_value("min_hold_days", mock_repo)

        assert result == 150.5

    @pytest.mark.asyncio
    async def test_returns_default_when_not_in_db(self):
        """Test that default is returned when not in DB."""
        mock_repo = AsyncMock()
        mock_repo.get.return_value = None

        result = await get_setting_value("min_hold_days", mock_repo)

        assert result == SETTING_DEFAULTS["min_hold_days"]

    @pytest.mark.asyncio
    async def test_returns_zero_for_unknown_setting(self):
        """Test that 0 is returned for unknown settings."""
        mock_repo = AsyncMock()
        mock_repo.get.return_value = None

        result = await get_setting_value("unknown_setting_xyz", mock_repo)

        assert result == 0


class TestTradingMode:
    """Test trading mode get/set functions."""

    @pytest.mark.asyncio
    async def test_get_trading_mode_returns_live(self):
        """Test getting 'live' trading mode."""
        mock_repo = AsyncMock()
        mock_repo.get.return_value = "live"

        with patch("app.api.settings.get_setting", return_value="live"):
            result = await get_trading_mode(mock_repo)

        assert result == "live"

    @pytest.mark.asyncio
    async def test_get_trading_mode_returns_research(self):
        """Test getting 'research' trading mode."""
        mock_repo = AsyncMock()

        with patch("app.api.settings.get_setting", return_value="research"):
            result = await get_trading_mode(mock_repo)

        assert result == "research"

    @pytest.mark.asyncio
    async def test_get_trading_mode_defaults_to_research(self):
        """Test that trading mode defaults to 'research' for safety."""
        mock_repo = AsyncMock()

        with patch("app.api.settings.get_setting", return_value=None):
            result = await get_trading_mode(mock_repo)

        # Should default to research for safety
        assert result == "research"

    @pytest.mark.asyncio
    async def test_get_trading_mode_rejects_invalid(self):
        """Test that invalid trading mode defaults to research."""
        mock_repo = AsyncMock()

        with patch("app.api.settings.get_setting", return_value="invalid"):
            result = await get_trading_mode(mock_repo)

        # Invalid values should default to research for safety
        assert result == "research"

    @pytest.mark.asyncio
    async def test_set_trading_mode_live(self):
        """Test setting trading mode to 'live'."""
        mock_repo = AsyncMock()

        with patch("app.api.settings.cache") as mock_cache:
            await set_trading_mode("live", mock_repo)

        mock_repo.set.assert_called_once()
        mock_cache.invalidate.assert_called_once_with("settings:all")

    @pytest.mark.asyncio
    async def test_set_trading_mode_rejects_invalid(self):
        """Test that invalid trading mode is rejected."""
        mock_repo = AsyncMock()

        with pytest.raises(ValueError) as exc_info:
            await set_trading_mode("invalid_mode", mock_repo)

        assert "Invalid trading mode" in str(exc_info.value)


class TestGetJobSettings:
    """Test job settings retrieval."""

    @pytest.mark.asyncio
    async def test_returns_all_job_settings(self):
        """Test that all job settings are returned."""
        mock_repo = AsyncMock()

        with patch(
            "app.api.settings.get_settings_batch", new_callable=AsyncMock
        ) as mock_batch:
            mock_batch.return_value = {
                "job_sync_cycle_minutes": "15.0",
                "job_maintenance_hour": "3.0",
            }

            result = await get_job_settings(mock_repo)

        # Should have all job settings (simplified to 2 settings)
        job_keys = [k for k in SETTING_DEFAULTS if k.startswith("job_")]
        assert all(k in result for k in job_keys)

    @pytest.mark.asyncio
    async def test_uses_defaults_when_not_set(self):
        """Test that defaults are used when not in DB."""
        mock_repo = AsyncMock()

        with patch(
            "app.api.settings.get_settings_batch", new_callable=AsyncMock
        ) as mock_batch:
            mock_batch.return_value = {}  # Nothing in DB

            result = await get_job_settings(mock_repo)

        # Should use defaults for sync cycle
        assert (
            result["job_sync_cycle_minutes"]
            == SETTING_DEFAULTS["job_sync_cycle_minutes"]
        )


class TestGetAllSettingsEndpoint:
    """Test the GET /settings endpoint."""

    @pytest.mark.asyncio
    async def test_returns_all_settings(self):
        """Test that all settings are returned."""
        from app.api.settings import get_all_settings

        mock_repo = AsyncMock()

        with patch(
            "app.api.settings.get_settings_batch", new_callable=AsyncMock
        ) as mock_batch:
            mock_batch.return_value = {"min_hold_days": "100"}

            result = await get_all_settings(mock_repo)

        assert "min_hold_days" in result
        assert result["min_hold_days"] == 100.0

    @pytest.mark.asyncio
    async def test_includes_trading_mode_as_string(self):
        """Test that trading_mode is returned as string, not float."""
        from app.api.settings import get_all_settings

        mock_repo = AsyncMock()

        with patch(
            "app.api.settings.get_settings_batch", new_callable=AsyncMock
        ) as mock_batch:
            mock_batch.return_value = {"trading_mode": "live"}

            result = await get_all_settings(mock_repo)

        assert result["trading_mode"] == "live"


class TestUpdateSettingEndpoint:
    """Test the PUT /settings/{key} endpoint."""

    @pytest.mark.asyncio
    async def test_updates_numeric_setting(self):
        """Test updating a numeric setting."""
        from app.api.settings import SettingUpdate, update_setting_value

        mock_repo = AsyncMock()
        mock_rec_cache = AsyncMock()

        with patch("app.api.settings.set_setting", new_callable=AsyncMock):
            with patch("app.api.settings.cache"):
                with patch(
                    "app.infrastructure.recommendation_cache.get_recommendation_cache",
                    return_value=mock_rec_cache,
                ):
                    result = await update_setting_value(
                        "min_hold_days", SettingUpdate(value=120), mock_repo
                    )

        assert result == {"min_hold_days": 120}

    @pytest.mark.asyncio
    async def test_rejects_unknown_setting(self):
        """Test that unknown settings are rejected."""
        from app.api.settings import SettingUpdate, update_setting_value

        mock_repo = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await update_setting_value(
                "unknown_setting", SettingUpdate(value=100), mock_repo
            )

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_invalidates_recommendation_cache_for_optimizer_settings(self):
        """Test that recommendation caches are invalidated for optimizer settings."""
        from app.api.settings import SettingUpdate, update_setting_value

        mock_repo = AsyncMock()
        mock_rec_cache = AsyncMock()
        mock_cache_service = MagicMock()
        mock_cache_service.return_value = mock_rec_cache

        with patch("app.api.settings.set_setting", new_callable=AsyncMock):
            with patch("app.api.settings.cache") as mock_cache:
                with patch(
                    "app.infrastructure.recommendation_cache.get_recommendation_cache",
                    return_value=mock_rec_cache,
                ):
                    await update_setting_value(
                        "optimizer_blend", SettingUpdate(value=0.7), mock_repo
                    )

        mock_cache.invalidate_prefix.assert_any_call("recommendations")


class TestRestartEndpoints:
    """Test the restart endpoints."""

    @pytest.mark.asyncio
    async def test_restart_service(self):
        """Test service restart endpoint."""
        from app.api.settings import restart_service

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")

            result = await restart_service()

        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_restart_service_handles_failure(self):
        """Test service restart error handling."""
        from app.api.settings import restart_service

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="Permission denied")

            result = await restart_service()

        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_restart_system(self):
        """Test system reboot endpoint."""
        from app.api.settings import restart_system

        with patch("subprocess.Popen") as mock_popen:
            result = await restart_system()

        assert result["status"] == "rebooting"
        mock_popen.assert_called_once()


class TestCacheManagement:
    """Test cache management endpoints."""

    @pytest.mark.asyncio
    async def test_reset_cache(self):
        """Test cache reset endpoint."""
        from app.api.settings import reset_cache

        with patch("app.api.settings.cache") as mock_cache:
            result = await reset_cache()

        assert result["status"] == "ok"
        mock_cache.clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_cache_stats(self):
        """Test cache stats endpoint."""
        from app.api.settings import get_cache_stats

        mock_calc_repo = AsyncMock()
        mock_calc_repo.delete_expired.return_value = 5

        mock_db_manager = MagicMock()
        mock_db = AsyncMock()
        mock_db_manager.calculations = mock_db
        mock_db.fetchone.return_value = {"cnt": 100}

        with patch("app.api.settings.cache") as mock_cache:
            mock_cache._cache = {"key1": "value1", "key2": "value2"}

            result = await get_cache_stats(mock_calc_repo, mock_db_manager)

        assert "simple_cache" in result
        assert "calculations_db" in result
        assert result["calculations_db"]["entries"] == 100
        assert result["calculations_db"]["expired_cleaned"] == 5


class TestRescheduleJobs:
    """Test job rescheduling endpoint."""

    @pytest.mark.asyncio
    async def test_reschedule_jobs(self):
        """Test job rescheduling endpoint."""
        from app.api.settings import reschedule_jobs

        with patch(
            "app.jobs.scheduler.reschedule_all_jobs", new_callable=AsyncMock
        ) as mock_reschedule:
            result = await reschedule_jobs()

        assert result["status"] == "ok"
        mock_reschedule.assert_called_once()


class TestTradingModeEndpoints:
    """Test trading mode endpoints."""

    @pytest.mark.asyncio
    async def test_get_trading_mode_endpoint(self):
        """Test GET /settings/trading-mode endpoint."""
        from app.api.settings import get_trading_mode_endpoint

        mock_repo = AsyncMock()

        with patch(
            "app.api.settings.get_trading_mode",
            new_callable=AsyncMock,
            return_value="live",
        ):
            result = await get_trading_mode_endpoint(mock_repo)

        assert result["trading_mode"] == "live"

    @pytest.mark.asyncio
    async def test_toggle_trading_mode_from_research_to_live(self):
        """Test toggling from research to live."""
        from app.api.settings import toggle_trading_mode

        mock_repo = AsyncMock()

        with patch(
            "app.api.settings.get_trading_mode",
            new_callable=AsyncMock,
            return_value="research",
        ):
            with patch(
                "app.api.settings.set_trading_mode", new_callable=AsyncMock
            ) as mock_set:
                result = await toggle_trading_mode(mock_repo)

        assert result["trading_mode"] == "live"
        assert result["previous_mode"] == "research"
        mock_set.assert_called_once_with("live", mock_repo)

    @pytest.mark.asyncio
    async def test_toggle_trading_mode_from_live_to_research(self):
        """Test toggling from live to research."""
        from app.api.settings import toggle_trading_mode

        mock_repo = AsyncMock()

        with patch(
            "app.api.settings.get_trading_mode",
            new_callable=AsyncMock,
            return_value="live",
        ):
            with patch(
                "app.api.settings.set_trading_mode", new_callable=AsyncMock
            ) as mock_set:
                result = await toggle_trading_mode(mock_repo)

        assert result["trading_mode"] == "research"
        assert result["previous_mode"] == "live"
        mock_set.assert_called_once_with("research", mock_repo)
