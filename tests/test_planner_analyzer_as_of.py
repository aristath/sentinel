from unittest.mock import AsyncMock, MagicMock

import pytest

from sentinel.planner.analyzer import PortfolioAnalyzer


@pytest.mark.asyncio
async def test_analyzer_positions_as_of_use_snapshot_quantities_and_historical_close():
    db = MagicMock()
    portfolio = MagicMock()
    currency = MagicMock()
    currency.to_eur = AsyncMock(side_effect=lambda amount, curr: amount)
    currency.get_rate = AsyncMock(return_value=1.0)

    db.get_portfolio_snapshot_as_of = AsyncMock(
        return_value={
            "date": 1705276800,
            "data": {"positions": {"AAA": {"quantity": 10}}, "cash_eur": 250.0},
        }
    )
    db.get_all_securities = AsyncMock(return_value=[{"symbol": "AAA", "currency": "EUR"}])
    db.get_prices = AsyncMock(return_value=[{"date": "2024-01-15", "close": 20.0}])

    analyzer = PortfolioAnalyzer(db=db, portfolio=portfolio, currency=currency)

    positions = await analyzer.get_positions_as_of("2024-01-15")
    assert len(positions) == 1
    assert positions[0]["symbol"] == "AAA"
    assert positions[0]["quantity"] == 10
    assert positions[0]["current_price"] == 20.0

    total = await analyzer.get_total_value(as_of_date="2024-01-15")
    # positions (10*20) + cash (250)
    assert total == 450.0
