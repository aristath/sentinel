"""Factory service for creating bucket-specific planners.

Creates configured HolisticPlanner instances based on bucket settings.
Supports both core and satellite buckets with strategy-specific configurations.
"""

import logging
from pathlib import Path
from typing import Optional

from app.modules.planning.domain.config.factory import ModularPlannerFactory
from app.modules.planning.domain.config.models import PlannerConfiguration
from app.modules.planning.domain.config.parameter_mapper import ParameterMapper
from app.modules.planning.domain.config.validator import ConfigurationValidator
from app.modules.planning.domain.planner import HolisticPlanner
from app.modules.satellites.domain.models import SatelliteSettings
from app.repositories import SettingsRepository, TradeRepository

logger = logging.getLogger(__name__)


class PlannerFactoryService:
    """Creates bucket-specific planner instances.

    Handles configuration loading from:
    - TOML files (for core bucket)
    - SatelliteSettings (for satellite buckets)
    - Defaults (fallback)
    """

    def __init__(
        self,
        settings_repo: Optional[SettingsRepository] = None,
        trade_repo: Optional[TradeRepository] = None,
    ):
        """Initialize factory with repositories.

        Args:
            settings_repo: Repository for settings lookup
            trade_repo: Repository for trade history
        """
        self.settings_repo = settings_repo or SettingsRepository()
        self.trade_repo = trade_repo or TradeRepository()

    def create_for_core_bucket(
        self,
        config_path: Optional[Path] = None,
    ) -> HolisticPlanner:
        """Create planner for the core bucket.

        Uses default configuration from TOML file if available,
        otherwise creates a sensible default configuration.

        Args:
            config_path: Optional path to TOML config (defaults to config/planner/default.toml)

        Returns:
            HolisticPlanner configured for core bucket
        """
        if config_path is None:
            config_path = Path("config/planner/default.toml")

        config: PlannerConfiguration

        if config_path.exists():
            logger.info(f"Loading core bucket config from {config_path}")
            factory = ModularPlannerFactory.from_config_file(config_path)
            if factory.config is None:
                raise ValueError(f"Failed to load config from {config_path}")
            config = factory.config
        else:
            logger.warning(
                f"Config file {config_path} not found, using default configuration"
            )
            config = self._create_default_config("core")

        # Validate configuration
        errors = ConfigurationValidator.validate(config)
        if errors:
            error_msg = "\n".join(errors)
            raise ValueError(f"Invalid configuration:\n{error_msg}")

        return HolisticPlanner(
            config=config,
            settings_repo=self.settings_repo,
            trade_repo=self.trade_repo,
            metrics_cache=None,  # TODO: Add metrics cache support
        )

    def create_for_satellite_bucket(
        self,
        satellite_id: str,
        satellite_settings: SatelliteSettings,
    ) -> HolisticPlanner:
        """Create planner for a satellite bucket.

        Uses SatelliteSettings sliders to create a custom configuration
        via the ParameterMapper.

        Args:
            satellite_id: ID of the satellite bucket
            satellite_settings: Strategy settings with slider values

        Returns:
            HolisticPlanner configured for satellite bucket
        """
        logger.info(f"Creating planner for satellite {satellite_id}")

        # Validate satellite settings
        satellite_settings.validate()

        # If preset is specified, try to load from file
        if satellite_settings.preset:
            preset_path = Path(f"config/planner/{satellite_settings.preset}.toml")
            if preset_path.exists():
                logger.info(
                    f"Loading preset {satellite_settings.preset} for {satellite_id}"
                )
                factory = ModularPlannerFactory.from_config_file(preset_path)
                if factory.config is None:
                    raise ValueError(
                        f"Failed to load preset {satellite_settings.preset}"
                    )
                config = factory.config

                # Override with slider-specific adjustments
                config = self._apply_slider_overrides(config, satellite_settings)
            else:
                logger.warning(
                    f"Preset {satellite_settings.preset} not found, creating from sliders"
                )
                config = self._create_config_from_sliders(
                    satellite_id, satellite_settings
                )
        else:
            # Create from sliders
            config = self._create_config_from_sliders(satellite_id, satellite_settings)

        # Validate configuration
        errors = ConfigurationValidator.validate(config)
        if errors:
            error_msg = "\n".join(errors)
            raise ValueError(f"Invalid satellite configuration:\n{error_msg}")

        return HolisticPlanner(
            config=config,
            settings_repo=self.settings_repo,
            trade_repo=self.trade_repo,
            metrics_cache=None,
        )

    def create_for_bucket(
        self,
        bucket_id: str,
        satellite_settings: Optional[SatelliteSettings] = None,
    ) -> HolisticPlanner:
        """Create planner for any bucket by ID.

        Routes to appropriate creation method based on bucket ID.

        Args:
            bucket_id: ID of the bucket ('core' or satellite ID)
            satellite_settings: Settings if this is a satellite bucket

        Returns:
            HolisticPlanner configured for the bucket
        """
        if bucket_id == "core":
            return self.create_for_core_bucket()
        else:
            if satellite_settings is None:
                raise ValueError(
                    f"satellite_settings required for non-core bucket {bucket_id}"
                )
            return self.create_for_satellite_bucket(bucket_id, satellite_settings)

    def _create_config_from_sliders(
        self,
        satellite_id: str,
        settings: SatelliteSettings,
    ) -> PlannerConfiguration:
        """Create PlannerConfiguration from SatelliteSettings sliders.

        Args:
            satellite_id: ID of satellite
            settings: Satellite settings with sliders

        Returns:
            PlannerConfiguration based on slider values
        """
        # Map slider values to technical parameters
        risk_params = ParameterMapper.map_risk_appetite(settings.risk_appetite)
        hold_params = ParameterMapper.map_hold_duration(settings.hold_duration)
        entry_params = ParameterMapper.map_entry_style(settings.entry_style)
        spread_params = ParameterMapper.map_position_spread(settings.position_spread)
        profit_params = ParameterMapper.map_profit_taking_aggressiveness(
            settings.profit_taking
        )

        # Combine all parameter mappings
        params = {
            **risk_params,
            **hold_params,
            **entry_params,
            **spread_params,
            **profit_params,
        }

        # Create configuration with available top-level fields
        config = PlannerConfiguration(
            name=f"satellite_{satellite_id}",
            description=f"Dynamic configuration for {satellite_id}",
            # Core planning parameters
            max_depth=int(params.get("max_depth", 5)),
            max_opportunities_per_category=int(
                params.get("max_opportunities_per_category", 5)
            ),
            priority_threshold=params.get("priority_threshold", 0.3),
            enable_diverse_selection=True,
            diversity_weight=params.get("diversity_weight", 0.3),
            # Transaction costs
            transaction_cost_fixed=2.0,
            transaction_cost_percent=0.002,
            # Trade constraints
            allow_sell=True,
            allow_buy=True,
        )

        # TODO: Apply module-specific parameters to individual module configs
        # For example:
        # - cost_penalty_factor -> evaluation module
        # - min_hold_days, sell_cooldown_days -> eligibility filter
        # - max_loss_threshold -> eligibility filter
        # - min_trade_amount -> pattern generators
        # - max_position_concentration -> diversity filter

        return config

    def _apply_slider_overrides(
        self,
        config: PlannerConfiguration,
        settings: SatelliteSettings,
    ) -> PlannerConfiguration:
        """Apply slider-based overrides to a preset configuration.

        Args:
            config: Base configuration from preset
            settings: Satellite settings with sliders

        Returns:
            Modified configuration with slider overrides
        """
        # Map sliders to parameters
        risk_params = ParameterMapper.map_risk_appetite(settings.risk_appetite)
        spread_params = ParameterMapper.map_position_spread(settings.position_spread)

        # Apply top-level overrides that exist in PlannerConfiguration
        config.priority_threshold = risk_params.get(
            "priority_threshold", config.priority_threshold
        )
        config.diversity_weight = spread_params.get(
            "diversity_weight", config.diversity_weight
        )

        # TODO: Apply other parameters to module-specific configs
        # - cost_penalty_factor -> evaluation parameters
        # - max_position_concentration -> diversity filter parameters

        return config

    def _create_default_config(self, name: str) -> PlannerConfiguration:
        """Create a sensible default configuration.

        Args:
            name: Configuration name

        Returns:
            Default PlannerConfiguration
        """
        return PlannerConfiguration(
            name=name,
            description=f"Default configuration for {name}",
            max_depth=5,
            max_opportunities_per_category=5,
            priority_threshold=0.3,
            enable_diverse_selection=True,
            diversity_weight=0.3,
            transaction_cost_fixed=2.0,
            transaction_cost_percent=0.002,
            allow_sell=True,
            allow_buy=True,
        )
