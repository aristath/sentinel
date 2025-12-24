"""Portfolio API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from app.infrastructure.dependencies import (
    get_portfolio_repository,
    get_position_repository,
    get_allocation_repository,
    get_stock_repository,
)
from app.domain.repositories import (
    PortfolioRepository,
    PositionRepository,
    AllocationRepository,
    StockRepository,
)
from app.application.services.portfolio_service import PortfolioService

router = APIRouter()


@router.get("")
async def get_portfolio(
    position_repo: PositionRepository = Depends(get_position_repository),
    stock_repo: StockRepository = Depends(get_stock_repository),
):
    """Get current portfolio positions with values."""
    positions = await position_repo.get_all()
    result = []
    
    for position in positions:
        stock = await stock_repo.get_by_symbol(position.symbol)
        pos_dict = {
            "symbol": position.symbol,
            "quantity": position.quantity,
            "avg_price": position.avg_price,
            "current_price": position.current_price,
            "currency": position.currency,
            "currency_rate": position.currency_rate,
            "market_value_eur": position.market_value_eur,
            "last_updated": position.last_updated,
        }
        if stock:
            pos_dict.update({
                "stock_name": stock.name,
                "industry": stock.industry,
                "geography": stock.geography,
            })
        result.append(pos_dict)
    
    # Sort by market value
    result.sort(key=lambda x: (x.get("quantity", 0) or 0) * (x.get("current_price") or x.get("avg_price") or 0), reverse=True)
    return result


@router.get("/summary")
async def get_portfolio_summary(
    portfolio_repo: PortfolioRepository = Depends(get_portfolio_repository),
    position_repo: PositionRepository = Depends(get_position_repository),
    allocation_repo: AllocationRepository = Depends(get_allocation_repository),
):
    """Get portfolio summary: total value, cash, allocation percentages."""
    portfolio_service = PortfolioService(
        portfolio_repo,
        position_repo,
        allocation_repo,
    )
    summary = await portfolio_service.get_portfolio_summary()

    # Calculate geographic percentages
    geo_dict = {g.name: g.current_pct for g in summary.geographic_allocations}
    
    return {
        "total_value": summary.total_value,
        "cash_balance": summary.cash_balance,
        "allocations": {
            "EU": geo_dict.get("EU", 0) * 100,
            "ASIA": geo_dict.get("ASIA", 0) * 100,
            "US": geo_dict.get("US", 0) * 100,
        },
    }


@router.get("/history")
async def get_portfolio_history(
    portfolio_repo: PortfolioRepository = Depends(get_portfolio_repository),
):
    """Get historical portfolio snapshots."""
    snapshots = await portfolio_repo.get_history(limit=90)
    return [
        {
            "id": None,  # Not in domain model
            "date": s.date,
            "total_value": s.total_value,
            "cash_balance": s.cash_balance,
            "geo_eu_pct": s.geo_eu_pct,
            "geo_asia_pct": s.geo_asia_pct,
            "geo_us_pct": s.geo_us_pct,
        }
        for s in snapshots
    ]


@router.get("/transactions")
async def get_transaction_history():
    """
    Get withdrawal transaction history from Tradernet API.

    Note: Only withdrawals are available via API. Deposits must be tracked manually.
    """
    from app.services.tradernet import get_tradernet_client

    client = get_tradernet_client()
    if not client.is_connected:
        if not client.connect():
            raise HTTPException(status_code=503, detail="Not connected to Tradernet")

    try:
        cash_movements = client.get_cash_movements()
        return {
            "total_withdrawals": cash_movements.get("total_withdrawals", 0),
            "withdrawals": cash_movements.get("withdrawals", []),
            "note": "Deposits are not available via API",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get transaction history: {str(e)}")


@router.get("/cash-breakdown")
async def get_cash_breakdown():
    """Get cash balance breakdown by currency."""
    from app.services.tradernet import get_tradernet_client

    client = get_tradernet_client()
    if not client.is_connected:
        if not client.connect():
            return {"balances": [], "total_eur": 0}

    try:
        balances = client.get_cash_balances()
        total_eur = client.get_total_cash_eur()

        return {
            "balances": [{"currency": b.currency, "amount": b.amount} for b in balances],
            "total_eur": total_eur,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get cash breakdown: {str(e)}")
