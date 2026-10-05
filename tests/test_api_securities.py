"""Tests for securities API endpoints."""

import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from sentinel.database import Database
from sentinel.settings import Settings


@pytest.mark.asyncio
async def test_broker_search_includes_untracked_inactive_and_held_sell_only_symbols():
    from sentinel.api.routers.securities import search_securities

    deps = MagicMock()
    deps.broker.connected = True
    deps.broker.search_securities = AsyncMock(
        return_value=[
            {"t": "NEW.EU", "n": "New", "isin": "NEW-ISIN", "mkt": "EU", "type": 1, "kind": 7},
            {"t": "OLD.EU", "n": "Old"},
            {"t": "HELD.EU", "n": "Held"},
        ]
    )
    deps.db.get_all_securities = AsyncMock(
        return_value=[
            {"symbol": "OLD.EU", "active": 0, "allow_buy": 0, "allow_sell": 0},
            {"symbol": "HELD.EU", "active": 1, "allow_buy": 0, "allow_sell": 1},
        ]
    )

    new, inactive, held = await search_securities(deps, " example ", " eu ")

    deps.broker.search_securities.assert_awaited_once_with("example", "EU")
    deps.db.get_all_securities.assert_awaited_once_with(active_only=False)
    assert new["symbol"] == "NEW.EU"
    assert new["name"] == "New"
    assert new["isin"] == "NEW-ISIN"
    assert new["market"] == "EU"
    assert new["instrument_type"] == 1
    assert new["instrument_kind"] == 7
    assert new["tracked"] is False
    assert new["in_universe"] is False
    assert new["allow_buy"] is None
    assert inactive["tracked"] is True
    assert inactive["in_universe"] is False
    assert held["in_universe"] is True
    assert held["allow_buy"] is False
    assert held["allow_sell"] is True
    deps.db.upsert_security.assert_not_called()
    deps.broker.add_stock_list_ticker.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "exchange", "connected", "matches", "status"),
    [
        (" ", None, True, [], 400),
        ("Apple", " ", True, [], 400),
        ("Apple", None, False, [], 503),
        ("Apple", None, True, None, 502),
    ],
)
async def test_broker_search_validation_and_failure(query, exchange, connected, matches, status):
    from sentinel.api.routers.securities import search_securities

    deps = MagicMock()
    deps.broker.connected = connected
    deps.broker.search_securities = AsyncMock(return_value=matches)
    with pytest.raises(HTTPException) as exc:
        await search_securities(deps, query, exchange)
    assert exc.value.status_code == status
    if status != 502:
        deps.broker.search_securities.assert_not_awaited()
    deps.db.get_all_securities.assert_not_called()


@pytest.mark.asyncio
async def test_isin_search_displays_company_name_instead_of_echoed_isin():
    from sentinel.api.routers.securities import search_securities

    deps = MagicMock()
    deps.broker.connected = True
    deps.broker.search_securities = AsyncMock(
        return_value=[{"t": "AAPL.US", "n": "US0378331005", "nm": "Apple Inc.", "isin": "US0378331005"}]
    )
    deps.db.get_all_securities = AsyncMock(return_value=[])
    results = await search_securities(deps, "US0378331005")
    assert results[0]["name"] == "Apple Inc."
    assert results[0]["isin"] == "US0378331005"
    assert results[0]["n"] == "US0378331005"


@pytest.mark.asyncio
async def test_search_http_route_precedes_dynamic_symbol_lookup():
    import httpx
    from fastapi import FastAPI

    from sentinel.api.dependencies import get_common_deps
    from sentinel.api.routers.securities import router

    deps = MagicMock()
    deps.broker.connected = True
    deps.broker.search_securities = AsyncMock(return_value=[])
    deps.db.get_all_securities = AsyncMock(return_value=[])
    test_app = FastAPI()
    test_app.include_router(router, prefix="/api")
    test_app.dependency_overrides[get_common_deps] = lambda: deps
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/api/securities/search", params={"query": "unknown"})
    assert response.status_code == 200
    assert response.json() == []
    deps.db.get_security.assert_not_called()


