"""Tests for securities API endpoints."""

import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from sentinel.database import Database
from sentinel.settings import Settings


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
            return_value=[{"symbol": "AAPL", "name": "Apple", "currency": "USD"}]
        )
    else:
        mock_deps.db.get_all_securities = AsyncMock(return_value=[])
    mock_deps.db.get_all_positions = AsyncMock(return_value=[])
    mock_cursor = MagicMock()
    mock_cursor.fetchall = AsyncMock(return_value=[])
    mock_cursor.fetchone = AsyncMock(return_value=None)
    mock_deps.db.conn.execute = AsyncMock(return_value=mock_cursor)
    mock_deps.broker.get_quotes = AsyncMock(return_value={})
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
    mock_planner.get_recommendations.assert_awaited_once_with(as_of_date="2024-01-15")
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
    mock_planner.get_recommendations.assert_awaited_once_with(as_of_date=None)
    mock_planner.calculate_ideal_portfolio.assert_awaited_once_with(as_of_date=None)
    mock_planner.get_current_allocations.assert_awaited_once_with(as_of_date=None)
    mock_deps.db.get_prices_bulk.assert_any_await(["AAPL"], days=365, end_date=None)


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
    assert "core_floor_active" in result[0]


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
                "clara_freshness": 0.12,
                "clara_strategic_sleeve": 0.08,
                "sentinel_baseline_sleeve": 0.72,
                "tactical_opportunity_sleeve": 0.20,
            },
            "symbols": {
                "AAPL": {
                    "allocation_sleeve": "core",
                    "baseline_target_pct": 0.20,
                    "clara_target_pct": 0.12,
                    "opportunity_target_pct": 0.10,
                    "final_target_pct": 0.42,
                }
            },
        },
    }

    with patch("sentinel.planner.Planner", return_value=mock_planner):
        result = await get_unified_view(mock_deps, period="1Y", as_of="2024-01-15")

    mock_deps.db.cache_get.assert_not_awaited()
    assert result[0]["sleeve"] == "core"
    assert result[0]["clara_freshness"] == 0.12
    assert result[0]["baseline_target_pct"] == 20.0
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
        await db.upsert_security("MOH.GR", name="Motor Oil Hellas", user_multiplier=0.5)
        await db.cache_set("planner:ideal_portfolio", "{}", ttl_seconds=600)
        deps = MagicMock()
        deps.db = db
        deps.settings = settings

        result = await update_security_preference(
            {
                "symbol": "MOH.GR",
                "user_multiplier": 0.02,
                "analysis": "Too fossil-heavy for the long-term portfolio.",
            },
            deps,
        )

        stored = await db.get_security("MOH.GR")
        assert stored is not None
        assert result["symbol"] == "MOH.GR"
        assert result["user_multiplier"] == 0.02
        assert result["user_multiplier_source"] == "clara"
        assert result["user_multiplier_analysis"] == "Too fossil-heavy for the long-term portfolio."
        assert stored["user_multiplier"] == 0.02
        assert stored["user_multiplier_source"] == "clara"
        assert await settings.get("clara_preferences_updated_at") is not None
        assert await db.cache_get("planner:ideal_portfolio") is None
    finally:
        await db.close()
        db.remove_from_cache()
        for ext in ("", "-wal", "-shm"):
            target = path + ext
            if os.path.exists(target):
                os.unlink(target)


@pytest.mark.asyncio
async def test_manual_security_preference_does_not_refresh_global_clara_freshness():
    from sentinel.api.routers.securities import update_security

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = Database(path)
    await db.connect()
    settings = Settings()
    settings._db = db
    await settings.init_defaults()
    try:
        await db.upsert_security("AMD.EU", name="AMD", user_multiplier=0.5)
        await settings.set("clara_preferences_updated_at", "2026-01-01T00:00:00+00:00")
        deps = MagicMock()
        deps.db = db
        deps.settings = settings

        result = await update_security("AMD.EU", {"user_multiplier": 0.9}, deps)

        stored = await db.get_security("AMD.EU")
        assert stored is not None
        assert result["user_multiplier"] == 0.9
        assert stored["user_multiplier_source"] == "manual"
        assert await settings.get("clara_preferences_updated_at") == "2026-01-01T00:00:00+00:00"
    finally:
        await db.close()
        db.remove_from_cache()
        for ext in ("", "-wal", "-shm"):
            target = path + ext
            if os.path.exists(target):
                os.unlink(target)


@pytest.mark.asyncio
async def test_update_security_preference_rejects_missing_user_multiplier():
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
    assert "user_multiplier" in exc.value.detail


@pytest.mark.asyncio
async def test_update_security_preference_rejects_non_finite_user_multiplier():
    from sentinel.api.routers.securities import update_security_preference

    deps = MagicMock()
    deps.db.get_security = AsyncMock(return_value={"symbol": "MOH.GR"})

    with pytest.raises(HTTPException) as exc:
        await update_security_preference(
            {
                "symbol": "MOH.GR",
                "user_multiplier": float("nan"),
                "analysis": "NaN should not be accepted.",
            },
            deps,
        )

    assert exc.value.status_code == 400
    assert "user_multiplier" in exc.value.detail
