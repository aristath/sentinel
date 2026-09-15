"""Tests for the cash-flow summary API."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_cashflow_summary_uses_transaction_date_fx_for_historical_flows():
    from sentinel.api.routers.trading import get_cashflows

    cash_flows = [
        {"date": "2025-01-01", "type_id": "card", "amount": 100.0, "currency": "USD"},
        {"date": "2025-02-01", "type_id": "card_payout", "amount": -20.0, "currency": "USD"},
        {"date": "2025-03-01", "type_id": "dividend", "amount": 10.0, "currency": "USD"},
        {"date": "2025-04-01", "type_id": "tax", "amount": -2.0, "currency": "USD"},
    ]
    rates = {
        "2025-01-01": 0.90,
        "2025-02-01": 0.80,
        "2025-03-01": 0.70,
        "2025-04-01": 0.75,
    }
    deps = MagicMock()
    deps.db.get_cash_flows = AsyncMock(return_value=cash_flows)
    deps.db.get_total_fees = AsyncMock(return_value={"EUR": 3.0})
    deps.currency.to_eur_for_date = AsyncMock(side_effect=lambda amount, currency, iso_date: amount * rates[iso_date])
    deps.currency.to_eur = AsyncMock(side_effect=lambda amount, currency: amount)

    valuation = MagicMock()
    valuation.current = AsyncMock(return_value={"total_value_eur": 200.0})
    with patch("sentinel.api.routers.trading.PortfolioValuationService", return_value=valuation):
        result = await get_cashflows(deps)

    assert result == {
        "deposits": 90.0,
        "withdrawals": 16.0,
        "dividends": 7.0,
        "taxes": 1.5,
        "fees": 3.0,
        "net_deposits": 74.0,
        "total_profit": 126.0,
    }
    assert deps.currency.to_eur_for_date.await_count == 4
