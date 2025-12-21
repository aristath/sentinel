"""Portfolio allocation and rebalancing logic."""

import logging
from dataclasses import dataclass
from typing import Optional

import aiosqlite

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class AllocationStatus:
    """Current allocation vs target."""
    category: str  # geography or industry
    name: str  # EU, ASIA, US or Technology, etc.
    target_pct: float
    current_pct: float
    current_value: float
    deviation: float  # current - target (negative = underweight)


@dataclass
class PortfolioSummary:
    """Complete portfolio allocation summary."""
    total_value: float
    cash_balance: float
    geographic_allocations: list[AllocationStatus]
    industry_allocations: list[AllocationStatus]


@dataclass
class TradeRecommendation:
    """Recommended trade for rebalancing."""
    symbol: str
    name: str
    side: str  # BUY or SELL
    quantity: float
    estimated_price: float
    estimated_value: float
    reason: str  # Why this trade is recommended


async def get_portfolio_summary(db: aiosqlite.Connection) -> PortfolioSummary:
    """
    Calculate current portfolio allocation vs targets.

    Returns complete summary with geographic and industry breakdowns.
    """
    # Get allocation targets
    cursor = await db.execute(
        "SELECT type, name, target_pct FROM allocation_targets"
    )
    targets = {}
    for row in await cursor.fetchall():
        key = f"{row[0]}:{row[1]}"
        targets[key] = row[2]

    # Get positions with stock info - use market_value_eur for EUR-converted values
    cursor = await db.execute("""
        SELECT p.symbol, p.quantity, p.current_price, p.avg_price,
               p.market_value_eur, s.name, s.geography, s.industry
        FROM positions p
        JOIN stocks s ON p.symbol = s.symbol
    """)
    positions = await cursor.fetchall()

    # Calculate totals by geography and industry using EUR values
    geo_values = {}
    industry_values = {}
    total_value = 0.0

    for pos in positions:
        # Use stored EUR value if available, otherwise fallback to calculation
        eur_value = pos[4]  # market_value_eur
        if eur_value is None or eur_value == 0:
            price = pos[2] or pos[3]  # current_price or avg_price
            eur_value = pos[1] * price

        total_value += eur_value

        geo = pos[6]  # geography (shifted due to new column)
        industry = pos[7]  # industry (shifted due to new column)

        geo_values[geo] = geo_values.get(geo, 0) + eur_value
        industry_values[industry] = industry_values.get(industry, 0) + eur_value

    # Get cash balance from latest snapshot
    cursor = await db.execute("""
        SELECT cash_balance FROM portfolio_snapshots
        ORDER BY date DESC LIMIT 1
    """)
    row = await cursor.fetchone()
    cash_balance = row[0] if row else 0

    # Build allocation status lists
    geo_allocations = []
    for geo in ["EU", "ASIA", "US"]:
        target = targets.get(f"geography:{geo}", 0)
        current_val = geo_values.get(geo, 0)
        current_pct = current_val / total_value if total_value > 0 else 0

        geo_allocations.append(AllocationStatus(
            category="geography",
            name=geo,
            target_pct=target,
            current_pct=round(current_pct, 4),
            current_value=round(current_val, 2),
            deviation=round(current_pct - target, 4),
        ))

    industry_allocations = []
    for industry in ["Technology", "Healthcare", "Finance", "Consumer", "Industrial"]:
        target = targets.get(f"industry:{industry}", 0)
        current_val = industry_values.get(industry, 0)
        current_pct = current_val / total_value if total_value > 0 else 0

        industry_allocations.append(AllocationStatus(
            category="industry",
            name=industry,
            target_pct=target,
            current_pct=round(current_pct, 4),
            current_value=round(current_val, 2),
            deviation=round(current_pct - target, 4),
        ))

    return PortfolioSummary(
        total_value=round(total_value, 2),
        cash_balance=round(cash_balance, 2),
        geographic_allocations=geo_allocations,
        industry_allocations=industry_allocations,
    )


@dataclass
class StockPriority:
    """Priority score for a stock candidate."""
    symbol: str
    name: str
    geography: str
    industry: str
    stock_score: float
    geo_need: float  # How underweight is this geography (0 to 1)
    industry_need: float  # How underweight is this industry (0 to 1)
    combined_priority: float  # geo_need + industry_need + stock_score


def get_max_trades(cash: float) -> int:
    """Calculate maximum trades based on available cash."""
    return min(
        settings.max_trades_per_cycle,
        int(cash / settings.min_trade_size)
    )


