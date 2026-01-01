"""Adaptive pattern generator.

Generates patterns based on portfolio gaps (geographic, sector, risk).
"""

from typing import Any, Dict, List, Optional, Tuple

from app.domain.models import Security
from app.modules.planning.domain.calculations.patterns.base import (
    PatternGenerator,
    pattern_generator_registry,
)
from app.modules.planning.domain.models import ActionCandidate
from app.modules.scoring.domain.models import PortfolioContext


class AdaptivePattern(PatternGenerator):
    """Adaptive pattern: Portfolio gap analysis and targeted rebalancing."""

    @property
    def name(self) -> str:
        return "adaptive"

    def default_params(self) -> Dict[str, Any]:
        return {
            "max_depth": 5,
            "available_cash_eur": 0.0,
            "portfolio_context": None,  # PortfolioContext instance
            "securities_by_symbol": None,  # Dict[str, Security]
        }

    def generate(
        self,
        opportunities: Dict[str, List[ActionCandidate]],
        params: Dict[str, Any],
    ) -> List[List[ActionCandidate]]:
        """
        Generate adaptive patterns based on portfolio gaps.

        Analyzes portfolio state and generates patterns targeting:
        - Geographic gaps (underweight countries)
        - Sector gaps (underweight industries)

        Args:
            opportunities: Dict of categorized opportunities
            params: Pattern parameters (must include portfolio_context, securities_by_symbol)

        Returns:
            List of adaptive pattern sequences (may be multiple)
        """
        max_depth = params.get("max_depth", 5)
        available_cash = params.get("available_cash_eur", 0.0)
        portfolio_context: Optional[PortfolioContext] = params.get("portfolio_context")
        securities_by_symbol: Optional[Dict[str, Security]] = params.get(
            "securities_by_symbol"
        )

        sequences: List[List[ActionCandidate]] = []

        if not portfolio_context or portfolio_context.total_value <= 0:
            return sequences

        # Calculate current allocations by group
        country_to_group = portfolio_context.country_to_group or {}
        industry_to_group = portfolio_context.industry_to_group or {}

        current_group_country_allocations: Dict[str, float] = {}
        current_group_industry_allocations: Dict[str, float] = {}

        for symbol, value in portfolio_context.positions.items():
            if value <= 0:
                continue

            weight = value / portfolio_context.total_value

            # Map country to group and aggregate
            if portfolio_context.security_countries:
                country = portfolio_context.security_countries.get(symbol)
                if country:
                    group = country_to_group.get(country, "OTHER")
                    current_group_country_allocations[group] = (
                        current_group_country_allocations.get(group, 0) + weight
                    )

            # Map industry to group and aggregate
            if portfolio_context.security_industries:
                industries_str = portfolio_context.security_industries.get(symbol)
                if industries_str:
                    industries = [i.strip() for i in industries_str.split(",")]
                    for industry in industries:
                        if industry:
                            group = industry_to_group.get(industry, "OTHER")
                            current_group_industry_allocations[group] = (
                                current_group_industry_allocations.get(group, 0)
                                + weight
                            )

        # Identify geographic gaps
        geographic_gaps: List[Tuple[str, float]] = []
        if portfolio_context.country_weights:
            for group, target_pct in portfolio_context.country_weights.items():
                current_weight = current_group_country_allocations.get(group, 0)
                gap = target_pct - current_weight
                if gap > 0.02:  # At least 2% gap
                    geographic_gaps.append((group, gap))

        # Identify sector gaps
        sector_gaps: List[Tuple[str, float]] = []
        if portfolio_context.industry_weights:
            for group, target_pct in portfolio_context.industry_weights.items():
                current_weight = current_group_industry_allocations.get(group, 0)
                gap = target_pct - current_weight
                if gap > 0.01:  # At least 1% gap
                    sector_gaps.append((group, gap))

        # Sort gaps by size
        geographic_gaps.sort(key=lambda x: x[1], reverse=True)
        sector_gaps.sort(key=lambda x: x[1], reverse=True)

        # Pattern 1: Geographic rebalance
        if geographic_gaps and securities_by_symbol:
            geo_buys: List[ActionCandidate] = []
            all_buys = opportunities.get("rebalance_buys", []) + opportunities.get(
                "opportunity_buys", []
            )
            running_cash = available_cash

            # Find buys for underweight countries
            for country, gap in geographic_gaps[:3]:  # Top 3 gaps
                for candidate in all_buys:
                    if len(geo_buys) >= max_depth or running_cash < candidate.value_eur:
                        break
                    security = securities_by_symbol.get(candidate.symbol)
                    if security and security.country == country:
                        if candidate not in geo_buys:
                            geo_buys.append(candidate)
                            running_cash -= candidate.value_eur

            if geo_buys:
                sequences.append(geo_buys)

        # Pattern 2: Sector rotation
        if sector_gaps and securities_by_symbol:
            sector_buys: List[ActionCandidate] = []
            all_buys = opportunities.get("rebalance_buys", []) + opportunities.get(
                "opportunity_buys", []
            )
            running_cash = available_cash

            # Find buys for underweight industries
            for industry, gap in sector_gaps[:3]:  # Top 3 gaps
                for candidate in all_buys:
                    if (
                        len(sector_buys) >= max_depth
                        or running_cash < candidate.value_eur
                    ):
                        break
                    security = securities_by_symbol.get(candidate.symbol)
                    if security and security.industry:
                        industries = [i.strip() for i in security.industry.split(",")]
                        if industry in industries:
                            if candidate not in sector_buys:
                                sector_buys.append(candidate)
                                running_cash -= candidate.value_eur

            if sector_buys:
                sequences.append(sector_buys)

        return sequences


# Auto-register this pattern
_adaptive_pattern = AdaptivePattern()
pattern_generator_registry.register(_adaptive_pattern.name, _adaptive_pattern)