@pytest.mark.asyncio
async def test_broker_info_lookup_does_not_require_or_add_local_security():
    from sentinel.api.routers.securities import get_broker_security_info

    deps = MagicMock()
    deps.broker.connected = True
    info = {"short_name": "Apple", "currency": "USD", "lot": 1}
    deps.broker.get_security_info = AsyncMock(return_value=info)
    assert await get_broker_security_info(" AAPL.US ", deps) == {"symbol": "AAPL.US", "info": info}
    deps.broker.get_security_info.assert_awaited_once_with("AAPL.US")
    deps.db.get_security.assert_not_called()
    deps.broker.add_stock_list_ticker.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("symbol", "connected", "status"), [(" ", True, 400), ("AAPL.US", False, 503), ("NO", True, 404)]
)
async def test_broker_info_validation_and_failure(symbol, connected, status):
    from sentinel.api.routers.securities import get_broker_security_info

    deps = MagicMock()
    deps.broker.connected = connected
    deps.broker.get_security_info = AsyncMock(return_value=None)
    with pytest.raises(HTTPException) as exc:
        await get_broker_security_info(symbol, deps)
    assert exc.value.status_code == status
    if status != 404:
        deps.broker.get_security_info.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_unified_view_returns_empty_list_when_no_securities():
    """GET /api/unified returns empty list when no securities exist."""
    from sentinel.api.routers.securities import get_unified_view

    # Create mock dependencies
    mock_deps = MagicMock()
    mock_deps.db.get_all_securities = AsyncMock(return_value=[])

    # Call the endpoint
    result = await get_unified_view(mock_deps, period="1Y")

    # Verify it returns an empty list
    assert result == []

    # Verify get_all_securities was called
    mock_deps.db.get_all_securities.assert_called_once_with(active_only=True)


@pytest.mark.asyncio
async def test_get_unified_view_does_not_call_planner_when_no_securities():
    """Verify planner is not instantiated when securities list is empty."""
    from sentinel.api.routers.securities import get_unified_view

    # Create mock dependencies
    mock_deps = MagicMock()
    mock_deps.db.get_all_securities = AsyncMock(return_value=[])

    # Mock Planner where it is defined (router imports it inside the endpoint)
    with patch("sentinel.planner.Planner") as mock_planner:
        result = await get_unified_view(mock_deps, period="1Y")

    # Verify Planner was not instantiated
    mock_planner.assert_not_called()
    assert result == []


def _make_unified_mocks(one_security=True):
    """Build mocks so get_unified_view runs without hitting real deps."""
    mock_deps = MagicMock()
    if one_security:
        mock_deps.db.get_all_securities = AsyncMock(
            return_value=[
                {
                    "symbol": "AAPL",
                    "name": "Apple",
                    "currency": "USD",
                    "data": '{"mrkt": {"mkt_id": 1}}',
                }
            ]
        )
    else:
        mock_deps.db.get_all_securities = AsyncMock(return_value=[])
    mock_deps.db.get_all_positions = AsyncMock(return_value=[])
    mock_deps.db.get_cash_balances = AsyncMock(return_value={})
    mock_cursor = MagicMock()
    mock_cursor.fetchall = AsyncMock(return_value=[])
    mock_cursor.fetchone = AsyncMock(return_value=None)
    mock_deps.db.conn.execute = AsyncMock(return_value=mock_cursor)
    mock_deps.broker.get_quotes = AsyncMock(return_value={})
    mock_deps.broker.get_market_status = AsyncMock(return_value={"m": [{"i": 1, "s": "OPEN"}]})
    mock_deps.db.get_prices_bulk = AsyncMock(return_value={"AAPL": []})
    mock_deps.currency.to_eur = AsyncMock(return_value=0.0)
    mock_deps.settings.get = AsyncMock(return_value=None)
    return mock_deps


@pytest.mark.asyncio
async def test_get_unified_view_with_as_of_no_prediction_fields():
    """When as_of is set, endpoint returns successfully with deterministic signals."""
    from sentinel.api.routers.securities import get_unified_view

    mock_deps = _make_unified_mocks(one_security=True)
    mock_planner = MagicMock()
    mock_planner.get_recommendations = AsyncMock(return_value=[])
    mock_planner.calculate_ideal_portfolio = AsyncMock(return_value={})
    mock_planner.get_current_allocations = AsyncMock(return_value={})

    with patch("sentinel.planner.Planner", return_value=mock_planner):
        result = await get_unified_view(mock_deps, period="1Y", as_of="2024-01-15")
    assert isinstance(result, list)
    mock_planner.get_recommendations.assert_awaited_once_with(as_of_date="2024-01-15", eligible_symbols=None)
    mock_planner.calculate_ideal_portfolio.assert_awaited_once_with(as_of_date="2024-01-15")
    mock_planner.get_current_allocations.assert_awaited_once_with(as_of_date="2024-01-15")
    mock_deps.db.get_prices_bulk.assert_any_await(["AAPL"], days=365, end_date="2024-01-15")


