"""Universe service interface."""

from dataclasses import dataclass
from typing import List, Optional, Protocol


@dataclass
class UniverseSecurity:
    """Security in the universe."""

    isin: str
    symbol: str
    name: str
    exchange: str
    current_price: Optional[float] = None
    is_tradable: bool = True


class UniverseServiceInterface(Protocol):
    """Universe service interface."""

    async def get_security(self, isin: str) -> Optional[UniverseSecurity]:
        """
        Get a security by ISIN.

        Args:
            isin: Security ISIN

        Returns:
            Security if found, None otherwise
        """
        ...

    async def get_universe(self, tradable_only: bool = True) -> List[UniverseSecurity]:
        """
        Get all securities in universe.

        Args:
            tradable_only: Only return tradable securities

        Returns:
            List of securities
        """
        ...

    async def sync_prices(self, isins: Optional[List[str]] = None) -> int:
        """
        Sync prices from external APIs.

        Args:
            isins: List of ISINs to sync, or None for all

        Returns:
            Number of securities synced
        """
        ...
