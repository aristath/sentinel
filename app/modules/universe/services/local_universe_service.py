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

    async def add_security(
        self,
        isin: str,
        symbol: str,
        name: str,
        exchange: Optional[str] = None,
    ) -> bool:
        """
        Add a security to the universe.

        Args:
            isin: Security ISIN
            symbol: Trading symbol
            name: Security name
            exchange: Exchange name

        Returns:
            True if added successfully, False otherwise
        """
        try:
            from app.domain.models import Security
            from app.domain.value_objects.product_type import ProductType
            from app.shared.domain.value_objects.currency import Currency

            # Create security instance
            security = Security(
                isin=isin,
                symbol=symbol,
                name=name,
                fullExchangeName=exchange,
                product_type=ProductType.EQUITY,
                currency=Currency.EUR,
                active=True,
                allow_buy=True,
                allow_sell=True,
                priority_multiplier=1.0,
                min_lot=1,
            )

            # Add to repository
            self.security_repo.save(security)
            return True
        except Exception:
            return False

    async def remove_security(self, isin: str) -> bool:
        """
        Remove a security from the universe.

        Args:
            isin: Security ISIN

        Returns:
            True if removed successfully, False otherwise
        """
        try:
            # Get security
            security = self.security_repo.get_by_isin(isin)
            if not security:
                return False

            # Mark as inactive rather than deleting
            security.active = False
            security.allow_buy = False
            security.allow_sell = False
            self.security_repo.update(security)
            return True
        except Exception:
            return False
