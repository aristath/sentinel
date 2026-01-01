"""Constraint relaxation scenario generator.

Generates "what if" sequences by relaxing normal trading constraints.
Useful for research and understanding the impact of various rules.
"""

from typing import Any, Dict, List

from app.modules.planning.domain.calculations.sequences.base import (
    SequenceGenerator,
    sequence_generator_registry,
)
from app.modules.planning.domain.models import ActionCandidate


class ConstraintRelaxationGenerator(SequenceGenerator):
    """
    Generates sequences with relaxed constraints.

    Explores "what if" scenarios by temporarily relaxing constraints
    that normally limit trading decisions. This helps understand:
    - What opportunities exist if sell restrictions were lifted
    - What trades would be possible with smaller lot sizes
    - Impact of constraint enforcement on portfolio optimization

    WARNING: These are research scenarios only. Do not execute
    constraint-relaxed sequences without careful review.

    Examples of constraints that can be relaxed:
    - allow_sell: Allow sells even if disabled in bucket settings
    - min_lot: Allow fractional shares or lots below normal minimum
    - max_position_size: Allow larger position sizes
    - cooldown_periods: Ignore buy/sell cooldown rules
    """

    @property
    def name(self) -> str:
        return "constraint_relaxation"

    def default_params(self) -> Dict[str, Any]:
        return {
            "relax_allow_sell": True,  # Generate sell opportunities even if disabled
            "relax_min_lot": True,  # Allow smaller lot sizes
            "relax_max_position": False,  # Allow exceeding position limits
            "relax_cooldown": False,  # Ignore cooldown periods
            "min_shares_relaxed": 0.1,  # Minimum shares when lot relaxed (fractional)
        }

    def generate(
        self,
        opportunities: List[ActionCandidate],
        params: Dict[str, Any],
    ) -> List[List[ActionCandidate]]:
        """
        Generate constraint-relaxed sequences.

        This generator creates variations of opportunities with relaxed
        constraints. Since we receive opportunities that may have already
        been filtered by constraints, we can:
        1. Include sell opportunities even if allow_sell=False
        2. Reduce lot sizes below normal minimums
        3. Combine actions that would normally violate constraints

        Args:
            opportunities: List of candidate actions
            params: Generator parameters

        Returns:
            List of action sequences with relaxed constraints
        """
        relax_allow_sell = params.get("relax_allow_sell", True)
        relax_min_lot = params.get("relax_min_lot", True)
        min_shares_relaxed = params.get("min_shares_relaxed", 0.1)

        sequences: List[List[ActionCandidate]] = []

        from app.domain.value_objects.trade_side import TradeSide

        # Separate opportunities by side
        sells = [opp for opp in opportunities if opp.side == TradeSide.SELL]
        buys = [opp for opp in opportunities if opp.side == TradeSide.BUY]

        # Scenario 1: If relax_allow_sell=True, generate sell-only sequences
        # (These might not exist if allow_sell was False)
        if relax_allow_sell and sells:
            for sell in sells:
                sequences.append([sell])

        # Scenario 2: If relax_min_lot=True, generate fractional share sequences
        if relax_min_lot:
            for opp in opportunities:
                # Create variations with smaller lot sizes
                fractional_sizes = [0.5, 0.25, 0.1]
                for fraction in fractional_sizes:
                    relaxed_quantity = opp.quantity * fraction
                    if relaxed_quantity < min_shares_relaxed:
                        continue

                    relaxed_candidate = ActionCandidate(
                        side=opp.side,
                        symbol=opp.symbol,
                        name=opp.name,
                        quantity=int(relaxed_quantity),
                        price=opp.price,
                        value_eur=opp.value_eur * fraction,
                        currency=opp.currency,
                        priority=opp.priority,
                        reason=f"{opp.reason} [Relaxed lot: {relaxed_quantity:.2f} shares]",
                        tags=opp.tags + ["relaxed_lot"],
                    )
                    sequences.append([relaxed_candidate])

        # Scenario 3: Generate mixed sell+buy sequences that might violate
        # normal ordering or cash constraints (research scenarios)
        if relax_allow_sell and sells and buys:
            # Create sequences that buy before selling (reverse normal order)
            for buy in buys[:5]:  # Limit to top 5 to avoid explosion
                for sell in sells[:5]:
                    # Buy first, then sell (might need sell proceeds normally)
                    sequences.append([buy, sell])

        return sequences


# Auto-register
_constraint_relaxation_generator = ConstraintRelaxationGenerator()
sequence_generator_registry.register(
    _constraint_relaxation_generator.name, _constraint_relaxation_generator
)
