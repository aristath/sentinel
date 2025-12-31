"""Cash balance reconstruction.

Reconstructs historical cash balance from cash flows and trades.
"""

from datetime import datetime
from typing import Optional

import pandas as pd

from app.repositories import CashFlowRepository, TradeRepository


def _process_cash_flows(cash_flows: list, transactions_by_date: dict) -> None:
    """Process cash flows and add to transactions dictionary."""
    for cf in cash_flows:
        date = cf.date
        amount = cf.amount_eur or 0.0
        tx_type = (cf.transaction_type or "").upper()

        if date not in transactions_by_date:
            transactions_by_date[date] = 0.0

        if "DEPOSIT" in tx_type:
            transactions_by_date[date] += amount
        elif "WITHDRAWAL" in tx_type:
            transactions_by_date[date] -= abs(amount)
        elif "DIVIDEND" in tx_type:
            transactions_by_date[date] += amount
        # Fees are already negative in amount_eur


def _get_trade_date(trade) -> Optional[str]:
    """Extract trade date as YYYY-MM-DD string."""
    if not trade.executed_at:
        return None

    if isinstance(trade.executed_at, datetime):
        return trade.executed_at.strftime("%Y-%m-%d")
    else:
        return str(trade.executed_at)[:10]


def _calculate_trade_value(trade) -> float:
    """Calculate trade value in EUR."""
    if trade.value_eur is not None:
        return trade.value_eur

    exchange_rate = trade.currency_rate if trade.currency_rate else 1.0
    return trade.quantity * trade.price * exchange_rate


def _process_trades(
    trades: list, start_date: str, end_date: str, transactions_by_date: dict
) -> None:
    """Process trades and add to transactions dictionary."""
    for trade in trades:
        trade_date = _get_trade_date(trade)
        if not trade_date or trade_date < start_date or trade_date > end_date:
            continue

        if trade_date not in transactions_by_date:
            transactions_by_date[trade_date] = 0.0

        trade_value = _calculate_trade_value(trade)

        if trade.side.upper() == "BUY":
            transactions_by_date[trade_date] -= trade_value
        elif trade.side.upper() == "SELL":
            transactions_by_date[trade_date] += trade_value


def _build_cash_series(
    start_date: str, end_date: str, initial_cash: float, transactions_by_date: dict
) -> pd.Series:
    """Build cash balance series from transactions."""
    dates = pd.date_range(start=start_date, end=end_date, freq="D")
    cash_series = pd.Series(0.0, index=dates)

    current_cash = initial_cash
    for date in dates:
        date_str = date.strftime("%Y-%m-%d")
        if date_str in transactions_by_date:
            current_cash += transactions_by_date[date_str]
        cash_series[date] = current_cash

    return cash_series


async def reconstruct_cash_balance(
    start_date: str, end_date: str, initial_cash: float = 0.0
) -> pd.Series:
    """
    Reconstruct cash balance over time from cash flows and trades.

    Args:
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        initial_cash: Starting cash balance

    Returns:
        Series with date index and cash balance values
    """
    cash_flow_repo = CashFlowRepository()
    trade_repo = TradeRepository()

    cash_flows = await cash_flow_repo.get_by_date_range(start_date, end_date)
    trades = await trade_repo.get_all_in_range(start_date, end_date)

    transactions_by_date: dict[str, list[dict]] = {}
    _process_cash_flows(cash_flows, transactions_by_date)
    _process_trades(trades, start_date, end_date, transactions_by_date)

    return _build_cash_series(start_date, end_date, initial_cash, transactions_by_date)
