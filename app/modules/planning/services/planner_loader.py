"""Planner loader service - hot-reload planner configurations without restart."""

import logging
from typing import Dict, Optional

from app.modules.planning.domain.config.factory import ModularPlannerFactory
from app.modules.planning.domain.config.parser import load_planner_config_from_string
from app.modules.planning.services.planner_config_service import PlannerConfigService

logger = logging.getLogger(__name__)


class PlannerLoader:
    """Service for hot-reloading planner configurations.

    Manages per-bucket planner instances and handles hot-reload without restart.
    """

    def __init__(self):
        self.config_service = PlannerConfigService()
        # In-memory cache of bucket_id -> ModularPlannerFactory
        self._planner_cache: Dict[str, ModularPlannerFactory] = {}

    async def load_planner_for_bucket(
        self, bucket_id: str, force_reload: bool = False
    ) -> Optional[ModularPlannerFactory]:
        """Load or reload planner for a specific bucket.

        Args:
            bucket_id: ID of the bucket
            force_reload: If True, reload even if cached

        Returns:
            ModularPlannerFactory instance or None if no config found
        """
        # Return cached if available and not forcing reload
        if not force_reload and bucket_id in self._planner_cache:
            logger.debug(f"Using cached planner for bucket {bucket_id}")
            return self._planner_cache[bucket_id]

        # Get config for this bucket
        config_model = await self.config_service.get_by_bucket(bucket_id)
        if not config_model:
            logger.warning(f"No planner config found for bucket {bucket_id}")
            return None

        try:
            # Parse TOML into PlannerConfiguration
            planner_config = load_planner_config_from_string(config_model.toml_config)

            # Create factory from config
            factory = ModularPlannerFactory.from_config(planner_config)

            # Cache it
            self._planner_cache[bucket_id] = factory

            logger.info(
                f"Loaded planner '{config_model.name}' for bucket {bucket_id}: "
                f"{len(factory.calculators)} calculators, "
                f"{len(factory.patterns)} patterns, "
                f"{len(factory.generators)} generators"
            )

            return factory

        except Exception as e:
            logger.error(
                f"Failed to load planner for bucket {bucket_id}: {e}", exc_info=True
            )
            return None

    async def reload_planner_for_bucket(
        self, bucket_id: str
    ) -> Optional[ModularPlannerFactory]:
        """Force reload planner for a bucket (hot-reload).

        Args:
            bucket_id: ID of the bucket

        Returns:
            ModularPlannerFactory instance or None if failed
        """
        logger.info(f"Hot-reloading planner for bucket {bucket_id}")
        return await self.load_planner_for_bucket(bucket_id, force_reload=True)

    async def apply_config(self, config_id: str) -> dict:
        """Apply a planner configuration (load/reload for its bucket).

        Args:
            config_id: ID of the planner configuration

        Returns:
            Dictionary with result:
            {
                "success": bool,
                "bucket_id": Optional[str],
                "error": Optional[str]
            }
        """
        try:
            # Get config
            config = await self.config_service.get_by_id(config_id)
            if not config:
                return {
                    "success": False,
                    "bucket_id": None,
                    "error": f"Configuration {config_id} not found",
                }

            if not config.bucket_id:
                return {
                    "success": False,
                    "bucket_id": None,
                    "error": "Configuration has no associated bucket (template only)",
                }

            # Reload planner for this bucket
            factory = await self.reload_planner_for_bucket(config.bucket_id)

            if not factory:
                return {
                    "success": False,
                    "bucket_id": config.bucket_id,
                    "error": "Failed to load planner configuration",
                }

            return {
                "success": True,
                "bucket_id": config.bucket_id,
                "error": None,
            }

        except Exception as e:
            logger.error(f"Failed to apply config {config_id}: {e}", exc_info=True)
            return {
                "success": False,
                "bucket_id": None,
                "error": str(e),
            }

    def clear_cache(self, bucket_id: Optional[str] = None) -> None:
        """Clear planner cache.

        Args:
            bucket_id: If provided, clear only for this bucket. Otherwise clear all.
        """
        if bucket_id:
            if bucket_id in self._planner_cache:
                del self._planner_cache[bucket_id]
                logger.info(f"Cleared planner cache for bucket {bucket_id}")
        else:
            self._planner_cache.clear()
            logger.info("Cleared all planner cache")

    def get_cached_planner(self, bucket_id: str) -> Optional[ModularPlannerFactory]:
        """Get cached planner for a bucket without loading.

        Args:
            bucket_id: ID of the bucket

        Returns:
            Cached ModularPlannerFactory or None
        """
        return self._planner_cache.get(bucket_id)


# Global singleton instance
_planner_loader: Optional[PlannerLoader] = None


def get_planner_loader() -> PlannerLoader:
    """Get global planner loader singleton."""
    global _planner_loader
    if _planner_loader is None:
        _planner_loader = PlannerLoader()
    return _planner_loader