@pytest.mark.asyncio
async def test_get_unified_view_without_as_of_no_prediction_fields():
    """When as_of is None, endpoint returns successfully with deterministic signals."""
    from sentinel.api.routers.securities import get_unified_view

    mock_deps = _make_unified_mocks(one_security=True)
    mock_planner = MagicMock()
    mock_planner.get_recommendations = AsyncMock(return_value=[])
    mock_planner.calculate_ideal_portfolio = AsyncMock(return_value={})
    mock_planner.get_current_allocations = AsyncMock(return_value={})

    with patch("sentinel.planner.Planner", return_value=mock_planner):
        result = await get_unified_view(mock_deps, period="1Y", as_of=None)
    assert isinstance(result, list)
    mock_planner.get_recommendations.assert_awaited_once_with(as_of_date=None, eligible_symbols={"AAPL"})
    mock_planner.calculate_ideal_portfolio.assert_awaited_once_with(as_of_date=None)
    mock_planner.get_current_allocations.assert_awaited_once_with(as_of_date=None)
    mock_deps.db.get_prices_bulk.assert_any_await(["AAPL"], days=365, end_date=None)


@pytest.mark.asyncio
async def test_get_unified_view_can_load_only_expandable_inactive_security_details():
    from sentinel.api.routers.securities import get_unified_view

    mock_deps = _make_unified_mocks(one_security=True)
    mock_deps.db.get_all_securities = AsyncMock(
        return_value=[
            {
                "symbol": "OLD.EU",
                "name": "Old Security",
                "currency": "EUR",
                "min_lot": 1,
                "active": 0,
                "allow_buy": 0,
                "allow_sell": 0,
            }
        ]
    )
    mock_deps.db.get_security_transaction_counts = AsyncMock(return_value={})
    mock_deps.db.get_prices_bulk = AsyncMock(return_value={"OLD.EU": []})

    with patch("sentinel.planner.Planner") as planner_cls:
        result = await get_unified_view(mock_deps, period="1Y", as_of="2024-01-15", inactive_only=True)

    mock_deps.db.get_all_securities.assert_awaited_once_with(active_only=False)
    planner_cls.assert_not_called()
    mock_deps.broker.get_quotes.assert_not_awaited()
    assert result[0]["symbol"] == "OLD.EU"
    assert result[0]["active"] == 0
    assert result[0]["can_delete"] is True
    assert result[0]["transaction_count"] == 0
    assert "prices" in result[0]


@pytest.mark.asyncio
async def test_get_unified_view_current_uses_simulated_cash_in_research_mode():
    from sentinel.api.routers.securities import get_unified_view

    mock_deps = _make_unified_mocks(one_security=True)
    mock_deps.db.get_all_securities = AsyncMock(
        return_value=[
            {
                "symbol": "AAPL",
                "name": "Apple",
                "currency": "EUR",
                "min_lot": 1,
                "data": '{"mrkt": {"mkt_id": 1}}',
            }
        ]
    )
    mock_deps.db.get_all_positions = AsyncMock(
        return_value=[
            {
                "symbol": "AAPL",
                "quantity": 10,
                "current_price": 100.0,
                "currency": "EUR",
                "avg_cost": 90.0,
            }
        ]
    )
    mock_deps.db.get_cash_balances = AsyncMock(return_value={"EUR": 0.0})
    mock_deps.db.get_prices_bulk = AsyncMock(return_value={"AAPL": []})
    mock_deps.currency.to_eur = AsyncMock(side_effect=lambda amount, _currency: amount)
    mock_deps.currency.get_rate = AsyncMock(return_value=1.0)
    mock_deps.settings.get = AsyncMock(
        side_effect=lambda key, default=None: {
            "trading_mode": "research",
            "simulated_cash_eur": 20_000.0,
            "transaction_fee_fixed": 0.0,
            "transaction_fee_percent": 0.0,
            "strategy_lot_standard_max_pct": 0.08,
            "strategy_lot_coarse_max_pct": 0.30,
            "strategy_min_opp_score": 0.55,
        }.get(key, default)
    )

    mock_planner = MagicMock()
    mock_planner.get_recommendations = AsyncMock(return_value=[])
    mock_planner.calculate_ideal_portfolio = AsyncMock(return_value={})
    mock_planner.get_current_allocations = AsyncMock(return_value={"AAPL": 1000.0 / 21_000.0})

    with patch("sentinel.planner.Planner", return_value=mock_planner):
        result = await get_unified_view(mock_deps, period="1Y", as_of=None)

    assert result
    assert result[0]["post_plan_allocation"] == pytest.approx(1000.0 / 21_000.0 * 100)


