"""Portfolio allocation and rebalancing logic."""

import logging
from dataclasses import dataclass
from typing import Optional

import aiosqlite

from app.config import settings

logger = logging.getLogger(__name__)


def parse_industries(industry_str: str) -> list[str]:
    """
    Parse comma-separated industry string into list.

    Args:
        industry_str: Comma-separated industries (e.g., "Industrial, Defense")

    Returns:
        List of industry names, or empty list if None/empty
    """
    if not industry_str:
        return []
    return [ind.strip() for ind in industry_str.split(",") if ind.strip()]


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

        geo = pos[6]  # geography
        industry_str = pos[7]  # industry (may be comma-separated)

        # Geographic allocation (simple - each stock has one geography)
        geo_values[geo] = geo_values.get(geo, 0) + eur_value

        # Industry allocation - proportional split for multi-industry stocks
        industries = parse_industries(industry_str)
        if industries:
            split_value = eur_value / len(industries)
            for ind in industries:
                industry_values[ind] = industry_values.get(ind, 0) + split_value

    # Get cash balance from latest snapshot
    cursor = await db.execute("""
        SELECT cash_balance FROM portfolio_snapshots
        ORDER BY date DESC LIMIT 1
    """)
    row = await cursor.fetchone()
    cash_balance = row[0] if row else 0

    # Build dynamic geography list from targets + actual positions
    # This ensures we show all geographies that have targets OR holdings
    all_geographies = set()

    # Add geographies from targets
    for key in targets:
        if key.startswith("geography:"):
            all_geographies.add(key.split(":", 1)[1])

    # Add geographies from current holdings
    all_geographies.update(geo_values.keys())

    geo_allocations = []
    for geo in sorted(all_geographies):
        # target_pct now stores weight (-1 to +1), not percentage
        weight = targets.get(f"geography:{geo}", 0)
        current_val = geo_values.get(geo, 0)
        current_pct = current_val / total_value if total_value > 0 else 0

        geo_allocations.append(AllocationStatus(
            category="geography",
            name=geo,
            target_pct=weight,  # Now stores weight, not percentage
            current_pct=round(current_pct, 4),
            current_value=round(current_val, 2),
            deviation=round(current_pct - weight, 4),  # Deviation still computed for display
        ))

    # Build dynamic industry list from targets + actual positions
    # This ensures we show all industries that have targets OR holdings
    all_industries = set()

    # Add industries from targets
    for key in targets:
        if key.startswith("industry:"):
            all_industries.add(key.split(":", 1)[1])

    # Add industries from current holdings
    all_industries.update(industry_values.keys())

    industry_allocations = []
    for industry in sorted(all_industries):
        # target_pct now stores weight (-1 to +1), not percentage
        weight = targets.get(f"industry:{industry}", 0)
        current_val = industry_values.get(industry, 0)
        current_pct = current_val / total_value if total_value > 0 else 0

        industry_allocations.append(AllocationStatus(
            category="industry",
            name=industry,
            target_pct=weight,  # Now stores weight, not percentage
            current_pct=round(current_pct, 4),
            current_value=round(current_val, 2),
            deviation=round(current_pct - weight, 4),  # Deviation still computed for display
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
    volatility: float  # Raw volatility (0.0-1.0)
    multiplier: float  # Manual priority multiplier
    min_lot: int  # Minimum lot size for trading
    geo_need: float  # How underweight is this geography (0 to 1)
    industry_need: float  # How underweight is this industry (0 to 1)
    combined_priority: float  # Enhanced priority score


def calculate_weight_boost(weight: float) -> float:
    """
    Convert allocation weight (-1 to +1) to priority boost (0 to 1).

    Weight scale:
    - weight = +1 → boost = 1.0 (strong buy signal)
    - weight = 0 → boost = 0.5 (neutral)
    - weight = -1 → boost = 0.0 (avoid)

    Args:
        weight: Allocation weight from -1 to +1

    Returns:
        Priority boost from 0 to 1
    """
    # Clamp weight to valid range
    weight = max(-1, min(1, weight))
    # Linear mapping: -1 → 0, 0 → 0.5, +1 → 1.0
    return (weight + 1) / 2


def calculate_diversification_penalty(
    position_pct: float,
    geo_overweight: float,
    industry_overweight: float
) -> float:
    """Penalty for concentrated positions."""
    position_penalty = min(0.3, position_pct * 3)  # 10% position = 0.3 penalty
    geo_penalty = max(0, geo_overweight * 0.5)
    industry_penalty = max(0, industry_overweight * 0.5)

    total_penalty = position_penalty * 0.4 + geo_penalty * 0.3 + industry_penalty * 0.3
    return min(0.5, total_penalty)  # Cap at 0.5


def calculate_risk_adjustment(volatility: float) -> float:
    """Lower score for higher volatility."""
    if volatility is None:
        return 0.5  # Neutral if unknown
    # 15% vol = 1.0, 50% vol = 0.0
    return max(0, min(1, 1 - (volatility - 0.15) / 0.35))


def calculate_position_size(
    candidate: StockPriority,
    base_size: float,
    min_size: float,
) -> float:
    """
    Calculate position size based on conviction and risk.

    Args:
        candidate: Stock priority data
        base_size: Base investment amount per trade
        min_size: Minimum trade size

    Returns:
        Adjusted position size (0.8x to 1.2x of base)
    """
    # Conviction multiplier: 0.8 to 1.2 based on stock score
    conviction_mult = 0.8 + (candidate.stock_score - 0.5) * 0.8
    conviction_mult = max(0.8, min(1.2, conviction_mult))

    # Priority multiplier: 0.9 to 1.1 based on combined priority
    priority_mult = 0.9 + (candidate.combined_priority / 3.0) * 0.2
    priority_mult = max(0.9, min(1.1, priority_mult))

    # Volatility penalty (if available)
    if candidate.volatility is not None:
        vol_mult = max(0.7, 1.0 - (candidate.volatility - 0.15) * 0.5)
    else:
        vol_mult = 1.0

    size = base_size * conviction_mult * priority_mult * vol_mult
    return max(min_size, min(size, base_size * 1.2))


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
    Calculate optimal trades using enhanced multi-factor priority algorithm.

    Strategy:
    1. Only consider stocks with score > min_stock_score
    2. Calculate enhanced priority:
       - Quality (40%): stock score + conviction boost
       - Allocation Weight (30%): boost from geo/industry weights
         * Weight +1 = 100% boost (prioritize)
         * Weight 0 = 50% boost (neutral)
         * Weight -1 = 0% boost (avoid)
       - Diversification (15%): penalty for concentrated positions
       - Risk (15%): volatility-based adjustment
    3. Apply manual multiplier from user
    4. Select top N stocks by combined priority
    5. Dynamic position sizing based on conviction/risk
    6. Minimum €400 per trade (min_trade_size)
    7. Maximum 5 trades per cycle (max_trades_per_cycle)
    """
    # Check minimum cash threshold
    if available_cash < settings.min_cash_threshold:
        logger.info(f"Cash €{available_cash:.2f} below minimum €{settings.min_cash_threshold:.2f}")
        return []

    max_trades = get_max_trades(available_cash)
    if max_trades == 0:
        return []

    # Get current portfolio summary for weight lookups
    summary = await get_portfolio_summary(db)
    total_value = summary.total_value or 1  # Avoid division by zero

    # Build weight maps for quick lookup (target_pct now stores weights -1 to +1)
    geo_weights = {a.name: a.target_pct for a in summary.geographic_allocations}
    industry_weights = {a.name: a.target_pct for a in summary.industry_allocations}

    # Get scored stocks from universe with volatility, multiplier, and min_lot
    cursor = await db.execute("""
        SELECT s.symbol, s.name, s.geography, s.industry,
               s.priority_multiplier, s.min_lot,
               sc.total_score, sc.volatility,
               p.quantity, p.current_price, p.market_value_eur
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
        multiplier = stock[4] or 1.0
        min_lot = stock[5] or 1
        score = stock[6] or 0
        volatility = stock[7]
        position_value = stock[10] or 0

        # Only consider stocks with score above threshold
        if score < settings.min_stock_score:
            logger.debug(f"Skipping {symbol}: score {score:.2f} < {settings.min_stock_score}")
            continue

        industries = parse_industries(industry)

        # 1. Quality with conviction boost
        conviction_boost = max(0, (score - 0.5) * 0.4) if score > 0.5 else 0
        quality = score + conviction_boost

        # 2. Allocation weight boost
        # Get weight for this stock's geography and industries
        # Weight ranges from -1 (avoid) to +1 (prioritize), 0 = neutral
        geo_weight = geo_weights.get(geography, 0)  # Default 0 = neutral
        geo_boost = calculate_weight_boost(geo_weight)
        geo_need = geo_boost  # For logging (higher = more desired)

        ind_boost = 0.5  # Default neutral
        industry_need = 0.5
        if industries:
            ind_weights = [industry_weights.get(ind, 0) for ind in industries]
            ind_boosts = [calculate_weight_boost(w) for w in ind_weights]
            ind_boost = sum(ind_boosts) / len(ind_boosts)
            industry_need = ind_boost

        # Combined allocation boost (weighted average of geo and industry)
        allocation_boost = geo_boost * 0.6 + ind_boost * 0.4

        # 3. Diversification penalty (reduce priority for concentrated positions)
        position_pct = position_value / total_value if total_value > 0 else 0
        # Higher weight = ok to have more, lower weight = penalize concentration more
        geo_concentration_penalty = position_pct * (1 - geo_boost)  # More penalty if weight is low
        diversification = 1.0 - min(0.5, geo_concentration_penalty * 3)

        # 4. Risk adjustment based on volatility
        risk_adj = calculate_risk_adjustment(volatility)

        # Weighted combination
        raw_priority = (
            quality * 0.40 +
            allocation_boost * 0.30 +
            diversification * 0.15 +
            risk_adj * 0.15
        )

        # Apply manual multiplier
        combined_priority = raw_priority * multiplier

        candidates.append(StockPriority(
            symbol=symbol,
            name=name,
            geography=geography,
            industry=industry or "Unknown",
            stock_score=score,
            volatility=volatility,
            multiplier=multiplier,
            min_lot=min_lot,
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

    # Calculate base trade size per stock
    base_trade_size = available_cash / len(selected)

    # Get current prices and generate recommendations with dynamic sizing
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

        # Dynamic position sizing based on conviction and risk
        dynamic_size = calculate_position_size(
            candidate,
            base_trade_size,
            settings.min_trade_size
        )
        invest_amount = min(dynamic_size, remaining_cash)
        if invest_amount < settings.min_trade_size:
            continue

        # Calculate quantity with minimum lot size rounding
        min_lot = candidate.min_lot or 1
        lot_cost = min_lot * price

        # Check if we can afford at least one lot
        if lot_cost > invest_amount:
            logger.debug(
                f"Skipping {candidate.symbol}: min lot {min_lot} @ €{price:.2f} = "
                f"€{lot_cost:.2f} > available €{invest_amount:.2f}"
            )
            continue

        # Calculate how many lots we can buy (rounding down to whole lots)
        num_lots = int(invest_amount / lot_cost)
        qty = num_lots * min_lot

        if qty <= 0:
            continue

        actual_value = qty * price

        # Build reason string with more detail
        reason_parts = []
        # geo_need and industry_need are now weight boosts (0-1)
        # > 0.5 = prioritized, < 0.5 = deprioritized
        if candidate.geo_need > 0.6:
            reason_parts.append(f"{candidate.geography} prioritized")
        elif candidate.geo_need < 0.4:
            reason_parts.append(f"{candidate.geography} neutral")
        if candidate.industry_need > 0.6:
            industries = parse_industries(candidate.industry)
            if industries:
                reason_parts.append(f"{industries[0]} prioritized")
        reason_parts.append(f"score: {candidate.stock_score:.2f}")
        if candidate.multiplier != 1.0:
            reason_parts.append(f"mult: {candidate.multiplier:.1f}x")
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
