"""Configuration validator for planner configurations.

Validates planner configurations and checks for common issues before use.
"""

from typing import List

from app.modules.planning.domain.config.models import PlannerConfiguration


class ConfigurationValidator:
    """Validates planner configurations and checks for issues."""

    @staticmethod
    def validate(config: PlannerConfiguration) -> List[str]:
        """
        Validate configuration and return list of issues.

        Args:
            config: Configuration to validate

        Returns:
            List of validation errors (empty list if valid)
        """
        errors: List[str] = []

        # Check module existence
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

        # Validate opportunity calculators
        for calc_name in config.get_enabled_calculators():
            if not opportunity_calculator_registry.get(calc_name):
                errors.append(f"Unknown opportunity calculator: '{calc_name}'")

        # Validate pattern generators
        for pattern_name in config.get_enabled_patterns():
            if not pattern_generator_registry.get(pattern_name):
                errors.append(f"Unknown pattern generator: '{pattern_name}'")

        # Validate sequence generators
        for gen_name in config.get_enabled_generators():
            if not sequence_generator_registry.get(gen_name):
                errors.append(f"Unknown sequence generator: '{gen_name}'")

        # Validate filters
        for filter_name in config.get_enabled_filters():
            if not sequence_filter_registry.get(filter_name):
                errors.append(f"Unknown filter: '{filter_name}'")

        # Validate parameter ranges
        if config.max_depth < 1:
            errors.append("max_depth must be >= 1")

        if config.max_depth > 10:
            errors.append(
                "max_depth > 10 may cause excessive computation time (recommended max: 7)"
            )

        if not 0.0 <= config.priority_threshold <= 1.0:
            errors.append("priority_threshold must be between 0.0 and 1.0")

        if config.max_opportunities_per_category < 0:
            errors.append("max_opportunities_per_category must be >= 0")

        if config.transaction_cost_fixed < 0:
            errors.append("transaction_cost_fixed must be >= 0")

        if not 0.0 <= config.transaction_cost_percent <= 1.0:
            errors.append("transaction_cost_percent must be between 0.0 and 1.0")

        if config.transaction_cost_percent > 0.01:
            errors.append(
                f"transaction_cost_percent = {config.transaction_cost_percent} seems unusually high (>1%)"
            )

        # Validate allow_sell and allow_buy
        if not config.allow_sell and not config.allow_buy:
            errors.append("Both allow_sell and allow_buy cannot be False")

        # Validate diversity settings
        if config.enable_diverse_selection:
            if not 0.0 <= config.diversity_weight <= 1.0:
                errors.append("diversity_weight must be between 0.0 and 1.0")

        return errors

    @staticmethod
    def check_dependencies(config: PlannerConfiguration) -> List[str]:
        """
        Check for module dependency issues.

        Args:
            config: Configuration to check

        Returns:
            List of warnings about missing dependencies or suboptimal configs
        """
        warnings: List[str] = []

        # Check if any modules are enabled at all
        enabled_calculators = config.get_enabled_calculators()
        enabled_patterns = config.get_enabled_patterns()
        enabled_generators = config.get_enabled_generators()

        if not enabled_calculators:
            warnings.append(
                "No opportunity calculators enabled - planner will have no opportunities to work with"
            )

        if not enabled_patterns:
            warnings.append(
                "No pattern generators enabled - planner will have no sequences to evaluate"
            )

        # Warn about specific module dependencies
        if (
            "combinatorial" in enabled_generators
            or "enhanced_combinatorial" in enabled_generators
        ):
            if len(enabled_patterns) < 2:
                warnings.append(
                    "Combinatorial generators work best with multiple patterns enabled (currently: {})".format(
                        len(enabled_patterns)
                    )
                )

        if "correlation_aware" in config.get_enabled_filters():
            warnings.append(
                "correlation_aware filter requires securities with correlation data - "
                "ensure risk model is available"
            )

        if "diversity" in config.get_enabled_filters():
            if not config.enable_diverse_selection:
                warnings.append(
                    "diversity filter is enabled but enable_diverse_selection=False - "
                    "filter may have no effect"
                )

        # Check for rebalance patterns without rebalance calculators
        rebalance_patterns = [p for p in enabled_patterns if "rebalance" in p]
        rebalance_calculators = [
            c for c in enabled_calculators if "rebalance" in c or "weight_based" in c
        ]

        if rebalance_patterns and not rebalance_calculators:
            warnings.append(
                f"Rebalance patterns enabled ({rebalance_patterns}) but no rebalance "
                "calculators enabled - patterns may produce empty sequences"
            )

        # Check for profit_taking pattern without profit_taking calculator
        if (
            "profit_taking" in enabled_patterns
            and "profit_taking" not in enabled_calculators
        ):
            warnings.append(
                "profit_taking pattern enabled but profit_taking calculator disabled - "
                "pattern may produce empty sequences"
            )

        # Check for averaging_down pattern without averaging_down calculator
        if (
            "averaging_down" in enabled_patterns
            and "averaging_down" not in enabled_calculators
        ):
            warnings.append(
                "averaging_down pattern enabled but averaging_down calculator disabled - "
                "pattern may produce empty sequences"
            )

        # Warn about performance implications
        if config.max_depth >= 7 and len(enabled_patterns) >= 10:
            warnings.append(
                f"High computational load: max_depth={config.max_depth} with "
                f"{len(enabled_patterns)} patterns may take >60s on Arduino"
            )

        if "combinatorial" in enabled_generators:
            combinatorial_params = config.get_generator_params("combinatorial")
            max_combinations = combinatorial_params.get("max_combinations", 50)
            if max_combinations > 100:
                warnings.append(
                    f"combinatorial generator max_combinations={max_combinations} "
                    "may cause very long planning times"
                )

        # Check if both allow_sell disabled but sell calculators enabled
        if not config.allow_sell:
            sell_calculators = [
                c
                for c in enabled_calculators
                if c in ["profit_taking", "rebalance_sells", "weight_based"]
            ]
            if sell_calculators:
                warnings.append(
                    f"allow_sell=False but sell calculators enabled: {sell_calculators} - "
                    "these calculators will have no effect"
                )

        # Check if both allow_buy disabled but buy calculators enabled
        if not config.allow_buy:
            buy_calculators = [
                c
                for c in enabled_calculators
                if c in ["averaging_down", "opportunity_buys", "rebalance_buys"]
            ]
            if buy_calculators:
                warnings.append(
                    f"allow_buy=False but buy calculators enabled: {buy_calculators} - "
                    "these calculators will have no effect"
                )

        return warnings

    @staticmethod
    def validate_and_warn(
        config: PlannerConfiguration,
    ) -> tuple[bool, List[str], List[str]]:
        """
        Validate configuration and return errors and warnings.

        Args:
            config: Configuration to validate

        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        errors = ConfigurationValidator.validate(config)
        warnings = ConfigurationValidator.check_dependencies(config)

        is_valid = len(errors) == 0

        return (is_valid, errors, warnings)
