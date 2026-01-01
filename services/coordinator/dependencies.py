"""Dependency injection for Coordinator Service."""

from functools import lru_cache

from app.modules.planning.services.local_coordinator_service import (
    LocalCoordinatorService,
)


@lru_cache()
def get_coordinator_service() -> LocalCoordinatorService:
    """Get singleton instance of LocalCoordinatorService."""
    return LocalCoordinatorService()
