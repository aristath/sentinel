"""
Holistic Goal Planner - Creates strategic plans evaluating end-state outcomes.

This planner differs from the standard goal planner by:
1. Evaluating action SEQUENCES (not just individual trades)
2. Scoring the END STATE of the portfolio after all actions
3. Using windfall detection for smart profit-taking
4. Generating narratives explaining the "why" behind each action
5. Exploring multiple pattern types and combinatorial combinations

The planner works by:
1. Identifying opportunities (buys, sells, profit-taking, averaging down)
2. Generating candidate action sequences using 10+ pattern types plus combinatorial generation
3. Early filtering by priority threshold and allow_sell/allow_buy flags
4. Simulating each sequence to get the end state
5. Scoring end states using holistic scoring
6. Selecting the sequence with the best end-state score

Pattern types include:
- Direct buys, profit-taking + reinvest, rebalance, averaging down, single best
- Multi-sell, mixed strategy, opportunity-first, deep rebalance, cash generation
- Combinatorial combinations (if enabled)

All sequences enforce rigid ordering: sells first, then buys.
"""

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, field
from itertools import combinations
from typing import Dict, List, Optional, Set, Tuple

from app.domain.models import Position, Stock
from app.domain.portfolio_hash import generate_portfolio_hash
from app.domain.scoring.diversification import calculate_portfolio_score
from app.domain.scoring.end_state import calculate_portfolio_end_state_score
from app.domain.scoring.models import PortfolioContext
from app.domain.value_objects.trade_side import TradeSide

logger = logging.getLogger(__name__)


def _hash_sequence(sequence: List["ActionCandidate"]) -> str:
    """
    Generate a deterministic hash for a sequence of actions.

    The hash is based on the sequence of (symbol, side, quantity) tuples,
    making it stable across runs for the same sequence.

    Args:
        sequence: List of ActionCandidate objects

    Returns:
        MD5 hash string
    """
    # Create a stable representation: (symbol, side, quantity) tuples
    sequence_repr = [(c.symbol, c.side, c.quantity) for c in sequence]
    # Sort to make order-independent (optional - we might want order-dependent)
    # For now, keep order-dependent since sequence order matters
    sequence_json = json.dumps(sequence_repr, sort_keys=False)
    return hashlib.md5(sequence_json.encode()).hexdigest()


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
    recently_sold: Optional[Set[str]] = None,
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
            # Skip sell opportunities for symbols in cooldown
            if recently_sold and symbol in recently_sold:
                logger.debug(
                    f"{symbol}: Skipping sell opportunity (in cooldown period)"
                )
                continue
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

    # Get recently bought symbols for buy cooldown
    recently_bought = await trade_repo.get_recently_bought_symbols(BUY_COOLDOWN_DAYS)

    # Get recently sold symbols for sell cooldown
    sell_cooldown_days = await settings_repo.get_int("sell_cooldown_days", 180)
    recently_sold = await trade_repo.get_recently_sold_symbols(sell_cooldown_days)

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

    # Identify profit-taking opportunities (filter out recently sold)
    profit_taking_all = await identify_profit_taking_opportunities(
        positions, stocks_by_symbol, exchange_rate_service
    )
    opportunities["profit_taking"] = [
        opp for opp in profit_taking_all if opp.symbol not in recently_sold
    ]

    # Identify rebalance sell opportunities (filter out recently sold)
    rebalance_sells_all = await identify_rebalance_sell_opportunities(
        positions,
        stocks_by_symbol,
        portfolio_context,
        country_allocations,
        total_value,
        exchange_rate_service,
    )
    opportunities["rebalance_sells"] = [
        opp for opp in rebalance_sells_all if opp.symbol not in recently_sold
    ]

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


def _generate_multi_sell_pattern(
    top_profit_taking: list,
    top_rebalance_sells: list,
    top_averaging: list,
    top_rebalance_buys: list,
    top_opportunity: list,
    available_cash: float,
    max_steps: int,
) -> Optional[List[ActionCandidate]]:
    """Generate pattern: Combine profit-taking + rebalance sells → multiple buys."""
    all_sells = top_profit_taking + top_rebalance_sells
    if not all_sells:
        return None

    # Take up to max_steps sells (prioritize profit-taking, then rebalance)
    sell_sequence = []
    for candidate in all_sells[:max_steps]:
        sell_sequence.append(candidate)
        if len(sell_sequence) >= max_steps:
            break

    cash_from_sells = sum(c.value_eur for c in sell_sequence)
    total_cash = available_cash + cash_from_sells

    # Add buys with remaining steps
    all_buys = top_averaging + top_rebalance_buys + top_opportunity
    for candidate in all_buys:
        if candidate.value_eur <= total_cash and len(sell_sequence) < max_steps:
            sell_sequence.append(candidate)
            total_cash -= candidate.value_eur

    return sell_sequence if len(sell_sequence) > 0 else None


