"""gRPC servicer implementation for Universe service."""

from typing import AsyncIterator

from contracts import universe_pb2, universe_pb2_grpc  # type: ignore[attr-defined]
from contracts.common import common_pb2  # type: ignore[attr-defined]
from app.modules.universe.services.local_universe_service import LocalUniverseService


class UniverseServicer(universe_pb2_grpc.UniverseServiceServicer):
    """
    gRPC servicer for Universe service.

    Implements the UniverseService gRPC interface by delegating to LocalUniverseService.
    """

    def __init__(self):
        """Initialize Universe servicer."""
        self.local_service = LocalUniverseService()

    async def GetUniverse(
        self,
        request: universe_pb2.GetUniverseRequest,
        context,
    ) -> universe_pb2.GetUniverseResponse:
        """Get all securities in universe."""
        securities = await self.local_service.get_universe(
            tradable_only=request.tradable_only
        )

        grpc_securities = [
            universe_pb2.Security(
                isin=sec.isin,
                symbol=sec.symbol,
                name=sec.name,
                exchange=sec.exchange,
                current_price=common_pb2.Money(
                    amount=str(sec.current_price or 0), currency="USD"
                )
                if sec.current_price
                else None,
                is_tradable=sec.is_tradable,
            )
            for sec in securities
        ]

        return universe_pb2.GetUniverseResponse(
            securities=grpc_securities,
            total=len(securities),
        )

    async def GetSecurity(
        self,
        request: universe_pb2.GetSecurityRequest,
        context,
    ) -> universe_pb2.GetSecurityResponse:
        """Get a specific security."""
        security = await self.local_service.get_security(isin=request.isin)

        if security:
            grpc_security = universe_pb2.Security(
                isin=security.isin,
                symbol=security.symbol,
                name=security.name,
                exchange=security.exchange,
                current_price=common_pb2.Money(
                    amount=str(security.current_price or 0), currency="USD"
                )
                if security.current_price
                else None,
                is_tradable=security.is_tradable,
            )
            return universe_pb2.GetSecurityResponse(
                found=True,
                security=grpc_security,
            )
        else:
            return universe_pb2.GetSecurityResponse(found=False)

    async def SearchSecurities(
        self,
        request: universe_pb2.SearchSecuritiesRequest,
        context,
    ) -> universe_pb2.SearchSecuritiesResponse:
        """Search securities."""
        # TODO: Implement security search
        return universe_pb2.SearchSecuritiesResponse(
            securities=[],
            total_matches=0,
        )

    async def SyncPrices(
        self,
        request: universe_pb2.SyncPricesRequest,
        context,
    ) -> AsyncIterator[universe_pb2.SyncPricesUpdate]:
        """Sync prices from external APIs (streaming)."""
        isins = list(request.isins) if request.isins else None

        # Yield initial progress
        yield universe_pb2.SyncPricesUpdate(
            progress_pct=0,
            synced=0,
            failed=0,
            total=len(isins) if isins else 0,
            current_isin="",
            complete=False,
        )

        # Perform sync
        synced_count = await self.local_service.sync_prices(isins=isins)

        # Yield completion
        yield universe_pb2.SyncPricesUpdate(
            progress_pct=100,
            synced=synced_count,
            failed=0,
            total=synced_count,
            current_isin="",
            complete=True,
        )

    async def SyncFundamentals(
        self,
        request: universe_pb2.SyncFundamentalsRequest,
        context,
    ) -> AsyncIterator[universe_pb2.SyncFundamentalsUpdate]:
        """Sync fundamentals (streaming)."""
        # TODO: Implement fundamentals sync
        yield universe_pb2.SyncFundamentalsUpdate(
            progress_pct=100,
            synced=0,
            failed=0,
            total=0,
            complete=True,
        )

    async def GetMarketData(
        self,
        request: universe_pb2.GetMarketDataRequest,
        context,
    ) -> universe_pb2.GetMarketDataResponse:
        """Get market data for a security."""
        # TODO: Implement market data retrieval
        return universe_pb2.GetMarketDataResponse(
            isin=request.isin,
            history=[],
        )

    async def AddSecurity(
        self,
        request: universe_pb2.AddSecurityRequest,
        context,
    ) -> universe_pb2.AddSecurityResponse:
        """Add security to universe."""
        # TODO: Implement add security
        return universe_pb2.AddSecurityResponse(
            success=False,
            message="Add security not yet implemented",
        )

    async def RemoveSecurity(
        self,
        request: universe_pb2.RemoveSecurityRequest,
        context,
    ) -> universe_pb2.RemoveSecurityResponse:
        """Remove security from universe."""
        # TODO: Implement remove security
        return universe_pb2.RemoveSecurityResponse(
            success=False,
            message="Remove security not yet implemented",
        )

    async def HealthCheck(
        self,
        request: universe_pb2.Empty,
        context,
    ) -> universe_pb2.HealthCheckResponse:
        """Health check."""
        return universe_pb2.HealthCheckResponse(
            healthy=True,
            version="1.0.0",
            status="OK",
        )
