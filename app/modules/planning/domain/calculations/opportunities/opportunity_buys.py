"""Opportunity buy calculator.

Identifies high-quality securities at good prices for general opportunity buys.
"""

from typing import Any, Dict, List, Optional

from app.domain.services.exchange_rate_service import ExchangeRateService
from app.domain.value_objects.trade_side import TradeSide
from app.modules.planning.domain.calculations.opportunities.base import (
    OpportunityCalculator,
    OpportunityContext,
    opportunity_calculator_registry,
)
from app.modules.planning.domain.holistic_planner import ActionCandidate
from app.modules.trading.domain.trade_sizing_service import TradeSizingService


class OpportunityBuysCalculator(OpportunityCalculator):
    """Identifies high-quality opportunities based on scores."""

    def __init__(self, exchange_rate_service: Optional[ExchangeRateService] = None):
        self.exchange_rate_service = exchange_rate_service

    @property
    def name(self) -> str:
        return "opportunity_buys"

    def default_params(self) -> Dict[str, Any]:
        return {
            "min_quality_score": 0.7,  # Minimum quality score required
            "base_trade_amount_eur": 1000.0,  # Base trade amount
        }

    async def calculate(
        self,
        context: OpportunityContext,
        params: Dict[str, Any],
    ) -> List[ActionCandidate]:
        """
        Identify general opportunity buy opportunities.

        Finds high-quality securities at good prices using:
        - Fundamental + technical + analyst scoring
        - Quality threshold filtering
        - Priority based on final scores

        Args:
            context: Portfolio context with securities
            params: Calculator parameters

        Returns:
            List of buy ActionCandidates for quality opportunities
        """
        opportunities = []
        min_quality_score = params.get("min_quality_score", 0.7)
        base_trade_amount = params.get("base_trade_amount_eur", 1000.0)

        for security in context.securities:
            if not security.allow_buy:
                continue

            # Use security's quality score from context
            quality_score = 0.5
            if context.security_scores:
                quality_score = context.security_scores.get(security.symbol, 0.5)
            if quality_score < min_quality_score:
                continue

            # Get current price
            # Try to find current price from positions first, or use security price
            price = None
            pos = next(
                (p for p in context.positions if p.symbol == security.symbol), None
            )
            if pos:
                price = pos.current_price

            if not price or price <= 0:
                # Skip if no valid price available
                continue

            # Calculate buy quantity using trade sizing service
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

            # Apply priority multiplier: higher multiplier = higher buy priority
            base_priority = quality_score
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
                    reason=f"High quality (score: {quality_score:.2f})",
                    tags=["quality", "opportunity"],
                )
            )

        return opportunities


# Auto-register this calculator
_opportunity_buys_calculator = OpportunityBuysCalculator()
opportunity_calculator_registry.register(
    _opportunity_buys_calculator.name, _opportunity_buys_calculator
)
