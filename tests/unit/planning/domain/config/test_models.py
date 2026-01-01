"""Tests for configuration models."""

from app.modules.planning.domain.config.models import (
    FiltersConfig,
    ModuleConfig,
    OpportunityCalculatorsConfig,
    PatternGeneratorsConfig,
    PlannerConfiguration,
    SequenceGeneratorsConfig,
)


def test_module_config_defaults():
    """Test ModuleConfig has correct defaults."""
    config = ModuleConfig()
    assert config.enabled is True
    assert config.params == {}


def test_module_config_with_params():
    """Test ModuleConfig with custom parameters."""
    config = ModuleConfig(enabled=False, params={"threshold": 0.5})
    assert config.enabled is False
    assert config.params["threshold"] == 0.5


def test_planner_configuration_defaults():
    """Test PlannerConfiguration has correct defaults."""
    config = PlannerConfiguration()
    assert config.name == "default"
    assert config.description == ""
    assert config.max_depth == 5
    assert config.max_opportunities_per_category == 5
    assert config.priority_threshold == 0.3
    assert config.enable_diverse_selection is True
    assert config.diversity_weight == 0.3
    assert config.transaction_cost_fixed == 5.0
    assert config.transaction_cost_percent == 0.001
    assert config.allow_sell is True
    assert config.allow_buy is True


def test_planner_configuration_custom_values():
    """Test PlannerConfiguration with custom values."""
    config = PlannerConfiguration(
        name="test",
        description="Test config",
        max_depth=3,
        priority_threshold=0.5,
        allow_sell=False,
    )
    assert config.name == "test"
    assert config.description == "Test config"
    assert config.max_depth == 3
    assert config.priority_threshold == 0.5
    assert config.allow_sell is False


def test_get_enabled_calculators_all_enabled():
    """Test getting enabled calculators when all are enabled."""
    config = PlannerConfiguration()
    enabled = config.get_enabled_calculators()
    assert "profit_taking" in enabled
    assert "averaging_down" in enabled
    assert "opportunity_buys" in enabled
    assert "rebalance_sells" in enabled
    assert "rebalance_buys" in enabled
    assert "weight_based" in enabled
    assert len(enabled) == 6


def test_get_enabled_calculators_selective():
    """Test getting enabled calculators when some are disabled."""
    calculators_config = OpportunityCalculatorsConfig(
        profit_taking=ModuleConfig(enabled=True),
        averaging_down=ModuleConfig(enabled=False),
        opportunity_buys=ModuleConfig(enabled=True),
        rebalance_sells=ModuleConfig(enabled=False),
        rebalance_buys=ModuleConfig(enabled=False),
        weight_based=ModuleConfig(enabled=False),
    )
    config = PlannerConfiguration(opportunity_calculators=calculators_config)
    enabled = config.get_enabled_calculators()
    assert "profit_taking" in enabled
    assert "opportunity_buys" in enabled
    assert "averaging_down" not in enabled
    assert "rebalance_sells" not in enabled
    assert len(enabled) == 2


def test_get_enabled_patterns_all_enabled():
    """Test getting enabled patterns when all are enabled."""
    config = PlannerConfiguration()
    enabled = config.get_enabled_patterns()
    assert "direct_buy" in enabled
    assert "profit_taking" in enabled
    assert "single_best" in enabled
    assert "adaptive" in enabled
    assert len(enabled) == 13


def test_get_enabled_patterns_selective():
    """Test getting enabled patterns when some are disabled."""
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
    enabled = config.get_enabled_patterns()
    assert "direct_buy" in enabled
    assert "single_best" in enabled
    assert "profit_taking" not in enabled
    assert len(enabled) == 2


def test_get_enabled_generators():
    """Test getting enabled sequence generators."""
    generators_config = SequenceGeneratorsConfig(
        combinatorial=ModuleConfig(enabled=False),
        enhanced_combinatorial=ModuleConfig(enabled=True),
        partial_execution=ModuleConfig(enabled=False),
        constraint_relaxation=ModuleConfig(enabled=False),
    )
    config = PlannerConfiguration(sequence_generators=generators_config)
    enabled = config.get_enabled_generators()
    assert "enhanced_combinatorial" in enabled
    assert "combinatorial" not in enabled
    assert len(enabled) == 1


def test_get_enabled_filters():
    """Test getting enabled filters."""
    filters_config = FiltersConfig(
        correlation_aware=ModuleConfig(enabled=True),
        diversity=ModuleConfig(enabled=False),
        eligibility=ModuleConfig(enabled=False),
        recently_traded=ModuleConfig(enabled=False),
    )
    config = PlannerConfiguration(filters=filters_config)
    enabled = config.get_enabled_filters()
    assert "correlation_aware" in enabled
    assert len(enabled) == 1


def test_get_calculator_params():
    """Test getting calculator parameters."""
    calculators_config = OpportunityCalculatorsConfig(
        profit_taking=ModuleConfig(
            enabled=True, params={"windfall_threshold": 0.40, "priority_weight": 1.5}
        ),
    )
    config = PlannerConfiguration(opportunity_calculators=calculators_config)
    params = config.get_calculator_params("profit_taking")
    assert params["windfall_threshold"] == 0.40
    assert params["priority_weight"] == 1.5


def test_get_pattern_params():
    """Test getting pattern parameters."""
    patterns_config = PatternGeneratorsConfig(
        single_best=ModuleConfig(enabled=True, params={"max_depth": 1}),
    )
    config = PlannerConfiguration(pattern_generators=patterns_config)
    params = config.get_pattern_params("single_best")
    assert params["max_depth"] == 1


def test_get_generator_params():
    """Test getting generator parameters."""
    generators_config = SequenceGeneratorsConfig(
        enhanced_combinatorial=ModuleConfig(
            enabled=True, params={"max_combinations": 100}
        ),
    )
    config = PlannerConfiguration(sequence_generators=generators_config)
    params = config.get_generator_params("enhanced_combinatorial")
    assert params["max_combinations"] == 100


def test_get_filter_params():
    """Test getting filter parameters."""
    filters_config = FiltersConfig(
        correlation_aware=ModuleConfig(
            enabled=True, params={"correlation_threshold": 0.6}
        ),
    )
    config = PlannerConfiguration(filters=filters_config)
    params = config.get_filter_params("correlation_aware")
    assert params["correlation_threshold"] == 0.6