@pytest.mark.asyncio
async def test_get_unified_view_populates_contrarian_signal_fields():
    """Unified payload includes deterministic contrarian signal fields."""
    from sentinel.api.routers.securities import get_unified_view

    mock_deps = _make_unified_mocks(one_security=True)
    mock_deps.db.get_prices_bulk = AsyncMock(return_value={"AAPL": [{"date": 1, "close": 100.0}] * 365})

    mock_planner = MagicMock()
    mock_planner.get_recommendations = AsyncMock(return_value=[])
    mock_planner.calculate_ideal_portfolio = AsyncMock(return_value={})
    mock_planner.get_current_allocations = AsyncMock(return_value={})

    with patch("sentinel.planner.Planner", return_value=mock_planner):
        result = await get_unified_view(mock_deps, period="1Y", as_of=None)

    assert isinstance(result, list)
    assert result
    assert "opp_score" in result[0]
    assert "dip_score" in result[0]
    assert "capitulation_score" in result[0]
    assert "ticket_pct" in result[0]
    assert "lot_class" in result[0]
    assert "sleeve" in result[0]
    assert "core_floor_active" not in result[0]


@pytest.mark.asyncio
async def test_get_unified_view_as_of_uses_historical_price_not_live_position_price():
    """As-of view must value cards from historical close, not live/stale position current_price."""
    from sentinel.api.routers.securities import get_unified_view

    mock_deps = _make_unified_mocks(one_security=True)
    # Stale live position price should not be used for as_of card valuation.
    mock_deps.db.get_all_positions = AsyncMock(
        return_value=[{"symbol": "AAPL", "quantity": 5, "current_price": 999.0, "currency": "USD", "avg_cost": 50.0}]
    )
    mock_deps.db.get_portfolio_snapshot_as_of = AsyncMock(
        return_value={
            "date": 1705276800,
            "data": {"positions": {"AAPL": {"quantity": 5}}, "cash_eur": 1000.0},
        }
    )

    def prices_bulk_side_effect(symbols, days=None, end_date=None):
        if days == 1:
            return {"AAPL": [{"date": "2024-01-15", "close": 100.0}]}
        return {"AAPL": [{"date": "2024-01-15", "close": 100.0}] * 365}

    mock_deps.db.get_prices_bulk = AsyncMock(side_effect=prices_bulk_side_effect)
    mock_deps.db.get_prices = AsyncMock(return_value=[{"date": "2024-01-15", "close": 100.0}])

    mock_planner = MagicMock()
    mock_planner.get_recommendations = AsyncMock(return_value=[])
    mock_planner.calculate_ideal_portfolio = AsyncMock(return_value={})
    mock_planner.get_current_allocations = AsyncMock(return_value={})

    with patch("sentinel.planner.Planner", return_value=mock_planner):
        result = await get_unified_view(mock_deps, period="1Y", as_of="2024-01-15")

    assert result
    assert result[0]["current_price"] == 100.0


@pytest.mark.asyncio
async def test_get_unified_view_as_of_uses_as_of_allocation_diagnostics_not_live_cache():
    """As-of allocation decomposition should come from the as-of planner run, not live cache."""
    from sentinel.api.routers.securities import get_unified_view

    mock_deps = _make_unified_mocks(one_security=True)
    mock_deps.db.cache_get = AsyncMock(return_value='{"AAPL": "opportunity"}')
    mock_deps.db.get_prices_bulk = AsyncMock(return_value={"AAPL": []})

    mock_planner = MagicMock()
    mock_planner.get_recommendations = AsyncMock(return_value=[])
    mock_planner.calculate_ideal_portfolio = AsyncMock(return_value={"AAPL": 0.42})
    mock_planner.get_current_allocations = AsyncMock(return_value={})
    mock_planner.get_last_allocation_diagnostics.return_value = {
        "sleeves": {"AAPL": "core"},
        "allocation_decomposition": {
            "global": {
                "target_model": "ai_research",
                "ai_research_target_pct": 1.0,
                "algo_blend_pct": 0.0,
            },
            "symbols": {
                "AAPL": {
                    "allocation_sleeve": "core",
                    "baseline_target_pct": 0.0,
                    "ai_research_target_pct": 0.42,
                    "opportunity_target_pct": 0.0,
                    "final_target_pct": 0.42,
                }
            },
        },
    }

    with patch("sentinel.planner.Planner", return_value=mock_planner):
        result = await get_unified_view(mock_deps, period="1Y", as_of="2024-01-15")

    mock_deps.db.cache_get.assert_not_awaited()
    assert result[0]["sleeve"] == "core"
    assert result[0]["ai_research_target_pct"] == 42.0
    assert result[0]["final_target_pct"] == 42.0


