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

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from app.domain.models import Position, Stock
from app.domain.scoring.diversification import calculate_portfolio_score
from app.domain.scoring.end_state import calculate_portfolio_end_state_score
from app.domain.scoring.models import PortfolioContext
from app.domain.value_objects.trade_side import TradeSide

logger = logging.getLogger(__name__)


def _calculate_weight_gaps(
    target_weights: Dict[str, float],
    current_weights: Dict[str, float],
    total_value: float,
) -> list[dict]:
    """Calculate weight gaps between target and current weights."""
    weight_gaps = []

    for symbol, target in target_weights.items():
        current = current_weights.get(symbol, 0.0)
        gap = target - current
        if abs(gap) > 0.005:  # Ignore tiny gaps (<0.5%)
            weight_gaps.append(
                {
                    "symbol": symbol,
                    "current": current,
                    "target": target,
                    "gap": gap,
                    "gap_value": gap * total_value,
                }
            )

    for symbol, current in current_weights.items():
        if symbol not in target_weights and current > 0.005:
            weight_gaps.append(
                {
                    "symbol": symbol,
                    "current": current,
                    "target": 0.0,
                    "gap": -current,
                    "gap_value": -current * total_value,
                }
            )

    def _get_gap_value(x: dict) -> float:
        gap = x.get("gap", 0.0)
        if isinstance(gap, (int, float)):
            return abs(float(gap))
        return 0.0

    weight_gaps.sort(key=_get_gap_value, reverse=True)
    return weight_gaps


def _is_trade_worthwhile(
    gap_value: float, transaction_cost_fixed: float, transaction_cost_percent: float
) -> bool:
    """Check if trade is worthwhile based on transaction costs."""
    trade_cost = transaction_cost_fixed + abs(gap_value) * transaction_cost_percent
    return abs(gap_value) >= trade_cost * 2


def _process_buy_opportunity(
    gap_info: dict,
    stock: Optional[Stock],
    position: Optional[Position],
    price: float,
    opportunities: dict,
) -> None:
    """Process a buy opportunity from weight gap."""
    if not stock or not stock.allow_buy:
        return

    symbol = gap_info["symbol"]
    gap_value = gap_info["gap_value"]

    quantity = int(gap_value / price)
    if stock.min_lot and quantity < stock.min_lot:
        quantity = stock.min_lot

    if quantity <= 0:
        return

    trade_value = quantity * price
    currency = position.currency if position else "EUR"

    if position and position.avg_price > price:
        category = "averaging_down"
        tags = ["averaging_down", "optimizer_target"]
    else:
        category = "rebalance_buys"
        tags = ["rebalance", "optimizer_target"]

    opportunities[category].append(
        ActionCandidate(
            side=TradeSide.BUY,
            symbol=symbol,
            name=stock.name if stock else symbol,
            quantity=quantity,
            price=price,
            value_eur=trade_value,
            currency=currency,
            priority=abs(gap_info["gap"]) * 100,
            reason=f"Optimizer target: {gap_info['target']:.1%} (current: {gap_info['current']:.1%})",
            tags=tags,
        )
    )


def _process_sell_opportunity(
    gap_info: dict,
    stock: Optional[Stock],
    position: Position,
    price: float,
    opportunities: dict,
) -> None:
    """Process a sell opportunity from weight gap."""
    if not position:
        return

    if stock and not stock.allow_sell:
        return

    if stock and position.quantity <= stock.min_lot:
        logger.debug(f"{gap_info['symbol']}: at min_lot, can't reduce further")
        return

    symbol = gap_info["symbol"]
    gap_value = gap_info["gap_value"]
    sell_value = abs(gap_value)
    quantity = int(float(sell_value) / float(price))

    if stock and stock.min_lot:
        remaining = position.quantity - quantity
        if remaining < stock.min_lot and remaining > 0:
            quantity = int(position.quantity - stock.min_lot)

    if quantity <= 0:
        return

    trade_value = quantity * price

    opportunities["rebalance_sells"].append(
        ActionCandidate(
            side=TradeSide.SELL,
            symbol=symbol,
            name=stock.name if stock else symbol,
            quantity=quantity,
            price=price,
            value_eur=trade_value,
            currency=position.currency,
            priority=abs(gap_info["gap"]) * 100,
            reason=f"Optimizer target: {gap_info['target']:.1%} (current: {gap_info['current']:.1%})",
            tags=["rebalance", "optimizer_target"],
        )
    )


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


