"""Configuration models for modular planner.

Dataclasses representing planner configuration loaded from TOML files.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ModuleConfig:
    """Configuration for a single module (calculator, pattern, generator, filter)."""

    enabled: bool = True
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OpportunityCalculatorsConfig:
    """Configuration for opportunity calculators."""

    profit_taking: ModuleConfig = field(default_factory=ModuleConfig)
    averaging_down: ModuleConfig = field(default_factory=ModuleConfig)
    opportunity_buys: ModuleConfig = field(default_factory=ModuleConfig)
    rebalance_sells: ModuleConfig = field(default_factory=ModuleConfig)
    rebalance_buys: ModuleConfig = field(default_factory=ModuleConfig)
    weight_based: ModuleConfig = field(default_factory=ModuleConfig)


@dataclass
class PatternGeneratorsConfig:
    """Configuration for pattern generators."""

    # Basic patterns
    direct_buy: ModuleConfig = field(default_factory=ModuleConfig)
    profit_taking: ModuleConfig = field(default_factory=ModuleConfig)
    rebalance: ModuleConfig = field(default_factory=ModuleConfig)
    averaging_down: ModuleConfig = field(default_factory=ModuleConfig)
    single_best: ModuleConfig = field(default_factory=ModuleConfig)
    multi_sell: ModuleConfig = field(default_factory=ModuleConfig)
    mixed_strategy: ModuleConfig = field(default_factory=ModuleConfig)
    opportunity_first: ModuleConfig = field(default_factory=ModuleConfig)
    deep_rebalance: ModuleConfig = field(default_factory=ModuleConfig)
    cash_generation: ModuleConfig = field(default_factory=ModuleConfig)
    cost_optimized: ModuleConfig = field(default_factory=ModuleConfig)

    # Complex patterns
    adaptive: ModuleConfig = field(default_factory=ModuleConfig)
    market_regime: ModuleConfig = field(default_factory=ModuleConfig)


@dataclass
class SequenceGeneratorsConfig:
    """Configuration for sequence generators."""

    combinatorial: ModuleConfig = field(default_factory=ModuleConfig)
    enhanced_combinatorial: ModuleConfig = field(default_factory=ModuleConfig)
    partial_execution: ModuleConfig = field(default_factory=ModuleConfig)
    constraint_relaxation: ModuleConfig = field(default_factory=ModuleConfig)


@dataclass
class FiltersConfig:
    """Configuration for sequence filters."""

    correlation_aware: ModuleConfig = field(default_factory=ModuleConfig)
    diversity: ModuleConfig = field(default_factory=ModuleConfig)
    eligibility: ModuleConfig = field(default_factory=ModuleConfig)
    recently_traded: ModuleConfig = field(default_factory=ModuleConfig)


@dataclass
class PlannerConfiguration:
    """Complete configuration for a planner instance.

    Each bucket can have its own planner configuration with different
    enabled modules and parameters.
    """

    # Planner identification
    name: str = "default"
    description: str = ""
    enable_batch_generation: bool = (
        True  # Enable continuous sequence generation in background
    )

    # Global planner settings
    max_depth: int = 5
    max_opportunities_per_category: int = 5
    priority_threshold: float = 0.3
    beam_width: int = 10
    enable_diverse_selection: bool = True
    diversity_weight: float = 0.3

    # Module configurations
    opportunity_calculators: OpportunityCalculatorsConfig = field(
        default_factory=OpportunityCalculatorsConfig
    )
    pattern_generators: PatternGeneratorsConfig = field(
        default_factory=PatternGeneratorsConfig
    )
    sequence_generators: SequenceGeneratorsConfig = field(
        default_factory=SequenceGeneratorsConfig
    )
    filters: FiltersConfig = field(default_factory=FiltersConfig)

    # Advanced settings
    transaction_cost_fixed: float = 5.0
    transaction_cost_percent: float = 0.001
    allow_sell: bool = True
    allow_buy: bool = True

    def get_enabled_calculators(self) -> List[str]:
        """Get list of enabled opportunity calculator names."""
        enabled = []
        for name in [
            "profit_taking",
            "averaging_down",
            "opportunity_buys",
            "rebalance_sells",
            "rebalance_buys",
            "weight_based",
        ]:
            config = getattr(self.opportunity_calculators, name)
            if config.enabled:
                enabled.append(name)
        return enabled

    def get_enabled_patterns(self) -> List[str]:
        """Get list of enabled pattern generator names."""
        enabled = []
        for name in [
            "direct_buy",
            "profit_taking",
            "rebalance",
            "averaging_down",
            "single_best",
            "multi_sell",
            "mixed_strategy",
            "opportunity_first",
            "deep_rebalance",
            "cash_generation",
            "cost_optimized",
            "adaptive",
            "market_regime",
        ]:
            config = getattr(self.pattern_generators, name)
            if config.enabled:
                enabled.append(name)
        return enabled

    def get_enabled_generators(self) -> List[str]:
        """Get list of enabled sequence generator names."""
        enabled = []
        for name in [
            "combinatorial",
            "enhanced_combinatorial",
            "partial_execution",
            "constraint_relaxation",
        ]:
            config = getattr(self.sequence_generators, name)
            if config.enabled:
                enabled.append(name)
        return enabled

    def get_enabled_filters(self) -> List[str]:
        """Get list of enabled filter names."""
        enabled = []
        for name in [
            "correlation_aware",
            "diversity",
            "eligibility",
            "recently_traded",
        ]:
            config = getattr(self.filters, name)
            if config.enabled:
                enabled.append(name)
        return enabled

    def get_calculator_params(self, name: str) -> Dict[str, Any]:
        """Get parameters for a specific calculator."""
        config = getattr(self.opportunity_calculators, name)
        return config.params

    def get_pattern_params(self, name: str) -> Dict[str, Any]:
        """Get parameters for a specific pattern."""
        config = getattr(self.pattern_generators, name)
        return config.params

    def get_generator_params(self, name: str) -> Dict[str, Any]:
        """Get parameters for a specific generator."""
        config = getattr(self.sequence_generators, name)
        return config.params

    def get_filter_params(self, name: str) -> Dict[str, Any]:
        """Get parameters for a specific filter."""
        config = getattr(self.filters, name)
        return config.params
