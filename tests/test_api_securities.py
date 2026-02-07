"""Tests for securities API endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


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
