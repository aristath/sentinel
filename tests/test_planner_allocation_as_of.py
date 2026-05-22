from datetime import datetime, timezone
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

    settings_values = {
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


def _flat_prices():
    return [{"date": f"2025-01-{(i % 28) + 1:02d}", "close": 100.0} for i in range(300)]


def _allocation_settings(settings_values=None):
    values = {
        "max_dividend_reinvestment_boost": 0,
        "strategy_core_target_pct": 80,
        "strategy_opportunity_target_pct": 20,
        "strategy_min_opp_score": 0.55,
        "max_position_pct": 100,
        "clara_preference_weekly_fade": 0.90,
        "clara_preference_strength": 5.0,
        "clara_preferences_updated_at": datetime(2026, 5, 17, tzinfo=timezone.utc).isoformat(),
    }
    if settings_values:
        values.update(settings_values)
    settings = MagicMock()
    settings.get = AsyncMock(side_effect=lambda key, default=None: values.get(key, default))
    return settings


@pytest.mark.asyncio
async def test_high_preference_zero_opportunity_creates_strategic_target():
    now_iso = datetime.now(timezone.utc).isoformat()
    db = MagicMock()
    db.cache_get = AsyncMock(return_value=None)
    db.cache_set = AsyncMock()
    db.get_all_securities = AsyncMock(
        return_value=[
            {"symbol": "AMD", "user_multiplier": 0.9, "user_multiplier_updated_at": now_iso},
            {"symbol": "BASE", "user_multiplier": 0.5, "user_multiplier_updated_at": now_iso},
        ]
    )
    db.get_prices = AsyncMock(return_value=_flat_prices())
    db.get_uninvested_dividends = AsyncMock(return_value={})

    portfolio = MagicMock()

    calculator = AllocationCalculator(
        db=db,
        portfolio=portfolio,
        currency=MagicMock(),
        settings=_allocation_settings({"clara_preferences_updated_at": now_iso}),
    )

    allocations = await calculator.calculate_ideal_portfolio()
    diagnostics = calculator.get_last_signal_bundle()

    assert allocations["AMD"] > allocations["BASE"]
    assert allocations["AMD"] > 0.8
    assert diagnostics is not None
    assert diagnostics["allocation_decomposition"]["symbols"]["AMD"]["final_target_pct"] == allocations["AMD"]


@pytest.mark.asyncio
async def test_low_preference_is_not_forced_to_min_position_floor():
    now_iso = datetime.now(timezone.utc).isoformat()
    db = MagicMock()
    db.cache_get = AsyncMock(return_value=None)
    db.cache_set = AsyncMock()
    db.get_all_securities = AsyncMock(
        return_value=[
            {
                "symbol": f"S{i}",
                "user_multiplier": 0.02 if i == 0 else 0.5,
                "user_multiplier_updated_at": now_iso,
            }
            for i in range(6)
        ]
    )
    db.get_prices = AsyncMock(return_value=_flat_prices())
    db.get_uninvested_dividends = AsyncMock(return_value={})

    portfolio = MagicMock()

    calculator = AllocationCalculator(
        db=db,
        portfolio=portfolio,
        currency=MagicMock(),
        settings=_allocation_settings({"clara_preferences_updated_at": now_iso}),
    )

    allocations = await calculator.calculate_ideal_portfolio()

    assert allocations["S0"] < 0.02
