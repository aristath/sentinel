"""
Portfolio Hash Generation

Generates a deterministic hash from current portfolio state.
Used to identify when recommendations apply to the same portfolio state.

The hash includes:
- All positions (including zero quantities for securities in universe)
- Cash balances as pseudo-positions (CASH.EUR, CASH.USD, etc.)
- The full securities universe to detect when new securities are added
- Per-symbol configuration: allow_buy, allow_sell, min_portfolio_target, max_portfolio_target, country, industry
"""

import hashlib
import logging
from typing import Any, Dict, List, Optional

from app.domain.models import Security

logger = logging.getLogger(__name__)


def apply_pending_orders_to_portfolio(
    positions: List[Dict[str, Any]],
    cash_balances: Dict[str, float],
    pending_orders: List[Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], Dict[str, float]]:
    """
    Apply pending orders to positions and cash balances to get hypothetical future state.

    For pending BUY orders: reduces cash balance by quantity * price in the order's currency.
    For pending SELL orders: reduces position quantity by the order quantity.

    Args:
        positions: List of position dicts with 'symbol' and 'quantity' keys
        cash_balances: Dict of currency -> amount (e.g., {"EUR": 1500.0, "USD": 200.0})
        pending_orders: List of pending order dicts with keys: symbol, side, quantity, price, currency

    Returns:
        Tuple of (adjusted_positions, adjusted_cash_balances)

    Example:
        positions = [{"symbol": "AAPL", "quantity": 10}]
        cash = {"EUR": 1500.0}
        orders = [{"symbol": "AAPL", "side": "buy", "quantity": 5, "price": 100.0, "currency": "EUR"}]
        adjusted_pos, adjusted_cash = apply_pending_orders_to_portfolio(positions, cash, orders)
        # adjusted_pos = [{"symbol": "AAPL", "quantity": 15}]
        # adjusted_cash = {"EUR": 1000.0}
    """
    # Create a copy of positions as a dict for easier manipulation
    position_map: Dict[str, float] = {
        p["symbol"].upper(): float(p.get("quantity", 0) or 0) for p in positions
    }

    # Create a copy of cash balances
    adjusted_cash = cash_balances.copy()

    # Process each pending order
    for order in pending_orders:
        symbol = (order.get("symbol") or "").upper()
        side = (order.get("side") or "").lower()
        quantity = float(order.get("quantity", 0) or 0)
        price = float(order.get("price", 0) or 0)
        currency = order.get("currency") or "EUR"

        if not symbol or quantity <= 0 or price <= 0:
            logger.warning(
                f"Skipping invalid pending order: symbol={symbol}, quantity={quantity}, price={price}"
            )
            continue

        if side == "buy":
            # Reduce cash by the order value
            order_value = quantity * price
            current_cash = adjusted_cash.get(currency, 0.0)
            adjusted_cash[currency] = max(0.0, current_cash - order_value)

            # Increase position quantity (assuming order will execute)
            current_quantity = position_map.get(symbol, 0.0)
            position_map[symbol] = current_quantity + quantity

            logger.debug(
                f"Applied pending BUY: {symbol} +{quantity}, cash {currency} -{order_value:.2f}"
            )

        elif side == "sell":
            # Reduce position quantity
            current_quantity = position_map.get(symbol, 0.0)
            new_quantity = max(0.0, current_quantity - quantity)
            position_map[symbol] = new_quantity

            # Note: Cash is not increased here because SELL orders don't generate cash until executed
            # The planner should account for this when calculating available cash

            logger.debug(
                f"Applied pending SELL: {symbol} -{quantity} (from {current_quantity} to {new_quantity})"
            )

        else:
            logger.warning(f"Unknown order side: {side} for order {symbol}")

    # Convert position_map back to list of dicts
    adjusted_positions = [
        {"symbol": symbol, "quantity": int(qty) if qty > 0 else 0}
        for symbol, qty in position_map.items()
        if qty > 0  # Only include positions with quantity > 0
    ]

    return adjusted_positions, adjusted_cash


