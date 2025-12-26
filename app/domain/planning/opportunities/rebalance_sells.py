"""Rebalance sell opportunity identification.

Identifies overweight positions that should be reduced for rebalancing.
"""

from typing import Dict, List, Optional

from app.domain.models import Position, Stock
from app.domain.planning.holistic_planner import ActionCandidate
from app.domain.scoring.models import PortfolioContext
from app.domain.services.exchange_rate_service import ExchangeRateService
from app.domain.value_objects.trade_side import TradeSide


async def identify_rebalance_sell_opportunities(
    positions: List[Position],
    stocks_by_symbol: dict[str, Stock],
    portfolio_context: PortfolioContext,
    geo_allocations: Dict[str, float],
    total_value: float,
    exchange_rate_service: Optional[ExchangeRateService] = None,
) -> List[ActionCandidate]:
    """
    Identify rebalance sell opportunities (overweight positions to reduce).

    Args:
        positions: Current positions
        stocks_by_symbol: Dict mapping symbol to Stock
        portfolio_context: Portfolio context with weights
        geo_allocations: Current geography allocation percentages
        total_value: Total portfolio value
        exchange_rate_service: Optional exchange rate service for currency conversion

    Returns:
        List of ActionCandidate for rebalance sell opportunities
    """
    opportunities = []

    for pos in positions:
        stock = stocks_by_symbol.get(pos.symbol)
        if not stock or not stock.allow_sell:
            continue

        position_value = pos.market_value_eur or 0
        if position_value <= 0:
            continue

        # Check for rebalance sells (overweight geography/industry)
        geo = stock.geography
        if geo in geo_allocations:
            target = 0.33 + portfolio_context.geo_weights.get(geo, 0) * 0.15
            if geo_allocations[geo] > target + 0.05:  # 5%+ overweight
                overweight = geo_allocations[geo] - target
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
                sell_qty = int(sell_value_native / (pos.current_price or pos.avg_price))

                if sell_qty > 0:
                    opportunities.append(
                        ActionCandidate(
                            side=TradeSide.SELL,
                            symbol=pos.symbol,
                            name=stock.name,
                            quantity=sell_qty,
                            price=pos.current_price or pos.avg_price,
                            value_eur=sell_value_eur,
                            currency=pos.currency or "EUR",
                            priority=overweight * 2,  # Proportional to overweight
                            reason=f"Overweight {geo} by {overweight*100:.1f}%",
                            tags=["rebalance", f"overweight_{geo.lower()}"],
                        )
                    )

    return opportunities
