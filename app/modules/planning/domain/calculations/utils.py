"""Utility functions for planner operations.

Pure functions extracted from holistic_planner.py for reusability and testability.
"""

import hashlib
import json
import logging
from typing import Dict, List, Optional, Set

from app.domain.models import Position, Security
from app.domain.value_objects.trade_side import TradeSide
from app.modules.planning.domain.models import ActionCandidate

logger = logging.getLogger(__name__)


def calculate_transaction_cost(
    sequence: List[ActionCandidate],
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


def hash_sequence(sequence: List[ActionCandidate]) -> str:
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
    # Keep order-dependent since sequence order matters
    sequence_json = json.dumps(sequence_repr, sort_keys=False)
    return hashlib.md5(sequence_json.encode()).hexdigest()


def calculate_weight_gaps(
    target_weights: Dict[str, float],
    current_weights: Dict[str, float],
    total_value: float,
) -> List[Dict]:
    """
    Calculate weight gaps between target and current weights.

    Args:
        target_weights: Target weight for each symbol (0-1)
        current_weights: Current weight for each symbol (0-1)
        total_value: Total portfolio value in EUR

    Returns:
        List of gap info dicts sorted by absolute gap (largest first)
    """
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

    def _get_gap_value(x: Dict) -> float:
        gap = x.get("gap", 0.0)
        if isinstance(gap, (int, float)):
            return abs(float(gap))
        return 0.0

    weight_gaps.sort(key=_get_gap_value, reverse=True)
    return weight_gaps


def is_trade_worthwhile(
    gap_value: float, transaction_cost_fixed: float, transaction_cost_percent: float
) -> bool:
    """
    Check if trade is worthwhile based on transaction costs.

    A trade is considered worthwhile if the gap value is at least 2x
    the transaction cost (to avoid churning).

    Args:
        gap_value: Value of the weight gap in EUR
        transaction_cost_fixed: Fixed cost per trade in EUR
        transaction_cost_percent: Variable cost as fraction

    Returns:
        True if trade is worth executing
    """
    trade_cost = transaction_cost_fixed + abs(gap_value) * transaction_cost_percent
    return abs(gap_value) >= trade_cost * 2


async def compute_ineligible_symbols(
    positions: List[Position],
    securities_by_symbol: Dict[str, Security],
    trade_repo,
    settings_repo,
) -> Set[str]:
    """
    Compute set of symbols that are ineligible for selling.

    Checks eligibility based on:
    - Minimum holding period
    - Sell cooldown period
    - Maximum loss threshold

    Args:
        positions: Current portfolio positions
        securities_by_symbol: Dict mapping symbol to Security
        trade_repo: Trade repository for transaction history
        settings_repo: Settings repository for rules

    Returns:
        Set of symbols that cannot be sold
    """
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
        security = securities_by_symbol.get(symbol)
        if not security or not security.allow_sell:
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
            allow_sell=security.allow_sell,
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


def process_buy_opportunity(
    gap_info: Dict,
    security: Optional[Security],
    position: Optional[Position],
    price: float,
    opportunities: Dict[str, List[ActionCandidate]],
) -> None:
    """
    Process a buy opportunity from weight gap.

    Creates an ActionCandidate for buying and adds it to the appropriate
    category (averaging_down or rebalance_buys).

    Args:
        gap_info: Weight gap information dict
        security: Security to buy (if available)
        position: Current position (if exists)
        price: Current price
        opportunities: Dict to add candidate to (modified in-place)
    """
    if not security or not security.allow_buy:
        return

    symbol = gap_info["symbol"]
    gap_value = gap_info["gap_value"]

    quantity = int(gap_value / price)
    if security.min_lot and quantity < security.min_lot:
        quantity = security.min_lot

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
    multiplier = security.priority_multiplier if security else 1.0
    final_priority = base_priority * multiplier

    opportunities[category].append(
        ActionCandidate(
            side=TradeSide.BUY,
            symbol=symbol,
            name=security.name if security else symbol,
            quantity=quantity,
            price=price,
            value_eur=trade_value,
            currency=currency,
            priority=final_priority,
            reason=f"Optimizer target: {gap_info['target']:.1%} (current: {gap_info['current']:.1%})",
            tags=tags,
        )
    )


def process_sell_opportunity(
    gap_info: Dict,
    security: Optional[Security],
    position: Position,
    price: float,
    opportunities: Dict[str, List[ActionCandidate]],
) -> None:
    """
    Process a sell opportunity from weight gap.

    Creates an ActionCandidate for selling and adds it to rebalance_sells.

    Args:
        gap_info: Weight gap information dict
        security: Security to sell (if available)
        position: Current position
        price: Current price
        opportunities: Dict to add candidate to (modified in-place)
    """
    if not position:
        return

    if security and not security.allow_sell:
        return

    if security and position.quantity <= security.min_lot:
        logger.debug(f"{gap_info['symbol']}: at min_lot, can't reduce further")
        return

    symbol = gap_info["symbol"]
    gap_value = gap_info["gap_value"]
    sell_value = abs(gap_value)
    quantity = int(float(sell_value) / float(price))

    if security and security.min_lot:
        remaining = position.quantity - quantity
        if remaining < security.min_lot and remaining > 0:
            quantity = int(position.quantity - security.min_lot)

    if quantity <= 0:
        return

    trade_value = quantity * price

    # Apply priority multiplier inversely: higher multiplier = lower sell priority
    base_priority = abs(gap_info["gap"]) * 100
    multiplier = security.priority_multiplier if security else 1.0
    final_priority = base_priority / multiplier

    opportunities["rebalance_sells"].append(
        ActionCandidate(
            side=TradeSide.SELL,
            symbol=symbol,
            name=security.name if security else symbol,
            quantity=quantity,
            price=price,
            value_eur=trade_value,
            currency=position.currency,
            priority=final_priority,
            reason=f"Optimizer target: {gap_info['target']:.1%} (current: {gap_info['current']:.1%})",
            tags=["rebalance", "optimizer_target"],
        )
    )
