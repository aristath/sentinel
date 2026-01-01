"""Example of creating a custom planner configuration programmatically.

This demonstrates creating configurations without TOML files,
useful for dynamic configuration or testing.
"""

from app.modules.planning.domain.config.factory import ModularPlannerFactory
from app.modules.planning.domain.config.models import (
    FiltersConfig,
    ModuleConfig,
    OpportunityCalculatorsConfig,
    PatternGeneratorsConfig,
    PlannerConfiguration,
    SequenceGeneratorsConfig,
)


def create_minimal_config() -> PlannerConfiguration:
    """Create a minimal configuration with only essential features."""

    calculators_config = OpportunityCalculatorsConfig(
        profit_taking=ModuleConfig(
            enabled=True, params={"windfall_threshold": 0.50, "priority_weight": 1.5}
        ),
        averaging_down=ModuleConfig(
            enabled=True, params={"dip_threshold": -0.25, "min_quality_score": 0.7}
        ),
        opportunity_buys=ModuleConfig(enabled=False),
        rebalance_sells=ModuleConfig(enabled=False),
        rebalance_buys=ModuleConfig(enabled=False),
        weight_based=ModuleConfig(enabled=False),
    )

    patterns_config = PatternGeneratorsConfig(
        single_best=ModuleConfig(enabled=True, params={"max_depth": 1}),
        direct_buy=ModuleConfig(enabled=True, params={"max_depth": 2}),
        profit_taking=ModuleConfig(enabled=False),
        rebalance=ModuleConfig(enabled=False),
        averaging_down=ModuleConfig(enabled=False),
        multi_sell=ModuleConfig(enabled=False),
        mixed_strategy=ModuleConfig(enabled=False),
        opportunity_first=ModuleConfig(enabled=False),
        deep_rebalance=ModuleConfig(enabled=False),
        cash_generation=ModuleConfig(enabled=False),
        cost_optimized=ModuleConfig(enabled=False),
        adaptive=ModuleConfig(enabled=False),
        market_regime=ModuleConfig(enabled=False),
    )

    generators_config = SequenceGeneratorsConfig(
        combinatorial=ModuleConfig(enabled=False),
        enhanced_combinatorial=ModuleConfig(enabled=False),
    )

    filters_config = FiltersConfig(
        correlation_aware=ModuleConfig(enabled=False),
    )

    return PlannerConfiguration(
        name="minimal",
        description="Minimal planner with only essential features",
        max_depth=2,
        priority_threshold=0.5,
        enable_diverse_selection=False,
        opportunity_calculators=calculators_config,
        pattern_generators=patterns_config,
        sequence_generators=generators_config,
        filters=filters_config,
    )


def create_rebalancing_config() -> PlannerConfiguration:
    """Create a configuration focused on rebalancing."""

    calculators_config = OpportunityCalculatorsConfig(
        profit_taking=ModuleConfig(enabled=False),
        averaging_down=ModuleConfig(enabled=False),
        opportunity_buys=ModuleConfig(enabled=False),
        rebalance_sells=ModuleConfig(
            enabled=True, params={"overweight_threshold": 0.01, "priority_weight": 1.0}
        ),
        rebalance_buys=ModuleConfig(
            enabled=True,
            params={"underweight_threshold": 0.01, "priority_weight": 1.0},
        ),
        weight_based=ModuleConfig(
            enabled=True, params={"min_gap_threshold": 0.005}
        ),
    )

    patterns_config = PatternGeneratorsConfig(
        single_best=ModuleConfig(enabled=False),
        direct_buy=ModuleConfig(enabled=False),
        profit_taking=ModuleConfig(enabled=False),
        rebalance=ModuleConfig(enabled=True, params={"max_depth": 5}),
        averaging_down=ModuleConfig(enabled=False),
        multi_sell=ModuleConfig(enabled=False),
        mixed_strategy=ModuleConfig(enabled=False),
        opportunity_first=ModuleConfig(enabled=False),
        deep_rebalance=ModuleConfig(enabled=True, params={"max_depth": 7}),
        cash_generation=ModuleConfig(enabled=False),
        cost_optimized=ModuleConfig(enabled=False),
        adaptive=ModuleConfig(enabled=False),
        market_regime=ModuleConfig(enabled=False),
    )

    generators_config = SequenceGeneratorsConfig(
        combinatorial=ModuleConfig(enabled=False),
        enhanced_combinatorial=ModuleConfig(enabled=False),
    )

    filters_config = FiltersConfig(
        correlation_aware=ModuleConfig(enabled=True, params={"correlation_threshold": 0.7}),
    )

    return PlannerConfiguration(
        name="rebalancing",
        description="Focus on portfolio rebalancing",
        max_depth=7,
        priority_threshold=0.2,
        enable_diverse_selection=True,
        diversity_weight=0.4,
        opportunity_calculators=calculators_config,
        pattern_generators=patterns_config,
        sequence_generators=generators_config,
        filters=filters_config,
    )


def main():
    """Demonstrate custom configuration creation."""

    print("=" * 70)
    print("Custom Configuration Example")
    print("=" * 70)

    # Create minimal configuration
    minimal_config = create_minimal_config()
    minimal_factory = ModularPlannerFactory.from_config(minimal_config)

    print(f"\n{minimal_config.name.upper()} Configuration:")
    print(f"  Calculators: {len(minimal_factory.get_calculators())}")
    print(f"  Patterns: {len(minimal_factory.get_patterns())}")
    print(f"  Enabled calculators: {', '.join(minimal_config.get_enabled_calculators())}")
    print(f"  Enabled patterns: {', '.join(minimal_config.get_enabled_patterns())}")

    # Create rebalancing configuration
    rebalancing_config = create_rebalancing_config()
    rebalancing_factory = ModularPlannerFactory.from_config(rebalancing_config)

    print(f"\n{rebalancing_config.name.upper()} Configuration:")
    print(f"  Calculators: {len(rebalancing_factory.get_calculators())}")
    print(f"  Patterns: {len(rebalancing_factory.get_patterns())}")
    print(f"  Enabled calculators: {', '.join(rebalancing_config.get_enabled_calculators())}")
    print(f"  Enabled patterns: {', '.join(rebalancing_config.get_enabled_patterns())}")

    print("\n" + "=" * 70)
    print("Both configurations created successfully!")
    print("=" * 70)


if __name__ == "__main__":
    main()
