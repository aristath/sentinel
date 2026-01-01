"""Adapter for gradual migration from monolithic to modular planner.

This adapter allows the modular system to be used within the existing
holistic_planner.py without requiring a complete rewrite.

Usage:
    # In holistic_planner.py, replace monolithic functions with adapter
    from app.modules.planning.domain.modular_adapter import ModularPlannerAdapter

    adapter = ModularPlannerAdapter.from_config_file(Path("config/planner/default.toml"))
    opportunities = await adapter.calculate_opportunities(context)
    sequences = adapter.generate_patterns(opportunities, available_cash, max_depth)
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.domain.models import Position, Security
from app.modules.planning.domain.calculations.opportunities.base import (
    OpportunityContext,
)
from app.modules.planning.domain.config.factory import ModularPlannerFactory
from app.modules.planning.domain.holistic_planner import ActionCandidate

logger = logging.getLogger(__name__)


class ModularPlannerAdapter:
    """Adapter bridging modular system with monolithic planner.

    This class provides a familiar interface that matches the monolithic
    planner's function signatures, but uses the modular system underneath.
    """

    def __init__(self, factory: ModularPlannerFactory):
        """Initialize adapter with a factory.

        Args:
            factory: ModularPlannerFactory with loaded configuration
        """
        self.factory = factory
        self.config = factory.config

    @classmethod
    def from_config_file(cls, config_path: Path) -> "ModularPlannerAdapter":
        """Create adapter from a TOML configuration file.

        Args:
            config_path: Path to TOML configuration file

        Returns:
            ModularPlannerAdapter instance
        """
        factory = ModularPlannerFactory.from_config_file(config_path)
        return cls(factory)

    async def calculate_opportunities(
        self,
        positions: List[Position],
        securities: List[Security],
        stocks_by_symbol: Dict[str, Security],
        available_cash_eur: float,
        total_portfolio_value_eur: float,
        country_allocations: Optional[Dict[str, float]] = None,
        country_to_group: Optional[Dict[str, str]] = None,
        country_weights: Optional[Dict[str, float]] = None,
        target_weights: Optional[Dict[str, float]] = None,
        security_scores: Optional[Dict[str, float]] = None,
    ) -> Dict[str, List[ActionCandidate]]:
        """Calculate all opportunities using enabled calculators.

        This replaces the monolithic identify_opportunities() function.

        Args:
            positions: Current portfolio positions
            securities: Available securities
            stocks_by_symbol: Symbol to Security mapping
            available_cash_eur: Available cash in EUR
            total_portfolio_value_eur: Total portfolio value in EUR
            country_allocations: Current country allocations (optional)
            country_to_group: Country to group mapping (optional)
            country_weights: Target country weights (optional)
            target_weights: Target security weights (optional)
            security_scores: Security quality scores (optional)

        Returns:
            Dict mapping opportunity type to list of ActionCandidates
        """
        # Build context for calculators
        context = OpportunityContext(
            positions=positions,
            securities=securities,
            stocks_by_symbol=stocks_by_symbol,
            available_cash_eur=available_cash_eur,
            total_portfolio_value_eur=total_portfolio_value_eur,
            country_allocations=country_allocations,
            country_to_group=country_to_group,
            country_weights=country_weights,
            target_weights=target_weights,
            security_scores=security_scores,
        )

        # Calculate opportunities using each enabled calculator
        opportunities: Dict[str, List[ActionCandidate]] = {}

        for calculator in self.factory.get_calculators():
            params = self.factory.get_calculator_params(calculator.name)

            # Merge default params with config params
            full_params = {**calculator.default_params(), **params}

            try:
                candidates = await calculator.calculate(context, full_params)
                opportunities[calculator.name] = candidates
                logger.debug(
                    f"Calculator '{calculator.name}' found {len(candidates)} opportunities"
                )
            except Exception as e:
                logger.error(f"Calculator '{calculator.name}' failed: {e}")
                opportunities[calculator.name] = []

        return opportunities

    def generate_patterns(
        self,
        opportunities: Dict[str, List[ActionCandidate]],
        available_cash: float,
        max_depth: int,
    ) -> List[List[ActionCandidate]]:
        """Generate action sequences using enabled pattern generators.

        This replaces the monolithic _generate_patterns_at_depth() function.

        Args:
            opportunities: Dict of categorized opportunities
            available_cash: Available cash in EUR
            max_depth: Maximum sequence depth

        Returns:
            List of action sequences
        """
        sequences: List[List[ActionCandidate]] = []

        # Add available_cash to params for each pattern
        base_params = {
            "available_cash_eur": available_cash,
            "max_depth": max_depth,
        }

        for pattern in self.factory.get_patterns():
            params = self.factory.get_pattern_params(pattern.name)

            # Merge base params with config params
            full_params = {**pattern.default_params(), **base_params, **params}

            try:
                pattern_sequences = pattern.generate(opportunities, full_params)
                sequences.extend(pattern_sequences)
                logger.debug(
                    f"Pattern '{pattern.name}' generated {len(pattern_sequences)} sequences"
                )
            except Exception as e:
                logger.error(f"Pattern '{pattern.name}' failed: {e}")

        return sequences

    def generate_combinatorial_sequences(
        self,
        opportunities: List[ActionCandidate],
        available_cash: float,
        max_depth: int,
    ) -> List[List[ActionCandidate]]:
        """Generate combinatorial sequences using enabled generators.

        This replaces the monolithic _generate_combinations() functions.

        Args:
            opportunities: List of all opportunities
            available_cash: Available cash in EUR
            max_depth: Maximum sequence depth

        Returns:
            List of action sequences
        """
        sequences: List[List[ActionCandidate]] = []

        base_params = {
            "available_cash_eur": available_cash,
            "max_depth": max_depth,
        }

        for generator in self.factory.get_generators():
            params = self.factory.get_generator_params(generator.name)

            # Merge params
            full_params = {**generator.default_params(), **base_params, **params}

            try:
                gen_sequences = generator.generate(opportunities, full_params)
                sequences.extend(gen_sequences)
                logger.debug(
                    f"Generator '{generator.name}' created {len(gen_sequences)} sequences"
                )
            except Exception as e:
                logger.error(f"Generator '{generator.name}' failed: {e}")

        return sequences

    async def filter_sequences(
        self,
        sequences: List[List[ActionCandidate]],
        securities: List[Security],
    ) -> List[List[ActionCandidate]]:
        """Filter sequences using enabled filters.

        This replaces monolithic filter functions.

        Args:
            sequences: List of sequences to filter
            securities: Available securities

        Returns:
            Filtered list of sequences
        """
        filtered = sequences

        base_params = {
            "securities": securities,
        }

        for filter_instance in self.factory.get_filters():
            params = self.factory.get_filter_params(filter_instance.name)

            # Merge params
            full_params = {**filter_instance.default_params(), **base_params, **params}

            try:
                filtered = await filter_instance.filter(filtered, full_params)
                logger.debug(
                    f"Filter '{filter_instance.name}': "
                    f"{len(sequences)} -> {len(filtered)} sequences"
                )
            except Exception as e:
                logger.error(f"Filter '{filter_instance.name}' failed: {e}")

        return filtered

    def get_configuration_summary(self) -> Dict[str, Any]:
        """Get summary of current configuration.

        Returns:
            Dict with configuration details
        """
        return {
            "name": self.config.name,
            "description": self.config.description,
            "max_depth": self.config.max_depth,
            "priority_threshold": self.config.priority_threshold,
            "enabled_calculators": self.config.get_enabled_calculators(),
            "enabled_patterns": self.config.get_enabled_patterns(),
            "enabled_generators": self.config.get_enabled_generators(),
            "enabled_filters": self.config.get_enabled_filters(),
            "total_modules": (
                len(self.factory.get_calculators())
                + len(self.factory.get_patterns())
                + len(self.factory.get_generators())
                + len(self.factory.get_filters())
            ),
        }
