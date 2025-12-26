"""Tests for SettingsService."""

from unittest.mock import AsyncMock

import pytest

from app.domain.services.settings_service import SettingsService
from app.repositories import SettingsRepository


class TestSettingsService:
    """Test SettingsService."""

    @pytest.mark.asyncio
    async def test_get_settings_loads_from_repository(self):
        """Test that get_settings loads from repository."""
        # Mock repository
        mock_repo = AsyncMock(spec=SettingsRepository)
        mock_repo.get_all.return_value = {
            "min_hold_days": "120",
            "sell_cooldown_days": "365",
            "max_loss_threshold": "-0.15",
            "target_annual_return": "0.12",
            "min_stock_score": "0.6",
            "optimizer_blend": "0.7",
            "optimizer_target_return": "0.12",
            "transaction_cost_fixed": "3.0",
            "transaction_cost_percent": "0.003",
            "min_cash_reserve": "1000.0",
        }

        service = SettingsService(mock_repo)
        settings = await service.get_settings()

        assert settings.min_hold_days == 120
        assert settings.sell_cooldown_days == 365
        assert settings.optimizer_blend == 0.7
        assert settings.transaction_cost_fixed == 3.0
        assert mock_repo.get_all.called

    @pytest.mark.asyncio
    async def test_get_settings_uses_defaults_when_empty(self):
        """Test that get_settings uses defaults when repository is empty."""
        mock_repo = AsyncMock(spec=SettingsRepository)
        mock_repo.get_all.return_value = {}

        service = SettingsService(mock_repo)
        settings = await service.get_settings()

        assert settings.min_hold_days == 90  # Default
        assert settings.optimizer_blend == 0.5  # Default
        assert settings.transaction_cost_fixed == 2.0  # Default

    @pytest.mark.asyncio
    async def test_get_settings_caches_result(self):
        """Test that get_settings caches the result."""
        mock_repo = AsyncMock(spec=SettingsRepository)
        mock_repo.get_all.return_value = {"min_hold_days": "120"}

        service = SettingsService(mock_repo)

        # First call
        settings1 = await service.get_settings()
        # Second call
        settings2 = await service.get_settings()

        # Repository should only be called once (cached)
        assert mock_repo.get_all.call_count == 1
        assert settings1 is settings2  # Same instance (cached)

    @pytest.mark.asyncio
    async def test_invalidate_cache(self):
        """Test that invalidate_cache clears the cache."""
        mock_repo = AsyncMock(spec=SettingsRepository)
        mock_repo.get_all.return_value = {"min_hold_days": "120"}

        service = SettingsService(mock_repo)

        # First call
        await service.get_settings()
        # Invalidate cache
        service.invalidate_cache()
        # Second call (should reload)
        await service.get_settings()

        # Repository should be called twice
        assert mock_repo.get_all.call_count == 2

    @pytest.mark.asyncio
    async def test_update_setting_invalidates_cache(self):
        """Test that updating a setting invalidates the cache."""
        mock_repo = AsyncMock(spec=SettingsRepository)
        mock_repo.get_all.return_value = {"optimizer_blend": "0.5"}
        mock_repo.set_float = AsyncMock()

        service = SettingsService(mock_repo)

        # Load settings (cached)
        await service.get_settings()
        # Update setting with float value
        await service.update_setting("optimizer_blend", 0.7)

        # Cache should be invalidated, next call should reload
        await service.get_settings()
        assert mock_repo.get_all.call_count == 2
        assert mock_repo.set_float.called
