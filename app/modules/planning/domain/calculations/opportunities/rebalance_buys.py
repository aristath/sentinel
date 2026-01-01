"""Rebalance buy opportunity calculator.

Identifies underweight areas that should be increased for rebalancing.
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
from app.modules.trading.domain.trade_sizing_service import TradeSizingService


class RebalanceBuysCalculator(OpportunityCalculator):
    """Identifies underweight areas to increase for rebalancing."""

    def __init__(self, exchange_rate_service: Optional[ExchangeRateService] = None):
        self.exchange_rate_service = exchange_rate_service

    @property
    def name(self) -> str:
        return "rebalance_buys"

    def default_params(self) -> Dict[str, Any]:
        return {
            "underweight_threshold": 0.05,  # 5%+ underweight triggers rebalance
            "base_trade_amount_eur": 1000.0,  # Base trade amount
        }

    async def calculate(
        self,
        context: OpportunityContext,
        params: Dict[str, Any],
    ) -> List[ActionCandidate]:
        """
        Identify rebalance buy opportunities (underweight areas to increase).

        Checks country/industry allocations against targets and suggests
        buys in underweight groups.

        Args:
            context: Portfolio context with allocations and targets
            params: Calculator parameters

        Returns:
            List of buy ActionCandidates for underweight areas
        """
        opportunities: List[ActionCandidate] = []

        # Require allocation data
        if not context.country_allocations or not context.country_to_group:
            return opportunities
        if not context.country_weights:
            return opportunities

        underweight_threshold = params.get("underweight_threshold", 0.05)
        base_trade_amount = params.get("base_trade_amount_eur", 1000.0)

        for security in context.securities:
            if not security.allow_buy:
                continue

            # Get current price from position if exists
            price = None
            pos = next(
                (p for p in context.positions if p.symbol == security.symbol), None
            )
            if pos:
                price = pos.current_price

            if not price or price <= 0:
                continue

            # Get quality score if available
            quality_score = 0.5
            if context.security_scores:
                quality_score = context.security_scores.get(security.symbol, 0.5)

            # Check if this security's country group is underweight
            country = security.country
            if not country:
                continue

            group = context.country_to_group.get(country, "OTHER")
            target = context.country_weights.get(group, 0)
            current = context.country_allocations.get(group, 0)

            if current < target - underweight_threshold:
                underweight = target - current

                # Calculate buy quantity
                exchange_rate = 1.0
                if security.currency and security.currency != "EUR":
                    if self.exchange_rate_service:
                        exchange_rate = await self.exchange_rate_service.get_rate(
                            security.currency, "EUR"
                        )

                sized = TradeSizingService.calculate_buy_quantity(
                    target_value_eur=base_trade_amount,
                    price=price,
                    min_lot=security.min_lot,
                    exchange_rate=exchange_rate,
                )

                # Apply priority multiplier
                base_priority = underweight * 2 + quality_score * 0.5
                security_multiplier = security.priority_multiplier if security else 1.0
                final_priority = base_priority * security_multiplier

                opportunities.append(
                    ActionCandidate(
                        side=TradeSide.BUY,
                        symbol=security.symbol,
                        name=security.name,
                        quantity=sized.quantity,
                        price=price,
                        value_eur=sized.value_eur,
                        currency=security.currency or "EUR",
                        priority=final_priority,
                        reason=f"Underweight {group} by {underweight*100:.1f}%",
                        tags=["rebalance", f"underweight_{group.lower()}"],
                    )
                )

        return opportunities


# Auto-register this calculator
_rebalance_buys_calculator = RebalanceBuysCalculator()
opportunity_calculator_registry.register(
    _rebalance_buys_calculator.name, _rebalance_buys_calculator
)
