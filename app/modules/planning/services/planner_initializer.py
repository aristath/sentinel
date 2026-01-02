"""Initialize planner configurations from TOML files.

Seeds the database with default planner configurations on first run.
"""

# mypy: disable-error-code="index,attr-defined"

import logging
from pathlib import Path
from typing import Any, Dict

from app.modules.planning.domain.config.parser import load_planner_config
from app.modules.planning.services.planner_config_service import PlannerConfigService

logger = logging.getLogger(__name__)


class PlannerInitializer:
    """Initializes planner configurations from TOML files."""

    def __init__(self) -> None:
        self.config_service = PlannerConfigService()
        self.config_dir = Path("config/planner")

    async def seed_default_configs(self) -> Dict[str, Any]:
        """Seed database with default planner configurations.

        Loads TOML configs and creates database entries if they don't exist.

        Returns:
            Dictionary with results:
            {
                "success": bool,
                "created": List[str],  # Names of created configs
                "skipped": List[str],  # Names of existing configs
                "errors": List[str]    # Error messages
            }
        """
        result = {
            "success": True,
            "created": [],
            "skipped": [],
            "errors": [],
        }

        # Default configs to load
        default_configs = [
            {
                "file": "default.toml",
                "bucket_id": "core",
                "name": "Core Portfolio Strategy",
            },
            {
                "file": "conservative.toml",
                "bucket_id": None,  # Template, not assigned
                "name": "Conservative Strategy (Template)",
            },
            {
                "file": "aggressive.toml",
                "bucket_id": None,  # Template, not assigned
                "name": "Aggressive Strategy (Template)",
            },
        ]

        for config_def in default_configs:
            config_path = self.config_dir / config_def["file"]

            if not config_path.exists():
                logger.warning(f"Config file not found: {config_path}")
                result["errors"].append(f"File not found: {config_def['file']}")
                continue

            try:
                # Check if config already exists
                existing = None
                if config_def["bucket_id"]:
                    # Check by bucket for assigned configs
                    existing = await self.config_service.get_by_bucket(
                        config_def["bucket_id"]
                    )
                else:
                    # Check by name for templates (no bucket assignment)
                    all_configs = await self.config_service.get_all()
                    existing = next(
                        (c for c in all_configs if c.name == config_def["name"]), None
                    )

                if existing:
                    logger.info(
                        f"Planner config '{config_def['name']}' already exists, skipping"
                    )
                    result["skipped"].append(config_def["name"])
                    continue

                # Load TOML file
                with open(config_path, "r") as f:
                    toml_content = f.read()

                # Validate it can be parsed
                try:
                    load_planner_config(config_path)
                except Exception as e:
                    logger.error(f"Failed to parse {config_path}: {e}")
                    result["errors"].append(f"Parse error in {config_def['file']}: {e}")
                    continue

                # Create database entry
                create_result = await self.config_service.create(
                    name=config_def["name"],
                    toml_config=toml_content,
                    bucket_id=config_def["bucket_id"],
                )

                if create_result["success"]:
                    logger.info(f"Created planner config: {config_def['name']}")
                    result["created"].append(config_def["name"])
                else:
                    logger.error(
                        f"Failed to create config {config_def['name']}: {create_result['error']}"
                    )
                    result["errors"].append(
                        f"{config_def['name']}: {create_result['error']}"
                    )
                    result["success"] = False

            except Exception as e:
                logger.error(
                    f"Error processing {config_def['file']}: {e}", exc_info=True
                )
                result["errors"].append(f"{config_def['file']}: {str(e)}")
                result["success"] = False

        return result

    async def ensure_core_config(self) -> bool:
        """Ensure core bucket has a planner configuration.

        Returns:
            True if core config exists or was created, False otherwise
        """
        # Check if core bucket has a config
        existing = await self.config_service.get_by_bucket("core")
        if existing:
            logger.debug("Core bucket planner config exists")
            return True

        # Create from default.toml
        logger.info("Core bucket has no planner config, creating from default.toml")

        config_path = self.config_dir / "default.toml"
        if not config_path.exists():
            logger.error(f"Default config file not found: {config_path}")
            return False

        try:
            with open(config_path, "r") as f:
                toml_content = f.read()

            # Validate
            load_planner_config(config_path)

            # Create
            result = await self.config_service.create(
                name="Core Portfolio Strategy",
                toml_config=toml_content,
                bucket_id="core",
            )

            if result["success"]:
                logger.info("Created core bucket planner config")
                return True
            else:
                logger.error(f"Failed to create core config: {result['error']}")
                return False

        except Exception as e:
            logger.error(f"Error creating core config: {e}", exc_info=True)
            return False


async def initialize_planner_configs() -> Dict[str, Any]:
    """Initialize planner configurations (convenience function).

    Returns:
        Result dictionary from seed_default_configs()
    """
    initializer = PlannerInitializer()
    return await initializer.seed_default_configs()
