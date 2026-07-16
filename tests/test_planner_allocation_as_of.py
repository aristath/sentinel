import json
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
        "strategy_min_opp_score": 0.55,
        "strategy_ideal_qualifying_threshold": 0.65,
        "max_position_pct": 100,
        "clara_preference_strength": 5.0,
        "user_multiplier_decay_factor": 0.90,
        "user_multiplier_decay_interval_days": 7,
    }
    if settings_values:
        values.update(settings_values)
    settings = MagicMock()
    settings.get = AsyncMock(side_effect=lambda key, default=None: values.get(key, default))
    return settings


@pytest.mark.asyncio
async def test_atomic_allocation_cache_restores_matching_signal_bundle():
    snapshot = {
        "ideal": {"AAA": 1.0},
        "signal_bundle": {
            "as_of_date": None,
            "rebalance_signals": {"AAA": {"user_multiplier": 0.91, "opp_score": 0.73}},
            "sleeves": {"AAA": "opportunity"},
            "allocation_decomposition": {"global": {}, "symbols": {}},
        },
    }
    db = MagicMock()
    db.cache_get = AsyncMock(
        side_effect=lambda key: json.dumps(snapshot) if key == "planner:allocation_snapshot" else None
    )
    db.get_all_securities = AsyncMock(side_effect=AssertionError("atomic cache should satisfy the request"))
    calculator = AllocationCalculator(db=db, settings=_allocation_settings())

    ideal = await calculator.calculate_ideal_portfolio()
    signals = calculator.get_last_signal_bundle()

    assert ideal == {"AAA": 1.0}
    assert signals["rebalance_signals"]["AAA"] == {"user_multiplier": 0.91, "opp_score": 0.73}


@pytest.mark.asyncio
async def test_legacy_split_weight_cache_is_not_reused_without_matching_atomic_signals():
    db = MagicMock()
    db.cache_get = AsyncMock(
        side_effect=lambda key: json.dumps({"STALE": 1.0}) if key == "planner:ideal_portfolio" else None
    )
    db.cache_set = AsyncMock()
    db.get_all_securities = AsyncMock(return_value=[{"symbol": "AAA", "user_multiplier": 0.9, "allow_buy": 1}])
    db.get_prices = AsyncMock(return_value=_flat_prices())
    db.get_uninvested_dividends = AsyncMock(return_value={})
    calculator = AllocationCalculator(db=db, settings=_allocation_settings())

    ideal = await calculator.calculate_ideal_portfolio()

    assert ideal == {"AAA": 1.0}
    assert db.cache_get.await_args_list[0].args == ("planner:allocation_snapshot",)
    assert all(call.args != ("planner:ideal_portfolio",) for call in db.cache_get.await_args_list)


@pytest.mark.asyncio
async def test_infeasible_position_caps_become_an_explicit_cash_target():
    db = MagicMock()
    db.cache_get = AsyncMock(return_value=None)
    db.cache_set = AsyncMock()
    db.get_all_securities = AsyncMock(
        return_value=[{"symbol": symbol, "user_multiplier": 0.8, "allow_buy": 1} for symbol in ("A", "B", "C")]
    )
    db.get_prices = AsyncMock(return_value=_flat_prices())
    db.get_uninvested_dividends = AsyncMock(return_value={})
    calculator = AllocationCalculator(
        db=db,
        settings=_allocation_settings({"max_position_pct": 30.0, "target_cash_pct": 0.0}),
    )

    ideal = await calculator.calculate_ideal_portfolio()
    diagnostics = calculator.get_last_signal_bundle()

    assert sum(ideal.values()) == pytest.approx(0.9)
    assert all(weight == pytest.approx(0.3) for weight in ideal.values())
    assert diagnostics["allocation_decomposition"]["global"]["effective_cash_target_pct"] == pytest.approx(0.1)


