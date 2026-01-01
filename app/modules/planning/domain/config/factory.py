"""Factory for creating modular planner instances from configuration.

Instantiates planner components using registries and configuration.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

from app.modules.planning.domain.calculations.filters.base import (
    SequenceFilter,
    sequence_filter_registry,
)
from app.modules.planning.domain.calculations.opportunities.base import (
    OpportunityCalculator,
    opportunity_calculator_registry,
)
from app.modules.planning.domain.calculations.patterns.base import (
    PatternGenerator,
    pattern_generator_registry,
)
from app.modules.planning.domain.calculations.sequences.base import (
    SequenceGenerator,
    sequence_generator_registry,
)
from app.modules.planning.domain.config.models import PlannerConfiguration
from app.modules.planning.domain.config.parser import load_planner_config

logger = logging.getLogger(__name__)


class ModularPlannerFactory:
    """Factory for creating modular planner instances.

    Loads configuration from TOML files and instantiates enabled modules
    using the registry pattern.
    """

    def __init__(self):
        """Initialize factory with empty module lists."""
        self.calculators: Dict[str, OpportunityCalculator] = {}
        self.patterns: Dict[str, PatternGenerator] = {}
        self.generators: Dict[str, SequenceGenerator] = {}
        self.filters: Dict[str, SequenceFilter] = {}
        self.config: Optional[PlannerConfiguration] = None

    @classmethod
    def from_config_file(cls, config_path: Path) -> "ModularPlannerFactory":
        """
        Create a factory from a TOML configuration file.

        Args:
            config_path: Path to TOML configuration file

        Returns:
            ModularPlannerFactory instance with loaded modules
        """
        factory = cls()
        factory.load_config(config_path)
        factory.instantiate_modules()
        return factory

    @classmethod
    def from_config(cls, config: PlannerConfiguration) -> "ModularPlannerFactory":
        """
        Create a factory from a PlannerConfiguration object.

        Args:
            config: PlannerConfiguration instance

        Returns:
            ModularPlannerFactory instance with loaded modules
        """
        factory = cls()
        factory.config = config
        factory.instantiate_modules()
        return factory

    def load_config(self, config_path: Path) -> None:
        """
        Load configuration from a TOML file.

        Args:
            config_path: Path to TOML configuration file
        """
        self.config = load_planner_config(config_path)
        logger.info(f"Loaded planner configuration: {self.config.name}")

    def instantiate_modules(self) -> None:
        """
        Instantiate all enabled modules from registries.

        Uses the configuration to determine which modules to enable
        and retrieves them from the global registries.
        """
        if not self.config:
            raise ValueError("Configuration not loaded. Call load_config() first.")

        # Load opportunity calculators
        for name in self.config.get_enabled_calculators():
            calculator = opportunity_calculator_registry.get(name)
            if calculator is None:
                raise ValueError(
                    f"Calculator '{name}' is enabled in config but not registered. "
                    f"Available calculators: {opportunity_calculator_registry.list_names()}"
                )
            self.calculators[name] = calculator
            logger.debug(f"Enabled calculator: {name}")

        # Load pattern generators
        for name in self.config.get_enabled_patterns():
            pattern = pattern_generator_registry.get(name)
            if pattern is None:
                raise ValueError(
                    f"Pattern '{name}' is enabled in config but not registered. "
                    f"Available patterns: {pattern_generator_registry.list_names()}"
                )
            self.patterns[name] = pattern
            logger.debug(f"Enabled pattern: {name}")

        # Load sequence generators
        for name in self.config.get_enabled_generators():
            generator = sequence_generator_registry.get(name)
            if generator is None:
                raise ValueError(
                    f"Generator '{name}' is enabled in config but not registered. "
                    f"Available generators: {sequence_generator_registry.list_names()}"
                )
            self.generators[name] = generator
            logger.debug(f"Enabled generator: {name}")

        # Load filters
        for name in self.config.get_enabled_filters():
            filter_instance = sequence_filter_registry.get(name)
            if filter_instance is None:
                raise ValueError(
                    f"Filter '{name}' is enabled in config but not registered. "
                    f"Available filters: {sequence_filter_registry.list_names()}"
                )
            self.filters[name] = filter_instance
            logger.debug(f"Enabled filter: {name}")

        logger.info(
            f"Instantiated modules: "
            f"{len(self.calculators)} calculators, "
            f"{len(self.patterns)} patterns, "
            f"{len(self.generators)} generators, "
            f"{len(self.filters)} filters"
        )

    def get_calculators(self) -> List[OpportunityCalculator]:
        """Get list of enabled opportunity calculators."""
        return list(self.calculators.values())

    def get_patterns(self) -> List[PatternGenerator]:
        """Get list of enabled pattern generators."""
        return list(self.patterns.values())

    def get_generators(self) -> List[SequenceGenerator]:
        """Get list of enabled sequence generators."""
        return list(self.generators.values())

    def get_filters(self) -> List[SequenceFilter]:
        """Get list of enabled filters."""
        return list(self.filters.values())

    def get_calculator_params(self, name: str) -> Dict:
        """Get parameters for a specific calculator."""
        if not self.config:
            return {}
        return self.config.get_calculator_params(name)

    def get_pattern_params(self, name: str) -> Dict:
        """Get parameters for a specific pattern."""
        if not self.config:
            return {}
        return self.config.get_pattern_params(name)

    def get_generator_params(self, name: str) -> Dict:
        """Get parameters for a specific generator."""
        if not self.config:
            return {}
        return self.config.get_generator_params(name)

    def get_filter_params(self, name: str) -> Dict:
        """Get parameters for a specific filter."""
        if not self.config:
            return {}
        return self.config.get_filter_params(name)


def create_planner_from_config(config_path: Path) -> ModularPlannerFactory:
    """
    Convenience function to create a modular planner from a config file.

    Args:
        config_path: Path to TOML configuration file

    Returns:
        ModularPlannerFactory instance ready to use

    Example:
        >>> from pathlib import Path
        >>> factory = create_planner_from_config(Path("config/planner/default.toml"))
        >>> calculators = factory.get_calculators()
        >>> patterns = factory.get_patterns()
    """
    return ModularPlannerFactory.from_config_file(config_path)
