"""Averaging down opportunity calculator.

Identifies quality securities that are down and present averaging down opportunities.
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


class AveragingDownCalculator(OpportunityCalculator):
    """Identifies quality positions that dipped to buy more."""

    def __init__(self, exchange_rate_service: Optional[ExchangeRateService] = None):
        self.exchange_rate_service = exchange_rate_service

    @property
    def name(self) -> str:
        return "averaging_down"

    def default_params(self) -> Dict[str, Any]:
        return {
            "max_drawdown": -0.15,  # Maximum drawdown to consider (-15%)
            "min_quality_score": 0.6,  # Minimum quality score required
            "priority_weight": 0.9,  # Slightly lower priority than new buys
            "base_trade_amount_eur": 1000.0,  # Base trade amount
        }

    async def calculate(
        self,
        context: OpportunityContext,
        params: Dict[str, Any],
    ) -> List[ActionCandidate]:
        """
        Identify averaging down opportunities (quality dips to buy more of).

        Only considers positions that:
        - Are currently owned
        - Have dropped below average cost
        - Still have good quality scores (not falling knives)
        - Are within the max drawdown threshold

        Args:
            context: Portfolio context with positions and securities
            params: Calculator parameters

        Returns:
            List of buy ActionCandidates for averaging down
        """
        opportunities = []
        max_drawdown = params.get("max_drawdown", -0.15)
        min_quality_score = params.get("min_quality_score", 0.6)
        base_trade_amount = params.get("base_trade_amount_eur", 1000.0)

        # Build position map for quick lookup
        positions_by_symbol = {pos.symbol: pos for pos in context.positions}

        for security in context.securities:
            if not security.allow_buy:
                continue

            # Must already own this position
            pos = positions_by_symbol.get(security.symbol)
            if not pos or pos.quantity <= 0:
                continue

            current_price = pos.current_price or pos.avg_price
            if not current_price or current_price <= 0:
                continue

            avg_price = pos.avg_price
            if not avg_price or avg_price <= 0:
                continue

            # Calculate loss percentage
            loss_pct = (current_price - avg_price) / avg_price

            # Only consider if down significantly (but not too much)
            if loss_pct >= 0 or loss_pct < max_drawdown:
                continue

            # Check quality score - must still be high quality
            # (don't catch falling knives)
            quality_score = 0.5
            if context.security_scores:
                quality_score = context.security_scores.get(security.symbol, 0.5)
            if quality_score < min_quality_score:
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
                price=current_price,
                min_lot=security.min_lot,
                exchange_rate=exchange_rate,
            )

            # Apply priority: quality + urgency (bigger drop = higher priority)
            # But use configured weight to adjust overall priority
            base_priority = quality_score + abs(loss_pct)
            priority_weight = params.get("priority_weight", 0.9)
            security_multiplier = security.priority_multiplier if security else 1.0
            final_priority = base_priority * priority_weight * security_multiplier

            opportunities.append(
                ActionCandidate(
                    side=TradeSide.BUY,
                    symbol=security.symbol,
                    name=security.name,
                    quantity=sized.quantity,
                    price=current_price,
                    value_eur=sized.value_eur,
                    currency=security.currency or "EUR",
                    priority=final_priority,
                    reason=f"Quality security down {abs(loss_pct)*100:.0f}%, averaging down",
                    tags=["averaging_down", "buy_low"],
                )
            )

        return opportunities


# Auto-register this calculator
_averaging_down_calculator = AveragingDownCalculator()
opportunity_calculator_registry.register(
    _averaging_down_calculator.name, _averaging_down_calculator
)
