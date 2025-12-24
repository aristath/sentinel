"""Repository interface for application settings data access."""

from abc import ABC, abstractmethod
from typing import Optional


class SettingsRepository(ABC):
    """Abstract repository for application settings operations."""

    @abstractmethod
    async def get(self, key: str) -> Optional[str]:
        """Get a setting value by key."""
        pass

    @abstractmethod
    async def set(self, key: str, value: str) -> None:
        """Set a setting value."""
        pass

    @abstractmethod
    async def get_float(self, key: str, default: float = 0.0) -> float:
        """Get a setting value as float."""
        pass

    @abstractmethod
    async def set_float(self, key: str, value: float) -> None:
        """Set a setting value as float."""
        pass

