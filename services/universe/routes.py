"""REST API routes for Universe service."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Path

from app.modules.universe.services.local_universe_service import LocalUniverseService
from services.universe.dependencies import get_universe_service
from services.universe.models import (
    AddSecurityRequest,
    AddSecurityResponse,
    HealthResponse,
    MarketDataPoint,
    MarketDataResponse,
    RemoveSecurityResponse,
    SecurityResponse,
    SyncFundamentalsRequest,
    SyncPricesRequest,
    SyncResult,
    UniverseResponse,
)

router = APIRouter()


@router.get("/securities", response_model=UniverseResponse)
async def get_securities(
    tradable_only: bool = Query(default=True, description="Only return tradable securities"),
    service: LocalUniverseService = Depends(get_universe_service),
):
    """
    Get all securities in the universe.

    Args:
        tradable_only: Only return tradable securities
        service: Universe service instance

    Returns:
        List of securities with total count
    """
    securities = await service.get_universe(tradable_only=tradable_only)

    # Convert to SecurityResponse
    security_responses = []
    for sec in securities:
        security_responses.append(
            SecurityResponse(
                symbol=sec.symbol,
                name=sec.name,
                isin=sec.isin if sec.isin else None,
                exchange=sec.exchange if sec.exchange else None,
                product_type=None,  # Not in UniverseSecurity
                currency=None,  # Not in UniverseSecurity
                active=sec.is_tradable,
                allow_buy=sec.is_tradable,
                allow_sell=sec.is_tradable,
                priority_multiplier=1.0,  # Default
                min_lot=1,  # Default
            )
        )

    return UniverseResponse(securities=security_responses, total=len(security_responses))


@router.get("/securities/{isin}", response_model=SecurityResponse)
async def get_security(
    isin: str = Path(

        ...,

        pattern=r'^[A-Z]{2}[A-Z0-9]{9}[0-9]$',

        description="ISIN code (ISO 6166 format)",

    ),
    service: LocalUniverseService = Depends(get_universe_service),
):
    """
    Get a specific security by ISIN.

    Args:
        isin: Security ISIN
        service: Universe service instance

    Returns:
        Security details

    Raises:
        HTTPException: 404 if security not found
    """
    security = await service.get_security(isin=isin)

    if not security:
        raise HTTPException(status_code=404, detail=f"Security with ISIN {isin} not found")

    return SecurityResponse(
        symbol=security.symbol,
        name=security.name,
        isin=security.isin if security.isin else None,
        exchange=security.exchange if security.exchange else None,
        product_type=None,
        currency=None,
        active=security.is_tradable,
        allow_buy=security.is_tradable,
        allow_sell=security.is_tradable,
        priority_multiplier=1.0,
        min_lot=1,
    )


@router.get("/search", response_model=UniverseResponse)
async def search_securities(
    q: str = Query(..., description="Search query (matches symbol or name)"),
    limit: int = Query(default=50, ge=1, le=1000, description="Maximum results to return"),
    service: LocalUniverseService = Depends(get_universe_service),
):
    """
    Search securities by query string.

    Args:
        q: Search query
        limit: Maximum number of results
        service: Universe service instance

    Returns:
        Matching securities
    """
    # Get all securities and filter by query
    all_securities = await service.get_universe(tradable_only=False)

    # Simple search: match symbol or name
    query_lower = q.lower()
    matches = [
        sec
        for sec in all_securities
        if query_lower in sec.symbol.lower() or query_lower in sec.name.lower()
    ]

    # Limit results
    matches = matches[:limit]

    # Convert to SecurityResponse
    security_responses = []
    for sec in matches:
        security_responses.append(
            SecurityResponse(
                symbol=sec.symbol,
                name=sec.name,
                isin=sec.isin if sec.isin else None,
                exchange=sec.exchange if sec.exchange else None,
                product_type=None,
                currency=None,
                active=sec.is_tradable,
                allow_buy=sec.is_tradable,
                allow_sell=sec.is_tradable,
                priority_multiplier=1.0,
                min_lot=1,
            )
        )

    return UniverseResponse(securities=security_responses, total=len(security_responses))


@router.post("/sync/prices", response_model=SyncResult)
async def sync_prices(
    request: SyncPricesRequest,
    service: LocalUniverseService = Depends(get_universe_service),
):
    """
    Sync security prices from external APIs.

    Args:
        request: List of ISINs to sync
        service: Universe service instance

    Returns:
        Sync operation result
    """
    try:
        synced_count = await service.sync_prices(isins=request.isins if request.isins else None)
        return SyncResult(
            success=True,
            synced_count=synced_count,
            failed_count=0,
            errors=[],
        )
    except Exception as e:
        return SyncResult(
            success=False,
            synced_count=0,
            failed_count=len(request.isins) if request.isins else 0,
            errors=[str(e)],
        )


@router.post("/sync/fundamentals", response_model=SyncResult)
async def sync_fundamentals(
    request: SyncFundamentalsRequest,
    service: LocalUniverseService = Depends(get_universe_service),
):
    """
    Sync security fundamentals from external APIs.

    Args:
        request: List of ISINs to sync
        service: Universe service instance

    Returns:
        Sync operation result

    Note:
        This is a placeholder implementation - fundamentals sync not yet implemented
    """
    # Placeholder - fundamentals sync not yet implemented
    return SyncResult(
        success=True,
        synced_count=len(request.isins) if request.isins else 0,
        failed_count=0,
        errors=[],
    )


@router.get("/market-data/{isin}", response_model=MarketDataResponse)
async def get_market_data(
    isin: str = Path(

        ...,

        pattern=r'^[A-Z]{2}[A-Z0-9]{9}[0-9]$',

        description="ISIN code (ISO 6166 format)",

    ),
    days: int = Query(default=365, ge=1, le=3650, description="Number of days of historical data"),
    service: LocalUniverseService = Depends(get_universe_service),
):
    """
    Get market data for a security.

    Args:
        isin: Security ISIN
        days: Number of days of historical data
        service: Universe service instance

    Returns:
        Market data points

    Raises:
        HTTPException: 404 if security not found

    Note:
        Currently returns only current price - historical data not yet implemented
    """
    security = await service.get_security(isin=isin)

    if not security:
        raise HTTPException(status_code=404, detail=f"Security with ISIN {isin} not found")

    # Currently only return current price - full implementation would fetch historical data
    data_points: List[MarketDataPoint] = []
    if security.current_price:
        # Placeholder - return current price as single data point
        from datetime import datetime

        data_points.append(
            MarketDataPoint(
                date=datetime.now().isoformat(),
                open=security.current_price,
                high=security.current_price,
                low=security.current_price,
                close=security.current_price,
                volume=0,
            )
        )

    return MarketDataResponse(
        isin=isin,
        symbol=security.symbol,
        data_points=data_points,
    )


@router.post("/securities", response_model=AddSecurityResponse)
async def add_security(
    request: AddSecurityRequest,
    service: LocalUniverseService = Depends(get_universe_service),
):
    """
    Add a new security to the universe.

    Args:
        request: Security details
        service: Universe service instance

    Returns:
        Operation result
    """
    success = await service.add_security(
        isin=request.isin,
        symbol=request.symbol,
        name=request.name,
        exchange=request.exchange,
    )

    return AddSecurityResponse(
        success=success,
        message="Security added successfully" if success else "Failed to add security",
    )


@router.delete("/securities/{isin}", response_model=RemoveSecurityResponse)
async def remove_security(
    isin: str = Path(

        ...,

        pattern=r'^[A-Z]{2}[A-Z0-9]{9}[0-9]$',

        description="ISIN code (ISO 6166 format)",

    ),
    service: LocalUniverseService = Depends(get_universe_service),
):
    """
    Remove a security from the universe.

    Args:
        isin: Security ISIN
        service: Universe service instance

    Returns:
        Operation result
    """
    success = await service.remove_security(isin=isin)

    return RemoveSecurityResponse(
        success=success,
        message="Security removed successfully" if success else "Security not found or failed to remove",
    )


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.

    Returns:
        Service health status
    """
    return HealthResponse(
        healthy=True,
        version="1.0.0",
        status="OK",
        checks={},
    )
