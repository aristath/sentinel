"""Portfolio API endpoints."""

import logging
from fastapi import APIRouter, HTTPException
from app.repositories import (
    PortfolioRepository,
    PositionRepository,
    AllocationRepository,
    StockRepository,
)
from app.application.services.portfolio_service import PortfolioService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("")
async def get_portfolio():
    """Get current portfolio positions with values."""
    position_repo = PositionRepository()
    stock_repo = StockRepository()

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
async def get_portfolio_summary():
    """Get portfolio summary: total value, cash, allocation percentages."""
    portfolio_repo = PortfolioRepository()
    position_repo = PositionRepository()
    allocation_repo = AllocationRepository()

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
async def get_portfolio_history():
    """Get historical portfolio snapshots."""
    portfolio_repo = PortfolioRepository()
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


@router.get("/analytics")
async def get_portfolio_analytics(days: int = 365):
    """
    Get comprehensive portfolio performance analytics using PyFolio.
    
    Args:
        days: Number of days to analyze (default 365)
    
    Returns:
        Dict with returns, risk_metrics, attribution, drawdowns
    """
    try:
        from datetime import datetime, timedelta
        from app.domain.analytics import (
            reconstruct_portfolio_values,
            calculate_portfolio_returns,
            get_portfolio_metrics,
            get_performance_attribution,
        )
        
        # Calculate date range
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        # Reconstruct portfolio history
        portfolio_values = await reconstruct_portfolio_values(start_date, end_date)
        
        if portfolio_values.empty:
            return {
                "error": "Insufficient data",
                "returns": {},
                "risk_metrics": {},
                "attribution": {},
            }
        
        # Calculate returns
        returns = calculate_portfolio_returns(portfolio_values)
        
        if returns.empty:
            return {
                "error": "Could not calculate returns",
                "returns": {},
                "risk_metrics": {},
                "attribution": {},
            }
        
        # Get portfolio metrics
        metrics = await get_portfolio_metrics(returns)
        
        # Get performance attribution
        attribution = await get_performance_attribution(returns, start_date, end_date)
        
        # Calculate daily/monthly/annual returns
        daily_returns = returns.tolist()
        returns_index = returns.index.strftime("%Y-%m-%d").tolist()
        
        # Monthly returns
        monthly_returns = returns.resample("M").apply(lambda x: (1 + x).prod() - 1)
        monthly_returns_list = monthly_returns.tolist()
        monthly_index = monthly_returns.index.strftime("%Y-%m").tolist()
        
        # Annual return
        annual_return = metrics.get("annual_return", 0.0)
        
        return {
            "returns": {
                "daily": [{"date": d, "return": r} for d, r in zip(returns_index, daily_returns)],
                "monthly": [{"month": m, "return": r} for m, r in zip(monthly_index, monthly_returns_list)],
                "annual": annual_return,
            },
            "risk_metrics": {
                "sharpe_ratio": metrics.get("sharpe_ratio", 0.0),
                "sortino_ratio": metrics.get("sortino_ratio", 0.0),
                "calmar_ratio": metrics.get("calmar_ratio", 0.0),
                "volatility": metrics.get("volatility", 0.0),
                "max_drawdown": metrics.get("max_drawdown", 0.0),
            },
            "attribution": {
                "geography": attribution.get("geography", {}),
                "industry": attribution.get("industry", {}),
            },
            "period": {
                "start_date": start_date,
                "end_date": end_date,
                "days": days,
            },
        }
    except Exception as e:
        logger.error(f"Error calculating portfolio analytics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to calculate analytics: {str(e)}")
