from unittest.mock import AsyncMock, MagicMock

import pytest

from sentinel.services.valuation import PortfolioValuationService


@pytest.mark.asyncio
async def test_current_valuation_uses_quote_price_and_account_previous_close():
    db = MagicMock()
    db.get_all_securities = AsyncMock(return_value=[{"symbol": "BYD.1211.AS", "currency": "HKD", "name": "BYD"}])
    db.get_all_positions = AsyncMock(return_value=[])
    db.get_cash_balances = AsyncMock(return_value={})

    broker = MagicMock()
    broker.connected = False
    broker.connect = AsyncMock(return_value=True)
    broker.get_portfolio = AsyncMock(
        return_value={
            "positions": [
                {
                    "symbol": "BYD.1211.AS",
                    "quantity": 1000,
                    "avg_cost": 84.9,
                    "current_price": 90.95,
                    "previous_close_price": 90.5,
                    "currency": "HKD",
                }
            ],
            "cash": {"EUR": 109.3},
        }
    )
    broker.get_quotes = AsyncMock(return_value={"BYD.1211.AS": {"price": 88.7}})

    currency = MagicMock()
    currency.to_eur = AsyncMock(side_effect=lambda amount, curr: amount * 0.1 if curr == "HKD" else amount)

    valuation = await PortfolioValuationService(db=db, broker=broker, currency=currency).current()

    assert valuation["positions"][0]["current_price"] == 88.7
    assert valuation["positions"][0]["price_source"] == "quote"
    assert valuation["positions"][0]["value_eur"] == pytest.approx(8870.0)
    assert valuation["total_value_eur"] == pytest.approx(8979.3)
    assert valuation["intraday_pnl_eur"] == pytest.approx(-180.0)


@pytest.mark.asyncio
async def test_current_valuation_falls_back_to_database_account_state_when_broker_unavailable():
    db = MagicMock()
    db.get_all_positions = AsyncMock(
        return_value=[
            {
                "symbol": "TEST.EU",
                "quantity": 10,
                "avg_cost": 90.0,
                "current_price": 100.0,
                "currency": "EUR",
            }
        ]
    )
    db.get_cash_balances = AsyncMock(return_value={"EUR": 50.0})
    db.get_all_securities = AsyncMock(return_value=[{"symbol": "TEST.EU", "currency": "EUR", "name": "Test"}])

    broker = MagicMock()
    broker.connected = False
    broker.connect = AsyncMock(return_value=False)

    currency = MagicMock()
    currency.to_eur = AsyncMock(side_effect=lambda amount, curr: amount)

    valuation = await PortfolioValuationService(db=db, broker=broker, currency=currency).current()

    assert valuation["positions"][0]["current_price"] == 100.0
    assert valuation["positions"][0]["price_source"] == "account"
    assert valuation["total_value_eur"] == 1050.0
    assert valuation["intraday_pnl_eur"] is None
