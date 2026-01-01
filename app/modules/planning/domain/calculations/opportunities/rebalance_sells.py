"""Rebalance sell opportunity calculator.

Identifies overweight positions that should be reduced for rebalancing.
"""

from typing import Any, Dict, List, Optional

from app.domain.services.exchange_rate_service import ExchangeRateService
from app.domain.value_objects.trade_side import TradeSide
from app.modules.planning.domain.calculations.opportunities.base import (
    OpportunityCalculator,
    OpportunityContext,
    opportunity_calculator_registry,
)
from app.modules.planning.domain.models import ActionCandidate


class RebalanceSellsCalculator(OpportunityCalculator):
    """Identifies overweight positions to trim for rebalancing."""

    def __init__(self, exchange_rate_service: Optional[ExchangeRateService] = None):
        self.exchange_rate_service = exchange_rate_service

    @property
    def name(self) -> str:
        return "rebalance_sells"

    def default_params(self) -> Dict[str, Any]:
        return {
            "overweight_threshold": 0.05,  # 5%+ overweight triggers rebalance
            "max_sell_pct": 0.3,  # Max 30% of position per rebalance
        }

    async def calculate(
        self,
        context: OpportunityContext,
        params: Dict[str, Any],
    ) -> List[ActionCandidate]:
        """
        Identify rebalance sell opportunities (overweight positions to reduce).

        Checks each position against country/industry allocation targets
        and suggests sells when groups are overweight.

        Args:
            context: Portfolio context with allocations and targets
            params: Calculator parameters

        Returns:
            List of sell ActionCandidates for overweight positions
        """
        opportunities: List[ActionCandidate] = []

        # Require allocation data
        if not context.country_allocations or not context.country_to_group:
            return opportunities
        if not context.country_weights:
            return opportunities

        overweight_threshold = params.get("overweight_threshold", 0.05)
        max_sell_pct = params.get("max_sell_pct", 0.3)

        for pos in context.positions:
            security = context.stocks_by_symbol.get(pos.symbol)
            if not security or not security.allow_sell:
                continue

            position_value = pos.market_value_eur or 0
            if position_value <= 0:
                continue

            # Check if this security's country group is overweight
            country = security.country
            if not country:
                continue

            group = context.country_to_group.get(country, "OTHER")
            if group not in context.country_allocations:
                continue

            target = context.country_weights.get(group, 0)
            current = context.country_allocations[group]

            if current > target + overweight_threshold:
                overweight = current - target
                sell_value_eur = min(
                    position_value * max_sell_pct,
                    overweight * context.total_portfolio_value_eur,
                )

                # Calculate quantity
                exchange_rate = 1.0
                if pos.currency and pos.currency != "EUR":
                    if self.exchange_rate_service:
                        exchange_rate = await self.exchange_rate_service.get_rate(
                            pos.currency, "EUR"
                        )

                sell_value_native = sell_value_eur * exchange_rate
                sell_qty = int(sell_value_native / (pos.current_price or pos.avg_price))

                if sell_qty > 0:
                    # Apply priority multiplier inversely
                    base_priority = overweight * 2
                    security_multiplier = (
                        security.priority_multiplier if security else 1.0
                    )
                    final_priority = base_priority / security_multiplier

                    opportunities.append(
                        ActionCandidate(
                            side=TradeSide.SELL,
                            symbol=pos.symbol,
                            name=security.name,
                            quantity=sell_qty,
                            price=pos.current_price or pos.avg_price,
                            value_eur=sell_value_eur,
                            currency=pos.currency or "EUR",
                            priority=final_priority,
                            reason=f"Overweight {group} by {overweight*100:.1f}%",
                            tags=["rebalance", f"overweight_{group.lower()}"],
                        )
                    )

        return opportunities


# Auto-register this calculator
_rebalance_sells_calculator = RebalanceSellsCalculator()
opportunity_calculator_registry.register(
    _rebalance_sells_calculator.name, _rebalance_sells_calculator
)
