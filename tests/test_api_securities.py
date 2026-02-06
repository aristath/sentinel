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
    mock_deps.db.get_setting = AsyncMock(return_value="http://localhost:8001")
    mock_deps.currency.to_eur = AsyncMock(return_value=0.0)
    mock_deps.settings.get = AsyncMock(return_value="http://localhost:8001")
    return mock_deps


@pytest.mark.asyncio
async def test_get_unified_view_with_as_of_no_local_ml_predictions():
    """When as_of is set, endpoint still returns successfully without local ml.db access."""
    from sentinel.api.routers.securities import get_unified_view

    mock_deps = _make_unified_mocks(one_security=True)
    mock_planner = MagicMock()
    mock_planner.get_recommendations = AsyncMock(return_value=[])
    mock_planner.calculate_ideal_portfolio = AsyncMock(return_value={})
    mock_planner.get_current_allocations = AsyncMock(return_value={})

    with patch("sentinel.planner.Planner", return_value=mock_planner):
        result = await get_unified_view(mock_deps, period="1Y", as_of="2024-01-15")
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_get_unified_view_without_as_of_no_local_ml_predictions():
    """When as_of is None, endpoint still returns successfully without local ml.db access."""
    from sentinel.api.routers.securities import get_unified_view

    mock_deps = _make_unified_mocks(one_security=True)
    mock_planner = MagicMock()
    mock_planner.get_recommendations = AsyncMock(return_value=[])
    mock_planner.calculate_ideal_portfolio = AsyncMock(return_value={})
    mock_planner.get_current_allocations = AsyncMock(return_value={})

    with patch("sentinel.planner.Planner", return_value=mock_planner):
        result = await get_unified_view(mock_deps, period="1Y", as_of=None)
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_get_unified_view_populates_ml_score_from_ml_service():
    """Unified payload includes ml_score when sentinel-ml returns scores."""
    from sentinel.api.routers.securities import get_unified_view

    mock_deps = _make_unified_mocks(one_security=True)
    mock_deps.db.conn.execute = AsyncMock(return_value=MagicMock(fetchall=AsyncMock(return_value=[])))
    mock_deps.settings.get = AsyncMock(return_value="http://localhost:8001")

    mock_planner = MagicMock()
    mock_planner.get_recommendations = AsyncMock(return_value=[])
    mock_planner.calculate_ideal_portfolio = AsyncMock(return_value={})
    mock_planner.get_current_allocations = AsyncMock(return_value={})

    with (
        patch("sentinel.planner.Planner", return_value=mock_planner),
        patch(
            "sentinel.api.routers.securities._get_blended_predictions",
            new=AsyncMock(return_value={"AAPL": {"ml_score": 0.62, "final_score": 0.62}}),
        ),
    ):
        result = await get_unified_view(mock_deps, period="1Y", as_of=None)

    assert isinstance(result, list)
    assert result
    assert result[0]["ml_score"] == 0.62
