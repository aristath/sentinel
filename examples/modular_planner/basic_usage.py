"""Basic usage example for the modular planner system.

This example demonstrates:
1. Loading a configuration from a TOML file
2. Instantiating a planner factory
3. Getting enabled modules
4. Accessing module parameters
5. Using modules in a planning workflow
"""

from pathlib import Path

from app.modules.planning.domain.config.factory import create_planner_from_config


def main():
    """Demonstrate basic modular planner usage."""

    # 1. Load configuration from TOML file
    print("=" * 70)
    print("STEP 1: Loading Configuration")
    print("=" * 70)

    config_path = Path("config/planner/default.toml")
    factory = create_planner_from_config(config_path)

    print(f"Loaded configuration: {factory.config.name}")
    print(f"Description: {factory.config.description}")
    print(f"Max depth: {factory.config.max_depth}")
    print(f"Priority threshold: {factory.config.priority_threshold}")
    print()

    # 2. Get enabled modules
    print("=" * 70)
    print("STEP 2: Enabled Modules")
    print("=" * 70)

    calculators = factory.get_calculators()
    patterns = factory.get_patterns()
    generators = factory.get_generators()
    filters = factory.get_filters()

    print(f"\nOpportunity Calculators ({len(calculators)}):")
    for calc in calculators:
        print(f"  - {calc.name}")

    print(f"\nPattern Generators ({len(patterns)}):")
    for pattern in patterns:
        print(f"  - {pattern.name}")

    print(f"\nSequence Generators ({len(generators)}):")
    for gen in generators:
        print(f"  - {gen.name}")

    print(f"\nFilters ({len(filters)}):")
    for filt in filters:
        print(f"  - {filt.name}")

    print()

    # 3. Access module parameters
    print("=" * 70)
    print("STEP 3: Module Parameters")
    print("=" * 70)

    # Get parameters for profit_taking calculator
    if "profit_taking" in factory.config.get_enabled_calculators():
        params = factory.get_calculator_params("profit_taking")
        print("\nProfit Taking Calculator Parameters:")
        for key, value in params.items():
            print(f"  {key}: {value}")

    # Get parameters for single_best pattern
    if "single_best" in factory.config.get_enabled_patterns():
        params = factory.get_pattern_params("single_best")
        print("\nSingle Best Pattern Parameters:")
        for key, value in params.items():
            print(f"  {key}: {value}")

    print()

    # 4. Multi-bucket example
    print("=" * 70)
    print("STEP 4: Multi-Bucket Configuration")
    print("=" * 70)

    # Load different configs for different buckets
    conservative_factory = create_planner_from_config(
        Path("config/planner/conservative.toml")
    )
    aggressive_factory = create_planner_from_config(
        Path("config/planner/aggressive.toml")
    )

    print("\nStable Bucket (Conservative):")
    print(f"  Max depth: {conservative_factory.config.max_depth}")
    print(f"  Patterns enabled: {len(conservative_factory.get_patterns())}")

    print("\nGrowth Bucket (Aggressive):")
    print(f"  Max depth: {aggressive_factory.config.max_depth}")
    print(f"  Patterns enabled: {len(aggressive_factory.get_patterns())}")

    print()

    # 5. Module usage workflow (conceptual)
    print("=" * 70)
    print("STEP 5: Planning Workflow (Conceptual)")
    print("=" * 70)

    print("\n1. OpportunityCalculators identify opportunities:")
    print("   - profit_taking: Find windfall gains to sell")
    print("   - averaging_down: Find quality dips to buy")
    print("   - rebalance_sells: Identify overweight positions")
    print("   - rebalance_buys: Identify underweight areas")

    print("\n2. PatternGenerators create action sequences:")
    print("   - direct_buy: Buy with available cash")
    print("   - profit_taking: Sell windfalls, reinvest proceeds")
    print("   - rebalance: Sell overweight, buy underweight")
    print("   - single_best: One highest priority action")

    print("\n3. SequenceGenerators combine opportunities:")
    print("   - enhanced_combinatorial: Weighted sampling with diversity")

    print("\n4. Filters refine sequences:")
    print("   - correlation_aware: Remove correlated positions")

    print("\n5. Evaluate and select best sequence")

    print()
    print("=" * 70)
    print("Example Complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
