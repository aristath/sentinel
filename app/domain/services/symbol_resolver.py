"""Symbol resolver service for translating between identifier formats.

Handles resolution of stock identifiers between:
- Tradernet format (e.g., AAPL.US, SAP.DE, SAN.EU)
- ISIN format (e.g., US0378331005, ES0113900J37)
- Yahoo Finance format (e.g., AAPL, SAP.DE)
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.infrastructure.external.tradernet import TradernetClient
    from app.repositories import StockRepository

logger = logging.getLogger(__name__)


class IdentifierType(Enum):
    """Type of stock identifier."""

    ISIN = "isin"
    TRADERNET = "tradernet"
    YAHOO = "yahoo"


@dataclass
class SymbolInfo:
    """Resolved symbol information."""

    tradernet_symbol: Optional[str]
    isin: Optional[str]
    yahoo_symbol: str  # Best identifier for Yahoo (ISIN if available, else converted)

    @property
    def has_isin(self) -> bool:
        """Check if ISIN is available."""
        return self.isin is not None


# ISIN pattern: 2-letter country code + 9 alphanumeric + 1 check digit
ISIN_PATTERN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")

# Tradernet suffix pattern: ends with .XX or .XXX
TRADERNET_SUFFIX_PATTERN = re.compile(r"\.[A-Z]{2,3}$")


def is_isin(identifier: str) -> bool:
    """Check if identifier is an ISIN."""
    if not identifier or len(identifier) != 12:
        return False
    return bool(ISIN_PATTERN.match(identifier.upper()))


def is_tradernet_format(identifier: str) -> bool:
    """Check if identifier is in Tradernet format (has .XX or .XXX suffix)."""
    if not identifier:
        return False
    return bool(TRADERNET_SUFFIX_PATTERN.search(identifier.upper()))


def detect_identifier_type(identifier: str) -> IdentifierType:
    """Detect the type of identifier.

    Args:
        identifier: Stock identifier string

    Returns:
        IdentifierType enum value
    """
    if is_isin(identifier):
        return IdentifierType.ISIN
    if is_tradernet_format(identifier):
        return IdentifierType.TRADERNET
    return IdentifierType.YAHOO


def tradernet_to_yahoo(tradernet_symbol: str) -> str:
    """Convert Tradernet symbol to Yahoo format (simple conversion).

    This is the fallback when ISIN is not available.
    For .US stocks, strips the suffix.
    For .GR stocks, converts to .AT (Athens).
    Other suffixes pass through unchanged.

    Args:
        tradernet_symbol: Symbol in Tradernet format

    Returns:
        Yahoo-compatible symbol
    """
    symbol = tradernet_symbol.upper()

    # US stocks: strip .US suffix
    if symbol.endswith(".US"):
        return symbol[:-3]

    # Greek stocks: .GR -> .AT (Athens Exchange)
    if symbol.endswith(".GR"):
        return symbol[:-3] + ".AT"

    # Everything else passes through unchanged
    return symbol


class SymbolResolver:
    """Service for resolving stock identifiers to usable formats.

    Can resolve:
    - Tradernet symbols to ISIN (via Tradernet API)
    - Check database cache for known ISINs
    - Fall back to simple conversion when ISIN unavailable
    """

    def __init__(
        self,
        tradernet_client: "TradernetClient",
        stock_repo: Optional["StockRepository"] = None,
    ):
        """Initialize the resolver.

        Args:
            tradernet_client: Client for fetching security info from Tradernet
            stock_repo: Optional repository for caching resolved ISINs
        """
        self._tradernet = tradernet_client
        self._stock_repo = stock_repo

    def detect_type(self, identifier: str) -> IdentifierType:
        """Detect the type of identifier."""
        return detect_identifier_type(identifier)

    async def resolve(self, identifier: str) -> SymbolInfo:
        """Resolve any identifier to SymbolInfo.

        For Tradernet symbols:
        1. Check if ISIN is cached in database
        2. If not, fetch from Tradernet API
        3. Return SymbolInfo with ISIN as yahoo_symbol (best for Yahoo lookups)

        For ISIN:
        1. Return directly with ISIN as yahoo_symbol

        For Yahoo format:
        1. Return as-is (no Tradernet symbol or ISIN known)

        Args:
            identifier: Stock identifier (any format)

        Returns:
            SymbolInfo with resolved identifiers
        """
        identifier = identifier.strip().upper()
        id_type = self.detect_type(identifier)

        if id_type == IdentifierType.ISIN:
            # ISIN provided directly - use as yahoo_symbol
            return SymbolInfo(
                tradernet_symbol=None,
                isin=identifier,
                yahoo_symbol=identifier,
            )

        if id_type == IdentifierType.TRADERNET:
            # Try to get ISIN for Tradernet symbol
            isin = await self._get_isin_for_tradernet(identifier)
            if isin:
                return SymbolInfo(
                    tradernet_symbol=identifier,
                    isin=isin,
                    yahoo_symbol=isin,  # Use ISIN for Yahoo
                )
            else:
                # Fall back to simple conversion
                yahoo = tradernet_to_yahoo(identifier)
                return SymbolInfo(
                    tradernet_symbol=identifier,
                    isin=None,
                    yahoo_symbol=yahoo,
                )

        # Yahoo format - return as-is
        return SymbolInfo(
            tradernet_symbol=None,
            isin=None,
            yahoo_symbol=identifier,
        )

    async def _get_isin_for_tradernet(self, tradernet_symbol: str) -> Optional[str]:
        """Get ISIN for a Tradernet symbol.

        1. Check database cache first
        2. If not cached, fetch from Tradernet API

        Args:
            tradernet_symbol: Symbol in Tradernet format

        Returns:
            ISIN string if found, None otherwise
        """
        # Check database cache first
        if self._stock_repo:
            stock = await self._stock_repo.get_by_symbol(tradernet_symbol)
            if stock and stock.isin:
                logger.debug(f"Found cached ISIN for {tradernet_symbol}: {stock.isin}")
                return stock.isin

        # Fetch from Tradernet API
        return self._fetch_isin_from_tradernet(tradernet_symbol)

    def _fetch_isin_from_tradernet(self, tradernet_symbol: str) -> Optional[str]:
        """Fetch ISIN from Tradernet's security_info API.

        Args:
            tradernet_symbol: Symbol in Tradernet format

        Returns:
            ISIN string if found, None otherwise
        """
        if not self._tradernet.is_connected:
            logger.warning("Tradernet client not connected, cannot fetch ISIN")
            return None

        try:
            security_info = self._tradernet.get_security_info(tradernet_symbol)
            if security_info:
                isin = security_info.get("isin")
                if isin and is_isin(isin):
                    logger.info(f"Fetched ISIN for {tradernet_symbol}: {isin}")
                    return isin
                else:
                    logger.debug(
                        f"No valid ISIN in security_info for {tradernet_symbol}"
                    )
            else:
                logger.warning(f"No security_info returned for {tradernet_symbol}")
        except Exception as e:
            logger.error(f"Failed to fetch security_info for {tradernet_symbol}: {e}")

        return None

    async def resolve_and_cache(self, tradernet_symbol: str) -> SymbolInfo:
        """Resolve a Tradernet symbol and cache the ISIN if found.

        Args:
            tradernet_symbol: Symbol in Tradernet format

        Returns:
            SymbolInfo with resolved identifiers
        """
        info = await self.resolve(tradernet_symbol)

        # Cache the ISIN if we have a repo and found an ISIN
        if self._stock_repo and info.isin:
            try:
                stock = await self._stock_repo.get_by_symbol(tradernet_symbol)
                if stock and not stock.isin:
                    await self._stock_repo.update(tradernet_symbol, isin=info.isin)
                    logger.info(f"Cached ISIN for {tradernet_symbol}: {info.isin}")
            except Exception as e:
                logger.warning(f"Failed to cache ISIN for {tradernet_symbol}: {e}")

        return info
