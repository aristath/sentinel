"""Opportunity buy identification.

Identifies high-quality stocks at good prices for general opportunity buys.
"""

from typing import Dict, List, Optional

from app.domain.models import Stock
from app.domain.planning.holistic_planner import ActionCandidate
from app.domain.scoring.models import PortfolioContext
from app.domain.services.exchange_rate_service import ExchangeRateService
from app.domain.services.trade_sizing_service import TradeSizingService
from app.domain.value_objects.trade_side import TradeSide


async def identify_opportunity_buy_opportunities(
    stocks: List[Stock],
    portfolio_context: PortfolioContext,
    batch_prices: Dict[str, float],
    base_trade_amount: float,
    min_quality_score: float = 0.7,
    exchange_rate_service: Optional[ExchangeRateService] = None,
) -> List[ActionCandidate]:
    """
    Identify general opportunity buy opportunities (high-quality stocks at good prices).

    Args:
        stocks: Available stocks
        portfolio_context: Portfolio context with scores
        batch_prices: Dict mapping symbol to current price
        base_trade_amount: Base trade amount in EUR
        min_quality_score: Minimum quality score required (default 0.7)
        exchange_rate_service: Optional exchange rate service for currency conversion

    Returns:
        List of ActionCandidate for opportunity buy opportunities
    """
    opportunities = []

    for stock in stocks:
        if not stock.allow_buy:
            continue

        price = batch_prices.get(stock.symbol)
        if not price or price <= 0:
            continue

        # Get quality score
        quality_score = portfolio_context.stock_scores.get(stock.symbol, 0.5)
        if quality_score < min_quality_score:
            continue

        # General opportunity buys (high quality at good price)
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
                priority=quality_score,
                reason=f"High quality (score: {quality_score:.2f})",
                tags=["quality", "opportunity"],
            )
        )

    return opportunities
