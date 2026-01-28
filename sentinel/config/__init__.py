"""
Sentinel Configuration Package

Contains configuration constants and defaults.
"""

from sentinel.config.currencies import (
    SUPPORTED_CURRENCIES,
    DIRECT_PAIRS,
    RATE_SYMBOLS,
)
from sentinel.config.categories import (
    DEFAULT_GEOGRAPHIES,
    DEFAULT_INDUSTRIES,
)

__all__ = [
    'SUPPORTED_CURRENCIES',
    'DIRECT_PAIRS',
    'RATE_SYMBOLS',
    'DEFAULT_GEOGRAPHIES',
    'DEFAULT_INDUSTRIES',
]
