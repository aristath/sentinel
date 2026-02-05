from unittest.mock import AsyncMock, MagicMock

import pytest

from sentinel.planner.analyzer import PortfolioAnalyzer
from sentinel.planner.rebalance import RebalanceEngine


@pytest.mark.asyncio
async def test_analyzer_invested_value_uses_historical_close_on_as_of_date():
    db = MagicMock()
    currency = MagicMock()
    portfolio = MagicMock()

    portfolio.positions = AsyncMock(
        return_value=[
            {
                "symbol": "AAA",
                "quantity": 2,
                "current_price": 999.0,
                "currency": "EUR",
            }
        ]
    )

    db.get_prices = AsyncMock(return_value=[{"symbol": "AAA", "date": "2025-01-01", "close": 10.0}])
    currency.get_rate = AsyncMock(return_value=1.0)

    analyzer = PortfolioAnalyzer(db=db, portfolio=portfolio, currency=currency)

    invested = await analyzer.get_invested_value_eur("2025-01-01")
    assert invested == 20.0

    db.get_prices.assert_awaited_once_with("AAA", days=1, end_date="2025-01-01")


@pytest.mark.asyncio
async def test_deficit_sells_use_historical_close_on_as_of_date():
    db = MagicMock()
    currency = MagicMock()
    portfolio = MagicMock()

    currency.to_eur = AsyncMock(side_effect=lambda amount, curr: amount)
    currency.get_rate = AsyncMock(return_value=1.0)

    portfolio.get_cash_balances = AsyncMock(return_value={"EUR": -50.0})
    portfolio.total_value = AsyncMock(return_value=1000.0)

    db.get_all_positions = AsyncMock(
        return_value=[
            {
                "symbol": "AAA",
                "quantity": 10,
                "current_price": 999.0,
                "currency": "EUR",
            }
        ]
    )
    db.get_all_securities = AsyncMock(
        return_value=[
            {
                "symbol": "AAA",
                "currency": "EUR",
                "min_lot": 1,
                "allow_sell": 1,
            }
        ]
    )
    db.get_scores = AsyncMock(return_value={"AAA": 0.0})
    db.get_prices = AsyncMock(return_value=[{"symbol": "AAA", "date": "2025-01-01", "close": 10.0}])

    engine = RebalanceEngine(db=db, portfolio=portfolio, currency=currency)

    sells = await engine._get_deficit_sells("2025-01-01")
    assert sells
    assert sells[0].symbol == "AAA"
    assert sells[0].price == 10.0

    db.get_prices.assert_awaited_once_with("AAA", days=1, end_date="2025-01-01")
