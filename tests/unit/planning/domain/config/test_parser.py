"""Tests for TOML configuration parser."""

import tempfile
from pathlib import Path

import pytest

from app.modules.planning.domain.config.parser import (
    load_planner_config,
    load_planner_config_from_string,
)


def test_load_from_string_minimal():
    """Test loading minimal configuration from string."""
    toml_content = """
[planner]
name = "test"
"""
    config = load_planner_config_from_string(toml_content)
    assert config.name == "test"
    assert config.max_depth == 5  # Default value


def test_load_from_string_with_global_settings():
    """Test loading configuration with global settings."""
    toml_content = """
[planner]
name = "custom"
description = "Custom strategy"
max_depth = 3
max_opportunities_per_category = 10
priority_threshold = 0.5
enable_diverse_selection = false
diversity_weight = 0.2
transaction_cost_fixed = 10.0
transaction_cost_percent = 0.002
allow_sell = false
allow_buy = true
"""
    config = load_planner_config_from_string(toml_content)
    assert config.name == "custom"
    assert config.description == "Custom strategy"
    assert config.max_depth == 3
    assert config.max_opportunities_per_category == 10
    assert config.priority_threshold == 0.5
    assert config.enable_diverse_selection is False
    assert config.diversity_weight == 0.2
    assert config.transaction_cost_fixed == 10.0
    assert config.transaction_cost_percent == 0.002
    assert config.allow_sell is False
    assert config.allow_buy is True


def test_load_from_string_with_calculator_config():
    """Test loading configuration with calculator settings."""
    toml_content = """
[planner]
name = "test"

[opportunity_calculators.profit_taking]
enabled = false

[opportunity_calculators.averaging_down]
enabled = true
[opportunity_calculators.averaging_down.params]
dip_threshold = -0.25
min_quality_score = 0.7
"""
    config = load_planner_config_from_string(toml_content)

    # profit_taking should be disabled
    enabled = config.get_enabled_calculators()
    assert "profit_taking" not in enabled
    assert "averaging_down" in enabled

    # Check params
    params = config.get_calculator_params("averaging_down")
    assert params["dip_threshold"] == -0.25
    assert params["min_quality_score"] == 0.7


def test_load_from_string_with_pattern_config():
    """Test loading configuration with pattern settings."""
    toml_content = """
[planner]
name = "test"

[pattern_generators.direct_buy]
enabled = true
[pattern_generators.direct_buy.params]
max_depth = 3

[pattern_generators.single_best]
enabled = true
[pattern_generators.single_best.params]
max_depth = 1

[pattern_generators.profit_taking]
enabled = false
"""
    config = load_planner_config_from_string(toml_content)

    enabled = config.get_enabled_patterns()
    assert "direct_buy" in enabled
    assert "single_best" in enabled
    assert "profit_taking" not in enabled

    params = config.get_pattern_params("direct_buy")
    assert params["max_depth"] == 3


def test_load_from_string_with_generator_config():
    """Test loading configuration with sequence generator settings."""
    toml_content = """
[planner]
name = "test"

[sequence_generators.combinatorial]
enabled = false

[sequence_generators.enhanced_combinatorial]
enabled = true
[sequence_generators.enhanced_combinatorial.params]
max_combinations = 100
max_sells = 4
"""
    config = load_planner_config_from_string(toml_content)

    enabled = config.get_enabled_generators()
    assert "enhanced_combinatorial" in enabled
    assert "combinatorial" not in enabled

    params = config.get_generator_params("enhanced_combinatorial")
    assert params["max_combinations"] == 100
    assert params["max_sells"] == 4


def test_load_from_string_with_filter_config():
    """Test loading configuration with filter settings."""
    toml_content = """
[planner]
name = "test"

[filters.correlation_aware]
enabled = true
[filters.correlation_aware.params]
correlation_threshold = 0.6
"""
    config = load_planner_config_from_string(toml_content)

    enabled = config.get_enabled_filters()
    assert "correlation_aware" in enabled

    params = config.get_filter_params("correlation_aware")
    assert params["correlation_threshold"] == 0.6


def test_load_from_file():
    """Test loading configuration from a file."""
    toml_content = """
[planner]
name = "file_test"
max_depth = 7

[opportunity_calculators.profit_taking]
enabled = true
[opportunity_calculators.profit_taking.params]
windfall_threshold = 0.5
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(toml_content)
        temp_path = Path(f.name)

    try:
        config = load_planner_config(temp_path)
        assert config.name == "file_test"
        assert config.max_depth == 7

        params = config.get_calculator_params("profit_taking")
        assert params["windfall_threshold"] == 0.5
    finally:
        temp_path.unlink()


def test_load_from_nonexistent_file():
    """Test loading from non-existent file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_planner_config(Path("/nonexistent/config.toml"))


def test_load_invalid_toml():
    """Test loading invalid TOML raises exception."""
    invalid_toml = """
[planner
name = "broken"
"""
    with pytest.raises(Exception):  # tomli.TOMLDecodeError
        load_planner_config_from_string(invalid_toml)


def test_load_empty_config():
    """Test loading empty configuration uses all defaults."""
    toml_content = ""
    config = load_planner_config_from_string(toml_content)
    assert config.name == "default"
    assert config.max_depth == 5
    # All calculators should be enabled by default
    assert len(config.get_enabled_calculators()) == 6


def test_load_conservative_example():
    """Test loading the conservative.toml example file."""
    config_path = Path("config/planner/conservative.toml")
    if not config_path.exists():
        pytest.skip("conservative.toml not found")

    config = load_planner_config(config_path)
    assert config.name == "conservative"
    assert config.max_depth == 2  # Conservative = fewer actions
    assert config.priority_threshold == 0.5  # Higher threshold

    # Should have specific patterns enabled for conservative approach
    enabled_patterns = config.get_enabled_patterns()
    assert "single_best" in enabled_patterns  # Perfect for conservative
    assert "rebalance" in enabled_patterns  # Conservative maintains balance
    assert (
        "averaging_down" not in enabled_patterns
    )  # Conservative avoids averaging down


def test_load_aggressive_example():
    """Test loading the aggressive.toml example file."""
    config_path = Path("config/planner/aggressive.toml")
    if not config_path.exists():
        pytest.skip("aggressive.toml not found")

    config = load_planner_config(config_path)
    assert config.name == "aggressive"
    assert config.max_depth == 7  # Aggressive = more actions
    assert config.priority_threshold == 0.2  # Lower threshold

    # Should have more patterns enabled
    enabled_patterns = config.get_enabled_patterns()
    assert len(enabled_patterns) >= 10


def test_load_default_example():
    """Test loading the default.toml example file."""
    config_path = Path("config/planner/default.toml")
    if not config_path.exists():
        pytest.skip("default.toml not found")

    config = load_planner_config(config_path)
    assert config.name == "default"
    assert config.max_depth == 5
    assert config.priority_threshold == 0.3

    # Should have most features enabled
    enabled_calculators = config.get_enabled_calculators()
    assert len(enabled_calculators) >= 5

    enabled_patterns = config.get_enabled_patterns()
    assert len(enabled_patterns) >= 10
