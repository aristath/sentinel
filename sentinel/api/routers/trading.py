"""Trading API routes."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from typing_extensions import Annotated

from sentinel.api.dependencies import CommonDependencies, get_common_deps
from sentinel.portfolio import Portfolio
from sentinel.security import Security

router = APIRouter(prefix="/trades", tags=["trades"])
cashflows_router = APIRouter(prefix="/cashflows", tags=["cashflows"])
trading_actions_router = APIRouter(prefix="/securities", tags=["trading"])


@router.get("")
async def get_trades(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
    symbol: Optional[str] = None,
    side: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    """
    Get trade history with optional filters.

    Query params:
        symbol: Filter by security symbol
        side: Filter by 'BUY' or 'SELL'
        start_date: Filter trades on or after (YYYY-MM-DD)
        end_date: Filter trades on or before (YYYY-MM-DD)
        limit: Max trades to return (default 100)
        offset: Number to skip for pagination

    Returns:
        trades: List of trade objects
        count: Number of trades in this response
        total: Total number of trades matching filters (for pagination)
    """
    trades = await deps.db.get_trades(
        symbol=symbol,
        side=side,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )

    # Get total count for pagination (without limit/offset)
    total = await deps.db.get_trades_count(
        symbol=symbol,
        side=side,
        start_date=start_date,
        end_date=end_date,
    )

    return {"trades": trades, "count": len(trades), "total": total}


@router.post("/sync")
async def sync_trades_endpoint() -> dict:
    """Trigger manual sync of trades from broker."""
    from sentinel.jobs import run_now

    result = await run_now("sync:trades")
    return result


@cashflows_router.get("")
async def get_cashflows(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict:
    """
    Get aggregated cash flow summary from database.

    Returns:
        deposits: Total deposits in EUR
        withdrawals: Total withdrawals in EUR (positive number)
        dividends: Total dividends received in EUR
        taxes: Total taxes paid in EUR (positive number)
        fees: Total trading fees in EUR (positive number)
        net_deposits: deposits - withdrawals
        total_profit: Current portfolio value + cash - net_deposits
    """
    # Get aggregated cash flows from database
    summary = await deps.db.get_cash_flow_summary()

    # Convert each type/currency combination to EUR
    deposits_eur = 0.0
    withdrawals_eur = 0.0
    dividends_eur = 0.0
    taxes_eur = 0.0

    for type_id, currencies in summary.items():
        for curr, total in currencies.items():
            amount_eur = await deps.currency.to_eur(total, curr)

            if type_id == "card":
                deposits_eur += amount_eur
            elif type_id == "card_payout":
                withdrawals_eur += abs(amount_eur)
            elif type_id == "dividend":
                dividends_eur += amount_eur
            elif type_id == "tax":
                taxes_eur += abs(amount_eur)

    # Get trading fees efficiently (aggregated query)
    fees_by_currency = await deps.db.get_total_fees()
    fees_eur = 0.0
    for curr, total in fees_by_currency.items():
        fees_eur += await deps.currency.to_eur(total, curr)

    # Get portfolio value for total profit calculation
    portfolio_obj = Portfolio()
    total_value = await portfolio_obj.total_value()
    cash_balances = await portfolio_obj.get_cash_balances()

    # Calculate total cash in EUR
    total_cash_eur = 0.0
    for curr, amount in cash_balances.items():
        total_cash_eur += await deps.currency.to_eur(amount, curr)

    net_deposits = deposits_eur - withdrawals_eur
    # Total profit = current value - what we put in (net deposits)
    # Note: dividends and fees are already reflected in cash balance
    total_profit = (total_value + total_cash_eur) - net_deposits

    return {
        "deposits": round(deposits_eur, 2),
        "withdrawals": round(withdrawals_eur, 2),
        "dividends": round(dividends_eur, 2),
        "taxes": round(taxes_eur, 2),
        "fees": round(fees_eur, 2),
        "net_deposits": round(net_deposits, 2),
        "total_profit": round(total_profit, 2),
    }


@cashflows_router.post("/sync")
async def sync_cashflows_endpoint() -> dict:
    """Trigger manual sync of cash flows from broker."""
    from sentinel.jobs import run_now

    result = await run_now("sync:cashflows")
    return result


@trading_actions_router.post("/{symbol}/buy")
async def buy_security(symbol: str, quantity: int) -> dict:
    """Buy a security."""
    security = Security(symbol)
    await security.load()
    order_id = await security.buy(quantity)
    if not order_id:
        raise HTTPException(status_code=400, detail="Buy order failed")
    return {"order_id": order_id}


@trading_actions_router.post("/{symbol}/sell")
async def sell_security(symbol: str, quantity: int) -> dict:
    """Sell a security."""
    security = Security(symbol)
    await security.load()
    order_id = await security.sell(quantity)
    if not order_id:
        raise HTTPException(status_code=400, detail="Sell order failed")
    return {"order_id": order_id}
