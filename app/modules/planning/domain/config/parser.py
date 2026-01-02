"""TOML configuration parser for modular planner.

Loads planner configuration from TOML files.
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

import tomli

from app.modules.planning.domain.config.models import (
    FiltersConfig,
    ModuleConfig,
    OpportunityCalculatorsConfig,
    PatternGeneratorsConfig,
    PlannerConfiguration,
    SequenceGeneratorsConfig,
)

logger = logging.getLogger(__name__)


def _parse_module_config(config_dict: Optional[Dict[str, Any]]) -> ModuleConfig:
    """Parse a module configuration dictionary."""
    if not config_dict:
        return ModuleConfig()

    return ModuleConfig(
        enabled=config_dict.get("enabled", True),
        params=config_dict.get("params", {}),
    )


def _parse_calculators_config(
    config_dict: Optional[Dict[str, Any]]
) -> OpportunityCalculatorsConfig:
    """Parse opportunity calculators configuration."""
    if not config_dict:
        return OpportunityCalculatorsConfig()

    return OpportunityCalculatorsConfig(
        profit_taking=_parse_module_config(config_dict.get("profit_taking")),
        averaging_down=_parse_module_config(config_dict.get("averaging_down")),
        opportunity_buys=_parse_module_config(config_dict.get("opportunity_buys")),
        rebalance_sells=_parse_module_config(config_dict.get("rebalance_sells")),
        rebalance_buys=_parse_module_config(config_dict.get("rebalance_buys")),
        weight_based=_parse_module_config(config_dict.get("weight_based")),
    )


def _parse_patterns_config(
    config_dict: Optional[Dict[str, Any]]
) -> PatternGeneratorsConfig:
    """Parse pattern generators configuration."""
    if not config_dict:
        return PatternGeneratorsConfig()

    return PatternGeneratorsConfig(
        direct_buy=_parse_module_config(config_dict.get("direct_buy")),
        profit_taking=_parse_module_config(config_dict.get("profit_taking")),
        rebalance=_parse_module_config(config_dict.get("rebalance")),
        averaging_down=_parse_module_config(config_dict.get("averaging_down")),
        single_best=_parse_module_config(config_dict.get("single_best")),
        multi_sell=_parse_module_config(config_dict.get("multi_sell")),
        mixed_strategy=_parse_module_config(config_dict.get("mixed_strategy")),
        opportunity_first=_parse_module_config(config_dict.get("opportunity_first")),
        deep_rebalance=_parse_module_config(config_dict.get("deep_rebalance")),
        cash_generation=_parse_module_config(config_dict.get("cash_generation")),
        cost_optimized=_parse_module_config(config_dict.get("cost_optimized")),
        adaptive=_parse_module_config(config_dict.get("adaptive")),
        market_regime=_parse_module_config(config_dict.get("market_regime")),
    )


def _parse_generators_config(
    config_dict: Optional[Dict[str, Any]]
) -> SequenceGeneratorsConfig:
    """Parse sequence generators configuration."""
    if not config_dict:
        return SequenceGeneratorsConfig()

    return SequenceGeneratorsConfig(
        combinatorial=_parse_module_config(config_dict.get("combinatorial")),
        enhanced_combinatorial=_parse_module_config(
            config_dict.get("enhanced_combinatorial")
        ),
    )


def _parse_filters_config(config_dict: Optional[Dict[str, Any]]) -> FiltersConfig:
    """Parse filters configuration."""
    if not config_dict:
        return FiltersConfig()

    return FiltersConfig(
        correlation_aware=_parse_module_config(config_dict.get("correlation_aware")),
    )


def load_planner_config(config_path: Path) -> PlannerConfiguration:
    """
    Load planner configuration from a TOML file.

    Args:
        config_path: Path to the TOML configuration file

    Returns:
        PlannerConfiguration instance

    Raises:
        FileNotFoundError: If config file doesn't exist
        tomli.TOMLDecodeError: If TOML is invalid
    """
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    logger.info(f"Loading planner configuration from {config_path}")

    with open(config_path, "rb") as f:
        config_dict = tomli.load(f)

    # Parse global settings
    planner = config_dict.get("planner", {})

    # Parse module configurations
    opportunity_calculators = _parse_calculators_config(
        config_dict.get("opportunity_calculators")
    )
    pattern_generators = _parse_patterns_config(config_dict.get("pattern_generators"))
    sequence_generators = _parse_generators_config(
        config_dict.get("sequence_generators")
    )
    filters = _parse_filters_config(config_dict.get("filters"))

    config = PlannerConfiguration(
        name=planner.get("name", "default"),
        description=planner.get("description", ""),
        enable_batch_generation=planner.get("enable_batch_generation", True),
        max_depth=planner.get("max_depth", 5),
        max_opportunities_per_category=planner.get("max_opportunities_per_category", 5),
        priority_threshold=planner.get("priority_threshold", 0.3),
        beam_width=planner.get("beam_width", 10),
        enable_diverse_selection=planner.get("enable_diverse_selection", True),
        diversity_weight=planner.get("diversity_weight", 0.3),
        transaction_cost_fixed=planner.get("transaction_cost_fixed", 5.0),
        transaction_cost_percent=planner.get("transaction_cost_percent", 0.001),
        allow_sell=planner.get("allow_sell", True),
        allow_buy=planner.get("allow_buy", True),
        opportunity_calculators=opportunity_calculators,
        pattern_generators=pattern_generators,
        sequence_generators=sequence_generators,
        filters=filters,
    )

    logger.info(
        f"Loaded configuration '{config.name}': "
        f"{len(config.get_enabled_calculators())} calculators, "
        f"{len(config.get_enabled_patterns())} patterns, "
        f"{len(config.get_enabled_generators())} generators, "
        f"{len(config.get_enabled_filters())} filters"
    )

    return config


def load_planner_config_from_string(toml_content: str) -> PlannerConfiguration:
    """
    Load planner configuration from a TOML string.

    Args:
        toml_content: TOML configuration as a string

    Returns:
        PlannerConfiguration instance

    Raises:
        tomli.TOMLDecodeError: If TOML is invalid
    """
    config_dict = tomli.loads(toml_content)

    # Parse global settings
    planner = config_dict.get("planner", {})

    # Parse module configurations
    opportunity_calculators = _parse_calculators_config(
        config_dict.get("opportunity_calculators")
    )
    pattern_generators = _parse_patterns_config(config_dict.get("pattern_generators"))
    sequence_generators = _parse_generators_config(
        config_dict.get("sequence_generators")
    )
    filters = _parse_filters_config(config_dict.get("filters"))

    return PlannerConfiguration(
        name=planner.get("name", "default"),
        description=planner.get("description", ""),
        enable_batch_generation=planner.get("enable_batch_generation", True),
        max_depth=planner.get("max_depth", 5),
        max_opportunities_per_category=planner.get("max_opportunities_per_category", 5),
        priority_threshold=planner.get("priority_threshold", 0.3),
        beam_width=planner.get("beam_width", 10),
        enable_diverse_selection=planner.get("enable_diverse_selection", True),
        diversity_weight=planner.get("diversity_weight", 0.3),
        transaction_cost_fixed=planner.get("transaction_cost_fixed", 5.0),
        transaction_cost_percent=planner.get("transaction_cost_percent", 0.001),
        allow_sell=planner.get("allow_sell", True),
        allow_buy=planner.get("allow_buy", True),
        opportunity_calculators=opportunity_calculators,
        pattern_generators=pattern_generators,
        sequence_generators=sequence_generators,
        filters=filters,
    )
