"""Rebalance buy opportunity identification.

Identifies underweight areas that should be increased for rebalancing.
"""

from typing import Dict, List, Optional

from app.domain.models import Stock
from app.domain.planning.holistic_planner import ActionCandidate
from app.domain.scoring.models import PortfolioContext
from app.domain.services.exchange_rate_service import ExchangeRateService
from app.domain.services.trade_sizing_service import TradeSizingService
from app.domain.value_objects.trade_side import TradeSide


async def identify_rebalance_buy_opportunities(
    stocks: List[Stock],
    portfolio_context: PortfolioContext,
    geo_allocations: Dict[str, float],
    batch_prices: Dict[str, float],
    base_trade_amount: float,
    exchange_rate_service: Optional[ExchangeRateService] = None,
) -> List[ActionCandidate]:
    """
    Identify rebalance buy opportunities (underweight areas to increase).

    Args:
        stocks: Available stocks
        portfolio_context: Portfolio context with weights
        geo_allocations: Current geography allocation percentages
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

        # Check for rebalance buys (underweight country/industry)
        # TODO: Update to use country_weights and country_allocations when allocation system is updated
        country = stock.country
        if country:
            target = 0.33 + portfolio_context.geo_weights.get(country, 0) * 0.15
            current = geo_allocations.get(country, 0)
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

                opportunities.append(
                    ActionCandidate(
                        side=TradeSide.BUY,
                        symbol=stock.symbol,
                        name=stock.name,
                        quantity=sized.quantity,
                        price=price,
                        value_eur=sized.value_eur,
                        currency=stock.currency or "EUR",
                        priority=underweight * 2 + quality_score * 0.5,
                        reason=f"Underweight {country} by {underweight*100:.1f}%",
                        tags=["rebalance", f"underweight_{country.lower()}"],
                    )
                )

    return opportunities