async def calculate_rebalance_trades(
    db: aiosqlite.Connection,
    available_cash: float
) -> list[TradeRecommendation]:
    """
    Calculate optimal trades using hybrid allocation logic.

    Strategy:
    1. Only consider stocks with score > 0.5 (min_stock_score)
    2. Calculate geo_need and industry_need for each stock
    3. Combined priority = geo_need + industry_need + stock_score
    4. Select top N stocks by combined priority
    5. Minimum €400 per trade (min_trade_size)
    6. Maximum 5 trades per cycle (max_trades_per_cycle)
    """
    # Check minimum cash threshold
    if available_cash < settings.min_cash_threshold:
        logger.info(f"Cash €{available_cash:.2f} below minimum €{settings.min_cash_threshold:.2f}")
        return []

    max_trades = get_max_trades(available_cash)
    if max_trades == 0:
        return []

    # Get current portfolio summary for deviation calculations
    summary = await get_portfolio_summary(db)

    # Build deviation maps for quick lookup
    geo_deviations = {a.name: a.deviation for a in summary.geographic_allocations}
    industry_deviations = {a.name: a.deviation for a in summary.industry_allocations}

    # Get scored stocks from universe
    cursor = await db.execute("""
        SELECT s.symbol, s.name, s.geography, s.industry,
               sc.total_score, p.quantity, p.current_price
        FROM stocks s
        LEFT JOIN scores sc ON s.symbol = sc.symbol
        LEFT JOIN positions p ON s.symbol = p.symbol
        WHERE s.active = 1
    """)
    stocks = await cursor.fetchall()

    # Calculate priority for each stock
    candidates: list[StockPriority] = []

    for stock in stocks:
        symbol = stock[0]
        name = stock[1]
        geography = stock[2]
        industry = stock[3]
        score = stock[4] or 0

        # Only consider stocks with score above threshold
        if score < settings.min_stock_score:
            logger.debug(f"Skipping {symbol}: score {score:.2f} < {settings.min_stock_score}")
            continue

        # Get geography need (negative deviation = underweight = positive need)
        geo_deviation = geo_deviations.get(geography, 0)
        geo_need = max(0, -geo_deviation)  # Convert negative deviation to positive need

        # Get industry need (negative deviation = underweight = positive need)
        industry_deviation = industry_deviations.get(industry, 0) if industry else 0
        industry_need = max(0, -industry_deviation)

        # Combined priority: balance geography + industry + stock quality
        combined_priority = geo_need + industry_need + score

        candidates.append(StockPriority(
            symbol=symbol,
            name=name,
            geography=geography,
            industry=industry or "Unknown",
            stock_score=score,
            geo_need=round(geo_need, 4),
            industry_need=round(industry_need, 4),
            combined_priority=round(combined_priority, 4),
        ))

    # Sort by combined priority (highest first)
    candidates.sort(key=lambda x: x.combined_priority, reverse=True)

    logger.info(f"Found {len(candidates)} qualified stocks (score >= {settings.min_stock_score})")

    if not candidates:
        logger.warning("No stocks qualify for purchase (all scores below threshold)")
        return []

    # Select top N candidates
    selected = candidates[:max_trades]

    # Calculate trade size per stock
    # Distribute cash evenly, respecting minimum trade size
    trade_size = max(settings.min_trade_size, available_cash / len(selected))

    # Get current prices and generate recommendations
    from app.services import yahoo

    recommendations = []
    remaining_cash = available_cash

    for candidate in selected:
        if remaining_cash < settings.min_trade_size:
            break

        # Get current price
        price = yahoo.get_current_price(candidate.symbol)
        if not price or price <= 0:
            logger.warning(f"Could not get price for {candidate.symbol}, skipping")
            continue

        # Calculate quantity - ensure minimum trade value
        invest_amount = min(trade_size, remaining_cash)
        if invest_amount < settings.min_trade_size:
            continue

        qty = int(invest_amount / price)
        if qty <= 0:
            continue

        actual_value = qty * price

        # Build reason string
        reason_parts = []
        if candidate.geo_need > 0:
            reason_parts.append(f"{candidate.geography} underweight")
        if candidate.industry_need > 0:
            reason_parts.append(f"{candidate.industry} underweight")
        reason_parts.append(f"score: {candidate.stock_score:.2f}")
        reason = ", ".join(reason_parts)

        recommendations.append(TradeRecommendation(
            symbol=candidate.symbol,
            name=candidate.name,
            side="BUY",
            quantity=qty,
            estimated_price=round(price, 2),
            estimated_value=round(actual_value, 2),
            reason=reason,
        ))

        remaining_cash -= actual_value

    total_invested = available_cash - remaining_cash
    logger.info(
        f"Generated {len(recommendations)} trade recommendations, "
        f"total value: €{total_invested:.2f} from €{available_cash:.2f}"
    )

    return recommendations


async def execute_trades(
    db: aiosqlite.Connection,
    trades: list[TradeRecommendation]
) -> list[dict]:
    """
    Execute a list of trade recommendations via Tradernet.

    Returns list of execution results.
    """
    from app.services.tradernet import get_tradernet_client
    from datetime import datetime

    client = get_tradernet_client()

    if not client.is_connected:
        if not client.connect():
            raise ConnectionError("Failed to connect to Tradernet")

    results = []

    for trade in trades:
        try:
            result = client.place_order(
                symbol=trade.symbol,
                side=trade.side,
                quantity=trade.quantity,
            )

            if result:
                # Record trade in database
                await db.execute(
                    """
                    INSERT INTO trades (symbol, side, quantity, price, executed_at, order_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        trade.symbol,
                        trade.side,
                        trade.quantity,
                        result.price or trade.estimated_price,
                        datetime.now().isoformat(),
                        result.order_id,
                    ),
                )

                results.append({
                    "symbol": trade.symbol,
                    "status": "success",
                    "order_id": result.order_id,
                })
            else:
                results.append({
                    "symbol": trade.symbol,
                    "status": "failed",
                    "error": "Order placement returned None",
                })

        except Exception as e:
            logger.error(f"Failed to execute trade for {trade.symbol}: {e}")
            results.append({
                "symbol": trade.symbol,
                "status": "error",
                "error": str(e),
            })

    await db.commit()
    return results