def generate_portfolio_hash(
    positions: List[Dict[str, Any]],
    securities: Optional[List[Security]] = None,
    cash_balances: Optional[Dict[str, float]] = None,
    pending_orders: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """
    Generate a deterministic hash from current portfolio state.

    Args:
        positions: List of position dicts with 'symbol' and 'quantity' keys
        securities: Optional list of Security objects in universe (to detect new securities and include config)
        cash_balances: Optional dict of currency -> amount (e.g., {"EUR": 1500.0})
        pending_orders: Optional list of pending order dicts with keys: symbol, side, quantity, price, currency

    Returns:
        8-character hex hash (first 8 chars of MD5)

    Example:
        positions = [{"symbol": "AAPL", "quantity": 10}]
        securities = [Security(symbol="AAPL", ...), Security(symbol="MSFT", ...)]
        cash = {"EUR": 1500.0, "USD": 200.0}
        orders = [{"symbol": "AAPL", "side": "buy", "quantity": 5, "price": 100.0, "currency": "EUR"}]
        hash = generate_portfolio_hash(positions, securities, cash, orders)
    """
    # Apply pending orders to get hypothetical future state
    if pending_orders:
        positions, cash_balances = apply_pending_orders_to_portfolio(
            positions, cash_balances or {}, pending_orders
        )

    # Build a dict of symbol -> quantity from positions
    # Use float | int to handle both security quantities (int) and cash (float)
    position_map: Dict[str, float | int] = {
        p["symbol"].upper(): int(p.get("quantity", 0) or 0) for p in positions
    }

    # Build a dict of symbol -> security config data
    stock_config_map: Dict[str, Dict[str, Any]] = {}

    if securities:
        for security in securities:
            symbol_upper = security.symbol.upper()
            # Ensure security is in position_map (with 0 if not held)
            if symbol_upper not in position_map:
                position_map[symbol_upper] = 0

            # Extract config fields
            stock_config_map[symbol_upper] = {
                "allow_buy": security.allow_buy,
                "allow_sell": security.allow_sell,
                "min_portfolio_target": security.min_portfolio_target,
                "max_portfolio_target": security.max_portfolio_target,
                "country": security.country or "",
                "industry": security.industry or "",
            }

    # Add cash balances as pseudo-positions (filter out zero balances)
    if cash_balances:
        for currency, amount in cash_balances.items():
            if amount > 0:
                # Round to 2 decimal places for stability
                position_map[f"CASH.{currency.upper()}"] = round(amount, 2)

    # Sort by symbol for deterministic ordering
    sorted_symbols = sorted(position_map.keys())

    # Build canonical string: "SYMBOL:QUANTITY:allow_buy:allow_sell:min_target:max_target:country:industry"
    parts = []
    for symbol in sorted_symbols:
        quantity = position_map[symbol]
        # Use int for security quantities, float for cash
        if symbol.startswith("CASH."):
            parts.append(f"{symbol}:{quantity}")
        else:
            # Get config for this symbol (use defaults if not in securities list)
            config = stock_config_map.get(symbol, {})
            allow_buy = config.get("allow_buy", True)
            allow_sell = config.get("allow_sell", False)
            min_target = config.get("min_portfolio_target")
            max_target = config.get("max_portfolio_target")
            country = config.get("country", "")
            industry = config.get("industry", "")

            # Format config fields
            min_target_str = "" if min_target is None else str(min_target)
            max_target_str = "" if max_target is None else str(max_target)

            parts.append(
                f"{symbol}:{int(quantity)}:{allow_buy}:{allow_sell}:{min_target_str}:{max_target_str}:{country}:{industry}"
            )

    canonical = ",".join(parts)

    # Generate hash and return first 8 characters
    full_hash = hashlib.md5(canonical.encode()).hexdigest()
    return full_hash[:8]


def generate_settings_hash(settings_dict: Dict[str, Any]) -> str:
    """
    Generate a deterministic hash from settings that affect recommendations.

    Args:
        settings_dict: Dictionary of settings values

    Returns:
        8-character hex hash (first 8 chars of MD5)

    Example:
        settings = {"min_trade_size": 100, "min_security_score": 0.5}
        hash = generate_settings_hash(settings)  # e.g., "b1c2d3e4"
    """
    # Settings that affect recommendation calculations
    # Note: min_trade_size and recommendation_depth removed (handled by optimizer now)
    relevant_keys = sorted(
        [
            "min_security_score",
            "min_hold_days",
            "sell_cooldown_days",
            "max_loss_threshold",
            "target_annual_return",
            "optimizer_blend",
            "optimizer_target_return",
            "transaction_cost_fixed",
            "transaction_cost_percent",
            "min_cash_reserve",
            "max_plan_depth",
        ]
    )

    # Build canonical string: "key:value,key:value,..."
    parts = [f"{k}:{settings_dict.get(k, '')}" for k in relevant_keys]
    canonical = ",".join(parts)

    # Generate hash and return first 8 characters
    full_hash = hashlib.md5(canonical.encode()).hexdigest()
    return full_hash[:8]


def generate_allocations_hash(allocations_dict: Dict[str, float]) -> str:
    """
    Generate a deterministic hash from allocation targets.

    Args:
        allocations_dict: Dictionary of allocation targets with keys like
                         "country:United States" or "industry:Technology"
                         and values as target percentages

    Returns:
        8-character hex hash (first 8 chars of MD5)

    Example:
        allocations = {"country:United States": 0.6, "industry:Technology": 0.3}
        hash = generate_allocations_hash(allocations)  # e.g., "a1b2c3d4"
    """
    if not allocations_dict:
        return "00000000"  # Empty allocations

    # Sort by key for deterministic ordering
    sorted_keys = sorted(allocations_dict.keys())

    # Build canonical string: "key:value,key:value,..."
    # Round values to 4 decimal places for stability
    parts = [f"{k}:{round(allocations_dict[k], 4)}" for k in sorted_keys]
    canonical = ",".join(parts)

    # Generate hash and return first 8 characters
    full_hash = hashlib.md5(canonical.encode()).hexdigest()
    return full_hash[:8]


def generate_recommendation_cache_key(
    positions: List[Dict[str, Any]],
    settings_dict: Dict[str, Any],
    securities: Optional[List[Security]] = None,
    cash_balances: Optional[Dict[str, float]] = None,
    allocations_dict: Optional[Dict[str, float]] = None,
    pending_orders: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """
    Generate a cache key from portfolio state, settings, and allocations.

    This ensures that cache is invalidated when positions, settings,
    securities universe, cash balances, per-symbol configuration, allocation targets,
    or pending orders change.

    Args:
        positions: List of position dicts with 'symbol' and 'quantity' keys
        settings_dict: Dictionary of settings values
        securities: Optional list of Security objects in universe
        cash_balances: Optional dict of currency -> amount
        allocations_dict: Optional dict of allocation targets (e.g., {"country:US": 0.6})
        pending_orders: Optional list of pending order dicts with keys: symbol, side, quantity, price, currency

    Returns:
        26-character combined hash (portfolio_hash:settings_hash:allocations_hash)

    Example:
        positions = [{"symbol": "AAPL", "quantity": 10}]
        settings = {"min_security_score": 0.5}
        securities = [Security(symbol="AAPL", ...), Security(symbol="MSFT", ...)]
        cash = {"EUR": 1500.0}
        allocations = {"country:United States": 0.6}
        orders = [{"symbol": "AAPL", "side": "buy", "quantity": 5, "price": 100.0, "currency": "EUR"}]
        key = generate_recommendation_cache_key(positions, settings, securities, cash, allocations, orders)
    """
    portfolio_hash = generate_portfolio_hash(
        positions, securities, cash_balances, pending_orders
    )
    settings_hash = generate_settings_hash(settings_dict)
    allocations_hash = generate_allocations_hash(allocations_dict or {})
    return f"{portfolio_hash}:{settings_hash}:{allocations_hash}"
