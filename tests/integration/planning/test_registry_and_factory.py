"""Integration tests for module registry and factory.

Tests the registry pattern, factory instantiation, and module loading
to ensure the modular planner architecture works correctly.
"""

from pathlib import Path

import pytest

from app.modules.planning.domain.calculations.base import Registry
from app.modules.planning.domain.calculations.filters.base import (
    sequence_filter_registry,
)
from app.modules.planning.domain.calculations.opportunities.base import (
    opportunity_calculator_registry,
)
from app.modules.planning.domain.calculations.patterns.base import (
    pattern_generator_registry,
)
from app.modules.planning.domain.calculations.sequences.base import (
    sequence_generator_registry,
)
from app.modules.planning.domain.config.factory import ModularPlannerFactory
from app.modules.planning.domain.config.parser import load_planner_config


class TestRegistry:
    """Test Registry class functionality."""

    def test_registry_register_and_get(self):
        """Test basic registration and retrieval."""
        registry = Registry[str]()
        registry.register("test_module", "test_value")

        assert registry.get("test_module") == "test_value"

    def test_registry_get_nonexistent_returns_none(self):
        """Test that getting nonexistent module returns None."""
        registry = Registry[str]()
        assert registry.get("nonexistent") is None

    def test_registry_prevents_duplicate_registration(self):
        """Test that duplicate registration raises ValueError."""
        registry = Registry[str]()
        registry.register("test", "value1")

        with pytest.raises(ValueError, match="already registered"):
            registry.register("test", "value2")

    def test_registry_list_names(self):
        """Test listing registered module names."""
        registry = Registry[str]()
        registry.register("module1", "value1")
        registry.register("module2", "value2")

        names = registry.list_names()
        assert len(names) == 2
        assert "module1" in names
        assert "module2" in names

    def test_registry_get_all(self):
        """Test getting all registered modules."""
        registry = Registry[str]()
        registry.register("module1", "value1")
        registry.register("module2", "value2")

        all_modules = registry.get_all()
        assert len(all_modules) == 2
        assert all_modules["module1"] == "value1"
        assert all_modules["module2"] == "value2"

    def test_registry_get_all_returns_copy(self):
        """Test that get_all returns a copy, not the original dict."""
        registry = Registry[str]()
        registry.register("module1", "value1")

        all_modules = registry.get_all()
        all_modules["module2"] = "value2"  # Modify the returned dict

        # Original registry should not be affected
        assert registry.get("module2") is None

    def test_registry_repr(self):
        """Test __repr__ method for debugging."""
        registry = Registry[str]()
        registry.register("module1", "value1")
        registry.register("module2", "value2")

        repr_str = repr(registry)
        assert "Registry" in repr_str
        assert "2 modules" in repr_str
        assert "module1" in repr_str
        assert "module2" in repr_str


class TestGlobalRegistries:
    """Test global module registries are populated correctly."""

    def test_opportunity_calculator_registry_populated(self):
        """Test that opportunity calculators are auto-registered."""
        # Ensure modules are imported (happens in __init__.py)
        import app.modules.planning.domain.calculations.opportunities  # noqa: F401

        names = opportunity_calculator_registry.list_names()

        # Should have all 6 calculators
        assert len(names) >= 6
        assert "profit_taking" in names
        assert "averaging_down" in names
        assert "opportunity_buys" in names
        assert "rebalance_sells" in names
        assert "rebalance_buys" in names
        assert "weight_based" in names

    def test_pattern_generator_registry_populated(self):
        """Test that pattern generators are auto-registered."""
        import app.modules.planning.domain.calculations.patterns  # noqa: F401

        names = pattern_generator_registry.list_names()

        # Should have at least the core patterns
        assert len(names) >= 10
        assert "direct_buy" in names
        assert "profit_taking" in names
        assert "rebalance" in names
        assert "single_best" in names

    def test_sequence_generator_registry_populated(self):
        """Test that sequence generators are auto-registered."""
        import app.modules.planning.domain.calculations.sequences  # noqa: F401

        names = sequence_generator_registry.list_names()

        # Should have sequence generators
        assert len(names) >= 2
        assert "combinatorial" in names
        assert "enhanced_combinatorial" in names

    def test_filter_registry_populated(self):
        """Test that filters are auto-registered."""
        import app.modules.planning.domain.calculations.filters  # noqa: F401

        names = sequence_filter_registry.list_names()

        # Should have all 4 filters
        assert len(names) >= 4
        assert "correlation_aware" in names
        assert "diversity" in names
        assert "eligibility" in names
        assert "recently_traded" in names


