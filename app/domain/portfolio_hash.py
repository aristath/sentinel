"""
Portfolio Hash Generation

Generates a deterministic hash from current portfolio state.
Used to identify when recommendations apply to the same portfolio state.

The hash includes:
- All positions (including zero quantities for stocks in universe)
- Cash balances as pseudo-positions (CASH.EUR, CASH.USD, etc.)
- The full stocks universe to detect when new stocks are added
"""

import hashlib
from typing import Any, Dict, List, Optional


def generate_portfolio_hash(
    positions: List[Dict[str, Any]],
    stocks: Optional[List[str]] = None,
    cash_balances: Optional[Dict[str, float]] = None,
) -> str:
    """
    Generate a deterministic hash from current portfolio state.

    Args:
        positions: List of position dicts with 'symbol' and 'quantity' keys
        stocks: Optional list of all stock symbols in universe (to detect new stocks)
        cash_balances: Optional dict of currency -> amount (e.g., {"EUR": 1500.0})

    Returns:
        8-character hex hash (first 8 chars of MD5)

    Example:
        positions = [{"symbol": "AAPL", "quantity": 10}]
        stocks = ["AAPL", "MSFT", "GOOGL"]
        cash = {"EUR": 1500.0, "USD": 200.0}
        hash = generate_portfolio_hash(positions, stocks, cash)
    """
    # Build a dict of symbol -> quantity from positions
    # Use Union[int, float] to handle both stock quantities (int) and cash (float)
    position_map: Dict[str, float | int] = {
        p["symbol"].upper(): int(p.get("quantity", 0) or 0) for p in positions
    }

    # If stocks universe provided, ensure all stocks are included (with 0 if not held)
    if stocks:
        for symbol in stocks:
            symbol_upper = symbol.upper()
            if symbol_upper not in position_map:
                position_map[symbol_upper] = 0

    # Add cash balances as pseudo-positions (filter out zero balances)
    if cash_balances:
        for currency, amount in cash_balances.items():
            if amount > 0:
                # Round to 2 decimal places for stability
                position_map[f"CASH.{currency.upper()}"] = round(amount, 2)

    # Sort by symbol for deterministic ordering
    sorted_symbols = sorted(position_map.keys())

    # Build canonical string: "SYMBOL:QUANTITY,SYMBOL:QUANTITY,..."
    parts = []
    for symbol in sorted_symbols:
        quantity = position_map[symbol]
        # Use int for stock quantities, float for cash
        if symbol.startswith("CASH."):
            parts.append(f"{symbol}:{quantity}")
        else:
            parts.append(f"{symbol}:{int(quantity)}")

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
        settings = {"min_trade_size": 100, "min_stock_score": 0.5}
        hash = generate_settings_hash(settings)  # e.g., "b1c2d3e4"
    """
    # Settings that affect recommendation calculations
    # Note: min_trade_size and recommendation_depth removed (handled by optimizer now)
    relevant_keys = sorted(
        [
            "min_stock_score",
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


def generate_recommendation_cache_key(
    positions: List[Dict[str, Any]],
    settings_dict: Dict[str, Any],
    stocks: Optional[List[str]] = None,
    cash_balances: Optional[Dict[str, float]] = None,
) -> str:
    """
    Generate a cache key from portfolio state and settings.

    This ensures that cache is invalidated when positions, settings,
    stocks universe, or cash balances change.

    Args:
        positions: List of position dicts with 'symbol' and 'quantity' keys
        settings_dict: Dictionary of settings values
        stocks: Optional list of all stock symbols in universe
        cash_balances: Optional dict of currency -> amount

    Returns:
        17-character combined hash (portfolio_hash:settings_hash)

    Example:
        positions = [{"symbol": "AAPL", "quantity": 10}]
        settings = {"min_stock_score": 0.5}
        stocks = ["AAPL", "MSFT"]
        cash = {"EUR": 1500.0}
        key = generate_recommendation_cache_key(positions, settings, stocks, cash)
    """
    portfolio_hash = generate_portfolio_hash(positions, stocks, cash_balances)
    settings_hash = generate_settings_hash(settings_dict)
    return f"{portfolio_hash}:{settings_hash}"
