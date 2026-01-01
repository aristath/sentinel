"""Profit-taking opportunity calculator.

Identifies windfall positions that should be trimmed for profit-taking.
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
from app.modules.scoring.domain.windfall import get_windfall_recommendation


class ProfitTakingCalculator(OpportunityCalculator):
    """Identifies positions with windfall gains to sell."""

    def __init__(self, exchange_rate_service: Optional[ExchangeRateService] = None):
        self.exchange_rate_service = exchange_rate_service

    @property
    def name(self) -> str:
        return "profit_taking"

    def default_params(self) -> Dict[str, Any]:
        return {
            "windfall_threshold": 0.30,  # 30% excess gain
            "priority_weight": 1.2,  # Prioritize profit-taking
        }

    async def calculate(
        self,
        context: OpportunityContext,
        params: Dict[str, Any],
    ) -> List[ActionCandidate]:
        """
        Identify profit-taking opportunities (windfall positions to trim).

        Checks each position for windfall gains (exceeding expected returns)
        and suggests selling a percentage to lock in profits.

        Args:
            context: Portfolio context with positions and securities
            params: Calculator parameters (windfall_threshold, priority_weight)

        Returns:
            List of sell ActionCandidates for windfall positions
        """
        opportunities = []

        for pos in context.positions:
            security = context.stocks_by_symbol.get(pos.symbol)
            if not security or not security.allow_sell:
                continue

            position_value = pos.market_value_eur or 0
            if position_value <= 0:
                continue

            # Check for windfall
            windfall_rec = await get_windfall_recommendation(
                symbol=pos.symbol,
                current_price=pos.current_price or pos.avg_price,
                avg_price=pos.avg_price,
                first_bought_at=(
                    pos.first_bought_at if hasattr(pos, "first_bought_at") else None
                ),
            )

            if windfall_rec.get("recommendation", {}).get("take_profits"):
                rec = windfall_rec["recommendation"]
                sell_pct = rec["suggested_sell_pct"] / 100
                sell_qty = int(pos.quantity * sell_pct)
                sell_value = sell_qty * (pos.current_price or pos.avg_price)

                # Convert to EUR
                exchange_rate = 1.0
                if pos.currency and pos.currency != "EUR":
                    if self.exchange_rate_service:
                        exchange_rate = await self.exchange_rate_service.get_rate(
                            pos.currency, "EUR"
                        )
                    else:
                        exchange_rate = 1.0  # Fallback
                sell_value_eur = (
                    sell_value / exchange_rate if exchange_rate > 0 else sell_value
                )

                # Apply priority multiplier inversely: higher multiplier = lower sell priority
                base_priority = windfall_rec.get("windfall_score", 0.5) + 0.5
                multiplier = params.get("priority_weight", 1.2)
                security_multiplier = security.priority_multiplier if security else 1.0
                final_priority = (base_priority * multiplier) / security_multiplier

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
                        reason=rec["reason"],
                        tags=["windfall", "profit_taking"],
                    )
                )

        return opportunities


# Auto-register this calculator
_profit_taking_calculator = ProfitTakingCalculator()
opportunity_calculator_registry.register(
    _profit_taking_calculator.name, _profit_taking_calculator
)
