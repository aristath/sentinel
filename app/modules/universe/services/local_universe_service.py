"""Local (in-process) universe service implementation."""

from typing import List, Optional

from app.infrastructure.external.tradernet import get_tradernet_client
from app.modules.universe.database.security_repository import SecurityRepository
from app.modules.universe.services.universe_service_interface import UniverseSecurity


class LocalUniverseService:
    """
    Local universe service implementation.

    Wraps existing domain logic for in-process execution.
    """

    def __init__(self):
        """Initialize local universe service."""
        self.security_repo = SecurityRepository()
        self.tradernet = get_tradernet_client()

    async def get_security(self, isin: str) -> Optional[UniverseSecurity]:
        """
        Get a security by ISIN.

        Args:
            isin: Security ISIN

        Returns:
            Security if found, None otherwise
        """
        # Get from repository
        security = self.security_repo.get_by_isin(isin)
        if not security:
            return None

        return UniverseSecurity(
            isin=security.isin or "",
            symbol=security.symbol,
            name=security.name,
            exchange=security.fullExchangeName or "",
            current_price=getattr(security, "current_price", None),
            is_tradable=security.allow_buy,
        )

    async def get_universe(self, tradable_only: bool = True) -> List[UniverseSecurity]:
        """
        Get all securities in universe.

        Args:
            tradable_only: Only return tradable securities

        Returns:
            List of securities
        """
        # Get all securities
        if tradable_only:
            securities = self.security_repo.get_tradable_securities()
        else:
            securities = self.security_repo.get_all_securities()

        # Convert to UniverseSecurity
        result = []
        for sec in securities:
            result.append(
                UniverseSecurity(
                    isin=sec.isin or "",
                    symbol=sec.symbol,
                    name=sec.name,
                    exchange=sec.fullExchangeName or "",
                    current_price=getattr(sec, "current_price", None),
                    is_tradable=sec.allow_buy,
                )
            )

        return result

    async def sync_prices(self, isins: Optional[List[str]] = None) -> int:
        """
        Sync prices from external APIs.

        Args:
            isins: List of ISINs to sync, or None for all

        Returns:
            Number of securities synced
        """
        # Get securities to sync
        if isins:
            securities = [
                self.security_repo.get_by_isin(isin)
                for isin in isins
                if self.security_repo.get_by_isin(isin)
            ]
        else:
            securities = self.security_repo.get_tradable_securities()

        # Sync prices
        synced_count = 0
        for security in securities:
            try:
                # Get latest price from API
                price_data = await self.tradernet.get_quote(security.symbol)
                if price_data and "lastPrice" in price_data:
                    # Update security price in database
                    security.current_price = price_data["lastPrice"]
                    self.security_repo.update(security)
                    synced_count += 1
            except Exception:
                # Continue on error
                continue

        return synced_count