@pytest.mark.asyncio
async def test_update_security_preference_persists_analysis_and_invalidates_planner_cache():
    from sentinel.api.routers.securities import update_security_preference

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = Database(path)
    await db.connect()
    settings = Settings()
    settings._db = db
    await settings.init_defaults()
    try:
        await db.upsert_security("MOH.GR", name="Motor Oil Hellas", ai_research_multiplier=0.5)
        await db.cache_set("planner:ideal_portfolio", "{}", ttl_seconds=600)
        deps = MagicMock()
        deps.db = db
        deps.settings = settings

        result = await update_security_preference(
            {
                "symbol": "MOH.GR",
                "ai_research_multiplier": 0.02,
                "analysis": "Too fossil-heavy for the long-term portfolio.",
            },
            deps,
        )

        stored = await db.get_security("MOH.GR")
        assert stored is not None
        assert result["symbol"] == "MOH.GR"
        assert result["ai_research_multiplier"] == 0.02
        assert result["ai_research_multiplier_source"] == "ai_research"
        assert result["ai_research_multiplier_analysis"] == "Too fossil-heavy for the long-term portfolio."
        assert stored["ai_research_multiplier"] == 0.02
        assert stored["ai_research_multiplier_source"] == "ai_research"
        assert await db.cache_get("planner:ideal_portfolio") is None
    finally:
        await db.close()
        db.remove_from_cache()
        for ext in ("", "-wal", "-shm"):
            target = path + ext
            if os.path.exists(target):
                os.unlink(target)


@pytest.mark.asyncio
async def test_update_security_ignores_direct_active_field_changes():
    from sentinel.api.routers.securities import update_security

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = Database(path)
    await db.connect()
    settings = Settings()
    settings._db = db
    await settings.init_defaults()
    try:
        await db.upsert_security("AMD.EU", name="AMD", active=1, allow_buy=1, allow_sell=1)
        deps = MagicMock()
        deps.db = db
        deps.settings = settings

        result = await update_security("AMD.EU", {"active": 0}, deps)

        stored = await db.get_security("AMD.EU")
        assert stored is not None
        assert result["active"] == 1
        assert int(stored["active"]) == 1
    finally:
        await db.close()
        db.remove_from_cache()
        for ext in ("", "-wal", "-shm"):
            target = path + ext
            if os.path.exists(target):
                os.unlink(target)


@pytest.mark.asyncio
async def test_delete_security_with_position_disables_buys_without_selling():
    from sentinel.api.routers.securities import delete_security
    from sentinel.universe import BROKER_POSITION_UNIVERSE_SOURCE

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = Database(path)
    await db.connect()
    try:
        await db.upsert_security("AMD.EU", name="AMD", active=1, allow_buy=1, allow_sell=1)
        await db.upsert_position("AMD.EU", quantity=3, current_price=150.0, currency="EUR")
        deps = MagicMock()
        deps.db = db
        deps.broker.delete_stock_list_ticker = AsyncMock(return_value=True)
        deps.broker.sell = AsyncMock()

        result = await delete_security("AMD.EU", deps, sell_position=True)

        row = await db.get_security("AMD.EU")
        position = await db.get_position("AMD.EU")
        assert result["status"] == "ok"
        assert result["sold_quantity"] == 0
        assert result["retained_position"] is True
        assert row is not None
        assert int(row["active"]) == 1
        assert int(row["allow_buy"]) == 0
        assert int(row["allow_sell"]) == 1
        assert row["universe_source"] == BROKER_POSITION_UNIVERSE_SOURCE
        assert position is not None
        assert position["quantity"] == 3
        deps.broker.delete_stock_list_ticker.assert_awaited_once_with("AMD.EU")
        deps.broker.sell.assert_not_awaited()
    finally:
        await db.close()
        db.remove_from_cache()
        for ext in ("", "-wal", "-shm"):
            target = path + ext
            if os.path.exists(target):
                os.unlink(target)


