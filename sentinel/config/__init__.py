"""
Sentinel Configuration Package

Contains configuration constants and defaults.
"""

from sentinel.config.currencies import (
    DIRECT_PAIRS,
    RATE_SYMBOLS,
    SUPPORTED_CURRENCIES,
)

__all__ = [
    "SUPPORTED_CURRENCIES",
    "DIRECT_PAIRS",
    "RATE_SYMBOLS",
]