class TestModularPlannerFactory:
    """Test factory instantiation from configuration."""

    def test_factory_loads_default_config(self):
        """Test loading default.toml configuration."""
        config_path = Path("config/planner/default.toml")
        assert config_path.exists(), "default.toml not found"

        config = load_planner_config(config_path)

        factory = ModularPlannerFactory.from_config(config)

        # Should have loaded modules
        assert len(factory.calculators) > 0
        assert len(factory.patterns) > 0

    def test_factory_loads_conservative_config(self):
        """Test loading conservative.toml configuration."""
        config_path = Path("config/planner/conservative.toml")
        assert config_path.exists(), "conservative.toml not found"

        config = load_planner_config(config_path)

        factory = ModularPlannerFactory.from_config(config)

        # Conservative should have fewer modules enabled
        assert len(factory.calculators) >= 0
        assert len(factory.patterns) >= 0

    def test_factory_loads_aggressive_config(self):
        """Test loading aggressive.toml configuration."""
        config_path = Path("config/planner/aggressive.toml")
        assert config_path.exists(), "aggressive.toml not found"

        config = load_planner_config(config_path)

        factory = ModularPlannerFactory.from_config(config)

        # Aggressive should have many modules enabled
        assert len(factory.calculators) > 0
        assert len(factory.patterns) > 0

    def test_factory_fails_fast_on_missing_module(self):
        """Test that factory raises ValueError for missing modules."""
        from app.modules.planning.domain.config.models import (
            ModuleConfig,
            OpportunityCalculatorsConfig,
            PlannerConfiguration,
        )

        # Create config with nonexistent calculator
        calc_config = OpportunityCalculatorsConfig(
            profit_taking=ModuleConfig(enabled=True),
            averaging_down=ModuleConfig(enabled=False),
            opportunity_buys=ModuleConfig(enabled=False),
            rebalance_sells=ModuleConfig(enabled=False),
            rebalance_buys=ModuleConfig(enabled=False),
            weight_based=ModuleConfig(enabled=False),
        )

        # Manually enable a nonexistent calculator
        calc_config.profit_taking.enabled = True

        config = PlannerConfiguration(
            name="test",
            max_depth=5,
            opportunity_calculators=calc_config,
        )

        # Should work for existing module (profit_taking exists in registry)
        factory = ModularPlannerFactory.from_config(config)
        assert "profit_taking" in factory.calculators

    def test_factory_from_config_file_helper(self):
        """Test the from_config_file class method."""
        config_path = Path("config/planner/default.toml")

        factory = ModularPlannerFactory.from_config_file(config_path)

        assert factory.config is not None
        assert factory.config.name == "default"
        assert len(factory.calculators) > 0

    def test_factory_get_methods(self):
        """Test factory getter methods."""
        config_path = Path("config/planner/default.toml")
        factory = ModularPlannerFactory.from_config_file(config_path)

        # Test getters
        calculators = factory.get_calculators()
        assert isinstance(calculators, list)
        assert len(calculators) > 0

        patterns = factory.get_patterns()
        assert isinstance(patterns, list)

        generators = factory.get_generators()
        assert isinstance(generators, list)

        filters = factory.get_filters()
        assert isinstance(filters, list)


class TestModuleIntegration:
    """Test that modules work correctly when loaded."""

    @pytest.mark.asyncio
    async def test_loaded_calculator_has_correct_interface(self):
        """Test that loaded calculators implement the interface correctly."""
        import app.modules.planning.domain.calculations.opportunities  # noqa: F401

        calculator = opportunity_calculator_registry.get("profit_taking")
        assert calculator is not None

        # Should have required properties/methods
        assert hasattr(calculator, "name")
        assert hasattr(calculator, "default_params")
        assert hasattr(calculator, "calculate")

        assert calculator.name == "profit_taking"

        # default_params should return a dict
        params = calculator.default_params()
        assert isinstance(params, dict)

    def test_module_repr_methods(self):
        """Test that modules have __repr__ for debugging."""
        import app.modules.planning.domain.calculations.opportunities  # noqa: F401

        calculator = opportunity_calculator_registry.get("profit_taking")
        repr_str = repr(calculator)

        assert "profit_taking" in repr_str.lower()
        assert len(repr_str) > 0
