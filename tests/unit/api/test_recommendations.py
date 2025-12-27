"""Tests for unified recommendations API endpoint.

These tests validate the unified recommendations endpoint that replaces
the separate buy/sell/multi-step endpoints. The endpoint always executes
the first step only.

Following TDD: These tests should fail initially (RED phase).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.value_objects.trade_side import TradeSide


@pytest.fixture
def mock_position_repo():
    """Mock position repository."""
    return AsyncMock()


@pytest.fixture
def mock_settings_service():
    """Mock settings service."""
    service = AsyncMock()
    mock_settings = MagicMock()
    mock_settings.to_dict.return_value = {"min_hold_days": 90}
    service.get_settings.return_value = mock_settings
    return service


@pytest.fixture
def mock_rebalancing_service():
    """Mock rebalancing service."""
    return AsyncMock()


@pytest.fixture
def mock_safety_service():
    """Mock trade safety service."""
    return AsyncMock()


@pytest.fixture
def mock_trade_execution_service():
    """Mock trade execution service."""
    return AsyncMock()


@pytest.fixture
def mock_trade_repo():
    """Mock trade repository."""
    return AsyncMock()


class TestGetRecommendations:
    """Test GET /api/trades/recommendations endpoint."""

    @pytest.mark.asyncio
    async def test_returns_recommendation_sequence(
        self, mock_position_repo, mock_settings_service, mock_rebalancing_service
    ):
        """Test that GET /recommendations returns sequence from holistic planner."""
        from app.api.recommendations import get_recommendations

        mock_position_repo.get_all.return_value = []

        mock_step = MagicMock()
        mock_step.step = 1
        mock_step.side = TradeSide.BUY
        mock_step.symbol = "AAPL"
        mock_step.name = "Apple Inc."
        mock_step.quantity = 5
        mock_step.estimated_price = 160.0
        mock_step.estimated_value = 800.0
        mock_step.currency = "USD"
        mock_step.reason = "High score"
        mock_step.portfolio_score_before = 70.0
        mock_step.portfolio_score_after = 75.0
        mock_step.score_change = 5.0
        mock_step.available_cash_before = 2000.0
        mock_step.available_cash_after = 1200.0

        mock_rebalancing_service.get_recommendations.return_value = [mock_step]

        with patch("app.api.recommendations.cache") as mock_cache:
            mock_cache.get.return_value = None
            with patch(
                "app.domain.portfolio_hash.generate_recommendation_cache_key",
                return_value="test-key",
            ):
                result = await get_recommendations(
                    mock_position_repo, mock_settings_service, mock_rebalancing_service
                )

        assert result["depth"] == 1
        assert len(result["steps"]) == 1
        assert result["steps"][0]["symbol"] == "AAPL"
        assert result["steps"][0]["side"] == TradeSide.BUY

    @pytest.mark.asyncio
    async def test_uses_recommendations_cache_key(
        self, mock_position_repo, mock_settings_service, mock_rebalancing_service
    ):
        """Test that cache key uses 'recommendations:' prefix, not 'multi_step_recommendations:'."""
        from app.api.recommendations import get_recommendations

        mock_position_repo.get_all.return_value = []

        cached_data = {
            "depth": 2,
            "steps": [
                {"step": 1, "symbol": "AAPL", "side": TradeSide.BUY},
                {"step": 2, "symbol": "GOOGL", "side": TradeSide.SELL},
            ],
            "total_score_improvement": 5.0,
            "final_available_cash": 1000.0,
        }

        with patch("app.api.recommendations.cache") as mock_cache:
            mock_cache.get.return_value = cached_data
            with patch(
                "app.domain.portfolio_hash.generate_recommendation_cache_key",
                return_value="test-key",
            ):
                await get_recommendations(
                    mock_position_repo, mock_settings_service, mock_rebalancing_service
                )

        # Verify cache key uses 'recommendations:' prefix
        cache_key_calls = [call[0][0] for call in mock_cache.get.call_args_list]
        assert any("recommendations:test-key" in str(call) for call in cache_key_calls)
        assert not any(
            "multi_step_recommendations:" in str(call) for call in cache_key_calls
        )


class TestExecuteRecommendation:
    """Test POST /api/trades/recommendations/execute endpoint."""

    @pytest.mark.asyncio
    async def test_executes_first_step_only(
        self,
        mock_trade_repo,
        mock_position_repo,
        mock_settings_service,
        mock_safety_service,
        mock_trade_execution_service,
        mock_rebalancing_service,
    ):
        """Test that execute endpoint always executes first step (no step_number parameter)."""
        from app.api.recommendations import execute_recommendation

        mock_position_repo.get_all.return_value = []

        cached_data = {
            "steps": [
                {
                    "step": 1,
                    "symbol": "AAPL",
                    "side": TradeSide.BUY,
                    "quantity": 5,
                    "estimated_value": 800.0,
                },
                {
                    "step": 2,
                    "symbol": "GOOGL",
                    "side": TradeSide.BUY,
                    "quantity": 3,
                    "estimated_value": 600.0,
                },
            ]
        }

        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.order_id = "order-123"
        mock_result.price = 160.0
        mock_client.place_order.return_value = mock_result

        with patch("app.api.recommendations.cache") as mock_cache:
            mock_cache.get.return_value = cached_data
            with patch(
                "app.domain.portfolio_hash.generate_recommendation_cache_key",
                return_value="test-key",
            ):
                with patch(
                    "app.infrastructure.external.tradernet_connection."
                    "ensure_tradernet_connected",
                    new_callable=AsyncMock,
                    return_value=mock_client,
                ):
                    with patch(
                        "app.infrastructure.cache_invalidation."
                        "get_cache_invalidation_service"
                    ):
                        result = await execute_recommendation(
                            mock_trade_repo,
                            mock_position_repo,
                            mock_settings_service,
                            mock_safety_service,
                            mock_trade_execution_service,
                            mock_rebalancing_service,
                        )

        # Should execute first step (step 1), not step 2
        assert result["status"] == "success"
        assert result["order_id"] == "order-123"
        assert result["symbol"] == "AAPL"  # First step
        assert result["step"] == 1  # Always step 1
        # Verify only first step was executed
        assert mock_client.place_order.call_count == 1

    @pytest.mark.asyncio
    async def test_no_step_number_parameter(
        self,
        mock_trade_repo,
        mock_position_repo,
        mock_settings_service,
        mock_safety_service,
        mock_trade_execution_service,
        mock_rebalancing_service,
    ):
        """Test that execute_recommendation function doesn't take step_number parameter."""
        # This test verifies the function signature doesn't have step_number
        import inspect

        from app.api.recommendations import execute_recommendation

        sig = inspect.signature(execute_recommendation)
        params = list(sig.parameters.keys())

        # Should not have step_number parameter
        assert "step_number" not in params

    @pytest.mark.asyncio
    async def test_uses_recommendations_cache_key_for_execute(
        self,
        mock_trade_repo,
        mock_position_repo,
        mock_settings_service,
        mock_safety_service,
        mock_trade_execution_service,
        mock_rebalancing_service,
    ):
        """Test that execute uses 'recommendations:' cache key."""
        from app.api.recommendations import execute_recommendation

        mock_position_repo.get_all.return_value = []

        cached_data = {
            "steps": [
                {
                    "step": 1,
                    "symbol": "AAPL",
                    "side": TradeSide.BUY,
                    "quantity": 5,
                    "estimated_value": 800.0,
                }
            ]
        }

        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.order_id = "order-123"
        mock_result.price = 160.0
        mock_client.place_order.return_value = mock_result

        with patch("app.api.recommendations.cache") as mock_cache:
            mock_cache.get.return_value = cached_data
            with patch(
                "app.domain.portfolio_hash.generate_recommendation_cache_key",
                return_value="test-key",
            ):
                with patch(
                    "app.infrastructure.external.tradernet_connection."
                    "ensure_tradernet_connected",
                    new_callable=AsyncMock,
                    return_value=mock_client,
                ):
                    with patch(
                        "app.infrastructure.cache_invalidation."
                        "get_cache_invalidation_service"
                    ):
                        await execute_recommendation(
                            mock_trade_repo,
                            mock_position_repo,
                            mock_settings_service,
                            mock_safety_service,
                            mock_trade_execution_service,
                            mock_rebalancing_service,
                        )

        # Verify cache key uses 'recommendations:' prefix
        cache_key_calls = [call[0][0] for call in mock_cache.get.call_args_list]
        assert any("recommendations:test-key" in str(call) for call in cache_key_calls)
        assert not any(
            "multi_step_recommendations:" in str(call) for call in cache_key_calls
        )


class TestRemovedEndpoints:
    """Test that removed endpoints don't exist."""

    @pytest.mark.asyncio
    async def test_execute_all_endpoint_does_not_exist(self):
        """Test that execute-all endpoint has been removed."""
        from app.api import recommendations

        # execute_all_recommendations should not exist
        assert not hasattr(recommendations, "execute_all_recommendations")
        assert not hasattr(recommendations, "execute_all_multi_step_recommendations")

    @pytest.mark.asyncio
    async def test_strategies_endpoint_does_not_exist(self):
        """Test that strategies endpoint has been removed."""
        from app.api import recommendations

        # list_recommendation_strategies should not exist
        assert not hasattr(recommendations, "list_recommendation_strategies")

    @pytest.mark.asyncio
    async def test_get_all_strategies_endpoint_does_not_exist(self):
        """Test that get_all_strategy_recommendations endpoint has been removed."""
        from app.api import recommendations

        # get_all_strategy_recommendations should not exist
        assert not hasattr(recommendations, "get_all_strategy_recommendations")
