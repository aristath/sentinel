"""
Validation Utilities - Re-exports from price_validator for unified interface.

The actual implementation remains in sentinel.price_validator.
This module provides a convenience re-export.
"""

# Re-export from the existing price_validator module
from sentinel.price_validator import (
    CONTEXT_WINDOW_DAYS,
    MAX_PRICE_CHANGE_PCT,
    MAX_PRICE_MULTIPLIER,
    MIN_PRICE_CHANGE_PCT,
    MIN_PRICE_MULTIPLIER,
    PriceValidator,
    check_trade_blocking,
    get_price_anomaly_warning,
)

__all__ = [
    "PriceValidator",
    "check_trade_blocking",
    "get_price_anomaly_warning",
    "MAX_PRICE_MULTIPLIER",
    "MIN_PRICE_MULTIPLIER",
    "MAX_PRICE_CHANGE_PCT",
    "MIN_PRICE_CHANGE_PCT",
    "CONTEXT_WINDOW_DAYS",
]
