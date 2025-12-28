"""Portfolio API endpoints."""

import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException

from app.api.models import (
    AttributionData,
    CashBreakdownResponse,
    PeriodInfo,
    PortfolioAnalyticsErrorResponse,
    PortfolioAnalyticsResponse,
    ReturnsData,
    RiskMetrics,
)
from app.infrastructure.dependencies import (
    ExchangeRateServiceDep,
    PortfolioRepositoryDep,
    PortfolioServiceDep,
    PositionRepositoryDep,
    StockRepositoryDep,
)
from app.infrastructure.external.tradernet_connection import ensure_tradernet_connected

logger = logging.getLogger(__name__)
router = APIRouter()


def _calculate_date_range(days: int) -> tuple[datetime, datetime]:
    """Calculate start and end dates for analytics period.

    Args:
        days: Number of days to analyze

    Returns:
        Tuple of (start_date, end_date)
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    return start_date, end_date


def _format_returns_data(returns, metrics: dict) -> dict:
    """Format returns data for API response.

    Args:
        returns: Pandas Series of returns
        metrics: Dictionary of portfolio metrics

    Returns:
        Formatted returns dictionary
    """
    daily_returns = returns.tolist()
    returns_index = returns.index.strftime("%Y-%m-%d").tolist()

    # Monthly returns
    monthly_returns = returns.resample("M").apply(lambda x: (1 + x).prod() - 1)
    monthly_returns_list = monthly_returns.tolist()
    monthly_index = monthly_returns.index.strftime("%Y-%m").tolist()

    # Annual return
    annual_return = metrics.get("annual_return", 0.0)

    return {
        "daily": [
            {"date": d, "return": r} for d, r in zip(returns_index, daily_returns)
        ],
        "monthly": [
            {"month": m, "return": r}
            for m, r in zip(monthly_index, monthly_returns_list)
        ],
        "annual": annual_return,
    }


def _format_risk_metrics(metrics: dict) -> dict:
    """Format risk metrics for API response.

    Args:
        metrics: Dictionary of portfolio metrics

    Returns:
        Formatted risk metrics dictionary
    """
    return {
        "sharpe_ratio": metrics.get("sharpe_ratio", 0.0),
        "sortino_ratio": metrics.get("sortino_ratio", 0.0),
        "calmar_ratio": metrics.get("calmar_ratio", 0.0),
        "volatility": metrics.get("volatility", 0.0),
        "max_drawdown": metrics.get("max_drawdown", 0.0),
    }


@router.get("")
async def get_portfolio(
    position_repo: PositionRepositoryDep,
    stock_repo: StockRepositoryDep,
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
            pos_dict.update(
                {
                    "stock_name": stock.name,
                    "industry": stock.industry,
                    "country": stock.country,
                    "fullExchangeName": stock.fullExchangeName,
                }
            )
        result.append(pos_dict)

    # Sort by market value
    def _get_market_value(x: dict) -> float:
        qty = x.get("quantity", 0) or 0
        price = x.get("current_price") or x.get("avg_price") or 0
        return float(qty) * float(price)

    result.sort(key=_get_market_value, reverse=True)
    return result


@router.get("/summary")
async def get_portfolio_summary(
    portfolio_service: PortfolioServiceDep,
):
    """Get portfolio summary: total value, cash, allocation percentages."""
    summary = await portfolio_service.get_portfolio_summary()

    # Calculate country percentages
    country_dict = {g.name: g.current_pct for g in summary.country_allocations}

    return {
        "total_value": summary.total_value,
        "cash_balance": summary.cash_balance,
        "allocations": {
            "EU": country_dict.get("EU", 0) * 100,
            "ASIA": country_dict.get("ASIA", 0) * 100,
            "US": country_dict.get("US", 0) * 100,
        },
    }


@router.get("/history")
async def get_portfolio_history(
    portfolio_repo: PortfolioRepositoryDep,
):
    """Get historical portfolio snapshots."""
    snapshots = await portfolio_repo.get_history(days=90)
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
    client = await ensure_tradernet_connected()

    try:
        cash_movements = client.get_cash_movements()
        return {
            "total_withdrawals": cash_movements.get("total_withdrawals", 0),
            "withdrawals": cash_movements.get("withdrawals", []),
            "note": "Deposits are not available via API",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get transaction history: {str(e)}"
        )


@router.get("/cash-breakdown", response_model=CashBreakdownResponse)
async def get_cash_breakdown(
    exchange_rate_service: ExchangeRateServiceDep,
):
    """Get cash balance breakdown by currency."""
    try:
        client = await ensure_tradernet_connected(raise_on_error=False)
        if not client:
            return {"balances": [], "total_eur": 0}
    except Exception:
        return {"balances": [], "total_eur": 0}

    try:
        balances = client.get_cash_balances()

        # Convert all balances to EUR using ExchangeRateService
        amounts_by_currency = {b.currency: b.amount for b in balances}
        amounts_in_eur = await exchange_rate_service.batch_convert_to_eur(
            amounts_by_currency
        )
        total_eur = sum(amounts_in_eur.values())

        return {
            "balances": [
                {"currency": b.currency, "amount": b.amount} for b in balances
            ],
            "total_eur": round(total_eur, 2),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get cash breakdown: {str(e)}"
        )


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
        from app.domain.analytics import (
            calculate_portfolio_returns,
            get_performance_attribution,
            get_portfolio_metrics,
            reconstruct_portfolio_values,
        )

        # Calculate date range
        start_date, end_date = _calculate_date_range(days)
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")

        # Reconstruct portfolio history
        portfolio_values = await reconstruct_portfolio_values(
            start_date_str, end_date_str
        )

        if portfolio_values.empty:
            return PortfolioAnalyticsErrorResponse(
                error="Insufficient data",
                returns={},
                risk_metrics={},
                attribution={},
            )

        # Calculate returns
        returns = calculate_portfolio_returns(portfolio_values)

        if returns.empty:
            return PortfolioAnalyticsErrorResponse(
                error="Could not calculate returns",
                returns={},
                risk_metrics={},
                attribution={},
            )

        # Get portfolio metrics
        metrics = await get_portfolio_metrics(returns)

        # Get performance attribution
        attribution = await get_performance_attribution(
            returns, start_date_str, end_date_str
        )

        # Format response using helper functions
        returns_data = _format_returns_data(returns, metrics)
        risk_metrics_data = _format_risk_metrics(metrics)

        # Convert dict responses to Pydantic models using model_validate
        # This handles the 'return' field alias properly
        returns_model = ReturnsData.model_validate(returns_data)

        return PortfolioAnalyticsResponse(
            returns=returns_model,
            risk_metrics=RiskMetrics(**risk_metrics_data),
            attribution=AttributionData(
                country=attribution.get("country", {}),
                industry=attribution.get("industry", {}),
            ),
            period=PeriodInfo(
                start_date=start_date_str,
                end_date=end_date_str,
                days=days,
            ),
        )
    except Exception as e:
        logger.error(f"Error calculating portfolio analytics: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to calculate analytics: {str(e)}"
        )
