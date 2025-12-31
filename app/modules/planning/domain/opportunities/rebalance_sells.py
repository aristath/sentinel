"""Rebalance sell opportunity identification.

Identifies overweight positions that should be reduced for rebalancing.
"""

from typing import Dict, List, Optional

from app.domain.models import Position, Security
from app.domain.services.exchange_rate_service import ExchangeRateService
from app.domain.value_objects.trade_side import TradeSide
from app.modules.planning.domain.holistic_planner import ActionCandidate
from app.modules.scoring.domain.models import PortfolioContext


async def identify_rebalance_sell_opportunities(
    positions: List[Position],
    stocks_by_symbol: dict[str, Security],
    portfolio_context: PortfolioContext,
    country_allocations: Dict[str, float],
    total_value: float,
    exchange_rate_service: Optional[ExchangeRateService] = None,
) -> List[ActionCandidate]:
    """
    Identify rebalance sell opportunities (overweight positions to reduce).

    Args:
        positions: Current positions
        stocks_by_symbol: Dict mapping symbol to Security
        portfolio_context: Portfolio context with weights
        country_allocations: Current country allocation percentages
        total_value: Total portfolio value
        exchange_rate_service: Optional exchange rate service for currency conversion

    Returns:
        List of ActionCandidate for rebalance sell opportunities
    """
    opportunities = []

    for pos in positions:
        security = stocks_by_symbol.get(pos.symbol)
        if not security or not security.allow_sell:
            continue

        position_value = pos.market_value_eur or 0
        if position_value <= 0:
            continue

        # Check for rebalance sells (overweight group)
        # Map individual country to group
        country = security.country
        if country:
            country_to_group = portfolio_context.country_to_group or {}
            group = country_to_group.get(country, "OTHER")

            if group in country_allocations:
                # target_pct is already a percentage (0-1), no conversion needed
                target = portfolio_context.country_weights.get(group, 0)
                if country_allocations[group] > target + 0.05:  # 5%+ overweight
                    overweight = country_allocations[group] - target
                    sell_value_eur = min(position_value * 0.3, overweight * total_value)

                    # Calculate quantity
                    exchange_rate = 1.0
                    if pos.currency and pos.currency != "EUR":
                        if exchange_rate_service:
                            exchange_rate = await exchange_rate_service.get_rate(
                                pos.currency, "EUR"
                            )
                        else:
                            exchange_rate = 1.0  # Fallback if service not provided
                    sell_value_native = sell_value_eur * exchange_rate
                    sell_qty = int(
                        sell_value_native / (pos.current_price or pos.avg_price)
                    )

                    if sell_qty > 0:
                        # Apply priority multiplier inversely: higher multiplier = lower sell priority
                        base_priority = overweight * 2
                        multiplier = security.priority_multiplier if security else 1.0
                        final_priority = base_priority / multiplier

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