@pytest.mark.asyncio
async def test_high_preference_zero_opportunity_creates_strategic_target():
    now_iso = datetime.now(timezone.utc).isoformat()
    db = MagicMock()
    db.cache_get = AsyncMock(return_value=None)
    db.cache_set = AsyncMock()
    db.get_all_securities = AsyncMock(
        return_value=[
            # Both rated above the configured threshold so both participate in the ideal.
            {"symbol": "AMD", "user_multiplier": 0.9, "user_multiplier_updated_at": now_iso},
            {"symbol": "BASE", "user_multiplier": 0.65, "user_multiplier_updated_at": now_iso},
        ]
    )
    db.get_prices = AsyncMock(return_value=_flat_prices())
    db.get_uninvested_dividends = AsyncMock(return_value={})

    portfolio = MagicMock()

    calculator = AllocationCalculator(
        db=db,
        portfolio=portfolio,
        currency=MagicMock(),
        settings=_allocation_settings(),
    )

    allocations = await calculator.calculate_ideal_portfolio()
    diagnostics = calculator.get_last_signal_bundle()

    assert allocations["AMD"] > allocations["BASE"]
    # AMD's slider (0.9) is much higher than BASE's threshold-level 0.65, so AMD's Clara share
    # dominates. With a non-trivial competitor in the pool it won't reach 100%,
    # but it should clearly exceed 70% of the total ideal.
    assert allocations["AMD"] > 0.7
    assert diagnostics is not None
    assert diagnostics["allocation_decomposition"]["symbols"]["AMD"]["final_target_pct"] == allocations["AMD"]
    assert diagnostics["allocation_decomposition"]["global"]["target_model"] == "clara_risk"
    assert diagnostics["allocation_decomposition"]["symbols"]["AMD"]["opportunity_target_pct"] == 0.0


@pytest.mark.asyncio
async def test_opportunity_changes_do_not_change_long_term_target_weights():
    now_iso = datetime.now(timezone.utc).isoformat()
    securities = [
        {"symbol": "A", "user_multiplier": 0.9, "user_multiplier_updated_at": now_iso},
        {"symbol": "B", "user_multiplier": 0.7, "user_multiplier_updated_at": now_iso},
    ]

    async def calculate(price_rows):
        db = MagicMock()
        db.cache_get = AsyncMock(return_value=None)
        db.cache_set = AsyncMock()
        db.get_all_securities = AsyncMock(return_value=securities)
        db.get_prices_for_symbols = AsyncMock(return_value=price_rows)
        db.get_uninvested_dividends = AsyncMock(return_value={})
        calculator = AllocationCalculator(
            db=db,
            portfolio=MagicMock(),
            currency=MagicMock(),
            settings=_allocation_settings(),
        )
        return await calculator.calculate_ideal_portfolio()

    flat = _flat_prices()
    falling = [{"date": row["date"], "close": 100.0 - (index * 0.2)} for index, row in enumerate(flat)]
    first = await calculate({"A": flat, "B": falling})
    second = await calculate({"A": falling, "B": flat})

    assert first == second


@pytest.mark.asyncio
async def test_low_preference_security_is_excluded_from_ideal():
    """A security below the configured Clara threshold should drop completely
    out of the ideal — even though the algo's contrarian signal might rank it
    highly — so capital flows to the actively-endorsed names."""
    now_iso = datetime.now(timezone.utc).isoformat()
    db = MagicMock()
    db.cache_get = AsyncMock(return_value=None)
    db.cache_set = AsyncMock()
    db.get_all_securities = AsyncMock(
        return_value=[
            # Three excluded below threshold, rest endorsed.
            {"symbol": "AVOID", "user_multiplier": 0.02, "user_multiplier_updated_at": now_iso},
            {"symbol": "NEUTRAL", "user_multiplier": 0.5, "user_multiplier_updated_at": now_iso},
            {"symbol": "LOW", "user_multiplier": 0.6, "user_multiplier_updated_at": now_iso},
            {"symbol": "ENDORSED2", "user_multiplier": 0.7, "user_multiplier_updated_at": now_iso},
            {"symbol": "ENDORSED3", "user_multiplier": 0.8, "user_multiplier_updated_at": now_iso},
        ]
    )
    db.get_prices = AsyncMock(return_value=_flat_prices())
    db.get_uninvested_dividends = AsyncMock(return_value={})

    calculator = AllocationCalculator(
        db=db,
        portfolio=MagicMock(),
        currency=MagicMock(),
        settings=_allocation_settings(),
    )

    allocations = await calculator.calculate_ideal_portfolio()

    # AVOID (0.02), NEUTRAL (0.5), and LOW (0.6) are below the default 0.65 threshold.
    assert allocations.get("AVOID", 0.0) == 0.0
    assert allocations.get("NEUTRAL", 0.0) == 0.0
    assert allocations.get("LOW", 0.0) == 0.0
    # The endorsed securities split the full 100%.
    endorsed_total = allocations["ENDORSED2"] + allocations["ENDORSED3"]
    assert abs(endorsed_total - 1.0) < 1e-6
    # Higher slider gets bigger share.
    assert allocations["ENDORSED3"] > allocations["ENDORSED2"]


