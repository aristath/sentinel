"""
Portfolio Hash Generation

Generates a deterministic hash from current portfolio positions.
Used to identify when recommendations apply to the same portfolio state.
"""

import hashlib
from typing import Any, Dict, List


def generate_portfolio_hash(positions: List[Dict[str, Any]]) -> str:
    """
    Generate a deterministic hash from current portfolio positions.

    Args:
        positions: List of position dicts with 'symbol' and 'quantity' keys

    Returns:
        8-character hex hash (first 8 chars of MD5)

    Example:
        positions = [{"symbol": "AAPL", "quantity": 10}, {"symbol": "MSFT", "quantity": 5}]
        hash = generate_portfolio_hash(positions)  # e.g., "a1b2c3d4"
    """
    # Filter out positions with zero or no quantity
    active_positions = [
        p for p in positions if p.get("quantity", 0) and p.get("quantity", 0) > 0
    ]

    # Sort positions by symbol for deterministic ordering
    sorted_positions = sorted(active_positions, key=lambda p: p["symbol"])

    # Build canonical string: "SYMBOL:QUANTITY,SYMBOL:QUANTITY,..."
    # Round quantity to integer to avoid float precision issues
    parts = [f"{p['symbol'].upper()}:{int(p['quantity'])}" for p in sorted_positions]
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
        ]
    )

    # Build canonical string: "key:value,key:value,..."
    parts = [f"{k}:{settings_dict.get(k, '')}" for k in relevant_keys]
    canonical = ",".join(parts)

    # Generate hash and return first 8 characters
    full_hash = hashlib.md5(canonical.encode()).hexdigest()
    return full_hash[:8]


def generate_recommendation_cache_key(
    positions: List[Dict[str, Any]], settings_dict: Dict[str, Any]
) -> str:
    """
    Generate a cache key from both portfolio positions and settings.

    This ensures that cache is invalidated when either positions or
    relevant settings change.

    Args:
        positions: List of position dicts with 'symbol' and 'quantity' keys
        settings_dict: Dictionary of settings values

    Returns:
        16-character combined hash (portfolio_hash:settings_hash)

    Example:
        positions = [{"symbol": "AAPL", "quantity": 10}]
        settings = {"min_trade_size": 100}
        key = generate_recommendation_cache_key(positions, settings)  # e.g., "a1b2c3d4:e5f6g7h8"
    """
    portfolio_hash = generate_portfolio_hash(positions)
    settings_hash = generate_settings_hash(settings_dict)
    return f"{portfolio_hash}:{settings_hash}"
