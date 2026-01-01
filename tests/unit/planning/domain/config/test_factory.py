"""Tests for ModularPlannerFactory."""

import tempfile
from pathlib import Path

import pytest

from app.modules.planning.domain.config.factory import (
    ModularPlannerFactory,
    create_planner_from_config,
)
from app.modules.planning.domain.config.models import (
    ModuleConfig,
    OpportunityCalculatorsConfig,
    PatternGeneratorsConfig,
    PlannerConfiguration,
)


# Ensure modules are imported so they auto-register
def setup_module():
    """Import all modules to ensure they're registered."""
    # Opportunity calculators
    # Filters
    import app.modules.planning.domain.calculations.filters.correlation_aware  # noqa: F401
    import app.modules.planning.domain.calculations.opportunities.averaging_down  # noqa: F401
    import app.modules.planning.domain.calculations.opportunities.opportunity_buys  # noqa: F401
    import app.modules.planning.domain.calculations.opportunities.profit_taking  # noqa: F401

    # Pattern generators
    import app.modules.planning.domain.calculations.patterns.direct_buy  # noqa: F401
    import app.modules.planning.domain.calculations.patterns.profit_taking  # noqa: F401
    import app.modules.planning.domain.calculations.patterns.single_best  # noqa: F401

    # Sequence generators
    import app.modules.planning.domain.calculations.sequences.combinatorial  # noqa: F401
    import app.modules.planning.domain.calculations.sequences.enhanced_combinatorial  # noqa: F401


def test_factory_initialization():
    """Test factory initializes with empty module lists."""
    factory = ModularPlannerFactory()
    assert factory.calculators == {}
    assert factory.patterns == {}
    assert factory.generators == {}
    assert factory.filters == {}
    assert factory.config is None


def test_factory_from_config():
    """Test creating factory from PlannerConfiguration object."""
    config = PlannerConfiguration(name="test", max_depth=3)
    factory = ModularPlannerFactory.from_config(config)
    assert factory.config == config
    assert factory.config.name == "test"


def test_factory_instantiate_modules_without_config():
    """Test instantiating modules without config raises ValueError."""
    factory = ModularPlannerFactory()
    with pytest.raises(ValueError, match="Configuration not loaded"):
        factory.instantiate_modules()


def test_factory_instantiate_calculators():
    """Test factory instantiates enabled calculators."""
    calculators_config = OpportunityCalculatorsConfig(
        profit_taking=ModuleConfig(enabled=True),
        averaging_down=ModuleConfig(enabled=True),
        opportunity_buys=ModuleConfig(enabled=False),
        rebalance_sells=ModuleConfig(enabled=False),
        rebalance_buys=ModuleConfig(enabled=False),
        weight_based=ModuleConfig(enabled=False),
    )
    config = PlannerConfiguration(opportunity_calculators=calculators_config)

    factory = ModularPlannerFactory.from_config(config)

    assert "profit_taking" in factory.calculators
    assert "averaging_down" in factory.calculators
    assert "opportunity_buys" not in factory.calculators
    assert len(factory.calculators) == 2


def test_factory_instantiate_patterns():
    """Test factory instantiates enabled patterns."""
    patterns_config = PatternGeneratorsConfig(
        direct_buy=ModuleConfig(enabled=True),
        single_best=ModuleConfig(enabled=True),
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
    config = PlannerConfiguration(pattern_generators=patterns_config)

    factory = ModularPlannerFactory.from_config(config)

    assert "direct_buy" in factory.patterns
    assert "single_best" in factory.patterns
    assert "profit_taking" not in factory.patterns
    assert len(factory.patterns) == 2


def test_factory_get_methods():
    """Test factory get_* methods return correct lists."""
    config = PlannerConfiguration(name="test")
    factory = ModularPlannerFactory.from_config(config)

    calculators = factory.get_calculators()
    patterns = factory.get_patterns()
    generators = factory.get_generators()
    filters = factory.get_filters()

    assert isinstance(calculators, list)
    assert isinstance(patterns, list)
    assert isinstance(generators, list)
    assert isinstance(filters, list)

    # All should be enabled by default
    assert len(calculators) > 0
    assert len(patterns) > 0


def test_factory_get_params():
    """Test factory param getter methods."""
    calculators_config = OpportunityCalculatorsConfig(
        profit_taking=ModuleConfig(enabled=True, params={"windfall_threshold": 0.40}),
    )
    config = PlannerConfiguration(opportunity_calculators=calculators_config)
    factory = ModularPlannerFactory.from_config(config)

    params = factory.get_calculator_params("profit_taking")
    assert params["windfall_threshold"] == 0.40


def test_factory_from_config_file():
    """Test creating factory from TOML file."""
    toml_content = """
[planner]
name = "test_file"
max_depth = 4

[opportunity_calculators.profit_taking]
enabled = true
[opportunity_calculators.profit_taking.params]
windfall_threshold = 0.35
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(toml_content)
        temp_path = Path(f.name)

    try:
        factory = ModularPlannerFactory.from_config_file(temp_path)
        assert factory.config.name == "test_file"
        assert factory.config.max_depth == 4

        params = factory.get_calculator_params("profit_taking")
        assert params["windfall_threshold"] == 0.35
    finally:
        temp_path.unlink()


def test_create_planner_from_config_convenience():
    """Test convenience function for creating planner."""
    toml_content = """
[planner]
name = "convenience_test"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(toml_content)
        temp_path = Path(f.name)

    try:
        factory = create_planner_from_config(temp_path)
        assert factory.config.name == "convenience_test"
        assert isinstance(factory, ModularPlannerFactory)
    finally:
        temp_path.unlink()


def test_factory_with_default_config():
    """Test factory with default.toml if it exists."""
    config_path = Path("config/planner/default.toml")
    if not config_path.exists():
        pytest.skip("default.toml not found")

    factory = create_planner_from_config(config_path)
    assert factory.config.name == "default"

    # Should have modules loaded
    calculators = factory.get_calculators()
    patterns = factory.get_patterns()

    assert len(calculators) > 0
    assert len(patterns) > 0

    # Test that we can get params
    for calc_name in factory.config.get_enabled_calculators():
        params = factory.get_calculator_params(calc_name)
        assert isinstance(params, dict)


def test_factory_with_conservative_config():
    """Test factory with conservative.toml if it exists."""
    config_path = Path("config/planner/conservative.toml")
    if not config_path.exists():
        pytest.skip("conservative.toml not found")

    factory = create_planner_from_config(config_path)
    assert factory.config.name == "conservative"

    # Conservative should have fewer modules enabled
    patterns = factory.get_patterns()
    assert len(patterns) < 10  # Should be selective


def test_factory_with_aggressive_config():
    """Test factory with aggressive.toml if it exists."""
    config_path = Path("config/planner/aggressive.toml")
    if not config_path.exists():
        pytest.skip("aggressive.toml not found")

    factory = create_planner_from_config(config_path)
    assert factory.config.name == "aggressive"

    # Aggressive should have many modules enabled
    patterns = factory.get_patterns()
    assert len(patterns) >= 10  # Should have most patterns


def test_factory_module_instances_are_reused():
    """Test that factory returns same module instances from registry."""
    config = PlannerConfiguration()
    factory1 = ModularPlannerFactory.from_config(config)
    factory2 = ModularPlannerFactory.from_config(config)

    # Both factories should get the same registered instances
    if (
        "profit_taking" in factory1.calculators
        and "profit_taking" in factory2.calculators
    ):
        assert (
            factory1.calculators["profit_taking"]
            is factory2.calculators["profit_taking"]
        )
