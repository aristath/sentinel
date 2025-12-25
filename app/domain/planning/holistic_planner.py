"""
Holistic Goal Planner - Creates strategic plans evaluating end-state outcomes.

This planner differs from the standard goal planner by:
1. Evaluating action SEQUENCES (not just individual trades)
2. Scoring the END STATE of the portfolio after all actions
3. Using windfall detection for smart profit-taking
4. Generating narratives explaining the "why" behind each action

The planner works by:
1. Identifying opportunities (buys, sells, profit-taking, averaging down)
2. Generating candidate action sequences (1-5 steps)
3. Simulating each sequence to get the end state
4. Scoring end states using holistic scoring
5. Selecting the sequence with the best end-state score
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable, Awaitable, Tuple

from app.domain.scoring.models import PortfolioContext
from app.domain.scoring.diversification import calculate_portfolio_score
from app.domain.scoring.end_state import calculate_portfolio_end_state_score
from app.domain.scoring.windfall import get_windfall_recommendation
from app.domain.models import Stock, Position
from app.domain.value_objects.trade_side import TradeSide

logger = logging.getLogger(__name__)


@dataclass
class HolisticStep:
    """A single step in a holistic plan."""
    step_number: int
    side: str  # "BUY" or "SELL"
    symbol: str
    name: str
    quantity: int
    estimated_price: float
    estimated_value: float  # In EUR
    currency: str
    reason: str
    narrative: str  # Human-readable explanation
    is_windfall: bool = False
    is_averaging_down: bool = False
    contributes_to: List[str] = field(default_factory=list)  # Goals addressed


@dataclass
class HolisticPlan:
    """A complete holistic plan with end-state scoring."""
    steps: List[HolisticStep]
    current_score: float
    end_state_score: float
    improvement: float
    narrative_summary: str
    score_breakdown: Dict
    cash_required: float
    cash_generated: float
    feasible: bool


@dataclass
class ActionCandidate:
    """A candidate action for sequence generation."""
    side: str
    symbol: str
    name: str
    quantity: int
    price: float
    value_eur: float
    currency: str
    priority: float  # Higher = more important
    reason: str
    tags: List[str]  # e.g., ["windfall", "averaging_down", "underweight_asia"]


async def identify_opportunities(
    portfolio_context: PortfolioContext,
    positions: List[Position],
    stocks: List[Stock],
    available_cash: float,
) -> Dict[str, List[ActionCandidate]]:
    """
    Identify all actionable opportunities in the portfolio.

    Returns categorized candidates:
    - profit_taking: Windfall positions to trim
    - averaging_down: Quality dips to buy more of
    - rebalance_sells: Overweight positions to reduce
    - rebalance_buys: Underweight areas to increase
    - opportunity_buys: High-quality stocks at good prices

    Args:
        portfolio_context: Current portfolio state
        positions: Current positions
        stocks: Available stocks
        available_cash: Available cash in EUR

    Returns:
        Dict mapping category to list of ActionCandidate
    """
    from app.repositories import SettingsRepository, TradeRepository
    from app.services import yahoo
    from app.services.tradernet import get_exchange_rate
    from app.domain.constants import BUY_COOLDOWN_DAYS
    from app.config import settings as app_settings

    settings_repo = SettingsRepository()
    trade_repo = TradeRepository()

    opportunities = {
        "profit_taking": [],
        "averaging_down": [],
        "rebalance_sells": [],
        "rebalance_buys": [],
        "opportunity_buys": [],
    }

    stocks_by_symbol = {s.symbol: s for s in stocks}
    total_value = portfolio_context.total_value

    # Get recently bought symbols for cooldown
    recently_bought = await trade_repo.get_recently_bought_symbols(BUY_COOLDOWN_DAYS)

    # Calculate current geography/industry allocations
    geo_allocations = {}
    ind_allocations = {}
    for symbol, value in portfolio_context.positions.items():
        geo = portfolio_context.stock_geographies.get(symbol, "OTHER")
        geo_allocations[geo] = geo_allocations.get(geo, 0) + value / total_value

        industries = portfolio_context.stock_industries.get(symbol)
        if industries:
            for ind in industries.split(","):
                ind = ind.strip()
                if ind:
                    ind_allocations[ind] = ind_allocations.get(ind, 0) + value / total_value

    # Analyze positions for sell opportunities
    for pos in positions:
        stock = stocks_by_symbol.get(pos.symbol)
        if not stock or not stock.allow_sell:
            continue

        position_value = pos.market_value_eur or 0
        if position_value <= 0:
            continue

        # Check for windfall
        windfall_rec = await get_windfall_recommendation(
            symbol=pos.symbol,
            current_price=pos.current_price or pos.avg_price,
            avg_price=pos.avg_price,
            first_bought_at=pos.first_bought_at if hasattr(pos, 'first_bought_at') else None,
        )

        if windfall_rec.get("recommendation", {}).get("take_profits"):
            rec = windfall_rec["recommendation"]
            sell_pct = rec["suggested_sell_pct"] / 100
            sell_qty = int(pos.quantity * sell_pct)
            sell_value = sell_qty * (pos.current_price or pos.avg_price)

            # Convert to EUR
            exchange_rate = 1.0
            if pos.currency and pos.currency != "EUR":
                exchange_rate = get_exchange_rate(pos.currency, "EUR")
            sell_value_eur = sell_value / exchange_rate if exchange_rate > 0 else sell_value

            opportunities["profit_taking"].append(ActionCandidate(
                side=TradeSide.SELL,
                symbol=pos.symbol,
                name=stock.name,
                quantity=sell_qty,
                price=pos.current_price or pos.avg_price,
                value_eur=sell_value_eur,
                currency=pos.currency or "EUR",
                priority=windfall_rec.get("windfall_score", 0.5) + 0.5,  # High priority
                reason=rec["reason"],
                tags=["windfall", "profit_taking"],
            ))

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
                    exchange_rate = get_exchange_rate(pos.currency, "EUR")
                sell_value_native = sell_value_eur * exchange_rate
                sell_qty = int(sell_value_native / (pos.current_price or pos.avg_price))

                if sell_qty > 0:
                    opportunities["rebalance_sells"].append(ActionCandidate(
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
                    ))

    # Analyze stocks for buy opportunities
    base_trade_amount = await settings_repo.get_float("min_trade_size", 150.0)

    # Get batch prices for efficiency
    yahoo_symbols = {s.symbol: s.yahoo_symbol for s in stocks if s.yahoo_symbol and s.allow_buy}
    batch_prices = yahoo.get_batch_quotes(yahoo_symbols)

    for stock in stocks:
        if not stock.allow_buy:
            continue
        if stock.symbol in recently_bought:
            continue

        price = batch_prices.get(stock.symbol)
        if not price or price <= 0:
            continue

        # Get quality score
        quality_score = portfolio_context.stock_scores.get(stock.symbol, 0.5)
        if quality_score < app_settings.min_stock_score:
            continue

        # Check if we own this and it's down (averaging down opportunity)
        current_position = portfolio_context.positions.get(stock.symbol, 0)
        current_price_data = portfolio_context.current_prices or {}
        avg_price_data = portfolio_context.position_avg_prices or {}

        if current_position > 0 and stock.symbol in avg_price_data:
            avg_price = avg_price_data[stock.symbol]
            if avg_price > 0:
                loss_pct = (price - avg_price) / avg_price
                if loss_pct < -0.20 and quality_score >= 0.6:  # Down 20%+ but quality
                    # Calculate buy amount
                    exchange_rate = get_exchange_rate(stock.currency or "EUR", "EUR")
                    trade_value_eur = base_trade_amount

                    opportunities["averaging_down"].append(ActionCandidate(
                        side=TradeSide.BUY,
                        symbol=stock.symbol,
                        name=stock.name,
                        quantity=int(trade_value_eur * exchange_rate / price),
                        price=price,
                        value_eur=trade_value_eur,
                        currency=stock.currency or "EUR",
                        priority=quality_score + abs(loss_pct),  # Higher quality + bigger dip = higher priority
                        reason=f"Quality stock down {abs(loss_pct)*100:.0f}%, averaging down",
                        tags=["averaging_down", "buy_low"],
                    ))
                    continue

        # Check for rebalance buys (underweight geography/industry)
        geo = stock.geography
        if geo:
            target = 0.33 + portfolio_context.geo_weights.get(geo, 0) * 0.15
            current = geo_allocations.get(geo, 0)
            if current < target - 0.05:  # 5%+ underweight
                underweight = target - current
                exchange_rate = get_exchange_rate(stock.currency or "EUR", "EUR")
                trade_value_eur = base_trade_amount

                opportunities["rebalance_buys"].append(ActionCandidate(
                    side=TradeSide.BUY,
                    symbol=stock.symbol,
                    name=stock.name,
                    quantity=int(trade_value_eur * exchange_rate / price),
                    price=price,
                    value_eur=trade_value_eur,
                    currency=stock.currency or "EUR",
                    priority=underweight * 2 + quality_score * 0.5,
                    reason=f"Underweight {geo} by {underweight*100:.1f}%",
                    tags=["rebalance", f"underweight_{geo.lower()}"],
                ))

        # General opportunity buys (high quality at good price)
        if quality_score >= 0.7:
            exchange_rate = get_exchange_rate(stock.currency or "EUR", "EUR")
            trade_value_eur = base_trade_amount

            opportunities["opportunity_buys"].append(ActionCandidate(
                side=TradeSide.BUY,
                symbol=stock.symbol,
                name=stock.name,
                quantity=int(trade_value_eur * exchange_rate / price),
                price=price,
                value_eur=trade_value_eur,
                currency=stock.currency or "EUR",
                priority=quality_score,
                reason=f"High quality (score: {quality_score:.2f})",
                tags=["quality", "opportunity"],
            ))

    # Sort each category by priority
    for category in opportunities:
        opportunities[category].sort(key=lambda x: x.priority, reverse=True)

    # Log opportunities found
    logger.info(f"Holistic planner identified opportunities: "
                f"profit_taking={len(opportunities['profit_taking'])}, "
                f"averaging_down={len(opportunities['averaging_down'])}, "
                f"rebalance_sells={len(opportunities['rebalance_sells'])}, "
                f"rebalance_buys={len(opportunities['rebalance_buys'])}, "
                f"opportunity_buys={len(opportunities['opportunity_buys'])}")

    return opportunities


async def generate_action_sequences(
    opportunities: Dict[str, List[ActionCandidate]],
    available_cash: float,
    max_steps: int = 5,
) -> List[List[ActionCandidate]]:
    """
    Generate candidate action sequences from opportunities.

    Sequences are built with these priorities:
    1. Profit-taking first (generates cash + reduces risk)
    2. Averaging down on quality dips
    3. Rebalancing (sells then buys)
    4. Opportunity buys

    Args:
        opportunities: Categorized opportunities from identify_opportunities
        available_cash: Starting available cash
        max_steps: Maximum steps in a sequence

    Returns:
        List of action sequences (each sequence is a list of ActionCandidate)
    """
    sequences = []

    # Get top candidates from each category
    top_profit_taking = opportunities.get("profit_taking", [])[:2]
    top_averaging = opportunities.get("averaging_down", [])[:2]
    top_rebalance_sells = opportunities.get("rebalance_sells", [])[:2]
    top_rebalance_buys = opportunities.get("rebalance_buys", [])[:3]
    top_opportunity = opportunities.get("opportunity_buys", [])[:2]

    # Sequence 1: Direct buys only (if cash available)
    if available_cash > 0:
        direct_buys = []
        remaining_cash = available_cash
        for candidate in (top_averaging + top_rebalance_buys + top_opportunity):
            if candidate.value_eur <= remaining_cash and len(direct_buys) < max_steps:
                direct_buys.append(candidate)
                remaining_cash -= candidate.value_eur
        if direct_buys:
            sequences.append(direct_buys)

    # Sequence 2: Profit-taking + reinvest
    if top_profit_taking:
        profit_sequence = list(top_profit_taking)
        cash_from_sells = sum(c.value_eur for c in profit_sequence)
        total_cash = available_cash + cash_from_sells

        # Add best buys within budget
        for candidate in (top_averaging + top_rebalance_buys):
            if candidate.value_eur <= total_cash and len(profit_sequence) < max_steps:
                profit_sequence.append(candidate)
                total_cash -= candidate.value_eur

        if len(profit_sequence) > len(top_profit_taking):  # Only if we added buys
            sequences.append(profit_sequence)

    # Sequence 3: Rebalance (sell overweight + buy underweight)
    if top_rebalance_sells:
        rebalance_sequence = list(top_rebalance_sells)
        cash_from_sells = sum(c.value_eur for c in rebalance_sequence)
        total_cash = available_cash + cash_from_sells

        for candidate in top_rebalance_buys:
            if candidate.value_eur <= total_cash and len(rebalance_sequence) < max_steps:
                rebalance_sequence.append(candidate)
                total_cash -= candidate.value_eur

        if len(rebalance_sequence) > len(top_rebalance_sells):
            sequences.append(rebalance_sequence)

    # Sequence 4: Averaging down focus
    if top_averaging:
        avg_sequence = []
        total_cash = available_cash

        # Add sells to fund if needed
        if total_cash < top_averaging[0].value_eur and top_profit_taking:
            avg_sequence.extend(top_profit_taking[:1])
            total_cash += top_profit_taking[0].value_eur

        for candidate in top_averaging:
            if candidate.value_eur <= total_cash and len(avg_sequence) < max_steps:
                avg_sequence.append(candidate)
                total_cash -= candidate.value_eur

        if avg_sequence:
            sequences.append(avg_sequence)

    # Sequence 5: Single best action (for when minimal intervention is best)
    all_candidates = (
        top_profit_taking + top_averaging +
        top_rebalance_sells + top_rebalance_buys + top_opportunity
    )
    if all_candidates:
        best = max(all_candidates, key=lambda x: x.priority)
        if best.side == TradeSide.BUY and best.value_eur <= available_cash:
            sequences.append([best])
        elif best.side == TradeSide.SELL:
            sequences.append([best])

    # Remove duplicates and empty sequences
    unique_sequences = []
    seen = set()
    for seq in sequences:
        if not seq:
            continue
        key = tuple((c.symbol, c.side) for c in seq)
        if key not in seen:
            seen.add(key)
            unique_sequences.append(seq)

    # Log sequences generated
    logger.info(f"Holistic planner generated {len(unique_sequences)} unique sequences")
    for i, seq in enumerate(unique_sequences[:3]):  # Log first 3
        symbols = [f"{c.side.value}:{c.symbol}" for c in seq]
        logger.info(f"  Sequence {i+1}: {symbols}")

    return unique_sequences


async def simulate_sequence(
    sequence: List[ActionCandidate],
    portfolio_context: PortfolioContext,
    available_cash: float,
    stocks: List[Stock],
) -> Tuple[PortfolioContext, float]:
    """
    Simulate executing a sequence and return the resulting portfolio state.

    Args:
        sequence: List of actions to execute
        portfolio_context: Starting portfolio state
        available_cash: Starting cash
        stocks: Available stocks for metadata

    Returns:
        Tuple of (final_context, final_cash)
    """
    stocks_by_symbol = {s.symbol: s for s in stocks}
    current_context = portfolio_context
    current_cash = available_cash

    for action in sequence:
        stock = stocks_by_symbol.get(action.symbol)
        geography = stock.geography if stock else ""
        industry = stock.industry if stock else None

        new_positions = dict(current_context.positions)
        new_geographies = dict(current_context.stock_geographies or {})
        new_industries = dict(current_context.stock_industries or {})

        if action.side == TradeSide.SELL:
            # Reduce position (cash is PART of portfolio, so total doesn't change)
            current_value = new_positions.get(action.symbol, 0)
            new_positions[action.symbol] = max(0, current_value - action.value_eur)
            if new_positions[action.symbol] <= 0:
                new_positions.pop(action.symbol, None)
            current_cash += action.value_eur
            # Total portfolio value stays the same - we just converted stock to cash
            new_total = current_context.total_value
        else:  # BUY
            if action.value_eur > current_cash:
                continue  # Skip if can't afford
            new_positions[action.symbol] = new_positions.get(action.symbol, 0) + action.value_eur
            new_geographies[action.symbol] = geography
            if industry:
                new_industries[action.symbol] = industry
            current_cash -= action.value_eur
            # Total portfolio value stays the same - we just converted cash to stock
            new_total = current_context.total_value

        current_context = PortfolioContext(
            geo_weights=current_context.geo_weights,
            industry_weights=current_context.industry_weights,
            positions=new_positions,
            total_value=new_total,
            stock_geographies=new_geographies,
            stock_industries=new_industries,
            stock_scores=current_context.stock_scores,
            stock_dividends=current_context.stock_dividends,
        )

    return current_context, current_cash


async def create_holistic_plan(
    portfolio_context: PortfolioContext,
    available_cash: float,
    stocks: List[Stock],
    positions: List[Position],
    max_steps: int = 5,
) -> HolisticPlan:
    """
    Create a holistic plan by evaluating action sequences and selecting the best.

    This is the main entry point for holistic planning.

    Args:
        portfolio_context: Current portfolio state
        available_cash: Available cash in EUR
        stocks: Available stocks
        positions: Current positions
        max_steps: Maximum steps in the plan (1-5)

    Returns:
        HolisticPlan with the best sequence and end-state analysis
    """
    from app.domain.planning.narrative import generate_plan_narrative, generate_step_narrative

    # Calculate current portfolio score
    current_score = await calculate_portfolio_score(portfolio_context)

    # Identify all opportunities
    opportunities = await identify_opportunities(
        portfolio_context, positions, stocks, available_cash
    )

    # Generate candidate sequences
    sequences = await generate_action_sequences(
        opportunities, available_cash, max_steps
    )

    if not sequences:
        # No actions to take
        return HolisticPlan(
            steps=[],
            current_score=current_score.total,
            end_state_score=current_score.total,
            improvement=0.0,
            narrative_summary="Portfolio is well-balanced. No actions recommended at this time.",
            score_breakdown={},
            cash_required=0.0,
            cash_generated=0.0,
            feasible=True,
        )

    # Evaluate each sequence by its end-state score
    best_sequence = None
    best_end_score = 0.0
    best_end_context = None
    best_breakdown = {}

    for seq_idx, sequence in enumerate(sequences):
        # Simulate the sequence
        end_context, end_cash = await simulate_sequence(
            sequence, portfolio_context, available_cash, stocks
        )

        # Calculate diversification score for end state
        div_score = await calculate_portfolio_score(end_context)

        # Calculate full end-state score
        end_score, breakdown = await calculate_portfolio_end_state_score(
            positions=end_context.positions,
            total_value=end_context.total_value,
            diversification_score=div_score.total / 100,  # Normalize to 0-1
        )

        # Log sequence evaluation
        invested_value = sum(end_context.positions.values())
        symbols = [f"{c.side.value}:{c.symbol}" for c in sequence]
        logger.info(f"Sequence {seq_idx+1} evaluation: {symbols}")
        logger.info(f"  End-state score: {end_score:.3f}, Diversification: {div_score.total:.1f}")
        logger.info(f"  Breakdown: {breakdown}")
        logger.info(f"  Cash: €{end_cash:.2f}, Invested: €{invested_value:.2f}, Total: €{end_context.total_value:.2f}")

        if end_score > best_end_score:
            best_end_score = end_score
            best_sequence = sequence
            best_end_context = end_context
            best_breakdown = breakdown
            logger.info(f"  -> NEW BEST (score: {end_score:.3f})")

    if not best_sequence:
        return HolisticPlan(
            steps=[],
            current_score=current_score.total,
            end_state_score=current_score.total,
            improvement=0.0,
            narrative_summary="No beneficial actions identified.",
            score_breakdown={},
            cash_required=0.0,
            cash_generated=0.0,
            feasible=True,
        )

    # Convert sequence to HolisticSteps
    steps = []
    for i, action in enumerate(best_sequence):
        narrative = generate_step_narrative(action, portfolio_context, opportunities)
        steps.append(HolisticStep(
            step_number=i + 1,
            side=action.side,
            symbol=action.symbol,
            name=action.name,
            quantity=action.quantity,
            estimated_price=action.price,
            estimated_value=action.value_eur,
            currency=action.currency,
            reason=action.reason,
            narrative=narrative,
            is_windfall="windfall" in action.tags,
            is_averaging_down="averaging_down" in action.tags,
            contributes_to=action.tags,
        ))

    # Calculate cash requirements
    cash_required = sum(s.estimated_value for s in steps if s.side == TradeSide.BUY)
    cash_generated = sum(s.estimated_value for s in steps if s.side == TradeSide.SELL)
    feasible = cash_required <= available_cash + cash_generated

    # Generate overall narrative
    narrative_summary = generate_plan_narrative(
        steps, current_score.total, best_end_score * 100, opportunities
    )

    improvement = (best_end_score * 100) - current_score.total

    return HolisticPlan(
        steps=steps,
        current_score=current_score.total,
        end_state_score=round(best_end_score * 100, 2),
        improvement=round(improvement, 2),
        narrative_summary=narrative_summary,
        score_breakdown=best_breakdown,
        cash_required=round(cash_required, 2),
        cash_generated=round(cash_generated, 2),
        feasible=feasible,
    )
