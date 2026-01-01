"""Planner configuration service - business logic for planner config management."""

import logging
from typing import List, Optional

import tomli

from app.modules.planning.database.planner_config_repository import (
    PlannerConfigRepository,
)
from app.modules.planning.domain.config.parser import load_planner_config_from_string
from app.modules.planning.domain.planner_config import (
    PlannerConfig,
    PlannerConfigHistory,
)

logger = logging.getLogger(__name__)


class PlannerConfigService:
    """Service for managing planner configurations.

    Handles validation, CRUD operations, and hot-reload coordination.
    """

    def __init__(self):
        self.repository = PlannerConfigRepository()

    async def get_all(self) -> List[PlannerConfig]:
        """Get all planner configurations."""
        return await self.repository.get_all()

    async def get_by_id(self, config_id: str) -> Optional[PlannerConfig]:
        """Get planner configuration by ID."""
        return await self.repository.get_by_id(config_id)

    async def get_by_bucket(self, bucket_id: str) -> Optional[PlannerConfig]:
        """Get planner configuration for a specific bucket."""
        return await self.repository.get_by_bucket(bucket_id)

    async def validate_toml(self, toml_string: str) -> dict:
        """Validate TOML configuration.

        Args:
            toml_string: TOML configuration string to validate

        Returns:
            Dictionary with validation result:
            {
                "valid": bool,
                "error": Optional[str],
                "config": Optional[PlannerConfiguration]
            }

        Raises:
            Never raises - returns validation errors in result dict
        """
        try:
            # First check if it's valid TOML syntax
            try:
                tomli.loads(toml_string)
            except tomli.TOMLDecodeError as e:
                return {
                    "valid": False,
                    "error": f"Invalid TOML syntax: {str(e)}",
                    "config": None,
                }

            # Then validate it can be parsed into PlannerConfiguration
            config = load_planner_config_from_string(toml_string)

            return {"valid": True, "error": None, "config": config}

        except Exception as e:
            logger.exception("Configuration validation failed")
            return {
                "valid": False,
                "error": f"Configuration validation failed: {str(e)}",
                "config": None,
            }

    async def create(
        self, name: str, toml_config: str, bucket_id: Optional[str] = None
    ) -> dict:
        """Create a new planner configuration.

        Args:
            name: Human-readable name
            toml_config: TOML configuration string
            bucket_id: Associated bucket (None for templates)

        Returns:
            Dictionary with result:
            {
                "success": bool,
                "config": Optional[PlannerConfig],
                "error": Optional[str]
            }
        """
        # Validate TOML first
        validation = await self.validate_toml(toml_config)
        if not validation["valid"]:
            return {"success": False, "config": None, "error": validation["error"]}

        try:
            config = await self.repository.create(name, toml_config, bucket_id)
            logger.info(f"Created planner config '{name}' with ID {config.id}")
            return {"success": True, "config": config, "error": None}

        except Exception as e:
            logger.exception("Failed to create planner config")
            return {"success": False, "config": None, "error": str(e)}

    async def update(
        self,
        config_id: str,
        name: Optional[str] = None,
        toml_config: Optional[str] = None,
        bucket_id: Optional[str] = None,
    ) -> dict:
        """Update a planner configuration.

        Automatically creates a backup before updating.

        Args:
            config_id: ID of the configuration to update
            name: New name (if provided)
            toml_config: New TOML configuration (if provided)
            bucket_id: New bucket assignment (if provided)

        Returns:
            Dictionary with result:
            {
                "success": bool,
                "config": Optional[PlannerConfig],
                "error": Optional[str]
            }
        """
        # Validate TOML if provided
        if toml_config is not None:
            validation = await self.validate_toml(toml_config)
            if not validation["valid"]:
                return {"success": False, "config": None, "error": validation["error"]}

        try:
            config = await self.repository.update(
                config_id,
                name=name,
                toml_config=toml_config,
                bucket_id=bucket_id,
                create_backup=True,
            )

            if not config:
                return {
                    "success": False,
                    "config": None,
                    "error": f"Configuration {config_id} not found",
                }

            logger.info(f"Updated planner config {config_id}")
            return {"success": True, "config": config, "error": None}

        except Exception as e:
            logger.exception("Failed to update planner config")
            return {"success": False, "config": None, "error": str(e)}

    async def delete(self, config_id: str) -> dict:
        """Delete a planner configuration.

        Args:
            config_id: ID of the configuration to delete

        Returns:
            Dictionary with result:
            {
                "success": bool,
                "error": Optional[str]
            }
        """
        try:
            deleted = await self.repository.delete(config_id)

            if not deleted:
                return {
                    "success": False,
                    "error": f"Configuration {config_id} not found",
                }

            logger.info(f"Deleted planner config {config_id}")
            return {"success": True, "error": None}

        except Exception as e:
            logger.exception("Failed to delete planner config")
            return {"success": False, "error": str(e)}

    async def get_history(self, config_id: str) -> List[PlannerConfigHistory]:
        """Get version history for a planner configuration.

        Args:
            config_id: ID of the configuration

        Returns:
            List of historical versions, newest first
        """
        return await self.repository.get_history(config_id)