def _generate_mixed_strategy_pattern(
    top_profit_taking: list,
    top_rebalance_sells: list,
    top_averaging: list,
    top_rebalance_buys: list,
    top_opportunity: list,
    available_cash: float,
    max_steps: int,
) -> Optional[List[ActionCandidate]]:
    """Generate pattern: Any combination of sells → any combination of buys (flexible)."""
    all_sells = top_profit_taking + top_rebalance_sells
    all_buys = top_averaging + top_rebalance_buys + top_opportunity

    if not all_sells and not all_buys:
        return None

    sequence: List[ActionCandidate] = []
    total_cash = available_cash

    # Add sells first (up to half of max_steps)
    max_sells = max(1, max_steps // 2)
    for candidate in all_sells[:max_sells]:
        if len(sequence) < max_steps:
            sequence.append(candidate)
            total_cash += candidate.value_eur

    # Add buys with remaining steps and cash
    for candidate in all_buys:
        if candidate.value_eur <= total_cash and len(sequence) < max_steps:
            sequence.append(candidate)
            total_cash -= candidate.value_eur

    return sequence if len(sequence) > 0 else None


def _generate_opportunity_first_pattern(
    top_opportunity: list,
    top_averaging: list,
    top_rebalance_buys: list,
    available_cash: float,
    max_steps: int,
) -> Optional[List[ActionCandidate]]:
    """Generate pattern: Focus on high-quality opportunity buys."""
    if not top_opportunity:
        return None

    sequence: List[ActionCandidate] = []
    remaining_cash = available_cash

    # Prioritize opportunity buys
    for candidate in top_opportunity:
        if candidate.value_eur <= remaining_cash and len(sequence) < max_steps:
            sequence.append(candidate)
            remaining_cash -= candidate.value_eur

    # Fill remaining with averaging down or rebalance buys
    for candidate in top_averaging + top_rebalance_buys:
        if candidate.value_eur <= remaining_cash and len(sequence) < max_steps:
            sequence.append(candidate)
            remaining_cash -= candidate.value_eur

    return sequence if sequence else None


def _generate_deep_rebalance_pattern(
    top_rebalance_sells: list,
    top_rebalance_buys: list,
    available_cash: float,
    max_steps: int,
) -> Optional[List[ActionCandidate]]:
    """Generate pattern: Multiple rebalance sells → multiple rebalance buys."""
    if not top_rebalance_sells or not top_rebalance_buys:
        return None

    sequence: List[ActionCandidate] = []
    total_cash = available_cash

    # Add multiple rebalance sells (up to half of max_steps)
    max_sells = max(1, max_steps // 2)
    for candidate in top_rebalance_sells[:max_sells]:
        if len(sequence) < max_steps:
            sequence.append(candidate)
            total_cash += candidate.value_eur

    # Add multiple rebalance buys
    for candidate in top_rebalance_buys:
        if candidate.value_eur <= total_cash and len(sequence) < max_steps:
            sequence.append(candidate)
            total_cash -= candidate.value_eur

    return sequence if len(sequence) > 0 else None


def _generate_cash_generation_pattern(
    top_profit_taking: list,
    top_rebalance_sells: list,
    top_averaging: list,
    top_rebalance_buys: list,
    top_opportunity: list,
    available_cash: float,
    max_steps: int,
) -> Optional[List[ActionCandidate]]:
    """Generate pattern: Multiple sells → strategic buys."""
    all_sells = top_profit_taking + top_rebalance_sells
    if not all_sells:
        return None

    sequence = []
    total_cash = available_cash

    # Generate cash from multiple sells
    for candidate in all_sells[:max_steps]:
        sequence.append(candidate)
        total_cash += candidate.value_eur
        if len(sequence) >= max_steps:
            break

    # Strategic buys: prioritize opportunity, then averaging, then rebalance
    strategic_buys = top_opportunity + top_averaging + top_rebalance_buys
    for candidate in strategic_buys:
        if candidate.value_eur <= total_cash and len(sequence) < max_steps:
            sequence.append(candidate)
            total_cash -= candidate.value_eur

    return sequence if len(sequence) > 0 else None


def _select_diverse_opportunities(
    opportunities: List[ActionCandidate],
    max_count: int,
    stocks_by_symbol: Optional[Dict[str, Stock]] = None,
    diversity_weight: float = 0.3,
) -> List[ActionCandidate]:
    """
    Select diverse opportunities using clustering.

    Clusters opportunities by country, industry, or symbol prefix to ensure
    diversity. Selects top opportunities from each cluster, balancing priority
    and diversity.

    Args:
        opportunities: List of opportunities to select from (already sorted by priority)
        max_count: Maximum number of opportunities to return
        stocks_by_symbol: Optional dict mapping symbol to Stock for country/industry info
        diversity_weight: Weight for diversity vs priority (0.0 = pure priority, 1.0 = pure diversity)

    Returns:
        List of diverse opportunities
    """
    if not opportunities or max_count <= 0:
        return []

    if len(opportunities) <= max_count:
        return opportunities[:max_count]

    # Cluster opportunities by country, industry, or symbol prefix
    clusters: Dict[str, List[ActionCandidate]] = {}

    for opp in opportunities:
        cluster_key = "OTHER"
        if stocks_by_symbol:
            stock = stocks_by_symbol.get(opp.symbol)
            if stock:
                # Prefer country, then industry, then symbol prefix
                if stock.country:
                    cluster_key = f"COUNTRY:{stock.country}"
                elif stock.industry:
                    cluster_key = f"INDUSTRY:{stock.industry}"
                else:
                    # Use symbol prefix (first 3 chars) as fallback
                    cluster_key = f"SYMBOL:{opp.symbol[:3]}"
            else:
                cluster_key = f"SYMBOL:{opp.symbol[:3]}"
        else:
            # No stock info, use symbol prefix
            cluster_key = f"SYMBOL:{opp.symbol[:3]}"

        if cluster_key not in clusters:
            clusters[cluster_key] = []
        clusters[cluster_key].append(opp)

    # Select from each cluster
    selected: List[ActionCandidate] = []
    opportunities_per_cluster = (
        max(1, max_count // len(clusters)) if clusters else max_count
    )

    # Sort clusters by total priority (sum of priorities in cluster)
    sorted_clusters = sorted(
        clusters.items(), key=lambda x: sum(c.priority for c in x[1]), reverse=True
    )

    for cluster_key, cluster_opps in sorted_clusters:
        # Take top opportunities from this cluster
        cluster_selected = cluster_opps[:opportunities_per_cluster]
        selected.extend(cluster_selected)

        if len(selected) >= max_count:
            break

    # If we still need more, fill from remaining opportunities sorted by priority
    if len(selected) < max_count:
        remaining = [opp for opp in opportunities if opp not in selected]
        remaining.sort(key=lambda x: x.priority, reverse=True)
        selected.extend(remaining[: max_count - len(selected)])

    # Balance priority and diversity: sort by weighted score
    # Score = (1 - diversity_weight) * priority + diversity_weight * diversity_bonus
    def _get_cluster_key(opp: ActionCandidate) -> str:
        """Get cluster key for an opportunity."""
        if stocks_by_symbol:
            stock = stocks_by_symbol.get(opp.symbol)
            if stock:
                if stock.country:
                    return f"COUNTRY:{stock.country}"
                elif stock.industry:
                    return f"INDUSTRY:{stock.industry}"
        return f"SYMBOL:{opp.symbol[:3]}"

    def _diversity_score(opp: ActionCandidate) -> float:
        """Calculate diversity-weighted score for an opportunity."""
        opp_cluster = _get_cluster_key(opp)

        # Count how many other selected opportunities are in same cluster
        same_cluster_count = sum(
            1
            for other in selected
            if other != opp and _get_cluster_key(other) == opp_cluster
        )
        diversity_bonus = 1.0 / (1.0 + same_cluster_count * 0.5)

        priority_score = opp.priority / 100.0 if opp.priority > 0 else 0.0
        return (
            1.0 - diversity_weight
        ) * priority_score + diversity_weight * diversity_bonus

    # Re-sort by diversity-weighted score
    selected.sort(key=_diversity_score, reverse=True)

    return selected[:max_count]


def _generate_combinations(
    sells: List[ActionCandidate],
    buys: List[ActionCandidate],
    max_sells: int = 3,
    max_buys: int = 3,
    priority_threshold: float = 0.3,
    max_steps: int = 5,
    max_combinations: int = 50,
    max_candidates: int = 12,
) -> List[List[ActionCandidate]]:
    """Generate valid combinations with smart pruning.

    IMPORTANT: All sequences must have sells first, then buys.
    Ordering is rigid and enforced.

    Args:
        sells: List of sell opportunities
        buys: List of buy opportunities
        max_sells: Maximum number of sells per combination
        max_buys: Maximum number of buys per combination
        priority_threshold: Minimum priority to include in combinations
        max_steps: Maximum total steps in sequence
        max_combinations: Maximum number of combinations to generate (safety limit)

    Returns:
        List of action sequences (sells first, then buys)
    """
    sequences: List[List[ActionCandidate]] = []

    # Filter by priority threshold
    filtered_sells = [s for s in sells if s.priority >= priority_threshold]
    filtered_buys = [b for b in buys if b.priority >= priority_threshold]

    # Limit the number of candidates to avoid combinatorial explosion
    filtered_sells = filtered_sells[:max_candidates]
    filtered_buys = filtered_buys[:max_candidates]

    # Generate combinations of sells (1 to max_sells)
    for num_sells in range(1, min(max_sells + 1, len(filtered_sells) + 1)):
        if len(sequences) >= max_combinations:
            break
        for sell_combo in combinations(filtered_sells, num_sells):
            if len(sequences) >= max_combinations:
                break
            remaining_steps = max_steps - len(sell_combo)
            if remaining_steps <= 0:
                continue

            # Generate combinations of buys (1 to min(max_buys, remaining_steps))
            max_buys_for_combo = min(max_buys, remaining_steps, len(filtered_buys))
            for num_buys in range(1, max_buys_for_combo + 1):
                if len(sequences) >= max_combinations:
                    break
                for buy_combo in combinations(filtered_buys, num_buys):
                    if len(sequences) >= max_combinations:
                        break
                    # Create sequence: sells first, then buys (rigid ordering)
                    sequence = list(sell_combo) + list(buy_combo)
                    if len(sequence) <= max_steps:
                        sequences.append(sequence)

    return sequences


def _generate_patterns_at_depth(
    opportunities: Dict[str, List[ActionCandidate]],
    available_cash: float,
    max_steps: int,
    max_opportunities_per_category: int = 5,
    enable_combinatorial: bool = True,
    priority_threshold: float = 0.3,
    combinatorial_max_combinations_per_depth: int = 50,
    combinatorial_max_sells: int = 4,
    combinatorial_max_buys: int = 4,
    combinatorial_max_candidates: int = 12,
    enable_diverse_selection: bool = True,
    diversity_weight: float = 0.3,
    stocks_by_symbol: Optional[Dict[str, Stock]] = None,
) -> List[List[ActionCandidate]]:
    """Generate sequence patterns capped at a specific depth."""
    sequences = []

    # Select opportunities (diverse or top N)
    all_profit_taking = opportunities.get("profit_taking", [])
    all_averaging = opportunities.get("averaging_down", [])
    all_rebalance_sells = opportunities.get("rebalance_sells", [])
    all_rebalance_buys = opportunities.get("rebalance_buys", [])
    all_opportunity = opportunities.get("opportunity_buys", [])

    if enable_diverse_selection:
        top_profit_taking = _select_diverse_opportunities(
            all_profit_taking,
            max_opportunities_per_category,
            stocks_by_symbol,
            diversity_weight,
        )
        top_averaging = _select_diverse_opportunities(
            all_averaging,
            max_opportunities_per_category,
            stocks_by_symbol,
            diversity_weight,
        )
        top_rebalance_sells = _select_diverse_opportunities(
            all_rebalance_sells,
            max_opportunities_per_category,
            stocks_by_symbol,
            diversity_weight,
        )
        top_rebalance_buys = _select_diverse_opportunities(
            all_rebalance_buys,
            max_opportunities_per_category,
            stocks_by_symbol,
            diversity_weight,
        )
        top_opportunity = _select_diverse_opportunities(
            all_opportunity,
            max_opportunities_per_category,
            stocks_by_symbol,
            diversity_weight,
        )
    else:
        # Simple top N selection
        top_profit_taking = all_profit_taking[:max_opportunities_per_category]
        top_averaging = all_averaging[:max_opportunities_per_category]
        top_rebalance_sells = all_rebalance_sells[:max_opportunities_per_category]
        top_rebalance_buys = all_rebalance_buys[:max_opportunities_per_category]
        top_opportunity = all_opportunity[:max_opportunities_per_category]

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

    # New pattern types
    pattern6 = _generate_multi_sell_pattern(
        top_profit_taking,
        top_rebalance_sells,
        top_averaging,
        top_rebalance_buys,
        top_opportunity,
        available_cash,
        max_steps,
    )
    if pattern6:
        sequences.append(pattern6)

    pattern7 = _generate_mixed_strategy_pattern(
        top_profit_taking,
        top_rebalance_sells,
        top_averaging,
        top_rebalance_buys,
        top_opportunity,
        available_cash,
        max_steps,
    )
    if pattern7:
        sequences.append(pattern7)

    pattern8 = _generate_opportunity_first_pattern(
        top_opportunity,
        top_averaging,
        top_rebalance_buys,
        available_cash,
        max_steps,
    )
    if pattern8:
        sequences.append(pattern8)

    pattern9 = _generate_deep_rebalance_pattern(
        top_rebalance_sells,
        top_rebalance_buys,
        available_cash,
        max_steps,
    )
    if pattern9:
        sequences.append(pattern9)

    pattern10 = _generate_cash_generation_pattern(
        top_profit_taking,
        top_rebalance_sells,
        top_averaging,
        top_rebalance_buys,
        top_opportunity,
        available_cash,
        max_steps,
    )
    if pattern10:
        sequences.append(pattern10)

    # Combinatorial generation (if enabled)
    if enable_combinatorial:
        all_sells = top_profit_taking + top_rebalance_sells
        all_buys = top_averaging + top_rebalance_buys + top_opportunity

        if all_sells or all_buys:
            combo_sequences = _generate_combinations(
                sells=all_sells,
                buys=all_buys,
                max_sells=min(combinatorial_max_sells, max_steps // 2),
                max_buys=min(combinatorial_max_buys, max_steps),
                priority_threshold=priority_threshold,
                max_steps=max_steps,
                max_combinations=combinatorial_max_combinations_per_depth,
                max_candidates=combinatorial_max_candidates,
            )
            sequences.extend(combo_sequences)

    return sequences


async def generate_action_sequences(
    opportunities: Dict[str, List[ActionCandidate]],
    available_cash: float,
    max_depth: int = 5,
    max_opportunities_per_category: int = 5,
    enable_combinatorial: bool = True,
    priority_threshold: float = 0.3,
    combinatorial_max_combinations_per_depth: int = 50,
    combinatorial_max_sells: int = 4,
    combinatorial_max_buys: int = 4,
    combinatorial_max_candidates: int = 12,
    enable_diverse_selection: bool = True,
    diversity_weight: float = 0.3,
    stocks: Optional[List[Stock]] = None,
) -> List[List[ActionCandidate]]:
    """
    Generate candidate action sequences at all depths (1 to max_depth).

    Automatically tests sequences of varying lengths to find the optimal depth.
    Each depth generates multiple pattern variants (original 5 + 5 new patterns):
    1. Direct buys (if cash available)
    2. Profit-taking + reinvest
    3. Rebalance (sell overweight, buy underweight)
    4. Averaging down focus
    5. Single best action
    6. Multi-sell pattern
    7. Mixed strategy pattern
    8. Opportunity-first pattern
    9. Deep rebalance pattern
    10. Cash generation pattern
    Plus combinatorial generation (if enabled)

    Args:
        opportunities: Categorized opportunities from identify_opportunities
        available_cash: Starting available cash
        max_depth: Maximum sequence depth (default 5, configurable via settings)
        max_opportunities_per_category: Max opportunities per category to consider (default 5)
        enable_combinatorial: Enable combinatorial generation (default True)
        priority_threshold: Minimum priority for combinations (default 0.3)

    Returns:
        List of action sequences (each sequence is a list of ActionCandidate)
    """
    all_sequences = []

    # Build stocks_by_symbol dict for diverse selection
    stocks_by_symbol: Optional[Dict[str, Stock]] = None
    if stocks and enable_diverse_selection:
        stocks_by_symbol = {s.symbol: s for s in stocks}

    # Generate patterns at each depth (1 to max_depth)
    for depth in range(1, max_depth + 1):
        depth_sequences = _generate_patterns_at_depth(
            opportunities,
            available_cash,
            depth,
            max_opportunities_per_category=max_opportunities_per_category,
            enable_combinatorial=enable_combinatorial,
            priority_threshold=priority_threshold,
            combinatorial_max_combinations_per_depth=combinatorial_max_combinations_per_depth,
            combinatorial_max_sells=combinatorial_max_sells,
            combinatorial_max_buys=combinatorial_max_buys,
            combinatorial_max_candidates=combinatorial_max_candidates,
            enable_diverse_selection=enable_diverse_selection,
            diversity_weight=diversity_weight,
            stocks_by_symbol=stocks_by_symbol,
        )
        all_sequences.extend(depth_sequences)

    # Remove duplicates and empty sequences, and filter sequences with duplicate symbols
    unique_sequences = []
    seen = set()
    for seq in all_sequences:
        if not seq:
            continue

        # Filter out sequences with duplicate symbols (same symbol shouldn't appear twice)
        symbols_in_seq = [c.symbol for c in seq]
        if len(symbols_in_seq) != len(set(symbols_in_seq)):
            side_str = (
                c.side.value if hasattr(c.side, "value") else str(c.side) for c in seq
            )
            logger.debug(
                f"Skipping sequence with duplicate symbols: {[f'{s}:{c.symbol}' for s, c in zip(side_str, seq)]}"
            )
            continue

        key = tuple((c.symbol, c.side) for c in seq)
        if key not in seen:
            seen.add(key)
            unique_sequences.append(seq)

    # Log sequences generated
    logger.info(
        f"Holistic planner generated {len(unique_sequences)} unique sequences "
        f"(testing depths 1-{max_depth}, "
        f"max_opportunities={max_opportunities_per_category}, "
        f"combinatorial={'enabled' if enable_combinatorial else 'disabled'})"
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


async def process_planner_incremental(
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
    max_opportunities_per_category: int = 5,
    enable_combinatorial: bool = True,
    priority_threshold: float = 0.3,
    combinatorial_max_combinations_per_depth: int = 50,
    combinatorial_max_sells: int = 4,
    combinatorial_max_buys: int = 4,
    combinatorial_max_candidates: int = 12,
    batch_size: int = 100,
) -> Optional[HolisticPlan]:
    """
    Process next batch of sequences incrementally and return best result so far.

    This function:
    1. Generates sequences on first run (if not in database)
    2. Gets next batch of sequences from database (priority order)
    3. Processes batch (simulate, evaluate, cache)
    4. Updates best result if better found
    5. Returns best result from database

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
        max_opportunities_per_category: Max opportunities per category (default 5)
        enable_combinatorial: Enable combinatorial generation (default True)
        priority_threshold: Minimum priority for combinations (default 0.3)
        batch_size: Number of sequences to process per batch (default 100)

    Returns:
        HolisticPlan with best sequence found so far, or None if no sequences evaluated yet
    """
    from datetime import datetime

    from app.domain.planning.narrative import (
        generate_plan_narrative,
        generate_step_narrative,
    )
    from app.repositories.calculations import CalculationsRepository
    from app.repositories.planner_repository import PlannerRepository

    # Generate portfolio hash
    position_dicts = [{"symbol": p.symbol, "quantity": p.quantity} for p in positions]
    portfolio_hash = generate_portfolio_hash(position_dicts, stocks)

    repo = PlannerRepository()

    # Check if portfolio changed - delete sequences for other portfolio hashes
    db = await repo._get_db()
    rows = await db.fetchall("SELECT DISTINCT portfolio_hash FROM sequences")
    for row in rows:
        old_hash = row["portfolio_hash"]
        if old_hash != portfolio_hash:
            logger.info(
                f"Portfolio changed ({old_hash[:8]} -> {portfolio_hash[:8]}), deleting old sequences"
            )
            await repo.delete_sequences_for_portfolio(old_hash)

    # Generate sequences if not exist
    if not await repo.has_sequences(portfolio_hash):
        logger.info(f"Generating sequences for portfolio {portfolio_hash[:8]}...")
        # Calculate current portfolio score
        current_score = await calculate_portfolio_score(portfolio_context)

        # Get recently sold symbols for sell cooldown
        from app.repositories import SettingsRepository, TradeRepository

        settings_repo = SettingsRepository()
        trade_repo = TradeRepository()
        sell_cooldown_days = await settings_repo.get_int("sell_cooldown_days", 180)
        recently_sold = await trade_repo.get_recently_sold_symbols(sell_cooldown_days)

        # Identify opportunities
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
                recently_sold=recently_sold,
            )
        else:
            logger.info("Using heuristic opportunity identification")
            opportunities = await identify_opportunities(
                portfolio_context,
                positions,
                stocks,
                available_cash,
                exchange_rate_service,
            )

        # Generate all sequences
        all_sequences = await generate_action_sequences(
            opportunities,
            available_cash,
            max_depth=max_plan_depth,
            max_opportunities_per_category=max_opportunities_per_category,
            enable_combinatorial=enable_combinatorial,
            priority_threshold=priority_threshold,
            combinatorial_max_combinations_per_depth=combinatorial_max_combinations_per_depth,
            combinatorial_max_sells=combinatorial_max_sells,
            combinatorial_max_buys=combinatorial_max_buys,
            combinatorial_max_candidates=combinatorial_max_candidates,
        )

        # Filter sequences (same logic as in create_holistic_plan)
        stocks_by_symbol = {s.symbol: s for s in stocks}
        positions_by_symbol = {p.symbol: p for p in positions}
        feasible_sequences = []

        def _get_sequence_priority(sequence: List[ActionCandidate]) -> float:
            """Calculate estimated priority for a sequence."""
            return sum(c.priority for c in sequence)

        for sequence in all_sequences:
            if not sequence:
                continue

            # Filter out sequences with duplicate symbols (same symbol shouldn't appear twice)
            symbols_in_seq = [c.symbol for c in sequence]
            if len(symbols_in_seq) != len(set(symbols_in_seq)):
                side_strs = [
                    c.side.value if hasattr(c.side, "value") else str(c.side)
                    for c in sequence
                ]
                logger.debug(
                    f"Skipping sequence with duplicate symbols: {[f'{s}:{c.symbol}' for s, c in zip(side_strs, sequence)]}"
                )
                continue

            if sequence:
                avg_priority = _get_sequence_priority(sequence) / len(sequence)
                if avg_priority < priority_threshold:
                    continue

            is_feasible = True
            running_cash = available_cash

            for action in sequence:
                stock = stocks_by_symbol.get(action.symbol)
                if action.side == TradeSide.BUY:
                    if not stock or not stock.allow_buy:
                        is_feasible = False
                        break
                    if action.value_eur > running_cash:
                        is_feasible = False
                        break
                    running_cash -= action.value_eur
                elif action.side == TradeSide.SELL:
                    if not stock or not stock.allow_sell:
                        is_feasible = False
                        break
                    position = positions_by_symbol.get(action.symbol)
                    if not position or position.quantity < action.quantity:
                        is_feasible = False
                        break
                    running_cash += action.value_eur

            if is_feasible:
                feasible_sequences.append(sequence)

        # Insert sequences into database
        await repo.ensure_sequences_generated(portfolio_hash, feasible_sequences)
        logger.info(f"Generated {len(feasible_sequences)} sequences")

    # Get next batch of sequences
    next_sequences = await repo.get_next_sequences(portfolio_hash, limit=batch_size)

    if not next_sequences:
        # No more sequences to process, return best result
        best_result = await repo.get_best_result(portfolio_hash)
        if not best_result:
            return None

        # Get best sequence
        best_sequence = await repo.get_best_sequence_from_hash(
            portfolio_hash, best_result["best_sequence_hash"]
        )
        if not best_sequence:
            return None

        # Get evaluation for best sequence
        eval_row = await db.fetchone(
            """SELECT end_score, breakdown_json, end_cash, end_context_positions_json,
                      div_score, total_value
               FROM evaluations
               WHERE sequence_hash = ? AND portfolio_hash = ?""",
            (best_result["best_sequence_hash"], portfolio_hash),
        )

        if not eval_row:
            return None

        breakdown = json.loads(eval_row["breakdown_json"])
        current_score = await calculate_portfolio_score(portfolio_context)

        # Convert sequence to HolisticSteps
        steps = []
        for i, action in enumerate(best_sequence):
            narrative = generate_step_narrative(action, portfolio_context, {})
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
                )
            )

        narrative_summary = generate_plan_narrative(
            steps, current_score.total, eval_row["end_score"] * 100, {}
        )

        return HolisticPlan(
            steps=steps,
            current_score=current_score.total,
            end_state_score=eval_row["end_score"] * 100,
            improvement=(eval_row["end_score"] * 100) - current_score.total,
            narrative_summary=narrative_summary,
            score_breakdown=breakdown,
            cash_required=sum(s.estimated_value for s in steps if s.side == "BUY"),
            cash_generated=sum(s.estimated_value for s in steps if s.side == "SELL"),
            feasible=True,
        )

    # Process batch
    calc_repo = CalculationsRepository()
    metrics_cache: Dict[str, Dict[str, float]] = {}
    required_metrics = [
        "CAGR_5Y",
        "DIVIDEND_YIELD",
        "CONSISTENCY_SCORE",
        "FINANCIAL_STRENGTH",
        "DIVIDEND_CONSISTENCY",
        "PAYOUT_RATIO",
        "SORTINO",
        "VOLATILITY_ANNUAL",
        "MAX_DRAWDOWN",
        "SHARPE",
    ]

    best_in_batch = None
    best_score_in_batch = 0.0

    for seq_data in next_sequences:
        # Deserialize sequence
        sequence_data = json.loads(seq_data["sequence_json"])
        sequence = [
            ActionCandidate(
                side=c["side"],
                symbol=c["symbol"],
                name=c["name"],
                quantity=c["quantity"],
                price=c["price"],
                value_eur=c["value_eur"],
                currency=c["currency"],
                priority=c["priority"],
                reason=c["reason"],
                tags=c["tags"],
            )
            for c in sequence_data
        ]

        sequence_hash = seq_data["sequence_hash"]

        # Check if evaluation already exists (from previous generation)
        if await repo.has_evaluation(sequence_hash, portfolio_hash):
            logger.debug(
                f"Evaluation already exists for sequence {sequence_hash[:8]}, skipping expensive evaluation"
            )
            # Get existing evaluation to update best result
            db = await repo._get_db()
            eval_row = await db.fetchone(
                """SELECT end_score FROM evaluations
                   WHERE sequence_hash = ? AND portfolio_hash = ?""",
                (sequence_hash, portfolio_hash),
            )
            if eval_row:
                end_score = eval_row["end_score"]
                # Mark sequence as completed
                evaluated_at = datetime.now().isoformat()
                await repo.mark_sequence_completed(
                    sequence_hash, portfolio_hash, evaluated_at
                )
                # Update best if better
                if end_score > best_score_in_batch:
                    best_score_in_batch = end_score
                    best_in_batch = sequence_hash
            continue

        # Simulate sequence
        end_context, end_cash = await simulate_sequence(
            sequence, portfolio_context, available_cash, stocks
        )

        # Fetch metrics for symbols in end_context if not cached
        for symbol in end_context.positions.keys():
            if symbol not in metrics_cache:
                metrics = await calc_repo.get_metrics(symbol, required_metrics)
                metrics_cache[symbol] = {
                    k: (v if v is not None else 0.0) for k, v in metrics.items()
                }

        # Evaluate sequence
        div_score = await calculate_portfolio_score(end_context)
        end_score, breakdown = await calculate_portfolio_end_state_score(
            positions=end_context.positions,
            total_value=end_context.total_value,
            diversification_score=div_score.total / 100,
            metrics_cache=metrics_cache,
        )

        # Insert evaluation
        await repo.insert_evaluation(
            sequence_hash=sequence_hash,
            portfolio_hash=portfolio_hash,
            end_score=end_score,
            breakdown=breakdown,
            end_cash=end_cash,
            end_context_positions=end_context.positions,
            div_score=div_score.total,
            total_value=end_context.total_value,
        )

        # Mark sequence as completed
        evaluated_at = datetime.now().isoformat()
        await repo.mark_sequence_completed(sequence_hash, portfolio_hash, evaluated_at)

        # Update best if better
        if end_score > best_score_in_batch:
            best_score_in_batch = end_score
            best_in_batch = sequence_hash

    # Update best result if better found
    if best_in_batch:
        current_best = await repo.get_best_result(portfolio_hash)
        if current_best is None or best_score_in_batch > current_best["best_score"]:
            await repo.update_best_result(
                portfolio_hash, best_in_batch, best_score_in_batch
            )
            logger.info(
                f"New best sequence found: score {best_score_in_batch:.3f} (hash: {best_in_batch[:8]}...)"
            )

    # Return best result from database
    best_result = await repo.get_best_result(portfolio_hash)
    if not best_result:
        return None

    # Get best sequence and return HolisticPlan
    best_sequence = await repo.get_best_sequence_from_hash(
        portfolio_hash, best_result["best_sequence_hash"]
    )
    if not best_sequence:
        return None

    eval_row = await db.fetchone(
        """SELECT end_score, breakdown_json, end_cash, end_context_positions_json,
                  div_score, total_value
           FROM evaluations
           WHERE sequence_hash = ? AND portfolio_hash = ?""",
        (best_result["best_sequence_hash"], portfolio_hash),
    )

    if not eval_row:
        return None

    breakdown = json.loads(eval_row["breakdown_json"])
    current_score = await calculate_portfolio_score(portfolio_context)

    steps = []
    for i, action in enumerate(best_sequence):
        narrative = generate_step_narrative(action, portfolio_context, {})
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
            )
        )

    narrative_summary = generate_plan_narrative(
        steps, current_score.total, eval_row["end_score"] * 100, {}
    )

    return HolisticPlan(
        steps=steps,
        current_score=current_score.total,
        end_state_score=eval_row["end_score"] * 100,
        improvement=(eval_row["end_score"] * 100) - current_score.total,
        narrative_summary=narrative_summary,
        score_breakdown=breakdown,
        cash_required=sum(s.estimated_value for s in steps if s.side == "BUY"),
        cash_generated=sum(s.estimated_value for s in steps if s.side == "SELL"),
        feasible=True,
    )


