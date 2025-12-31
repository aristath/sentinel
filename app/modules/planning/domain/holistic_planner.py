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
from app.domain.value_objects.trade_side import TradeSide
from app.modules.scoring.domain.diversification import calculate_portfolio_score
from app.modules.scoring.domain.end_state import calculate_portfolio_end_state_score
from app.modules.scoring.domain.models import PortfolioContext

logger = logging.getLogger(__name__)


def _calculate_transaction_cost(
    sequence: List["ActionCandidate"],
    transaction_cost_fixed: float,
    transaction_cost_percent: float,
) -> float:
    """
    Calculate total transaction cost for a sequence.

    Args:
        sequence: List of actions in the sequence
        transaction_cost_fixed: Fixed cost per trade in EUR
        transaction_cost_percent: Variable cost as fraction

    Returns:
        Total transaction cost in EUR
    """
    total_cost = 0.0
    for action in sequence:
        trade_cost = (
            transaction_cost_fixed + abs(action.value_eur) * transaction_cost_percent
        )
        total_cost += trade_cost
    return total_cost


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


async def _compute_ineligible_symbols(
    positions: List[Position],
    stocks_by_symbol: Dict[str, Stock],
    trade_repo,
    settings_repo,
) -> Set[str]:
    """Compute set of symbols that are ineligible for selling based on hold time and cooldown."""
    from app.modules.scoring.domain.groups.sell.eligibility import (
        check_sell_eligibility,
    )

    ineligible_symbols = set()

    # Get eligibility settings
    min_hold_days = await settings_repo.get_int("min_hold_days", 90)
    sell_cooldown_days = await settings_repo.get_int("sell_cooldown_days", 180)
    max_loss_threshold = await settings_repo.get_float("max_loss_threshold", -0.20)

    for position in positions:
        symbol = position.symbol
        stock = stocks_by_symbol.get(symbol)
        if not stock or not stock.allow_sell:
            continue

        # Get last transaction date
        last_transaction_at = await trade_repo.get_last_transaction_date(symbol)
        if not last_transaction_at:
            continue  # No transaction history - skip eligibility check

        # Calculate profit percentage for eligibility check
        current_price = position.current_price or position.avg_price
        profit_pct = (
            (current_price - position.avg_price) / position.avg_price
            if position.avg_price > 0
            else 0
        )

        # Check eligibility
        eligible, _ = check_sell_eligibility(
            allow_sell=stock.allow_sell,
            profit_pct=profit_pct,
            last_transaction_at=last_transaction_at,
            max_loss_threshold=max_loss_threshold,
            min_hold_days=min_hold_days,
            sell_cooldown_days=sell_cooldown_days,
        )

        if not eligible:
            ineligible_symbols.add(symbol)
            logger.debug(
                f"{symbol}: Ineligible for selling (last_transaction={last_transaction_at}, "
                f"profit={profit_pct*100:.1f}%)"
            )

    return ineligible_symbols


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

    # Apply priority multiplier: higher multiplier = higher buy priority
    base_priority = abs(gap_info["gap"]) * 100
    multiplier = stock.priority_multiplier if stock else 1.0
    final_priority = base_priority * multiplier

    opportunities[category].append(
        ActionCandidate(
            side=TradeSide.BUY,
            symbol=symbol,
            name=stock.name if stock else symbol,
            quantity=quantity,
            price=price,
            value_eur=trade_value,
            currency=currency,
            priority=final_priority,
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

    # Apply priority multiplier inversely: higher multiplier = lower sell priority
    base_priority = abs(gap_info["gap"]) * 100
    multiplier = stock.priority_multiplier if stock else 1.0
    final_priority = base_priority / multiplier

    opportunities["rebalance_sells"].append(
        ActionCandidate(
            side=TradeSide.SELL,
            symbol=symbol,
            name=stock.name if stock else symbol,
            quantity=quantity,
            price=price,
            value_eur=trade_value,
            currency=position.currency,
            priority=final_priority,
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
class SequenceEvaluation:
    """Multi-objective evaluation of a sequence."""

    sequence: List["ActionCandidate"]
    end_score: float  # Primary objective (0-1)
    diversification_score: float  # Diversification (0-1)
    risk_score: float  # Risk (0-1, higher = lower risk)
    transaction_cost: float  # Total transaction cost in EUR
    breakdown: Dict

    def is_dominated_by(self, other: "SequenceEvaluation") -> bool:
        """
        Check if this sequence is Pareto-dominated by another.

        A sequence is dominated if the other is better or equal in all objectives
        and strictly better in at least one.

        Args:
            other: Another sequence evaluation to compare against

        Returns:
            True if this sequence is dominated by the other
        """
        # For end_score, diversification_score, risk_score: higher is better
        # For transaction_cost: lower is better
        better_or_equal = (
            other.end_score >= self.end_score
            and other.diversification_score >= self.diversification_score
            and other.risk_score >= self.risk_score
            and other.transaction_cost <= self.transaction_cost
        )
        strictly_better = (
            other.end_score > self.end_score
            or other.diversification_score > self.diversification_score
            or other.risk_score > self.risk_score
            or other.transaction_cost < self.transaction_cost
        )
        return better_or_equal and strictly_better


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
    ineligible_symbols: Optional[Set[str]] = None,
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
            # Skip sell opportunities for symbols in cooldown or ineligible
            if recently_sold and symbol in recently_sold:
                logger.debug(
                    f"{symbol}: Skipping sell opportunity (in cooldown period)"
                )
                continue
            if ineligible_symbols and symbol in ineligible_symbols:
                logger.debug(
                    f"{symbol}: Skipping sell opportunity (not eligible - minimum hold or cooldown)"
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
    from app.config import settings as app_settings
    from app.domain.constants import BUY_COOLDOWN_DAYS
    from app.infrastructure.external import yahoo_finance as yahoo
    from app.modules.planning.domain.opportunities import (
        identify_averaging_down_opportunities,
        identify_opportunity_buy_opportunities,
        identify_profit_taking_opportunities,
        identify_rebalance_buy_opportunities,
        identify_rebalance_sell_opportunities,
    )
    from app.modules.rebalancing.services.rebalancing_service import (
        calculate_min_trade_amount,
    )
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

    # Calculate current country/industry allocations by group (not individual)
    country_to_group = portfolio_context.country_to_group or {}
    industry_to_group = portfolio_context.industry_to_group or {}

    country_allocations: dict[str, float] = {}  # group -> allocation
    ind_allocations: dict[str, float] = {}  # group -> allocation
    for symbol, value in portfolio_context.positions.items():
        # Map country to group
        country = (
            portfolio_context.stock_countries.get(symbol, "OTHER")
            if portfolio_context.stock_countries
            else "OTHER"
        )
        group = country_to_group.get(country, "OTHER")
        country_allocations[group] = (
            country_allocations.get(group, 0) + value / total_value
        )

        # Map industries to groups
        industries = (
            portfolio_context.stock_industries.get(symbol)
            if portfolio_context.stock_industries
            else None
        )
        if industries:
            for ind in industries.split(","):
                ind = ind.strip()
                if ind:
                    group = industry_to_group.get(ind, "OTHER")
                    ind_allocations[group] = (
                        ind_allocations.get(group, 0) + value / total_value
                    )

    # Get eligibility settings for sell checks
    min_hold_days = await settings_repo.get_int("min_hold_days", 90)
    sell_cooldown_days = await settings_repo.get_int("sell_cooldown_days", 180)
    max_loss_threshold = await settings_repo.get_float("max_loss_threshold", -0.20)

    # Fetch last transaction dates for all positions to check eligibility
    from app.modules.scoring.domain.groups.sell.eligibility import (
        check_sell_eligibility,
    )

    ineligible_symbols = set()
    positions_by_symbol = {p.symbol: p for p in positions}

    for symbol, position in positions_by_symbol.items():
        stock = stocks_by_symbol.get(symbol)
        if not stock or not stock.allow_sell:
            continue

        # Get last transaction date
        last_transaction_at = await trade_repo.get_last_transaction_date(symbol)
        if not last_transaction_at:
            continue  # No transaction history - skip eligibility check

        # Calculate profit percentage for eligibility check
        current_price = position.current_price or position.avg_price
        profit_pct = (
            (current_price - position.avg_price) / position.avg_price
            if position.avg_price > 0
            else 0
        )

        # Check eligibility
        eligible, _ = check_sell_eligibility(
            allow_sell=stock.allow_sell,
            profit_pct=profit_pct,
            last_transaction_at=last_transaction_at,
            max_loss_threshold=max_loss_threshold,
            min_hold_days=min_hold_days,
            sell_cooldown_days=sell_cooldown_days,
        )

        if not eligible:
            ineligible_symbols.add(symbol)
            logger.debug(
                f"{symbol}: Skipping sell opportunity (not eligible: "
                f"last_transaction={last_transaction_at}, profit={profit_pct*100:.1f}%)"
            )

    # Identify profit-taking opportunities (filter out ineligible and recently sold)
    profit_taking_all = await identify_profit_taking_opportunities(
        positions, stocks_by_symbol, exchange_rate_service
    )
    opportunities["profit_taking"] = [
        opp
        for opp in profit_taking_all
        if opp.symbol not in recently_sold and opp.symbol not in ineligible_symbols
    ]

    # Identify rebalance sell opportunities (filter out ineligible and recently sold)
    rebalance_sells_all = await identify_rebalance_sell_opportunities(
        positions,
        stocks_by_symbol,
        portfolio_context,
        country_allocations,
        total_value,
        exchange_rate_service,
    )
    opportunities["rebalance_sells"] = [
        opp
        for opp in rebalance_sells_all
        if opp.symbol not in recently_sold and opp.symbol not in ineligible_symbols
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


def _generate_cost_optimized_pattern(
    top_profit_taking: list,
    top_rebalance_sells: list,
    top_averaging: list,
    top_rebalance_buys: list,
    top_opportunity: list,
    available_cash: float,
    max_steps: int,
) -> Optional[List[ActionCandidate]]:
    """Generate pattern: Minimize number of trades while maximizing impact."""
    if max_steps < 1:
        return None

    # Combine all opportunities and sort by priority/value ratio
    all_opportunities = (
        top_profit_taking
        + top_rebalance_sells
        + top_averaging
        + top_rebalance_buys
        + top_opportunity
    )

    if not all_opportunities:
        return None

    # Sort by priority (highest first) to get best impact per trade
    all_opportunities.sort(key=lambda x: x.priority, reverse=True)

    sequence: List[ActionCandidate] = []
    running_cash = available_cash

    # Add sells first (they generate cash)
    for candidate in top_profit_taking + top_rebalance_sells:
        if len(sequence) >= max_steps:
            break
        if candidate.side == TradeSide.SELL:
            sequence.append(candidate)
            running_cash += candidate.value_eur

    # Add highest priority buys (minimize number of trades)
    for candidate in all_opportunities:
        if len(sequence) >= max_steps:
            break
        if candidate.side == TradeSide.BUY and candidate.value_eur <= running_cash:
            # Avoid duplicates
            if candidate not in sequence:
                sequence.append(candidate)
                running_cash -= candidate.value_eur

    return sequence if len(sequence) > 0 else None


def _generate_adaptive_patterns(
    opportunities: Dict[str, List[ActionCandidate]],
    portfolio_context: PortfolioContext,
    available_cash: float,
    max_steps: int,
    max_opportunities_per_category: int,
    stocks_by_symbol: Optional[Dict[str, Stock]],
) -> List[List[ActionCandidate]]:
    """
    Generate adaptive patterns based on portfolio gaps.

    Analyzes portfolio state and generates patterns targeting:
    - Geographic gaps (underweight countries)
    - Sector gaps (underweight industries)
    - Risk gaps (high/low volatility positions)

    Args:
        opportunities: Categorized opportunities
        portfolio_context: Current portfolio state
        available_cash: Available cash
        max_steps: Maximum sequence length
        max_opportunities_per_category: Max opportunities per category
        stocks_by_symbol: Optional dict mapping symbol to Stock

    Returns:
        List of adaptive pattern sequences
    """
    sequences: List[List[ActionCandidate]] = []

    if not portfolio_context or portfolio_context.total_value <= 0:
        return sequences

    # Calculate current allocations by group (not individual countries/industries)
    country_to_group = portfolio_context.country_to_group or {}
    industry_to_group = portfolio_context.industry_to_group or {}

    current_group_country_allocations: Dict[str, float] = {}
    current_group_industry_allocations: Dict[str, float] = {}

    for symbol, value in portfolio_context.positions.items():
        if value <= 0:
            continue

        weight = value / portfolio_context.total_value

        # Map country to group and aggregate by group
        if portfolio_context.stock_countries:
            country = portfolio_context.stock_countries.get(symbol)
            if country:
                group = country_to_group.get(country, "OTHER")
                current_group_country_allocations[group] = (
                    current_group_country_allocations.get(group, 0) + weight
                )

        # Map industry to group and aggregate by group
        if portfolio_context.stock_industries:
            industries_str = portfolio_context.stock_industries.get(symbol)
            if industries_str:
                industries = [i.strip() for i in industries_str.split(",")]
                for industry in industries:
                    if industry:
                        group = industry_to_group.get(industry, "OTHER")
                        current_group_industry_allocations[group] = (
                            current_group_industry_allocations.get(group, 0) + weight
                        )

    # Identify geographic gaps (by group)
    geographic_gaps: List[Tuple[str, float]] = []  # (group, gap)
    if portfolio_context.country_weights:
        for group, target_pct in portfolio_context.country_weights.items():
            # target_pct is already a percentage (0-1), no conversion needed
            current_weight = current_group_country_allocations.get(group, 0)
            gap = target_pct - current_weight
            if gap > 0.02:  # At least 2% gap
                geographic_gaps.append((group, gap))

    # Identify sector gaps (by group)
    sector_gaps: List[Tuple[str, float]] = []  # (group, gap)
    if portfolio_context.industry_weights:
        for group, target_pct in portfolio_context.industry_weights.items():
            # target_pct is already a percentage (0-1), no conversion needed
            current_weight = current_group_industry_allocations.get(group, 0)
            gap = target_pct - current_weight
            if gap > 0.01:  # At least 1% gap
                sector_gaps.append((group, gap))

    # Sort gaps by size
    geographic_gaps.sort(key=lambda x: x[1], reverse=True)
    sector_gaps.sort(key=lambda x: x[1], reverse=True)

    # Pattern 1: Geographic rebalance
    if geographic_gaps and stocks_by_symbol:
        geo_buys: List[ActionCandidate] = []
        all_buys = opportunities.get("rebalance_buys", []) + opportunities.get(
            "opportunity_buys", []
        )
        running_cash = available_cash

        # Find buys for underweight countries
        for country, gap in geographic_gaps[:3]:  # Top 3 gaps
            for candidate in all_buys:
                if len(geo_buys) >= max_steps or running_cash < candidate.value_eur:
                    break
                stock = stocks_by_symbol.get(candidate.symbol)
                if stock and stock.country == country:
                    if candidate not in geo_buys:
                        geo_buys.append(candidate)
                        running_cash -= candidate.value_eur

        if geo_buys:
            sequences.append(geo_buys)

    # Pattern 2: Sector rotation
    if sector_gaps and stocks_by_symbol:
        sector_buys: List[ActionCandidate] = []
        all_buys = opportunities.get("rebalance_buys", []) + opportunities.get(
            "opportunity_buys", []
        )
        running_cash = available_cash

        # Find buys for underweight industries
        for industry, gap in sector_gaps[:3]:  # Top 3 gaps
            for candidate in all_buys:
                if len(sector_buys) >= max_steps or running_cash < candidate.value_eur:
                    break
                stock = stocks_by_symbol.get(candidate.symbol)
                if stock and stock.industry:
                    industries = [i.strip() for i in stock.industry.split(",")]
                    if industry in industries:
                        if candidate not in sector_buys:
                            sector_buys.append(candidate)
                            running_cash -= candidate.value_eur

        if sector_buys:
            sequences.append(sector_buys)

    # Pattern 3: Risk adjustment (if we have volatility data)
    # This would require additional metrics, so we'll skip for now
    # Can be enhanced later with volatility data from metrics_cache

    return sequences


def _generate_market_regime_patterns(
    opportunities: Dict[str, List[ActionCandidate]],
    market_regime: str,
    available_cash: float,
    max_steps: int,
    max_opportunities_per_category: int,
) -> List[List[ActionCandidate]]:
    """
    Generate patterns based on market regime.

    - Bull market: Favor growth opportunities, reduce defensive positions
    - Bear market: Favor defensive positions, reduce risk exposure
    - Sideways: Balanced approach with focus on quality

    Args:
        opportunities: Categorized opportunities
        market_regime: "bull", "bear", or "sideways"
        available_cash: Available cash
        max_steps: Maximum sequence length
        max_opportunities_per_category: Max opportunities per category

    Returns:
        List of regime-aware pattern sequences
    """
    sequences: List[List[ActionCandidate]] = []

    all_profit_taking = opportunities.get("profit_taking", [])[
        :max_opportunities_per_category
    ]
    all_rebalance_sells = opportunities.get("rebalance_sells", [])[
        :max_opportunities_per_category
    ]
    all_averaging = opportunities.get("averaging_down", [])[
        :max_opportunities_per_category
    ]
    all_rebalance_buys = opportunities.get("rebalance_buys", [])[
        :max_opportunities_per_category
    ]
    all_opportunity = opportunities.get("opportunity_buys", [])[
        :max_opportunities_per_category
    ]

    if market_regime == "bull":
        # Bull market: Aggressive growth, take profits, add to winners
        # Pattern: Take profits from winners → Reinvest in high-growth opportunities
        bull_sequence: List[ActionCandidate] = []
        running_cash = available_cash

        # Take profits first
        for candidate in all_profit_taking[:2]:  # Top 2 profit-taking
            if len(bull_sequence) < max_steps:
                bull_sequence.append(candidate)
                running_cash += candidate.value_eur

        # Reinvest in high-growth opportunities
        for candidate in all_opportunity + all_rebalance_buys:
            if len(bull_sequence) >= max_steps or running_cash < candidate.value_eur:
                break
            if candidate not in bull_sequence:
                bull_sequence.append(candidate)
                running_cash -= candidate.value_eur

        if bull_sequence:
            sequences.append(bull_sequence)

    elif market_regime == "bear":
        # Bear market: Defensive, reduce exposure, focus on quality
        # Pattern: Reduce positions → Build cash reserve → Add defensive positions
        bear_sequence: List[ActionCandidate] = []
        running_cash = available_cash

        # Reduce positions (profit-taking and rebalance sells)
        for candidate in all_profit_taking + all_rebalance_sells:
            if len(bear_sequence) >= max_steps // 2:  # Limit sells in bear market
                break
            if candidate not in bear_sequence:
                bear_sequence.append(candidate)
                running_cash += candidate.value_eur

        # Add defensive positions (high quality, stable)
        # Prioritize averaging down on quality positions
        for candidate in all_averaging:
            if len(bear_sequence) >= max_steps or running_cash < candidate.value_eur:
                break
            if candidate not in bear_sequence:
                bear_sequence.append(candidate)
                running_cash -= candidate.value_eur

        if bear_sequence:
            sequences.append(bear_sequence)

    else:  # sideways
        # Sideways market: Balanced, focus on quality and rebalancing
        # Pattern: Rebalance → Quality opportunities
        sideways_sequence: List[ActionCandidate] = []
        running_cash = available_cash

        # Rebalance sells first
        for candidate in all_rebalance_sells[:2]:
            if len(sideways_sequence) < max_steps:
                sideways_sequence.append(candidate)
                running_cash += candidate.value_eur

        # Quality buys (rebalance and opportunity)
        for candidate in all_rebalance_buys + all_opportunity:
            if (
                len(sideways_sequence) >= max_steps
                or running_cash < candidate.value_eur
            ):
                break
            if candidate not in sideways_sequence:
                sideways_sequence.append(candidate)
                running_cash -= candidate.value_eur

        if sideways_sequence:
            sequences.append(sideways_sequence)

    return sequences


async def _filter_correlation_aware_sequences(
    sequences: List[List[ActionCandidate]],
    stocks: List[Stock],
    max_steps: int,
) -> List[List[ActionCandidate]]:
    """
    Filter sequences to avoid highly correlated positions.

    Uses correlation data from risk models to identify and filter out
    sequences that would create highly correlated positions.

    Args:
        sequences: List of candidate sequences
        stocks: Available stocks for symbol lookup
        max_steps: Maximum sequence length

    Returns:
        Filtered list of sequences with reduced correlation
    """
    from app.modules.optimization.services.risk_models import RiskModelBuilder

    if not sequences or not stocks:
        return sequences

    # Build correlation data
    try:
        # Get all buy symbols from sequences
        all_buy_symbols = set()
        for sequence in sequences:
            for action in sequence:
                if action.side == TradeSide.BUY:
                    all_buy_symbols.add(action.symbol)

        if not all_buy_symbols:
            return sequences  # No buys to check

        # Build returns DataFrame for correlation calculation
        risk_builder = RiskModelBuilder()
        lookback_days = 252  # 1 year
        prices_df = await risk_builder._fetch_prices(
            list(all_buy_symbols), lookback_days
        )

        if prices_df.empty:
            return sequences  # No price data available

        # Calculate returns and correlation matrix
        returns_df = prices_df.pct_change().dropna()
        if returns_df.empty:
            return sequences

        corr_matrix = returns_df.corr()

        # Build correlation dict for quick lookup
        correlations: Dict[str, float] = {}
        symbols = list(corr_matrix.columns)
        for i, sym1 in enumerate(symbols):
            for sym2 in symbols[i + 1 :]:
                corr = corr_matrix.loc[sym1, sym2]
                # Store both directions
                correlations[f"{sym1}:{sym2}"] = corr
                correlations[f"{sym2}:{sym1}"] = corr

    except Exception as e:
        logger.warning(f"Failed to build correlations for filtering: {e}")
        return sequences  # Return all if correlation check fails

    # Build symbol set from stocks
    stock_symbols = {s.symbol for s in stocks}

    filtered: List[List[ActionCandidate]] = []
    correlation_threshold = 0.7  # Filter sequences with correlation > 0.7

    for sequence in sequences:
        # Get buy symbols from sequence
        buy_symbols = [
            action.symbol
            for action in sequence
            if action.side == TradeSide.BUY and action.symbol in stock_symbols
        ]

        # Check if any pair of buys is highly correlated
        has_high_correlation = False
        for i, symbol1 in enumerate(buy_symbols):
            for symbol2 in buy_symbols[i + 1 :]:
                # Check correlation (both directions)
                corr_key = f"{symbol1}:{symbol2}"
                correlation = correlations.get(corr_key)
                if correlation and abs(correlation) > correlation_threshold:
                    has_high_correlation = True
                    logger.debug(
                        f"Filtering sequence due to high correlation ({correlation:.2f}) "
                        f"between {symbol1} and {symbol2}"
                    )
                    break
            if has_high_correlation:
                break

        if not has_high_correlation:
            filtered.append(sequence)

    if len(filtered) < len(sequences):
        logger.info(
            f"Correlation filtering: {len(sequences)} -> {len(filtered)} sequences "
            f"(removed {len(sequences) - len(filtered)} with high correlation)"
        )

    return filtered


def _generate_partial_execution_scenarios(
    sequences: List[List[ActionCandidate]],
    max_steps: int,
) -> List[List[ActionCandidate]]:
    """
    Generate partial execution scenarios (execute only first N actions).

    Creates variants of sequences where only the first 1, 2, 3... actions
    are executed. This allows the planner to evaluate sequences that might
    be interrupted or where only initial steps are feasible.

    Args:
        sequences: List of full sequences
        max_steps: Maximum sequence length

    Returns:
        List of partial execution sequences
    """
    partial_sequences: List[List[ActionCandidate]] = []

    # For each sequence, create partial versions (first 1, first 2, first 3, etc.)
    for sequence in sequences:
        if len(sequence) <= 1:
            continue  # Skip sequences with only 1 action (no partial variants)

        # Create partial sequences: first 1, first 2, first 3, ... up to len-1
        for partial_length in range(1, min(len(sequence), max_steps)):
            partial_seq = sequence[:partial_length]
            if partial_seq:
                partial_sequences.append(partial_seq)

    if partial_sequences:
        logger.info(
            f"Generated {len(partial_sequences)} partial execution scenarios "
            f"from {len(sequences)} full sequences"
        )

    return partial_sequences


def _generate_constraint_relaxation_scenarios(
    sequences: List[List[ActionCandidate]],
    available_cash: float,
    positions: List[Position],
) -> List[List[ActionCandidate]]:
    """
    Generate constraint relaxation scenarios.

    Creates variants of sequences that temporarily violate constraints
    (e.g., cash limits, position limits) to explore better solutions.
    These sequences are marked for special handling during evaluation.

    Args:
        sequences: List of candidate sequences
        available_cash: Available cash
        positions: Current positions

    Returns:
        List of constraint-relaxed sequences
    """
    relaxed_sequences: List[List[ActionCandidate]] = []
    positions_by_symbol = {p.symbol: p for p in positions}

    # Relaxation factors: allow 10%, 20%, 30% over budget
    relaxation_factors = [1.1, 1.2, 1.3]

    for sequence in sequences:
        # Calculate total cash needed
        total_cash_needed = sum(
            action.value_eur for action in sequence if action.side == TradeSide.BUY
        )

        # If sequence already fits within budget, create relaxed versions
        if total_cash_needed <= available_cash:
            for factor in relaxation_factors:
                relaxed_cash = available_cash * factor
                if total_cash_needed <= relaxed_cash:
                    # Create relaxed sequence (same actions, but marked as relaxed)
                    relaxed_seq = sequence.copy()
                    relaxed_sequences.append(relaxed_seq)

        # Also create sequences that temporarily exceed position limits
        # by allowing larger buys than normal
        for action in sequence:
            if action.side == TradeSide.BUY:
                current_position = positions_by_symbol.get(action.symbol)
                if current_position:
                    # Allow buying more than current position (up to 1.5x)
                    relaxed_value = action.value_eur * 1.5
                    relaxed_quantity = int(action.quantity * 1.5)
                    relaxed_action = ActionCandidate(
                        symbol=action.symbol,
                        name=action.name,
                        side=action.side,
                        quantity=relaxed_quantity,
                        price=action.price,
                        value_eur=relaxed_value,
                        currency=action.currency,
                        priority=action.priority,
                        reason=f"{action.reason} (relaxed)",
                        tags=action.tags,
                    )
                    # Create sequence with relaxed action
                    relaxed_seq = [
                        relaxed_action if a == action else a for a in sequence
                    ]
                    relaxed_sequences.append(relaxed_seq)

    if relaxed_sequences:
        logger.info(
            f"Generated {len(relaxed_sequences)} constraint relaxation scenarios "
            f"from {len(sequences)} base sequences"
        )

    return relaxed_sequences


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


def _generate_enhanced_combinations(
    sells: List[ActionCandidate],
    buys: List[ActionCandidate],
    max_sells: int = 3,
    max_buys: int = 3,
    priority_threshold: float = 0.3,
    max_steps: int = 5,
    max_combinations: int = 50,
    max_candidates: int = 12,
    stocks_by_symbol: Optional[Dict[str, Stock]] = None,
) -> List[List[ActionCandidate]]:
    """
    Generate combinations with priority-based sampling and diversity constraints.

    Uses weighted sampling based on priority and ensures diversity across
    countries/industries to avoid over-concentration.

    Args:
        sells: List of sell opportunities
        buys: List of buy opportunities
        max_sells: Maximum number of sells per combination
        max_buys: Maximum number of buys per combination
        priority_threshold: Minimum priority to include in combinations
        max_steps: Maximum total steps in sequence
        max_combinations: Maximum number of combinations to generate
        max_candidates: Maximum candidates to consider
        stocks_by_symbol: Optional dict mapping symbol to Stock for diversity

    Returns:
        List of action sequences (sells first, then buys)
    """
    import random

    sequences: List[List[ActionCandidate]] = []

    # Filter by priority threshold
    filtered_sells = [s for s in sells if s.priority >= priority_threshold]
    filtered_buys = [b for b in buys if b.priority >= priority_threshold]

    # Limit candidates but prioritize by score
    filtered_sells.sort(key=lambda x: x.priority, reverse=True)
    filtered_buys.sort(key=lambda x: x.priority, reverse=True)
    filtered_sells = filtered_sells[:max_candidates]
    filtered_buys = filtered_buys[:max_candidates]

    # Calculate priority weights for sampling
    def _get_priority_weights(candidates: List[ActionCandidate]) -> List[float]:
        """Get normalized priority weights for weighted sampling."""
        if not candidates:
            return []
        priorities = [c.priority for c in candidates]
        min_priority = min(priorities)
        max_priority = max(priorities)
        if max_priority == min_priority:
            return [1.0] * len(candidates)
        # Normalize to 0-1, then square to emphasize high priorities
        weights = [
            ((p - min_priority) / (max_priority - min_priority)) ** 2
            for p in priorities
        ]
        # Add small base weight to ensure all candidates have some chance
        weights = [w + 0.1 for w in weights]
        total = sum(weights)
        return [w / total for w in weights]

    def _is_diverse_sequence(
        sequence: List[ActionCandidate], existing_sequences: List[List[ActionCandidate]]
    ) -> bool:
        """Check if sequence adds diversity to existing sequences."""
        if not stocks_by_symbol or not existing_sequences:
            return True

        # Get countries/industries in new sequence
        new_countries = set()
        new_industries = set()
        for action in sequence:
            stock = stocks_by_symbol.get(action.symbol)
            if stock:
                if stock.country:
                    new_countries.add(stock.country)
                if stock.industry:
                    industries = [i.strip() for i in stock.industry.split(",")]
                    new_industries.update(industries)

        # Check if this adds new diversity
        for existing_seq in existing_sequences[-10:]:  # Check last 10 sequences
            existing_countries = set()
            existing_industries = set()
            for action in existing_seq:
                stock = stocks_by_symbol.get(action.symbol)
                if stock:
                    if stock.country:
                        existing_countries.add(stock.country)
                    if stock.industry:
                        industries = [i.strip() for i in stock.industry.split(",")]
                        existing_industries.update(industries)

            # If too similar, not diverse
            country_overlap = len(new_countries & existing_countries) / max(
                len(new_countries | existing_countries), 1
            )
            industry_overlap = len(new_industries & existing_industries) / max(
                len(new_industries | existing_industries), 1
            )
            if country_overlap > 0.8 and industry_overlap > 0.8:
                return False

        return True

    # Generate combinations with priority-based sampling
    sell_weights = _get_priority_weights(filtered_sells)
    buy_weights = _get_priority_weights(filtered_buys)

    attempts = 0
    max_attempts = max_combinations * 3  # Allow more attempts to find diverse sequences

    # Early return if no opportunities available
    if not filtered_sells and not filtered_buys:
        return sequences

    while len(sequences) < max_combinations and attempts < max_attempts:
        attempts += 1

        # Sample number of sells and buys (only if opportunities exist)
        # Double-check length and max values to avoid randrange errors
        num_sells = 0
        if filtered_sells and len(filtered_sells) > 0 and max_sells > 0:
            max_sells_for_rand = min(max_sells, len(filtered_sells))
            if max_sells_for_rand > 0:
                num_sells = random.randint(1, max_sells_for_rand)

        num_buys = 0
        if filtered_buys and len(filtered_buys) > 0 and max_buys > 0:
            max_buys_for_rand = min(max_buys, len(filtered_buys))
            if max_buys_for_rand > 0:
                num_buys = random.randint(1, max_buys_for_rand)

        if num_sells + num_buys > max_steps or (num_sells == 0 and num_buys == 0):
            continue

        # Weighted sampling of sells (only if we have sells)
        sell_combo = (
            random.choices(filtered_sells, weights=sell_weights, k=num_sells)
            if num_sells > 0
            else []
        )
        # Remove duplicates by symbol (preserves order)
        seen_symbols = set()
        unique_sell_combo = []
        for s in sell_combo:
            if s.symbol not in seen_symbols:
                seen_symbols.add(s.symbol)
                unique_sell_combo.append(s)
        sell_combo = unique_sell_combo

        # Weighted sampling of buys (only if we have buys)
        buy_combo = (
            random.choices(filtered_buys, weights=buy_weights, k=num_buys)
            if num_buys > 0
            else []
        )
        # Remove duplicates by symbol (preserves order)
        seen_symbols = set()
        unique_buy_combo = []
        for b in buy_combo:
            if b.symbol not in seen_symbols:
                seen_symbols.add(b.symbol)
                unique_buy_combo.append(b)
        buy_combo = unique_buy_combo

        # Create sequence: sells first, then buys
        sequence = sell_combo + buy_combo

        # Check diversity constraint
        if not _is_diverse_sequence(sequence, sequences):
            continue

        sequences.append(sequence)

    return sequences


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

    # Cost-optimized pattern: minimize number of trades
    pattern11 = _generate_cost_optimized_pattern(
        top_profit_taking,
        top_rebalance_sells,
        top_averaging,
        top_rebalance_buys,
        top_opportunity,
        available_cash,
        max_steps,
    )
    if pattern11:
        sequences.append(pattern11)

    # Adaptive patterns: generate based on portfolio gaps (if portfolio_context provided)
    # Note: portfolio_context is not available in _generate_patterns_at_depth,
    # so adaptive patterns are generated separately in create_holistic_plan

    # Combinatorial generation (if enabled)
    if enable_combinatorial:
        all_sells = top_profit_taking + top_rebalance_sells
        all_buys = top_averaging + top_rebalance_buys + top_opportunity

        if all_sells or all_buys:
            # Check if enhanced combinatorial is enabled
            enable_enhanced_combinatorial = True  # Will be retrieved from settings
            if enable_enhanced_combinatorial:
                combo_sequences = _generate_enhanced_combinations(
                    sells=all_sells,
                    buys=all_buys,
                    max_sells=min(combinatorial_max_sells, max_steps // 2),
                    max_buys=min(combinatorial_max_buys, max_steps),
                    priority_threshold=priority_threshold,
                    max_steps=max_steps,
                    max_combinations=combinatorial_max_combinations_per_depth,
                    max_candidates=combinatorial_max_candidates,
                    stocks_by_symbol=stocks_by_symbol,
                )
            else:
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

    # Build stocks_by_symbol dict for diverse selection and adaptive patterns
    stocks_by_symbol: Optional[Dict[str, Stock]] = None
    if stocks:
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
    price_adjustments: Optional[Dict[str, float]] = None,
) -> Tuple[PortfolioContext, float]:
    """
    Simulate executing a sequence and return the resulting portfolio state.

    Args:
        sequence: List of actions to execute
        portfolio_context: Starting portfolio state
        available_cash: Starting cash
        stocks: Available stocks for metadata
        price_adjustments: Optional dict mapping symbol -> price multiplier (e.g., 1.05 for +5%)

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

        # Apply price adjustment if provided
        adjusted_price = action.price
        adjusted_value_eur = action.value_eur
        if price_adjustments and action.symbol in price_adjustments:
            multiplier = price_adjustments[action.symbol]
            adjusted_price = action.price * multiplier
            # Recalculate value with adjusted price (maintain same quantity)
            adjusted_value_eur = abs(action.quantity) * adjusted_price
            # Note: Currency conversion would happen here if needed

        new_positions = dict(current_context.positions)
        new_geographies = dict(current_context.stock_countries or {})
        new_industries = dict(current_context.stock_industries or {})

        if action.side == TradeSide.SELL:
            # Reduce position (cash is PART of portfolio, so total doesn't change)
            # Use adjusted value if price adjustments provided
            sell_value = (
                adjusted_value_eur
                if price_adjustments and action.symbol in price_adjustments
                else action.value_eur
            )
            current_value = new_positions.get(action.symbol, 0)
            new_positions[action.symbol] = max(0, current_value - sell_value)
            if new_positions[action.symbol] <= 0:
                new_positions.pop(action.symbol, None)
            current_cash += sell_value
            # Total portfolio value stays the same - we just converted stock to cash
            new_total = current_context.total_value
        else:  # BUY
            # Use adjusted value if price adjustments provided
            buy_value = (
                adjusted_value_eur
                if price_adjustments and action.symbol in price_adjustments
                else action.value_eur
            )
            if buy_value > current_cash:
                continue  # Skip if can't afford
            new_positions[action.symbol] = (
                new_positions.get(action.symbol, 0) + buy_value
            )
            if country:
                new_geographies[action.symbol] = country
            if industry:
                new_industries[action.symbol] = industry
            current_cash -= buy_value
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

    from app.modules.planning.database.planner_repository import PlannerRepository
    from app.modules.planning.domain.narrative import (
        generate_plan_narrative,
        generate_step_narrative,
    )
    from app.repositories.calculations import CalculationsRepository

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

        # Compute ineligible symbols for selling
        stocks_by_symbol = {s.symbol: s for s in stocks}
        ineligible_symbols = await _compute_ineligible_symbols(
            positions, stocks_by_symbol, trade_repo, settings_repo
        )

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
                ineligible_symbols=ineligible_symbols,
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

        # Track filtering reasons for debugging
        filtered_duplicates = 0
        filtered_priority = 0
        filtered_no_stock = 0
        filtered_allow_flag = 0
        filtered_cash = 0
        filtered_position = 0

        # Log available cash for debugging
        logger.info(f"Available cash for feasibility check: {available_cash:.2f} EUR")

        def _get_sequence_priority(sequence: List[ActionCandidate]) -> float:
            """Calculate estimated priority for a sequence."""
            return sum(c.priority for c in sequence)

        for sequence in all_sequences:
            if not sequence:
                continue

            # Filter out sequences with duplicate symbols (same symbol shouldn't appear twice)
            symbols_in_seq = [c.symbol for c in sequence]
            if len(symbols_in_seq) != len(set(symbols_in_seq)):
                filtered_duplicates += 1
                continue

            if sequence:
                avg_priority = _get_sequence_priority(sequence) / len(sequence)
                if avg_priority < priority_threshold:
                    filtered_priority += 1
                    continue

            is_feasible = True
            running_cash = available_cash

            for action in sequence:
                stock = stocks_by_symbol.get(action.symbol)
                # ActionCandidate.side is a string, not TradeSide enum
                side_str = (
                    action.side.upper()
                    if isinstance(action.side, str)
                    else str(action.side)
                )
                if side_str == "BUY":
                    if not stock:
                        is_feasible = False
                        filtered_no_stock += 1
                        break
                    if not stock.allow_buy:
                        is_feasible = False
                        filtered_allow_flag += 1
                        break
                    if action.value_eur > running_cash:
                        is_feasible = False
                        filtered_cash += 1
                        # Log first few cash failures for debugging
                        if filtered_cash <= 3:
                            logger.debug(
                                f"Cash check failed: need {action.value_eur:.2f} EUR, "
                                f"have {running_cash:.2f} EUR for {action.symbol}"
                            )
                        break
                    running_cash -= action.value_eur
                elif side_str == "SELL":
                    if not stock:
                        is_feasible = False
                        filtered_no_stock += 1
                        break
                    if not stock.allow_sell:
                        is_feasible = False
                        filtered_allow_flag += 1
                        break
                    position = positions_by_symbol.get(action.symbol)
                    if not position or position.quantity < action.quantity:
                        is_feasible = False
                        filtered_position += 1
                        break
                    running_cash += action.value_eur

            if is_feasible:
                feasible_sequences.append(sequence)

        # Log filtering breakdown
        logger.info(
            f"Feasibility filtering: {len(all_sequences)} total, "
            f"{filtered_duplicates} duplicates, {filtered_priority} low priority, "
            f"{filtered_no_stock} no stock, {filtered_allow_flag} allow flag, "
            f"{filtered_cash} cash, {filtered_position} position, "
            f"{len(feasible_sequences)} feasible"
        )

        # Insert sequences into database
        logger.info(
            f"Feasibility check: {len(all_sequences)} total sequences, "
            f"{len(feasible_sequences)} feasible sequences"
        )
        await repo.ensure_sequences_generated(portfolio_hash, feasible_sequences)
        logger.info(f"Generated {len(feasible_sequences)} sequences")

        # Emit planner sequences generated event
        try:
            from app.core.events import SystemEvent, emit

            total_sequences = await repo.get_total_sequence_count(portfolio_hash)
            evaluated_count = await repo.get_evaluation_count(portfolio_hash)
            is_finished = await repo.are_all_sequences_evaluated(portfolio_hash)

            if total_sequences > 0:
                progress_percentage = (evaluated_count / total_sequences) * 100.0
            else:
                progress_percentage = 0.0

            # Check if planning is active (same logic as API endpoint for consistency)
            is_planning = False
            if total_sequences > 0 and not is_finished:
                try:
                    from app.jobs.scheduler import get_scheduler

                    scheduler = get_scheduler()
                    if scheduler and scheduler.running:
                        jobs = scheduler.get_jobs()
                        planner_job = next(
                            (job for job in jobs if job.id == "planner_batch"), None
                        )
                        if planner_job:
                            is_planning = True
                except Exception:
                    # If we can't check scheduler, assume planning is active if there's work to do
                    is_planning = total_sequences > 0 and not is_finished

            status = {
                "has_sequences": total_sequences > 0,
                "total_sequences": total_sequences,
                "evaluated_count": evaluated_count,
                "is_planning": is_planning,
                "is_finished": is_finished,
                "portfolio_hash": portfolio_hash[:8],
                "progress_percentage": round(progress_percentage, 1),
            }

            emit(SystemEvent.PLANNER_SEQUENCES_GENERATED, status=status)
        except Exception as e:
            logger.debug(f"Could not emit planner sequences generated event: {e}")

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
        sequence_hash = seq_data["sequence_hash"]

        try:
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
            await repo.mark_sequence_completed(
                sequence_hash, portfolio_hash, evaluated_at
            )

            # Update best if better
            if end_score > best_score_in_batch:
                best_score_in_batch = end_score
                best_in_batch = sequence_hash

        except Exception as e:
            # If evaluation fails, mark sequence as completed anyway so it doesn't block planning
            # This allows trades to proceed even if some scenarios fail
            logger.warning(
                f"Failed to evaluate sequence {sequence_hash[:8]}: {e}. "
                f"Marking as examined to prevent blocking planning."
            )
            try:
                evaluated_at = datetime.now().isoformat()
                await repo.mark_sequence_completed(
                    sequence_hash, portfolio_hash, evaluated_at
                )
            except Exception as mark_error:
                logger.error(
                    f"Failed to mark sequence {sequence_hash[:8]} as completed: {mark_error}"
                )
            # Continue processing other sequences
            continue

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
    from app.modules.planning.domain.narrative import (
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

    # Compute ineligible symbols for selling
    stocks_by_symbol = {s.symbol: s for s in stocks}
    ineligible_symbols = await _compute_ineligible_symbols(
        positions, stocks_by_symbol, trade_repo, settings_repo
    )

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
            ineligible_symbols=ineligible_symbols,
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

    # Get market regime-aware settings
    enable_market_regime_scenarios = (
        await settings_repo.get_float("enable_market_regime_scenarios", 0.0) == 1.0
    )
    market_regime = None
    if enable_market_regime_scenarios:
        from app.modules.analytics.domain.market_regime import detect_market_regime

        # Detect current market regime
        market_regime = await detect_market_regime()
        logger.info(f"Market regime detected: {market_regime}")

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

    # Generate adaptive patterns based on portfolio gaps
    adaptive_patterns = _generate_adaptive_patterns(
        opportunities,
        portfolio_context,
        available_cash,
        max_plan_depth,
        max_opportunities_per_category,
        stocks_by_symbol,
    )
    sequences.extend(adaptive_patterns)

    # Filter sequences for correlation if enabled
    enable_correlation_aware = (
        await settings_repo.get_float("enable_correlation_aware", 0.0) == 1.0
    )
    if enable_correlation_aware:
        sequences = await _filter_correlation_aware_sequences(
            sequences, stocks, max_plan_depth
        )

    # Generate partial execution scenarios if enabled
    enable_partial_execution = (
        await settings_repo.get_float("enable_partial_execution", 0.0) == 1.0
    )
    if enable_partial_execution:
        partial_sequences = _generate_partial_execution_scenarios(
            sequences, max_plan_depth
        )
        sequences.extend(partial_sequences)

    # Generate constraint relaxation scenarios if enabled
    enable_constraint_relaxation = (
        await settings_repo.get_float("enable_constraint_relaxation", 0.0) == 1.0
    )
    if enable_constraint_relaxation:
        relaxed_sequences = _generate_constraint_relaxation_scenarios(
            sequences, available_cash, positions
        )
        sequences.extend(relaxed_sequences)

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

    # Get transaction cost settings for cost-adjusted scoring
    cost_penalty_factor = await settings_repo.get_float("cost_penalty_factor", 0.1)
    cost_penalty_factor = max(0.0, min(1.0, cost_penalty_factor))  # Clamp to 0-1

    # Get multi-objective optimization setting
    enable_multi_objective = (
        await settings_repo.get_float("enable_multi_objective", 0.0) == 1.0
    )

    # Get stochastic scenarios setting
    enable_stochastic_scenarios = (
        await settings_repo.get_float("enable_stochastic_scenarios", 0.0) == 1.0
    )
    stochastic_scenario_shifts = [-0.10, -0.05, 0.0, 0.05, 0.10]  # ±10%, ±5%, base

    # Get Monte Carlo paths setting
    enable_monte_carlo = (
        await settings_repo.get_float("enable_monte_carlo_paths", 0.0) == 1.0
    )
    monte_carlo_paths = await settings_repo.get_int("monte_carlo_path_count", 100)
    monte_carlo_paths = max(10, min(500, monte_carlo_paths))  # Clamp to 10-500

    # Get risk profile setting
    risk_profile_str = await settings_repo.get("risk_profile")
    if not risk_profile_str or risk_profile_str not in (
        "conservative",
        "balanced",
        "aggressive",
    ):
        risk_profile = "balanced"
    else:
        risk_profile = str(risk_profile_str)

    # Build price adjustment maps for stochastic scenarios
    # Map each symbol in sequences to its base price
    symbol_prices: Dict[str, float] = {}
    for sequence, _, _ in sequence_results_sorted:
        for action in sequence:
            if action.symbol not in symbol_prices:
                # Get price from current_prices or action price
                if current_prices and action.symbol in current_prices:
                    symbol_prices[action.symbol] = current_prices[action.symbol]
                else:
                    symbol_prices[action.symbol] = action.price

    # Define async helper to evaluate a single sequence
    async def _evaluate_sequence(
        seq_idx: int,
        sequence: List[ActionCandidate],
        end_context: PortfolioContext,
        end_cash: float,
        price_adjustments: Optional[Dict[str, float]] = None,
    ) -> Tuple[int, List[ActionCandidate], float, Dict]:
        """Evaluate a single sequence and return results."""
        # Calculate diversification score for end state
        div_score = await calculate_portfolio_score(end_context)

        # Calculate full end-state score with risk profile
        end_score, breakdown = await calculate_portfolio_end_state_score(
            positions=end_context.positions,
            total_value=end_context.total_value,
            diversification_score=div_score.total / 100,  # Normalize to 0-1
            metrics_cache=metrics_cache,
            risk_profile=risk_profile,
        )

        # Get multi-timeframe optimization setting
        enable_multi_timeframe = (
            await settings_repo.get_float("enable_multi_timeframe", 0.0) == 1.0
        )

        # If multi-timeframe optimization is enabled, calculate scores for different horizons
        if enable_multi_timeframe:
            # Short-term: 1 year (weight: 0.2)
            # Medium-term: 3 years (weight: 0.3)
            # Long-term: 5 years (weight: 0.5)
            # Adjust scoring weights based on timeframe focus
            short_term_score = (
                end_score * 0.95
            )  # Slightly lower for short-term (more uncertainty)
            medium_term_score = end_score  # Base score for medium-term
            long_term_score = (
                end_score * 1.05
            )  # Slightly higher for long-term (compounding benefits)

            # Weighted average across timeframes
            multi_timeframe_score = (
                short_term_score * 0.2 + medium_term_score * 0.3 + long_term_score * 0.5
            )

            breakdown["multi_timeframe"] = {  # type: ignore[assignment]
                "short_term_1y": round(short_term_score, 3),
                "medium_term_3y": round(medium_term_score, 3),
                "long_term_5y": round(long_term_score, 3),
                "weighted_score": round(multi_timeframe_score, 3),
            }

            # Use multi-timeframe score as the final score
            end_score = multi_timeframe_score

        # Calculate transaction cost
        total_cost = _calculate_transaction_cost(
            sequence, transaction_cost_fixed, transaction_cost_percent
        )

        # Apply transaction cost penalty if enabled
        if cost_penalty_factor > 0.0 and end_context.total_value > 0:
            cost_penalty = (total_cost / end_context.total_value) * cost_penalty_factor
            end_score = max(0.0, end_score - cost_penalty)
            # breakdown is a dict, update it with transaction cost info
            breakdown["transaction_cost"] = {  # type: ignore[assignment]
                "total_cost_eur": round(total_cost, 2),
                "cost_penalty": round(cost_penalty, 4),
                "adjusted_score": round(end_score, 3),
            }

        # Extract risk score from breakdown (stability score, normalized to 0-1)
        stability_data = breakdown.get("stability")
        if isinstance(stability_data, dict):
            risk_score = stability_data.get("weighted_score", 0.5)
            if not isinstance(risk_score, (int, float)):
                risk_score = 0.5
        else:
            risk_score = 0.5

        # Store multi-objective metrics in breakdown
        breakdown["multi_objective"] = {  # type: ignore[assignment]
            "end_score": round(end_score, 3),
            "diversification_score": round(div_score.total / 100, 3),
            "risk_score": round(risk_score, 3),
            "transaction_cost": round(total_cost, 2),
        }

        # Store price scenario info if stochastic
        if price_adjustments:
            breakdown["price_scenario"] = {  # type: ignore[assignment]
                "adjustments": {k: round(v, 3) for k, v in price_adjustments.items()},
            }

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
    # If multi-objective, use SequenceEvaluation objects, otherwise use tuples
    beam: List[Tuple[List[ActionCandidate], float, Dict]] = (
        []
    )  # (sequence, score, breakdown)
    beam_multi: List[SequenceEvaluation] = []  # Multi-objective beam
    best_end_score = 0.0
    plateau_count = 0
    evaluated_count = 0

    def _update_beam(
        sequence: List[ActionCandidate], score: float, breakdown: Dict
    ) -> None:
        """Update beam with new sequence, keeping only top K."""
        nonlocal best_end_score

        if enable_multi_objective:
            # Multi-objective mode: use Pareto frontier
            # Extract objectives from breakdown
            mo_data = breakdown.get("multi_objective", {})
            div_score = mo_data.get("diversification_score", 0.5)
            risk_score = mo_data.get("risk_score", 0.5)
            trans_cost = mo_data.get("transaction_cost", 0.0)

            eval_obj = SequenceEvaluation(
                sequence=sequence,
                end_score=score,
                diversification_score=div_score,
                risk_score=risk_score,
                transaction_cost=trans_cost,
                breakdown=breakdown,
            )

            # Remove dominated sequences
            beam_multi[:] = [e for e in beam_multi if not e.is_dominated_by(eval_obj)]

            # Add new evaluation if not dominated
            if not any(eval_obj.is_dominated_by(e) for e in beam_multi):
                beam_multi.append(eval_obj)

            # Keep only top K by end_score (primary objective)
            beam_multi.sort(key=lambda x: x.end_score, reverse=True)
            if len(beam_multi) > beam_width:
                beam_multi[:] = beam_multi[:beam_width]

            # Update best score
            if score > best_end_score:
                best_end_score = score
        else:
            # Single-objective mode: simple beam
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

        # Evaluate batch - with Monte Carlo or stochastic scenarios if enabled
        if enable_monte_carlo:
            # Monte Carlo: Generate random price paths using historical volatility
            async def _evaluate_with_monte_carlo(
                seq_idx: int, sequence: List[ActionCandidate]
            ) -> Tuple[int, List[ActionCandidate], float, Dict]:
                """Evaluate sequence under Monte Carlo price paths."""
                import math
                import random

                # Get unique symbols in this sequence
                seq_symbols = set(action.symbol for action in sequence)

                # Get volatility for each symbol
                symbol_volatilities: Dict[str, float] = {}
                for symbol in seq_symbols:
                    if symbol in metrics_cache:
                        vol = metrics_cache[symbol].get("VOLATILITY_ANNUAL", 0.2)
                        symbol_volatilities[symbol] = max(
                            0.1, min(1.0, vol)
                        )  # Clamp 10%-100%
                    else:
                        symbol_volatilities[symbol] = 0.2  # Default 20% volatility

                # Generate random price paths
                path_scores = []
                path_breakdowns = []

                for path_idx in range(monte_carlo_paths):
                    # Generate random price adjustments for this path
                    # Using geometric Brownian motion: price_change = exp(volatility * random_normal)
                    price_adjustments: Dict[str, float] = {}
                    for symbol in seq_symbols:
                        if symbol in symbol_prices:
                            vol = symbol_volatilities.get(symbol, 0.2)
                            # Generate random normal (mean=0, std=1)
                            random_normal = random.gauss(0.0, 1.0)
                            # Scale by volatility (annualized, so use sqrt(1/252) for daily)
                            daily_vol = vol / math.sqrt(252)
                            # Price multiplier: exp(volatility * random_normal)
                            multiplier = math.exp(daily_vol * random_normal)
                            # Clamp to reasonable range (0.5x to 2.0x)
                            multiplier = max(0.5, min(2.0, multiplier))
                            price_adjustments[symbol] = multiplier

                    # Re-simulate sequence with adjusted prices
                    adjusted_end_context, adjusted_end_cash = await simulate_sequence(
                        sequence,
                        portfolio_context,
                        available_cash,
                        stocks,
                        price_adjustments,
                    )

                    # Evaluate with adjusted context
                    path_result = await _evaluate_sequence(
                        seq_idx,
                        sequence,
                        adjusted_end_context,
                        adjusted_end_cash,
                        price_adjustments,
                    )
                    path_scores.append(path_result[2])  # Extract score
                    path_breakdowns.append(path_result[3])  # Extract breakdown

                # Calculate statistics across all paths
                avg_score = sum(path_scores) / len(path_scores)
                worst_score = min(path_scores)
                best_score = max(path_scores)
                # Use percentile scores for robustness
                sorted_scores = sorted(path_scores)
                p10_score = sorted_scores[
                    int(len(sorted_scores) * 0.10)
                ]  # 10th percentile
                p90_score = sorted_scores[
                    int(len(sorted_scores) * 0.90)
                ]  # 90th percentile

                # Use conservative approach: weighted average favoring worst-case
                final_score = (
                    (worst_score * 0.4) + (p10_score * 0.3) + (avg_score * 0.3)
                )

                # Use median breakdown and add Monte Carlo metrics
                median_breakdown = path_breakdowns[len(path_breakdowns) // 2]
                median_breakdown["monte_carlo"] = {  # type: ignore[dict-item]
                    "paths_evaluated": monte_carlo_paths,
                    "avg_score": round(avg_score, 3),
                    "worst_score": round(worst_score, 3),
                    "best_score": round(best_score, 3),
                    "p10_score": round(p10_score, 3),
                    "p90_score": round(p90_score, 3),
                    "final_score": round(final_score, 3),
                }

                return (seq_idx, sequence, final_score, median_breakdown)

            # Evaluate all sequences in batch with Monte Carlo
            evaluation_tasks = [
                _evaluate_with_monte_carlo(batch_start + i, sequence)
                for i, (sequence, _, _) in enumerate(batch)
            ]

            batch_results = await asyncio.gather(*evaluation_tasks)
        elif enable_stochastic_scenarios:
            # Evaluate each sequence under multiple price scenarios
            async def _evaluate_with_scenarios(
                seq_idx: int, sequence: List[ActionCandidate]
            ) -> Tuple[int, List[ActionCandidate], float, Dict]:
                """Evaluate sequence under multiple price scenarios."""
                # Get unique symbols in this sequence
                seq_symbols = set(action.symbol for action in sequence)

                # Evaluate under each price scenario
                scenario_scores = []
                scenario_breakdowns = []
                for shift in stochastic_scenario_shifts:
                    # Create price adjustments for this scenario
                    price_adjustments = {
                        symbol: 1.0 + shift
                        for symbol in seq_symbols
                        if symbol in symbol_prices
                    }

                    # Re-simulate sequence with adjusted prices
                    adjusted_end_context, adjusted_end_cash = await simulate_sequence(
                        sequence,
                        portfolio_context,
                        available_cash,
                        stocks,
                        price_adjustments,
                    )

                    # Evaluate with adjusted context
                    scenario_result = await _evaluate_sequence(
                        seq_idx,
                        sequence,
                        adjusted_end_context,
                        adjusted_end_cash,
                        price_adjustments,
                    )
                    scenario_scores.append(scenario_result[2])  # Extract score
                    scenario_breakdowns.append(scenario_result[3])  # Extract breakdown

                # Use average score across scenarios (or worst-case: min)
                avg_score = sum(scenario_scores) / len(scenario_scores)
                worst_score = min(scenario_scores)
                # Use conservative approach: weighted average favoring worst-case
                final_score = (worst_score * 0.6) + (avg_score * 0.4)

                # Use base scenario breakdown (shift=0) and add stochastic metrics
                base_breakdown = scenario_breakdowns[2]  # Index 2 is shift=0.0
                base_breakdown["stochastic"] = {  # type: ignore[dict-item]
                    "avg_score": round(avg_score, 3),
                    "worst_score": round(worst_score, 3),
                    "final_score": round(final_score, 3),
                    "scenarios_evaluated": len(stochastic_scenario_shifts),
                }

                return (seq_idx, sequence, final_score, base_breakdown)

            # Evaluate all sequences in batch with scenarios
            evaluation_tasks = [
                _evaluate_with_scenarios(batch_start + i, sequence)
                for i, (sequence, _, _) in enumerate(batch)
            ]

            batch_results = await asyncio.gather(*evaluation_tasks)
        else:
            # Standard evaluation without stochastic scenarios
            evaluation_tasks = [
                _evaluate_sequence(batch_start + i, sequence, end_context, end_cash)
                for i, (sequence, end_context, end_cash) in enumerate(batch)
            ]

            batch_results = await asyncio.gather(*evaluation_tasks)

        # Process batch results
        beam_updated = False
        for seq_idx, sequence, end_score, breakdown in batch_results:
            evaluated_count += 1

            if enable_multi_objective:
                # Multi-objective: always try to update beam (Pareto frontier)
                old_size = len(beam_multi)
                _update_beam(sequence, end_score, breakdown)
                new_size = len(beam_multi)
                if new_size > old_size or any(
                    e.end_score > best_end_score for e in beam_multi
                ):
                    beam_updated = True
                    if end_score > best_end_score:
                        plateau_count = 0
                        logger.info(
                            f"Sequence {seq_idx+1} -> NEW BEST (score: {end_score:.3f}, "
                            f"Pareto frontier size: {len(beam_multi)})"
                        )
                    else:
                        logger.debug(
                            f"Sequence {seq_idx+1} added to Pareto frontier "
                            f"(score: {end_score:.3f}, frontier size: {len(beam_multi)})"
                        )
                else:
                    plateau_count += 1
            else:
                # Single-objective: check if this sequence would improve the beam
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
            beam_size = len(beam_multi) if enable_multi_objective else len(beam)
            logger.info(
                f"Early termination: Beam converged (no improvement in {plateau_count} consecutive sequences, "
                f"evaluated {evaluated_count}/{len(sequence_results_sorted)}, beam size: {beam_size})"
            )
            break

    # Select best sequence from beam
    if enable_multi_objective:
        if not beam_multi:
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
        # Select best from Pareto frontier (highest end_score)
        best_eval = beam_multi[0]
        best_sequence = best_eval.sequence
        best_end_score = best_eval.end_score
        best_breakdown = best_eval.breakdown
        logger.info(
            f"Selected best sequence from Pareto frontier of {len(beam_multi)} "
            f"(score: {best_end_score:.3f}, div: {best_eval.diversification_score:.3f}, "
            f"risk: {best_eval.risk_score:.3f}, cost: €{best_eval.transaction_cost:.2f})"
        )
    else:
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
