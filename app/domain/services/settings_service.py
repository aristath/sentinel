"""Settings domain service.

Provides type-safe access to application settings via Settings value object.
"""

from typing import Optional, Union

from app.domain.repositories.protocols import ISettingsRepository
from app.domain.value_objects.settings import Settings


class SettingsService:
    """Domain service for accessing application settings.

    Loads settings from repository and provides them as a Settings value object.
    Caches the result for performance.
    """

    def __init__(self, settings_repo: ISettingsRepository):
        """Initialize settings service.

        Args:
            settings_repo: Settings repository instance (implements ISettingsRepository)
        """
        self._settings_repo = settings_repo
        self._cached_settings: Optional[Settings] = None

    async def get_settings(self) -> Settings:
        """Get application settings.

        Loads from repository and caches the result.
        Subsequent calls return cached instance until invalidate_cache() is called.

        Returns:
            Settings value object with current application settings
        """
        if self._cached_settings is None:
            all_settings = await self._settings_repo.get_all()
            self._cached_settings = Settings.from_dict(all_settings)

        return self._cached_settings

    def invalidate_cache(self) -> None:
        """Invalidate the settings cache.

        Next call to get_settings() will reload from repository.
        """
        self._cached_settings = None

    async def update_setting(self, key: str, value: Union[float, int]) -> None:
        """Update a single setting value.

        Args:
            key: Setting key
            value: New value (float or int)
        """
        if isinstance(value, float):
            await self._settings_repo.set_float(key, value)
        elif isinstance(value, int):
            await self._settings_repo.set_int(key, value)
        else:
            raise ValueError(f"Unsupported value type: {type(value)}")

        # Invalidate cache so next get_settings() reloads
        self.invalidate_cache()
