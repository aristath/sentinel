"""Tradernet API client package.

This package provides the Tradernet (Freedom24) API client and related utilities.

The package is organized into modules:
- models.py: Data classes (Position, CashBalance, Quote, OHLC, OrderResult)
- parsers.py: Response parsing functions
- transactions.py: Transaction parsing and processing functions
- utils.py: Shared utilities (LED API call context, exchange rate sync)
- client.py: Main TradernetClient class and singleton getter
"""

from tradernet import TraderNetAPI

from app.infrastructure.external.tradernet.client import (
    TradernetClient,
    get_tradernet_client,
)
from app.infrastructure.external.tradernet.models import (
    OHLC,
    CashBalance,
    OrderResult,
    Position,
    Quote,
)

# Alias for backward compatibility
Tradernet = TraderNetAPI

__all__ = [
    "TradernetClient",
    "get_tradernet_client",
    "Tradernet",
    "TraderNetAPI",
    "Position",
    "CashBalance",
    "Quote",
    "OHLC",
    "OrderResult",
]
