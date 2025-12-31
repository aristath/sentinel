"""Averaging down opportunity identification.

Identifies quality stocks that are down and present averaging down opportunities.
"""

from typing import Dict, List, Optional

from app.domain.models import Stock
from app.domain.scoring.models import PortfolioContext
from app.domain.services.exchange_rate_service import ExchangeRateService
from app.domain.services.trade_sizing_service import TradeSizingService
from app.domain.value_objects.trade_side import TradeSide
from app.modules.planning.domain.holistic_planner import ActionCandidate


async def identify_averaging_down_opportunities(
    stocks: List[Stock],
    portfolio_context: PortfolioContext,
    batch_prices: Dict[str, float],
    base_trade_amount: float,
    exchange_rate_service: Optional[ExchangeRateService] = None,
) -> List[ActionCandidate]:
    """
    Identify averaging down opportunities (quality dips to buy more of).

    Args:
        stocks: Available stocks
        portfolio_context: Portfolio context with positions and prices
        batch_prices: Dict mapping symbol to current price
        base_trade_amount: Base trade amount in EUR
        exchange_rate_service: Optional exchange rate service for currency conversion

    Returns:
        List of ActionCandidate for averaging down opportunities
    """
    opportunities = []
    avg_price_data = portfolio_context.position_avg_prices or {}

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
        if quality_score < 0.6:  # Need at least 0.6 for averaging down
            continue

        # Check if we own this and it's down (averaging down opportunity)
        current_position = portfolio_context.positions.get(stock.symbol, 0)

        if current_position > 0 and stock.symbol in avg_price_data:
            avg_price = avg_price_data[stock.symbol]
            if avg_price > 0:
                loss_pct = (price - avg_price) / avg_price
                if loss_pct < -0.20:  # Down 20%+ but quality
                    # Calculate buy amount with lot-aware sizing
                    exchange_rate = 1.0
                    if (
                        stock.currency
                        and stock.currency != "EUR"
                        and exchange_rate_service
                    ):
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
                    base_priority = quality_score + abs(loss_pct)
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
                            reason=f"Quality stock down {abs(loss_pct)*100:.0f}%, averaging down",
                            tags=["averaging_down", "buy_low"],
                        )
                    )

    return opportunities
