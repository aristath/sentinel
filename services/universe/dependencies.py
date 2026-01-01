"""Dependency injection for Universe service."""

from functools import lru_cache

from app.modules.universe.services.local_universe_service import LocalUniverseService


@lru_cache()
def get_universe_service() -> LocalUniverseService:
    """
    Get Universe service instance.

    Returns:
        LocalUniverseService instance (cached singleton)
    """
    return LocalUniverseService()
