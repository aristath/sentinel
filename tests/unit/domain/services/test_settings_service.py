"""Tests for SettingsService."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from app.domain.services.settings_service import SettingsService
from app.domain.value_objects.settings import Settings
from app.repositories import SettingsRepository


class TestSettingsService:
    """Test SettingsService."""

    @pytest.mark.asyncio
    async def test_get_settings_loads_from_repository(self):
        """Test that get_settings loads from repository."""
        # Mock repository
        mock_repo = AsyncMock(spec=SettingsRepository)
        mock_repo.get_all.return_value = {
            "min_trade_size": "200.0",
            "min_hold_days": "120",
            "sell_cooldown_days": "365",
            "max_loss_threshold": "-0.15",
            "target_annual_return": "0.12",
            "recommendation_depth": "2",
        }
        
        service = SettingsService(mock_repo)
        settings = await service.get_settings()
        
        assert settings.min_trade_size == 200.0
        assert settings.min_hold_days == 120
        assert settings.sell_cooldown_days == 365
        assert mock_repo.get_all.called

    @pytest.mark.asyncio
    async def test_get_settings_uses_defaults_when_empty(self):
        """Test that get_settings uses defaults when repository is empty."""
        mock_repo = AsyncMock(spec=SettingsRepository)
        mock_repo.get_all.return_value = {}
        
        service = SettingsService(mock_repo)
        settings = await service.get_settings()
        
        assert settings.min_trade_size == 150.0  # Default
        assert settings.min_hold_days == 90  # Default

    @pytest.mark.asyncio
    async def test_get_settings_caches_result(self):
        """Test that get_settings caches the result."""
        mock_repo = AsyncMock(spec=SettingsRepository)
        mock_repo.get_all.return_value = {"min_trade_size": "200.0"}
        
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
        mock_repo.get_all.return_value = {"min_trade_size": "200.0"}
        
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
        mock_repo.get_all.return_value = {"min_trade_size": "200.0"}
        mock_repo.set_float = AsyncMock()
        
        service = SettingsService(mock_repo)
        
        # Load settings (cached)
        await service.get_settings()
        # Update setting
        await service.update_setting("min_trade_size", 250.0)
        
        # Cache should be invalidated, next call should reload
        settings = await service.get_settings()
        assert mock_repo.get_all.call_count == 2
        assert mock_repo.set_float.called

