"""Rebalance buy opportunity identification.

Identifies underweight areas that should be increased for rebalancing.
"""

from typing import Dict, List, Optional

from app.domain.models import Stock
from app.domain.scoring.models import PortfolioContext
from app.domain.services.exchange_rate_service import ExchangeRateService
from app.domain.services.trade_sizing_service import TradeSizingService
from app.domain.value_objects.trade_side import TradeSide
from app.modules.planning.domain.holistic_planner import ActionCandidate


async def identify_rebalance_buy_opportunities(
    stocks: List[Stock],
    portfolio_context: PortfolioContext,
    country_allocations: Dict[str, float],
    batch_prices: Dict[str, float],
    base_trade_amount: float,
    exchange_rate_service: Optional[ExchangeRateService] = None,
) -> List[ActionCandidate]:
    """
    Identify rebalance buy opportunities (underweight areas to increase).

    Args:
        stocks: Available stocks
        portfolio_context: Portfolio context with weights
        country_allocations: Current country allocation percentages
        batch_prices: Dict mapping symbol to current price
        base_trade_amount: Base trade amount in EUR
        exchange_rate_service: Optional exchange rate service for currency conversion

    Returns:
        List of ActionCandidate for rebalance buy opportunities
    """
    opportunities = []

    for stock in stocks:
        if not stock.allow_buy:
            continue

        price = batch_prices.get(stock.symbol)
        if not price or price <= 0:
            continue

        # Get quality score
        quality_score = (
            portfolio_context.stock_scores.get(stock.symbol, 0.5)
            if portfolio_context.stock_scores
            else 0.5
        )

        # Check for rebalance buys (underweight group)
        # Map individual country to group
        country = stock.country
        if country:
            country_to_group = portfolio_context.country_to_group or {}
            group = country_to_group.get(country, "OTHER")

            # target_pct is already a percentage (0-1), no conversion needed
            target = portfolio_context.country_weights.get(group, 0)
            current = country_allocations.get(group, 0)
            if current < target - 0.05:  # 5%+ underweight
                underweight = target - current
                exchange_rate = 1.0
                if stock.currency and stock.currency != "EUR" and exchange_rate_service:
                    exchange_rate = await exchange_rate_service.get_rate(
                        stock.currency or "EUR", "EUR"
                    )
                sized = TradeSizingService.calculate_buy_quantity(
                    target_value_eur=base_trade_amount,
                    price=price,
                    min_lot=stock.min_lot,
                    exchange_rate=exchange_rate,
                )

                # Apply priority multiplier: higher multiplier = higher buy priority
                base_priority = underweight * 2 + quality_score * 0.5
                multiplier = stock.priority_multiplier if stock else 1.0
                final_priority = base_priority * multiplier

                opportunities.append(
                    ActionCandidate(
                        side=TradeSide.BUY,
                        symbol=stock.symbol,
                        name=stock.name,
                        quantity=sized.quantity,
                        price=price,
                        value_eur=sized.value_eur,
                        currency=stock.currency or "EUR",
                        priority=final_priority,
                        reason=f"Underweight {group} by {underweight*100:.1f}%",
                        tags=["rebalance", f"underweight_{group.lower()}"],
                    )
                )

    return opportunities
