"""Profit-taking opportunity identification.

Identifies windfall positions that should be trimmed for profit-taking.
"""

from typing import List, Optional

from app.domain.models import Position, Security
from app.domain.services.exchange_rate_service import ExchangeRateService
from app.domain.value_objects.trade_side import TradeSide
from app.modules.planning.domain.holistic_planner import ActionCandidate
from app.modules.scoring.domain.windfall import get_windfall_recommendation


async def identify_profit_taking_opportunities(
    positions: List[Position],
    stocks_by_symbol: dict[str, Security],
    exchange_rate_service: Optional[ExchangeRateService] = None,
) -> List[ActionCandidate]:
    """
    Identify profit-taking opportunities (windfall positions to trim).

    Args:
        positions: Current positions
        stocks_by_symbol: Dict mapping symbol to Security
        exchange_rate_service: Optional exchange rate service for currency conversion

    Returns:
        List of ActionCandidate for profit-taking opportunities
    """
    opportunities = []

    for pos in positions:
        security = stocks_by_symbol.get(pos.symbol)
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
                if exchange_rate_service:
                    exchange_rate = await exchange_rate_service.get_rate(
                        pos.currency, "EUR"
                    )
                else:
                    exchange_rate = 1.0  # Fallback if service not provided
            sell_value_eur = (
                sell_value / exchange_rate if exchange_rate > 0 else sell_value
            )

            # Apply priority multiplier inversely: higher multiplier = lower sell priority
            base_priority = windfall_rec.get("windfall_score", 0.5) + 0.5
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
                    reason=rec["reason"],
                    tags=["windfall", "profit_taking"],
                )
            )

    return opportunities