@pytest.mark.asyncio
async def test_buy_disabled_security_is_excluded_from_ideal():
    """A security that cannot be bought must not consume ideal allocation.

    It still has signals computed by the allocator so the rebalance engine can
    handle existing holdings on the sell side.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    db = MagicMock()
    db.cache_get = AsyncMock(return_value=None)
    db.cache_set = AsyncMock()
    db.get_all_securities = AsyncMock(
        return_value=[
            {
                "symbol": "NO_BUY",
                "user_multiplier": 1.0,
                "user_multiplier_updated_at": now_iso,
                "allow_buy": 0,
                "allow_sell": 1,
            },
            {
                "symbol": "BUYABLE",
                "user_multiplier": 0.7,
                "user_multiplier_updated_at": now_iso,
                "allow_buy": 1,
                "allow_sell": 1,
            },
        ]
    )
    db.get_prices = AsyncMock(return_value=_flat_prices())
    db.get_uninvested_dividends = AsyncMock(return_value={})

    calculator = AllocationCalculator(
        db=db,
        portfolio=MagicMock(),
        currency=MagicMock(),
        settings=_allocation_settings(),
    )

    allocations = await calculator.calculate_ideal_portfolio()
    diagnostics = calculator.get_last_signal_bundle()

    assert allocations.get("NO_BUY", 0.0) == 0.0
    assert abs(allocations["BUYABLE"] - 1.0) < 1e-6
    assert diagnostics is not None
    assert "NO_BUY" in diagnostics["rebalance_signals"]
    assert "NO_BUY" not in diagnostics["allocation_decomposition"]["symbols"]


@pytest.mark.asyncio
async def test_strong_algo_signal_cannot_resurrect_excluded_security():
    """Regression: even a security with a dominant contrarian signal — the
    kind that previously let INTC@0.45 beat OPAP@0.55 — must stay at zero in
    the ideal once its slider is at/below neutral. The exclusion gates BOTH
    the Clara half AND the algo half."""
    now_iso = datetime.now(timezone.utc).isoformat()
    db = MagicMock()
    db.cache_get = AsyncMock(return_value=None)
    db.cache_set = AsyncMock()
    db.get_all_securities = AsyncMock(
        return_value=[
            {"symbol": "ALGO_FAV", "user_multiplier": 0.45, "user_multiplier_updated_at": now_iso},
            {"symbol": "USER_FAV", "user_multiplier": 0.7, "user_multiplier_updated_at": now_iso},
        ]
    )

    def _prices_for(symbol, **_):
        if symbol == "ALGO_FAV":
            # Steep recent drawdown -> high core_rank/opp_score
            base = [100.0] * 200 + [60.0] * 30 + [55.0] * 30
            return [{"date": f"2025-{(i // 30) + 1:02d}-{(i % 30) + 1:02d}", "close": p} for i, p in enumerate(base)]
        return _flat_prices()

    db.get_prices = AsyncMock(side_effect=_prices_for)
    db.get_uninvested_dividends = AsyncMock(return_value={})

    calculator = AllocationCalculator(
        db=db,
        portfolio=MagicMock(),
        currency=MagicMock(),
        settings=_allocation_settings(),
    )

    allocations = await calculator.calculate_ideal_portfolio()

    # ALGO_FAV is dialed down — even with a dominant contrarian signal it must
    # not appear in the ideal. USER_FAV should get the full 100%.
    assert allocations.get("ALGO_FAV", 0.0) == 0.0
    assert abs(allocations.get("USER_FAV", 0.0) - 1.0) < 1e-6
