"""Tradernet API client package.

This package provides the Tradernet (Freedom24) API client and related utilities.
"""

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
Tradernet = TradernetClient

__all__ = [
    "TradernetClient",
    "get_tradernet_client",
    "Tradernet",
    "Position",
    "CashBalance",
    "Quote",
    "OHLC",
    "OrderResult",
]