async def identify_opportunities_from_weights(
    target_weights: Dict[str, float],
    portfolio_context: PortfolioContext,
    positions: List[Position],
    stocks: List[Stock],
    available_cash: float,
    current_prices: Dict[str, float],
    transaction_cost_fixed: float = 2.0,
    transaction_cost_percent: float = 0.002,
    exchange_rate_service=None,
) -> Dict[str, List[ActionCandidate]]:
    """
    Identify opportunities based on optimizer target weights.

    Compares current portfolio weights to target weights and generates:
    - Buy candidates for underweight positions
    - Sell candidates for overweight positions

    Args:
        target_weights: Dict mapping symbol to target weight (0-1)
        portfolio_context: Current portfolio state
        positions: Current positions
        stocks: Available stocks
        available_cash: Available cash in EUR
        current_prices: Dict mapping symbol to current price
        transaction_cost_fixed: Fixed cost per trade (EUR)
        transaction_cost_percent: Variable cost as fraction
        exchange_rate_service: Optional exchange rate service

    Returns:
        Dict mapping category to list of ActionCandidate
    """

    stocks_by_symbol = {s.symbol: s for s in stocks}
    positions_by_symbol = {p.symbol: p for p in positions}
    total_value = portfolio_context.total_value

    opportunities: dict[str, list] = {
        "profit_taking": [],
        "averaging_down": [],
        "rebalance_sells": [],
        "rebalance_buys": [],
        "opportunity_buys": [],
    }

    if total_value <= 0:
        return opportunities

    # Calculate current weights
    current_weights = {}
    for symbol, value in portfolio_context.positions.items():
        current_weights[symbol] = value / total_value

    weight_gaps = _calculate_weight_gaps(target_weights, current_weights, total_value)

    for gap_info in weight_gaps:
        symbol = gap_info["symbol"]
        gap = gap_info["gap"]
        gap_value = gap_info["gap_value"]

        stock = stocks_by_symbol.get(symbol)
        position = positions_by_symbol.get(symbol)
        price = current_prices.get(symbol, 0)

        if price <= 0:
            continue

        if not _is_trade_worthwhile(
            gap_value, transaction_cost_fixed, transaction_cost_percent
        ):
            logger.debug(
                f"{symbol}: gap €{gap_value:.0f} too small (cost would be high)"
            )
            continue

        if gap > 0:
            _process_buy_opportunity(gap_info, stock, position, price, opportunities)
        else:
            if position is not None:
                _process_sell_opportunity(
                    gap_info, stock, position, price, opportunities
                )

    # Sort each category by priority
    for category in opportunities:
        opportunities[category].sort(key=lambda x: x.priority, reverse=True)

    logger.info(
        f"Weight-based opportunities: "
        f"rebalance_sells={len(opportunities['rebalance_sells'])}, "
        f"rebalance_buys={len(opportunities['rebalance_buys'])}, "
        f"averaging_down={len(opportunities['averaging_down'])}"
    )

    return opportunities