@pytest.mark.asyncio
async def test_delete_inactive_security_without_transactions_is_permanent():
    from sentinel.api.routers.securities import delete_security

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = Database(path)
    await db.connect()
    try:
        await db.upsert_security("UNUSED.EU", name="Unused", active=0, allow_buy=0, allow_sell=0)
        deps = MagicMock()
        deps.db = db
        deps.broker.delete_stock_list_ticker = AsyncMock(return_value=True)

        result = await delete_security("UNUSED.EU", deps)

        assert result["deleted"] is True
        assert await db.get_security("UNUSED.EU") is None
        deps.broker.delete_stock_list_ticker.assert_not_awaited()
    finally:
        await db.close()
        db.remove_from_cache()
        for ext in ("", "-wal", "-shm"):
            target = path + ext
            if os.path.exists(target):
                os.unlink(target)


@pytest.mark.asyncio
async def test_delete_inactive_security_with_transactions_returns_conflict():
    from sentinel.api.routers.securities import delete_security

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = Database(path)
    await db.connect()
    try:
        await db.upsert_security("USED.EU", name="Used", active=0, allow_buy=0, allow_sell=0)
        await db.upsert_trade(
            broker_trade_id="used-api-trade",
            symbol="USED.EU",
            side="BUY",
            quantity=1,
            price=10,
            commission=0,
            commission_currency="EUR",
            executed_at=1_700_000_000,
            raw_data={},
        )
        deps = MagicMock()
        deps.db = db
        deps.broker.delete_stock_list_ticker = AsyncMock(return_value=True)

        with pytest.raises(HTTPException) as exc:
            await delete_security("USED.EU", deps)

        assert exc.value.status_code == 409
        assert "1 historical transaction" in exc.value.detail
        assert await db.get_security("USED.EU") is not None
        deps.broker.delete_stock_list_ticker.assert_not_awaited()
    finally:
        await db.close()
        db.remove_from_cache()
        for ext in ("", "-wal", "-shm"):
            target = path + ext
            if os.path.exists(target):
                os.unlink(target)


@pytest.mark.asyncio
async def test_delete_security_does_not_change_local_state_when_favorites_mutation_fails():
    from sentinel.api.routers.securities import delete_security

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = Database(path)
    await db.connect()
    try:
        await db.upsert_security("AMD.EU", name="AMD", active=1, allow_buy=1, allow_sell=1)
        deps = MagicMock()
        deps.db = db
        deps.broker.delete_stock_list_ticker = AsyncMock(return_value=False)
        deps.broker.sell = AsyncMock()

        with pytest.raises(HTTPException) as exc:
            await delete_security("AMD.EU", deps)

        row = await db.get_security("AMD.EU")
        assert exc.value.status_code == 502
        assert row is not None
        assert int(row["active"]) == 1
        assert int(row["allow_buy"]) == 1
        assert int(row["allow_sell"]) == 1
        deps.broker.sell.assert_not_awaited()
    finally:
        await db.close()
        db.remove_from_cache()
        for ext in ("", "-wal", "-shm"):
            target = path + ext
            if os.path.exists(target):
                os.unlink(target)


@pytest.mark.asyncio
async def test_update_security_preference_rejects_missing_ai_research_multiplier():
    from sentinel.api.routers.securities import update_security_preference

    deps = MagicMock()
    deps.db.get_security = AsyncMock(return_value={"symbol": "MOH.GR"})

    with pytest.raises(HTTPException) as exc:
        await update_security_preference(
            {
                "symbol": "MOH.GR",
                "user_multipler": 0.02,
                "analysis": "typo field",
            },
            deps,
        )

    assert exc.value.status_code == 400
    assert "ai_research_multiplier" in exc.value.detail


@pytest.mark.asyncio
async def test_update_security_preference_rejects_non_finite_ai_research_multiplier():
    from sentinel.api.routers.securities import update_security_preference

    deps = MagicMock()
    deps.db.get_security = AsyncMock(return_value={"symbol": "MOH.GR"})

    with pytest.raises(HTTPException) as exc:
        await update_security_preference(
            {
                "symbol": "MOH.GR",
                "ai_research_multiplier": float("nan"),
                "analysis": "NaN should not be accepted.",
            },
            deps,
        )

    assert exc.value.status_code == 400
    assert "ai_research_multiplier" in exc.value.detail
