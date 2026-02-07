from unittest.mock import AsyncMock, MagicMock

import pytest

from sentinel.planner.allocation import AllocationCalculator


@pytest.mark.asyncio
async def test_allocation_as_of_uses_historical_prices_and_skips_live_cache():
    db = MagicMock()
    portfolio = MagicMock()
    currency = MagicMock()
    settings = MagicMock()

    db.cache_get = AsyncMock(return_value='{"AAA": 1.0}')
    db.cache_set = AsyncMock()
    db.get_all_securities = AsyncMock(
        return_value=[
            {
                "symbol": "AAA",
                "user_multiplier": 1.0,
                "geography": "US",
                "industry": "Tech",
            }
        ]
    )
    db.get_prices = AsyncMock(
        return_value=[{"date": f"2025-01-{(i % 28) + 1:02d}", "close": 100.0 + i} for i in range(300)]
    )
    db.get_uninvested_dividends = AsyncMock(return_value={})

    portfolio.get_allocations = AsyncMock(return_value={"by_geography": {}, "by_industry": {}})
    portfolio.get_target_allocations = AsyncMock(return_value={"geography": {}, "industry": {}})

    settings_values = {
        "diversification_impact_pct": 10,
        "max_dividend_reinvestment_boost": 0.15,
        "strategy_core_target_pct": 70,
        "strategy_opportunity_target_pct": 30,
        "strategy_min_opp_score": 0.55,
        "max_position_pct": 35,
        "min_position_pct": 1,
    }
    settings.get = AsyncMock(side_effect=lambda key, default=None: settings_values.get(key, default))

    calculator = AllocationCalculator(db=db, portfolio=portfolio, currency=currency, settings=settings)
    allocations = await calculator.calculate_ideal_portfolio(as_of_date="2025-01-15")

    assert allocations
    db.get_prices.assert_awaited_once_with("AAA", days=300, end_date="2025-01-15")
    db.cache_get.assert_not_awaited()
    db.cache_set.assert_not_awaited()
