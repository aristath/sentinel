"""Cash balance reconstruction.

Reconstructs historical cash balance from cash flows and trades.
"""

from datetime import datetime

import pandas as pd

from app.repositories import CashFlowRepository, TradeRepository


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

    # Get cash flows (deposits, withdrawals, dividends, fees)
    cash_flows = await cash_flow_repo.get_by_date_range(start_date, end_date)

    # Get trades to account for trade values
    trades = await trade_repo.get_all_in_range(start_date, end_date)

    # Combine all transactions by date
    transactions_by_date = {}  # {date: net_change}

    # Add cash flows
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

    # Add trades (BUY reduces cash, SELL increases cash)
    for trade in trades:
        if not trade.executed_at:
            continue

        trade_date = (
            trade.executed_at.strftime("%Y-%m-%d")
            if isinstance(trade.executed_at, datetime)
            else str(trade.executed_at)[:10]
        )

        if trade_date < start_date or trade_date > end_date:
            continue

        if trade_date not in transactions_by_date:
            transactions_by_date[trade_date] = 0.0

        # Trade value in EUR
        if trade.value_eur is not None:
            trade_value = trade.value_eur
        else:
            # Calculate from quantity * price * exchange rate
            exchange_rate = trade.currency_rate if trade.currency_rate else 1.0
            trade_value = trade.quantity * trade.price * exchange_rate

        if trade.side.upper() == "BUY":
            # BUY reduces cash
            transactions_by_date[trade_date] -= trade_value
        elif trade.side.upper() == "SELL":
            # SELL increases cash
            transactions_by_date[trade_date] += trade_value

    # Build cash balance series
    dates = pd.date_range(start=start_date, end=end_date, freq="D")
    cash_series = pd.Series(0.0, index=dates)

    current_cash = initial_cash
    for date in dates:
        date_str = date.strftime("%Y-%m-%d")

        # Apply transaction for this date
        if date_str in transactions_by_date:
            current_cash += transactions_by_date[date_str]

        cash_series[date] = current_cash

    return cash_series
