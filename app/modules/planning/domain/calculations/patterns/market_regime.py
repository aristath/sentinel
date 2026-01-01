"""Market regime pattern generator.

Generates patterns based on market regime (bull, bear, sideways).
"""

from typing import Any, Dict, List

from app.modules.planning.domain.calculations.patterns.base import (
    PatternGenerator,
    pattern_generator_registry,
)
from app.modules.planning.domain.models import ActionCandidate


class MarketRegimePattern(PatternGenerator):
    """Market regime pattern: Adaptive strategy based on market conditions."""

    @property
    def name(self) -> str:
        return "market_regime"

    def default_params(self) -> Dict[str, Any]:
        return {
            "max_depth": 5,
            "available_cash_eur": 0.0,
            "market_regime": "sideways",  # "bull", "bear", or "sideways"
            "max_opportunities_per_category": 10,
        }

    def generate(
        self,
        opportunities: Dict[str, List[ActionCandidate]],
        params: Dict[str, Any],
    ) -> List[List[ActionCandidate]]:
        """
        Generate patterns based on market regime.

        - Bull market: Favor growth opportunities, reduce defensive positions
        - Bear market: Favor defensive positions, reduce risk exposure
        - Sideways: Balanced approach with focus on quality

        Args:
            opportunities: Dict of categorized opportunities
            params: Pattern parameters (must include market_regime)

        Returns:
            List containing regime-appropriate sequence, or empty list
        """
        max_depth = params.get("max_depth", 5)
        available_cash = params.get("available_cash_eur", 0.0)
        market_regime = params.get("market_regime", "sideways")
        max_per_category = params.get("max_opportunities_per_category", 10)

        sequences: List[List[ActionCandidate]] = []

        # Get top opportunities from each category
        all_profit_taking = opportunities.get("profit_taking", [])[:max_per_category]
        all_rebalance_sells = opportunities.get("rebalance_sells", [])[
            :max_per_category
        ]
        all_averaging = opportunities.get("averaging_down", [])[:max_per_category]
        all_rebalance_buys = opportunities.get("rebalance_buys", [])[:max_per_category]
        all_opportunity = opportunities.get("opportunity_buys", [])[:max_per_category]

        if market_regime == "bull":
            # Bull market: Aggressive growth, take profits, add to winners
            bull_sequence: List[ActionCandidate] = []
            running_cash = available_cash

            # Take profits first
            for candidate in all_profit_taking[:2]:  # Top 2 profit-taking
                if len(bull_sequence) < max_depth:
                    bull_sequence.append(candidate)
                    running_cash += candidate.value_eur

            # Reinvest in high-growth opportunities
            for candidate in all_opportunity + all_rebalance_buys:
                if (
                    len(bull_sequence) >= max_depth
                    or running_cash < candidate.value_eur
                ):
                    break
                if candidate not in bull_sequence:
                    bull_sequence.append(candidate)
                    running_cash -= candidate.value_eur

            if bull_sequence:
                sequences.append(bull_sequence)

        elif market_regime == "bear":
            # Bear market: Defensive, reduce exposure, focus on quality
            bear_sequence: List[ActionCandidate] = []
            running_cash = available_cash

            # Reduce positions (profit-taking and rebalance sells)
            for candidate in all_profit_taking + all_rebalance_sells:
                if len(bear_sequence) >= max_depth // 2:  # Limit sells in bear market
                    break
                if candidate not in bear_sequence:
                    bear_sequence.append(candidate)
                    running_cash += candidate.value_eur

            # Add defensive positions (high quality, stable)
            for candidate in all_averaging:
                if (
                    len(bear_sequence) >= max_depth
                    or running_cash < candidate.value_eur
                ):
                    break
                if candidate not in bear_sequence:
                    bear_sequence.append(candidate)
                    running_cash -= candidate.value_eur

            if bear_sequence:
                sequences.append(bear_sequence)

        else:  # sideways
            # Sideways market: Balanced, focus on quality and rebalancing
            sideways_sequence: List[ActionCandidate] = []
            running_cash = available_cash

            # Rebalance sells first
            for candidate in all_rebalance_sells[:2]:
                if len(sideways_sequence) < max_depth:
                    sideways_sequence.append(candidate)
                    running_cash += candidate.value_eur

            # Quality buys (rebalance and opportunity)
            for candidate in all_rebalance_buys + all_opportunity:
                if (
                    len(sideways_sequence) >= max_depth
                    or running_cash < candidate.value_eur
                ):
                    break
                if candidate not in sideways_sequence:
                    sideways_sequence.append(candidate)
                    running_cash -= candidate.value_eur

            if sideways_sequence:
                sequences.append(sideways_sequence)

        return sequences


# Auto-register this pattern
_market_regime_pattern = MarketRegimePattern()
pattern_generator_registry.register(_market_regime_pattern.name, _market_regime_pattern)
