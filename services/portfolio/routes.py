"""REST API routes for Portfolio service."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from app.modules.portfolio.services.local_portfolio_service import LocalPortfolioService
from services.portfolio.dependencies import get_portfolio_service
from services.portfolio.models import (
    CashBalanceResponse,
    HealthResponse,
    PerformanceDataPoint,
    PerformanceResponse,
    PositionResponse,
    PositionsResponse,
    SummaryResponse,
    UpdatePositionsResponse,
)

router = APIRouter()


@router.get("/positions", response_model=PositionsResponse)
async def get_positions(
    account_id: str = Query(default="default", description="Account identifier"),
    service: LocalPortfolioService = Depends(get_portfolio_service),
):
    """
    Get all portfolio positions.

    Args:
        account_id: Account identifier
        service: Portfolio service instance

    Returns:
        List of positions with total count
    """
    positions = await service.get_positions(account_id=account_id)

    # Convert to PositionResponse
    position_responses = []
    for pos in positions:
        # Calculate unrealized PnL percentage
        unrealized_pnl_pct = None
        if pos.average_price > 0:
            unrealized_pnl_pct = (
                (pos.current_price - pos.average_price) / pos.average_price * 100
            )

        position_responses.append(
            PositionResponse(
                symbol=pos.symbol,
                isin=pos.isin if pos.isin else None,
                quantity=pos.quantity,
                average_price=pos.average_price,
                current_price=pos.current_price,
                market_value=pos.market_value,
                unrealized_pnl=pos.unrealized_pnl,
                unrealized_pnl_pct=unrealized_pnl_pct,
            )
        )

    return PositionsResponse(
        positions=position_responses, total_positions=len(position_responses)
    )


@router.get("/positions/{symbol}", response_model=PositionResponse)
async def get_position(
    symbol: str = Path(
        ...,
        pattern=r'^[A-Z0-9][A-Z0-9.-]{0,19}$',
        description="Stock symbol (uppercase alphanumeric with dots/hyphens)",
    ),
    account_id: str = Query(
        default="default",
        pattern=r'^[a-z0-9_-]{1,50}$',
        description="Account identifier",
    ),
    isin: Optional[str] = Query(
        default=None,
        pattern=r'^[A-Z]{2}[A-Z0-9]{9}[0-9]$',
        description="Optional ISIN filter (ISO 6166 format)",
    ),
    service: LocalPortfolioService = Depends(get_portfolio_service),
):
    """
    Get a specific position by symbol or ISIN.

    Args:
        symbol: Trading symbol
        account_id: Account identifier
        isin: Optional ISIN filter
        service: Portfolio service instance

    Returns:
        Position details

    Raises:
        HTTPException: 404 if position not found
    """
    positions = await service.get_positions(account_id=account_id)

    # Find matching position
    matching_pos = None
    for pos in positions:
        if pos.symbol == symbol or (isin and pos.isin == isin):
            matching_pos = pos
            break

    if not matching_pos:
        raise HTTPException(
            status_code=404, detail=f"Position for symbol {symbol} not found"
        )

    # Calculate unrealized PnL percentage
    unrealized_pnl_pct = None
    if matching_pos.average_price > 0:
        unrealized_pnl_pct = (
            (matching_pos.current_price - matching_pos.average_price)
            / matching_pos.average_price
            * 100
        )

    return PositionResponse(
        symbol=matching_pos.symbol,
        isin=matching_pos.isin if matching_pos.isin else None,
        quantity=matching_pos.quantity,
        average_price=matching_pos.average_price,
        current_price=matching_pos.current_price,
        market_value=matching_pos.market_value,
        unrealized_pnl=matching_pos.unrealized_pnl,
        unrealized_pnl_pct=unrealized_pnl_pct,
    )


@router.get("/summary", response_model=SummaryResponse)
async def get_summary(
    account_id: str = Query(default="default", description="Account identifier"),
    service: LocalPortfolioService = Depends(get_portfolio_service),
):
    """
    Get portfolio summary.

    Args:
        account_id: Account identifier
        service: Portfolio service instance

    Returns:
        Portfolio summary with totals
    """
    summary = await service.get_summary(account_id=account_id)

    return SummaryResponse(
        portfolio_hash=summary.portfolio_hash,
        total_value=summary.total_value,
        total_cost=0.0,  # Not tracked in current implementation
        total_pnl=summary.total_pnl,
        cash_balance=summary.cash_balance,
        position_count=summary.position_count,
    )


@router.get("/performance", response_model=PerformanceResponse)
async def get_performance(
    account_id: str = Query(default="default", description="Account identifier"),
    days: int = Query(default=30, ge=1, le=3650, description="Number of days of history"),
    service: LocalPortfolioService = Depends(get_portfolio_service),
):
    """
    Get portfolio performance history.

    Args:
        account_id: Account identifier
        days: Number of days of historical data
        service: Portfolio service instance

    Returns:
        Performance history

    Note:
        Currently returns only current snapshot - historical data not yet implemented
    """
    # Get current summary
    summary = await service.get_summary(account_id=account_id)

    # Create basic performance data point for current state
    # Full implementation would query historical data from database
    history_entry = PerformanceDataPoint(
        date=datetime.now().isoformat(),
        portfolio_value=summary.total_value,
        cash_balance=summary.cash_balance,
        total_pnl=summary.total_pnl,
        daily_return_pct=0.0,  # Would calculate from historical data
        cumulative_return_pct=0.0,  # Would calculate from historical data
    )

    return PerformanceResponse(history=[history_entry])


@router.post("/positions/sync", response_model=UpdatePositionsResponse)
async def update_positions(
    account_id: str = Query(default="default", description="Account identifier"),
    service: LocalPortfolioService = Depends(get_portfolio_service),
):
    """
    Update positions (sync from broker).

    Args:
        account_id: Account identifier
        service: Portfolio service instance

    Returns:
        Sync operation result

    Note:
        Currently returns current positions - broker sync not yet implemented
    """
    # Get current positions before sync
    positions_before = await service.get_positions(account_id=account_id)

    # In a full implementation, would trigger broker sync here
    # For now, get current positions (which may have been synced by background task)
    positions_after = await service.get_positions(account_id=account_id)

    # Calculate changes (simplified - full implementation would track actual changes)
    positions_updated = len(positions_after)
    positions_added = max(0, len(positions_after) - len(positions_before))
    positions_removed = max(0, len(positions_before) - len(positions_after))

    return UpdatePositionsResponse(
        success=True,
        positions_updated=positions_updated,
        positions_added=positions_added,
        positions_removed=positions_removed,
    )


@router.get("/cash", response_model=CashBalanceResponse)
async def get_cash_balance(
    account_id: str = Query(default="default", description="Account identifier"),
    service: LocalPortfolioService = Depends(get_portfolio_service),
):
    """
    Get cash balance.

    Args:
        account_id: Account identifier
        service: Portfolio service instance

    Returns:
        Cash balance details
    """
    balance = await service.get_cash_balance(account_id=account_id)

    return CashBalanceResponse(
        cash_balance=balance,
        pending_deposits=0.0,  # Not tracked in current implementation
        pending_withdrawals=0.0,  # Not tracked in current implementation
        available_for_trading=balance,  # Simplified - would subtract pending
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