async def identify_opportunities(
    portfolio_context: PortfolioContext,
    positions: List[Position],
    stocks: List[Stock],
    available_cash: float,
    exchange_rate_service=None,
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
        exchange_rate_service: Optional exchange rate service

    Returns:
        Dict mapping category to list of ActionCandidate
    """
    from app.application.services.rebalancing_service import calculate_min_trade_amount
    from app.config import settings as app_settings
    from app.domain.constants import BUY_COOLDOWN_DAYS
    from app.domain.planning.opportunities import (
        identify_averaging_down_opportunities,
        identify_opportunity_buy_opportunities,
        identify_profit_taking_opportunities,
        identify_rebalance_buy_opportunities,
        identify_rebalance_sell_opportunities,
    )
    from app.infrastructure.external import yahoo_finance as yahoo
    from app.repositories import SettingsRepository, TradeRepository

    settings_repo = SettingsRepository()
    trade_repo = TradeRepository()

    opportunities: dict[str, list] = {
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

    # Calculate current country/industry allocations
    country_allocations: dict[str, float] = {}
    ind_allocations: dict[str, float] = {}
    for symbol, value in portfolio_context.positions.items():
        country = (
            portfolio_context.stock_countries.get(symbol, "OTHER")
            if portfolio_context.stock_countries
            else "OTHER"
        )
        country_allocations[country] = (
            country_allocations.get(country, 0) + value / total_value
        )

        industries = (
            portfolio_context.stock_industries.get(symbol)
            if portfolio_context.stock_industries
            else None
        )
        if industries:
            for ind in industries.split(","):
                ind = ind.strip()
                if ind:
                    ind_allocations[ind] = (
                        ind_allocations.get(ind, 0) + value / total_value
                    )

    # Identify profit-taking opportunities
    opportunities["profit_taking"] = await identify_profit_taking_opportunities(
        positions, stocks_by_symbol, exchange_rate_service
    )

    # Identify rebalance sell opportunities
    opportunities["rebalance_sells"] = await identify_rebalance_sell_opportunities(
        positions,
        stocks_by_symbol,
        portfolio_context,
        country_allocations,
        total_value,
        exchange_rate_service,
    )

    # Calculate minimum worthwhile trade from transaction costs
    transaction_cost_fixed = await settings_repo.get_float(
        "transaction_cost_fixed", 2.0
    )
    transaction_cost_percent = await settings_repo.get_float(
        "transaction_cost_percent", 0.002
    )
    base_trade_amount = calculate_min_trade_amount(
        transaction_cost_fixed, transaction_cost_percent
    )
    yahoo_symbols: Dict[str, Optional[str]] = {
        s.symbol: s.yahoo_symbol for s in stocks if s.yahoo_symbol and s.allow_buy
    }
    batch_prices = yahoo.get_batch_quotes(yahoo_symbols)

    # Filter stocks for buy opportunities (exclude recently bought and low quality)
    eligible_stocks = [
        s
        for s in stocks
        if s.allow_buy
        and s.symbol not in recently_bought
        and batch_prices.get(s.symbol, 0) > 0
        and (
            portfolio_context.stock_scores.get(s.symbol, 0.5)
            if portfolio_context.stock_scores
            else 0.5
        )
        >= app_settings.min_stock_score
    ]

    # Identify averaging down opportunities
    opportunities["averaging_down"] = await identify_averaging_down_opportunities(
        eligible_stocks,
        portfolio_context,
        batch_prices,
        base_trade_amount,
        exchange_rate_service,
    )

    # Identify rebalance buy opportunities
    opportunities["rebalance_buys"] = await identify_rebalance_buy_opportunities(
        eligible_stocks,
        portfolio_context,
        country_allocations,
        batch_prices,
        base_trade_amount,
        exchange_rate_service,
    )

    # Identify general opportunity buys
    opportunities["opportunity_buys"] = await identify_opportunity_buy_opportunities(
        eligible_stocks,
        portfolio_context,
        batch_prices,
        base_trade_amount,
        min_quality_score=0.7,
        exchange_rate_service=exchange_rate_service,
    )

    # Sort each category by priority
    for category in opportunities:
        opportunities[category].sort(key=lambda x: x.priority, reverse=True)

    # Log opportunities found
    logger.info(
        f"Holistic planner identified opportunities: "
        f"profit_taking={len(opportunities['profit_taking'])}, "
        f"averaging_down={len(opportunities['averaging_down'])}, "
        f"rebalance_sells={len(opportunities['rebalance_sells'])}, "
        f"rebalance_buys={len(opportunities['rebalance_buys'])}, "
        f"opportunity_buys={len(opportunities['opportunity_buys'])}"
    )

    return opportunities


def _generate_direct_buy_pattern(
    top_averaging: list,
    top_rebalance_buys: list,
    top_opportunity: list,
    available_cash: float,
    max_steps: int,
) -> Optional[List[ActionCandidate]]:
    """Generate pattern: Direct buys only (if cash available)."""
    if available_cash <= 0:
        return None

    direct_buys: list = []
    remaining_cash = available_cash
    for candidate in top_averaging + top_rebalance_buys + top_opportunity:
        if candidate.value_eur <= remaining_cash and len(direct_buys) < max_steps:
            direct_buys.append(candidate)
            remaining_cash -= candidate.value_eur

    return direct_buys if direct_buys else None


def _generate_profit_taking_pattern(
    top_profit_taking: list,
    top_averaging: list,
    top_rebalance_buys: list,
    available_cash: float,
    max_steps: int,
) -> Optional[List[ActionCandidate]]:
    """Generate pattern: Profit-taking + reinvest."""
    if not top_profit_taking:
        return None

    profit_sequence = list(top_profit_taking[: min(len(top_profit_taking), max_steps)])
    cash_from_sells = sum(c.value_eur for c in profit_sequence)
    total_cash = available_cash + cash_from_sells

    for candidate in top_averaging + top_rebalance_buys:
        if candidate.value_eur <= total_cash and len(profit_sequence) < max_steps:
            profit_sequence.append(candidate)
            total_cash -= candidate.value_eur

    return profit_sequence if len(profit_sequence) > 0 else None


def _generate_rebalance_pattern(
    top_rebalance_sells: list,
    top_rebalance_buys: list,
    available_cash: float,
    max_steps: int,
) -> Optional[List[ActionCandidate]]:
    """Generate pattern: Rebalance (sell overweight + buy underweight)."""
    if not top_rebalance_sells:
        return None

    rebalance_sequence = list(
        top_rebalance_sells[: min(len(top_rebalance_sells), max_steps)]
    )
    cash_from_sells = sum(c.value_eur for c in rebalance_sequence)
    total_cash = available_cash + cash_from_sells

    for candidate in top_rebalance_buys:
        if candidate.value_eur <= total_cash and len(rebalance_sequence) < max_steps:
            rebalance_sequence.append(candidate)
            total_cash -= candidate.value_eur

    return rebalance_sequence if len(rebalance_sequence) > 0 else None


def _generate_averaging_down_pattern(
    top_averaging: list,
    top_profit_taking: list,
    available_cash: float,
    max_steps: int,
) -> Optional[List[ActionCandidate]]:
    """Generate pattern: Averaging down focus."""
    if not top_averaging:
        return None

    avg_sequence = []
    total_cash = available_cash

    if total_cash < top_averaging[0].value_eur and top_profit_taking:
        avg_sequence.extend(top_profit_taking[:1])
        total_cash += top_profit_taking[0].value_eur

    for candidate in top_averaging:
        if candidate.value_eur <= total_cash and len(avg_sequence) < max_steps:
            avg_sequence.append(candidate)
            total_cash -= candidate.value_eur

    return avg_sequence if avg_sequence else None


def _generate_single_best_pattern(
    top_profit_taking: list,
    top_averaging: list,
    top_rebalance_sells: list,
    top_rebalance_buys: list,
    top_opportunity: list,
    available_cash: float,
    max_steps: int,
) -> Optional[List[ActionCandidate]]:
    """Generate pattern: Single best action (for minimal intervention)."""
    if max_steps < 1:
        return None

    all_candidates = (
        top_profit_taking
        + top_averaging
        + top_rebalance_sells
        + top_rebalance_buys
        + top_opportunity
    )

    if not all_candidates:
        return None

    best = max(all_candidates, key=lambda x: x.priority)
    if best.side == TradeSide.BUY and best.value_eur <= available_cash:
        return [best]
    elif best.side == TradeSide.SELL:
        return [best]

    return None


def _generate_patterns_at_depth(
    opportunities: Dict[str, List[ActionCandidate]],
    available_cash: float,
    max_steps: int,
) -> List[List[ActionCandidate]]:
    """Generate sequence patterns capped at a specific depth."""
    sequences = []

    top_profit_taking = opportunities.get("profit_taking", [])[:2]
    top_averaging = opportunities.get("averaging_down", [])[:2]
    top_rebalance_sells = opportunities.get("rebalance_sells", [])[:2]
    top_rebalance_buys = opportunities.get("rebalance_buys", [])[:3]
    top_opportunity = opportunities.get("opportunity_buys", [])[:2]

    pattern1 = _generate_direct_buy_pattern(
        top_averaging, top_rebalance_buys, top_opportunity, available_cash, max_steps
    )
    if pattern1:
        sequences.append(pattern1)

    pattern2 = _generate_profit_taking_pattern(
        top_profit_taking, top_averaging, top_rebalance_buys, available_cash, max_steps
    )
    if pattern2:
        sequences.append(pattern2)

    pattern3 = _generate_rebalance_pattern(
        top_rebalance_sells, top_rebalance_buys, available_cash, max_steps
    )
    if pattern3:
        sequences.append(pattern3)

    pattern4 = _generate_averaging_down_pattern(
        top_averaging, top_profit_taking, available_cash, max_steps
    )
    if pattern4:
        sequences.append(pattern4)

    pattern5 = _generate_single_best_pattern(
        top_profit_taking,
        top_averaging,
        top_rebalance_sells,
        top_rebalance_buys,
        top_opportunity,
        available_cash,
        max_steps,
    )
    if pattern5:
        sequences.append(pattern5)

    return sequences


async def generate_action_sequences(
    opportunities: Dict[str, List[ActionCandidate]],
    available_cash: float,
    max_depth: int = 5,
) -> List[List[ActionCandidate]]:
    """
    Generate candidate action sequences at all depths (1 to max_depth).

    Automatically tests sequences of varying lengths to find the optimal depth.
    Each depth generates 5 pattern variants:
    1. Direct buys (if cash available)
    2. Profit-taking + reinvest
    3. Rebalance (sell overweight, buy underweight)
    4. Averaging down focus
    5. Single best action

    Args:
        opportunities: Categorized opportunities from identify_opportunities
        available_cash: Starting available cash
        max_depth: Maximum sequence depth (default 5, configurable via settings)

    Returns:
        List of action sequences (each sequence is a list of ActionCandidate)
    """
    all_sequences = []

    # Generate patterns at each depth (1 to max_depth)
    for depth in range(1, max_depth + 1):
        depth_sequences = _generate_patterns_at_depth(
            opportunities, available_cash, depth
        )
        all_sequences.extend(depth_sequences)

    # Remove duplicates and empty sequences
    unique_sequences = []
    seen = set()
    for seq in all_sequences:
        if not seq:
            continue
        key = tuple((c.symbol, c.side) for c in seq)
        if key not in seen:
            seen.add(key)
            unique_sequences.append(seq)

    # Log sequences generated
    logger.info(
        f"Holistic planner generated {len(unique_sequences)} unique sequences (testing depths 1-{max_depth})"
    )
    for i, seq in enumerate(unique_sequences[:5]):  # Log first 5
        symbols = [
            f"{c.side.value if isinstance(c.side, TradeSide) else str(c.side)}:{c.symbol}"
            for c in seq
        ]
        logger.info(f"  Sequence {i+1} (len={len(seq)}): {symbols}")

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
        country = stock.country if stock else None
        industry = stock.industry if stock else None

        new_positions = dict(current_context.positions)
        new_geographies = dict(current_context.stock_countries or {})
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
            new_positions[action.symbol] = (
                new_positions.get(action.symbol, 0) + action.value_eur
            )
            if country:
                new_geographies[action.symbol] = country
            if industry:
                new_industries[action.symbol] = industry
            current_cash -= action.value_eur
            # Total portfolio value stays the same - we just converted cash to stock
            new_total = current_context.total_value

        current_context = PortfolioContext(
            country_weights=current_context.country_weights,
            industry_weights=current_context.industry_weights,
            positions=new_positions,
            total_value=new_total,
            stock_countries=new_geographies,
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
    exchange_rate_service=None,
    target_weights: Optional[Dict[str, float]] = None,
    current_prices: Optional[Dict[str, float]] = None,
    transaction_cost_fixed: float = 2.0,
    transaction_cost_percent: float = 0.002,
    max_plan_depth: int = 5,
) -> HolisticPlan:
    """
    Create a holistic plan by evaluating action sequences and selecting the best.

    This is the main entry point for holistic planning. The planner automatically
    tests sequences at all depths (1 to max_plan_depth) and returns the optimal sequence.

    If target_weights is provided (from optimizer), uses weight-based opportunity
    identification. Otherwise falls back to heuristic-based identification.

    Args:
        portfolio_context: Current portfolio state
        available_cash: Available cash in EUR
        stocks: Available stocks
        positions: Current positions
        exchange_rate_service: Optional exchange rate service
        target_weights: Optional dict from optimizer (symbol -> target weight)
        current_prices: Current prices (required if target_weights provided)
        transaction_cost_fixed: Fixed transaction cost in EUR
        transaction_cost_percent: Variable transaction cost as fraction
        max_plan_depth: Maximum sequence depth to test (default 5)

    Returns:
        HolisticPlan with the best sequence and end-state analysis
    """
    from app.domain.planning.narrative import (
        generate_plan_narrative,
        generate_step_narrative,
    )

    # Calculate current portfolio score
    current_score = await calculate_portfolio_score(portfolio_context)

    # Identify opportunities (weight-based if optimizer provided, else heuristic)
    if target_weights and current_prices:
        logger.info("Using optimizer target weights for opportunity identification")
        opportunities = await identify_opportunities_from_weights(
            target_weights=target_weights,
            portfolio_context=portfolio_context,
            positions=positions,
            stocks=stocks,
            available_cash=available_cash,
            current_prices=current_prices,
            transaction_cost_fixed=transaction_cost_fixed,
            transaction_cost_percent=transaction_cost_percent,
            exchange_rate_service=exchange_rate_service,
        )
    else:
        logger.info("Using heuristic opportunity identification")
        opportunities = await identify_opportunities(
            portfolio_context, positions, stocks, available_cash, exchange_rate_service
        )

    # Generate candidate sequences at all depths (1 to max_plan_depth)
    sequences = await generate_action_sequences(
        opportunities, available_cash, max_depth=max_plan_depth
    )

    # Filter infeasible sequences
    positions_by_symbol = {p.symbol: p for p in positions}
    feasible_sequences = []

    for sequence in sequences:
        is_feasible = True
        running_cash = available_cash

        for action in sequence:
            if action.side == TradeSide.BUY:
                # Check if we have enough cash
                if action.value_eur > running_cash:
                    is_feasible = False
                    break
                running_cash -= action.value_eur
            elif action.side == TradeSide.SELL:
                # Check if we have the position to sell
                position = positions_by_symbol.get(action.symbol)
                if not position or position.quantity < action.quantity:
                    is_feasible = False
                    break
                running_cash += action.value_eur

        if is_feasible:
            feasible_sequences.append(sequence)

    if len(feasible_sequences) < len(sequences):
        logger.info(
            f"Filtered {len(sequences) - len(feasible_sequences)} infeasible sequences "
            f"({len(feasible_sequences)} remaining)"
        )

    sequences = feasible_sequences

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

    # Pre-fetch all metrics for all symbols that will be evaluated
    # First, collect all symbols from all sequence end states by simulating them
    all_symbols: set[str] = set()
    sequence_results = []  # Store (sequence, end_context, end_cash) tuples

    for sequence in sequences:
        end_context, end_cash = await simulate_sequence(
            sequence, portfolio_context, available_cash, stocks
        )
        all_symbols.update(end_context.positions.keys())
        sequence_results.append((sequence, end_context, end_cash))

    # Batch fetch all required metrics for all symbols
    from app.repositories.calculations import CalculationsRepository

    calc_repo = CalculationsRepository()
    metrics_cache: Dict[str, Dict[str, float]] = {}

    required_metrics = [
        "CAGR_5Y",
        "DIVIDEND_YIELD",
        "CONSISTENCY_SCORE",
        "FINANCIAL_STRENGTH",
        "DIVIDEND_CONSISTENCY",
        "PAYOUT_RATIO",  # Used as fallback for dividend consistency
        "SORTINO",
        "VOLATILITY_ANNUAL",
        "MAX_DRAWDOWN",
        "SHARPE",
    ]

    for symbol in all_symbols:
        metrics = await calc_repo.get_metrics(symbol, required_metrics)
        # Convert None values to 0.0 for easier handling
        metrics_cache[symbol] = {
            k: (v if v is not None else 0.0) for k, v in metrics.items()
        }

    logger.info(
        f"Pre-fetched metrics for {len(metrics_cache)} symbols ({len(required_metrics)} metrics each)"
    )

    # Sort sequences by priority (estimated from action priorities)
    def _get_sequence_priority(sequence: List[ActionCandidate]) -> float:
        """Calculate estimated priority for a sequence."""
        return sum(c.priority for c in sequence)

    sequence_results_sorted = sorted(
        sequence_results, key=lambda x: _get_sequence_priority(x[0]), reverse=True
    )

    logger.info(
        f"Sorted {len(sequence_results_sorted)} sequences by priority (highest first)"
    )

    # Define async helper to evaluate a single sequence
    async def _evaluate_sequence(
        seq_idx: int,
        sequence: List[ActionCandidate],
        end_context: PortfolioContext,
        end_cash: float,
    ) -> Tuple[int, List[ActionCandidate], float, Dict]:
        """Evaluate a single sequence and return results."""
        # Calculate diversification score for end state
        div_score = await calculate_portfolio_score(end_context)

        # Calculate full end-state score
        end_score, breakdown = await calculate_portfolio_end_state_score(
            positions=end_context.positions,
            total_value=end_context.total_value,
            diversification_score=div_score.total / 100,  # Normalize to 0-1
            metrics_cache=metrics_cache,
        )

        # Log sequence evaluation
        invested_value = sum(end_context.positions.values())
        symbols = [
            f"{c.side.value if isinstance(c.side, TradeSide) else str(c.side)}:{c.symbol}"
            for c in sequence
        ]
        logger.info(f"Sequence {seq_idx+1} evaluation: {symbols}")
        logger.info(
            f"  End-state score: {end_score:.3f}, Diversification: {div_score.total:.1f}"
        )
        logger.info(f"  Breakdown: {breakdown}")
        logger.info(
            f"  Cash: €{end_cash:.2f}, Invested: €{invested_value:.2f}, Total: €{end_context.total_value:.2f}"
        )

        return (seq_idx, sequence, end_score, breakdown)

    # Evaluate sequences in batches with early termination
    # Always evaluate at least first 10 sequences to ensure quality
    min_sequences_to_evaluate = min(10, len(sequence_results_sorted))
    batch_size = 5  # Evaluate 5 sequences at a time
    plateau_threshold = 5  # Stop if no improvement in 5 consecutive sequences

    best_sequence = None
    best_end_score = 0.0
    best_breakdown = {}
    plateau_count = 0
    evaluated_count = 0

    for batch_start in range(0, len(sequence_results_sorted), batch_size):
        batch_end = min(batch_start + batch_size, len(sequence_results_sorted))
        batch = sequence_results_sorted[batch_start:batch_end]

        # Evaluate batch in parallel
        evaluation_tasks = [
            _evaluate_sequence(batch_start + i, sequence, end_context, end_cash)
            for i, (sequence, end_context, end_cash) in enumerate(batch)
        ]

        batch_results = await asyncio.gather(*evaluation_tasks)

        # Process batch results
        for seq_idx, sequence, end_score, breakdown in batch_results:
            evaluated_count += 1

            if end_score > best_end_score:
                best_end_score = end_score
                best_sequence = sequence
                best_breakdown = breakdown
                plateau_count = 0
                logger.info(
                    f"Sequence {seq_idx+1} -> NEW BEST (score: {end_score:.3f})"
                )
            else:
                plateau_count += 1

        # Early termination check (but always evaluate at least min_sequences_to_evaluate)
        if (
            evaluated_count >= min_sequences_to_evaluate
            and plateau_count >= plateau_threshold
        ):
            logger.info(
                f"Early termination: No improvement in {plateau_count} consecutive sequences "
                f"(evaluated {evaluated_count}/{len(sequence_results_sorted)})"
            )
            break

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
        steps.append(
            HolisticStep(
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
            )
        )

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