async def create_holistic_plan_incremental(
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
    max_opportunities_per_category: int = 5,
    enable_combinatorial: bool = True,
    priority_threshold: float = 0.3,
    combinatorial_max_combinations_per_depth: int = 50,
    combinatorial_max_sells: int = 4,
    combinatorial_max_buys: int = 4,
    combinatorial_max_candidates: int = 12,
    batch_size: int = 100,
) -> Optional[HolisticPlan]:
    """
    Incremental mode entry point: process next batch, return best so far.

    This is a wrapper around process_planner_incremental() that reads
    batch_size from settings if not provided.

    Args:
        Same as process_planner_incremental()

    Returns:
        HolisticPlan with best sequence found so far, or None if no sequences evaluated yet
    """
    return await process_planner_incremental(
        portfolio_context=portfolio_context,
        available_cash=available_cash,
        stocks=stocks,
        positions=positions,
        exchange_rate_service=exchange_rate_service,
        target_weights=target_weights,
        current_prices=current_prices,
        transaction_cost_fixed=transaction_cost_fixed,
        transaction_cost_percent=transaction_cost_percent,
        max_plan_depth=max_plan_depth,
        max_opportunities_per_category=max_opportunities_per_category,
        enable_combinatorial=enable_combinatorial,
        priority_threshold=priority_threshold,
        combinatorial_max_combinations_per_depth=combinatorial_max_combinations_per_depth,
        combinatorial_max_sells=combinatorial_max_sells,
        combinatorial_max_buys=combinatorial_max_buys,
        combinatorial_max_candidates=combinatorial_max_candidates,
        batch_size=batch_size,
    )


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
    max_opportunities_per_category: int = 5,
    enable_combinatorial: bool = True,
    priority_threshold: float = 0.3,
    combinatorial_max_combinations_per_depth: int = 50,
    combinatorial_max_sells: int = 4,
    combinatorial_max_buys: int = 4,
    combinatorial_max_candidates: int = 12,
    beam_width: int = 10,
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
        max_opportunities_per_category: Max opportunities per category (default 5)
        enable_combinatorial: Enable combinatorial generation (default True)
        priority_threshold: Minimum priority for combinations (default 0.3)

    Returns:
        HolisticPlan with the best sequence and end-state analysis
    """
    from app.domain.planning.narrative import (
        generate_plan_narrative,
        generate_step_narrative,
    )

    # Calculate current portfolio score
    current_score = await calculate_portfolio_score(portfolio_context)

    # Get recently sold symbols for sell cooldown
    from app.repositories import SettingsRepository, TradeRepository

    settings_repo = SettingsRepository()
    trade_repo = TradeRepository()
    sell_cooldown_days = await settings_repo.get_int("sell_cooldown_days", 180)
    recently_sold = await trade_repo.get_recently_sold_symbols(sell_cooldown_days)

    # Get beam_width from settings if not provided
    if beam_width is None or beam_width <= 0:
        beam_width = await settings_repo.get_int("beam_width", 10)
        beam_width = max(1, min(50, beam_width))  # Clamp to 1-50

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
            recently_sold=recently_sold,
        )
    else:
        logger.info("Using heuristic opportunity identification")
        opportunities = await identify_opportunities(
            portfolio_context, positions, stocks, available_cash, exchange_rate_service
        )

    # Get diverse selection settings
    enable_diverse_selection = (
        await settings_repo.get_float("enable_diverse_selection", 1.0) == 1.0
    )
    diversity_weight = await settings_repo.get_float("diversity_weight", 0.3)
    diversity_weight = max(0.0, min(1.0, diversity_weight))  # Clamp to 0-1

    # Generate candidate sequences at all depths (1 to max_plan_depth)
    sequences = await generate_action_sequences(
        opportunities,
        available_cash,
        max_depth=max_plan_depth,
        max_opportunities_per_category=max_opportunities_per_category,
        enable_combinatorial=enable_combinatorial,
        priority_threshold=priority_threshold,
        enable_diverse_selection=enable_diverse_selection,
        diversity_weight=diversity_weight,
        stocks=stocks,
    )

    # Early filtering: Filter by priority threshold and invalid steps before simulation
    stocks_by_symbol = {s.symbol: s for s in stocks}
    positions_by_symbol = {p.symbol: p for p in positions}
    feasible_sequences = []
    filtered_by_priority = 0
    filtered_by_flags = 0
    filtered_by_cash = 0
    filtered_by_position = 0

    def _get_sequence_priority(sequence: List[ActionCandidate]) -> float:
        """Calculate estimated priority for a sequence."""
        return sum(c.priority for c in sequence)

    for sequence in sequences:
        if not sequence:
            continue

        # Filter out sequences with duplicate symbols (same symbol shouldn't appear twice)
        symbols_in_seq = [c.symbol for c in sequence]
        if len(symbols_in_seq) != len(set(symbols_in_seq)):
            side_strs = [
                c.side.value if hasattr(c.side, "value") else str(c.side)
                for c in sequence
            ]
            logger.debug(
                f"Skipping sequence with duplicate symbols: {[f'{s}:{c.symbol}' for s, c in zip(side_strs, sequence)]}"
            )
            continue

        # Quick priority check - filter low-priority sequences early
        # Check if average priority per action meets threshold
        if sequence:
            avg_priority = _get_sequence_priority(sequence) / len(sequence)
            if avg_priority < priority_threshold:
                filtered_by_priority += 1
                continue

        is_feasible = True
        running_cash = available_cash

        for action in sequence:
            # Check allow_sell/allow_buy flags
            stock = stocks_by_symbol.get(action.symbol)
            if action.side == TradeSide.BUY:
                if not stock or not stock.allow_buy:
                    filtered_by_flags += 1
                    is_feasible = False
                    break
                # Check if we have enough cash
                if action.value_eur > running_cash:
                    filtered_by_cash += 1
                    is_feasible = False
                    break
                running_cash -= action.value_eur
            elif action.side == TradeSide.SELL:
                if not stock or not stock.allow_sell:
                    filtered_by_flags += 1
                    is_feasible = False
                    break
                # Check if we have the position to sell
                position = positions_by_symbol.get(action.symbol)
                if not position or position.quantity < action.quantity:
                    filtered_by_position += 1
                    is_feasible = False
                    break
                running_cash += action.value_eur

        if is_feasible:
            feasible_sequences.append(sequence)

    if len(feasible_sequences) < len(sequences):
        logger.info(
            f"Early filtering: {len(sequences)} -> {len(feasible_sequences)} sequences "
            f"(priority: {filtered_by_priority}, flags: {filtered_by_flags}, "
            f"cash: {filtered_by_cash}, position: {filtered_by_position})"
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

    # Evaluate sequences in batches with beam search and early termination
    # Always evaluate at least first 10 sequences to ensure quality
    min_sequences_to_evaluate = min(10, len(sequence_results_sorted))
    batch_size = 5  # Evaluate 5 sequences at a time
    plateau_threshold = 5  # Stop if no improvement in 5 consecutive sequences

    # Beam search: maintain top K sequences instead of just the best one
    beam: List[Tuple[List[ActionCandidate], float, Dict]] = (
        []
    )  # (sequence, score, breakdown)
    best_end_score = 0.0
    plateau_count = 0
    evaluated_count = 0

    def _update_beam(
        sequence: List[ActionCandidate], score: float, breakdown: Dict
    ) -> None:
        """Update beam with new sequence, keeping only top K."""
        nonlocal best_end_score

        # Add to beam
        beam.append((sequence, score, breakdown))

        # Sort by score descending and keep only top K
        beam.sort(key=lambda x: x[1], reverse=True)
        if len(beam) > beam_width:
            beam[:] = beam[:beam_width]

        # Update best score
        if score > best_end_score:
            best_end_score = score

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
        beam_updated = False
        for seq_idx, sequence, end_score, breakdown in batch_results:
            evaluated_count += 1

            # Check if this sequence would improve the beam
            if len(beam) < beam_width or end_score > beam[-1][1]:
                _update_beam(sequence, end_score, breakdown)
                beam_updated = True
                if end_score > best_end_score:
                    plateau_count = 0
                    logger.info(
                        f"Sequence {seq_idx+1} -> NEW BEST (score: {end_score:.3f}, beam size: {len(beam)})"
                    )
                else:
                    logger.debug(
                        f"Sequence {seq_idx+1} added to beam (score: {end_score:.3f}, beam size: {len(beam)})"
                    )
            else:
                plateau_count += 1

        # Early termination check: beam has converged if no improvement in beam
        if (
            evaluated_count >= min_sequences_to_evaluate
            and not beam_updated
            and plateau_count >= plateau_threshold
        ):
            logger.info(
                f"Early termination: Beam converged (no improvement in {plateau_count} consecutive sequences, "
                f"evaluated {evaluated_count}/{len(sequence_results_sorted)}, beam size: {len(beam)})"
            )
            break

    # Select best sequence from beam
    if not beam:
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

    # Get best sequence from beam (first one has highest score)
    best_sequence, best_end_score, best_breakdown = beam[0]
    logger.info(
        f"Selected best sequence from beam of {len(beam)} (score: {best_end_score:.3f})"
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
