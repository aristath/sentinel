"""Tests for multi-step recommendation API endpoints.

These tests validate the holistic multi-step recommendation system,
including step execution, safety checks, and cache management.
CRITICAL: These endpoints orchestrate complex multi-trade sequences.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

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
def mock_recommendation_repo():
    """Mock recommendation repository."""
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


class TestExecuteSingleStep:
    """Test the _execute_single_step helper function."""

    @pytest.mark.asyncio
    async def test_executes_step_successfully(
        self, mock_safety_service, mock_trade_execution_service
    ):
        """Test successful step execution."""
        from app.api.multi_step_recommendations import _execute_single_step

        step = {
            "symbol": "AAPL",
            "side": TradeSide.BUY,
            "quantity": 5,
            "estimated_value": 800.0,
        }

        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.order_id = "order-123"
        mock_result.price = 160.0
        mock_client.place_order.return_value = mock_result

        mock_safety_service.check_pending_orders.return_value = False

        result = await _execute_single_step(
            1, step, mock_client, mock_safety_service, mock_trade_execution_service
        )

        assert result["status"] == "success"
        assert result["order_id"] == "order-123"
        assert result["step"] == 1

    @pytest.mark.asyncio
    async def test_blocks_when_pending_order_exists(
        self, mock_safety_service, mock_trade_execution_service
    ):
        """Test that step is blocked when pending order exists."""
        from app.api.multi_step_recommendations import _execute_single_step

        step = {
            "symbol": "AAPL",
            "side": TradeSide.BUY,
            "quantity": 5,
            "estimated_value": 800.0,
        }

        mock_client = MagicMock()
        mock_safety_service.check_pending_orders.return_value = True

        result = await _execute_single_step(
            1, step, mock_client, mock_safety_service, mock_trade_execution_service
        )

        assert result["status"] == "blocked"
        assert "pending order" in result["error"]

    @pytest.mark.asyncio
    async def test_handles_order_failure(
        self, mock_safety_service, mock_trade_execution_service
    ):
        """Test handling when order placement fails."""
        from app.api.multi_step_recommendations import _execute_single_step

        step = {
            "symbol": "AAPL",
            "side": TradeSide.BUY,
            "quantity": 5,
            "estimated_value": 800.0,
        }

        mock_client = MagicMock()
        mock_client.place_order.return_value = None  # Order failed
        mock_safety_service.check_pending_orders.return_value = False

        result = await _execute_single_step(
            1, step, mock_client, mock_safety_service, mock_trade_execution_service
        )

        assert result["status"] == "failed"

    @pytest.mark.asyncio
    async def test_handles_exception(
        self, mock_safety_service, mock_trade_execution_service
    ):
        """Test exception handling during step execution."""
        from app.api.multi_step_recommendations import _execute_single_step

        step = {
            "symbol": "AAPL",
            "side": TradeSide.BUY,
            "quantity": 5,
            "estimated_value": 800.0,
        }

        mock_client = MagicMock()
        mock_client.place_order.side_effect = Exception("Network error")
        mock_safety_service.check_pending_orders.return_value = False

        result = await _execute_single_step(
            1, step, mock_client, mock_safety_service, mock_trade_execution_service
        )

        assert result["status"] == "failed"
        assert "Network error" in result["error"]


class TestGetMultiStepRecommendations:
    """Test the GET /multi-step endpoint."""

    @pytest.mark.asyncio
    async def test_returns_cached_recommendations(
        self, mock_position_repo, mock_settings_service, mock_rebalancing_service
    ):
        """Test that cached recommendations are returned."""
        from app.api.multi_step_recommendations import get_multi_step_recommendations

        mock_position_repo.get_all.return_value = []

        cached_data = {
            "depth": 2,
            "steps": [
                {"step": 1, "symbol": "AAPL", "side": TradeSide.BUY},
                {"step": 2, "symbol": "GOOGL", "side": TradeSide.BUY},
            ],
            "total_score_improvement": 5.0,
            "final_available_cash": 1000.0,
        }

        with patch("app.api.multi_step_recommendations.cache") as mock_cache:
            mock_cache.get.return_value = cached_data
            with patch(
                "app.domain.portfolio_hash.generate_recommendation_cache_key",
                return_value="test-key",
            ):
                result = await get_multi_step_recommendations(
                    mock_position_repo, mock_settings_service, mock_rebalancing_service
                )

        assert result == cached_data

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_steps(
        self, mock_position_repo, mock_settings_service, mock_rebalancing_service
    ):
        """Test return value when no steps available."""
        from app.api.multi_step_recommendations import get_multi_step_recommendations

        mock_position_repo.get_all.return_value = []
        mock_rebalancing_service.get_multi_step_recommendations.return_value = []

        with patch("app.api.multi_step_recommendations.cache") as mock_cache:
            mock_cache.get.return_value = None
            with patch(
                "app.domain.portfolio_hash.generate_recommendation_cache_key",
                return_value="test-key",
            ):
                result = await get_multi_step_recommendations(
                    mock_position_repo, mock_settings_service, mock_rebalancing_service
                )

        assert result["depth"] == 0
        assert result["steps"] == []

    @pytest.mark.asyncio
    async def test_generates_steps_on_cache_miss(
        self, mock_position_repo, mock_settings_service, mock_rebalancing_service
    ):
        """Test that steps are generated on cache miss."""
        from app.api.multi_step_recommendations import get_multi_step_recommendations

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

        mock_rebalancing_service.get_multi_step_recommendations.return_value = [
            mock_step
        ]

        with patch("app.api.multi_step_recommendations.cache") as mock_cache:
            mock_cache.get.return_value = None
            with patch(
                "app.domain.portfolio_hash.generate_recommendation_cache_key",
                return_value="test-key",
            ):
                result = await get_multi_step_recommendations(
                    mock_position_repo, mock_settings_service, mock_rebalancing_service
                )

        assert result["depth"] == 1
        assert len(result["steps"]) == 1
        assert result["steps"][0]["symbol"] == "AAPL"

    @pytest.mark.asyncio
    async def test_handles_service_error(
        self, mock_position_repo, mock_settings_service, mock_rebalancing_service
    ):
        """Test error handling when service fails."""
        from app.api.multi_step_recommendations import get_multi_step_recommendations

        mock_position_repo.get_all.return_value = []
        mock_rebalancing_service.get_multi_step_recommendations.side_effect = Exception(
            "Service error"
        )

        with patch("app.api.multi_step_recommendations.cache") as mock_cache:
            mock_cache.get.return_value = None
            with patch(
                "app.domain.portfolio_hash.generate_recommendation_cache_key",
                return_value="test-key",
            ):
                with pytest.raises(HTTPException) as exc_info:
                    await get_multi_step_recommendations(
                        mock_position_repo,
                        mock_settings_service,
                        mock_rebalancing_service,
                    )

        assert exc_info.value.status_code == 500


class TestExecuteMultiStepRecommendationStep:
    """Test the POST /multi-step/execute-step/{step_number} endpoint."""

    @pytest.mark.asyncio
    async def test_rejects_step_number_less_than_1(
        self,
        mock_trade_repo,
        mock_position_repo,
        mock_settings_service,
        mock_safety_service,
        mock_trade_execution_service,
        mock_rebalancing_service,
    ):
        """Test that step number < 1 is rejected."""
        from app.api.multi_step_recommendations import (
            execute_multi_step_recommendation_step,
        )

        with pytest.raises(HTTPException) as exc_info:
            await execute_multi_step_recommendation_step(
                0,  # Invalid step number
                mock_trade_repo,
                mock_position_repo,
                mock_settings_service,
                mock_safety_service,
                mock_trade_execution_service,
                mock_rebalancing_service,
            )

        assert exc_info.value.status_code == 400
        assert "must be >= 1" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_rejects_step_number_greater_than_5(
        self,
        mock_trade_repo,
        mock_position_repo,
        mock_settings_service,
        mock_safety_service,
        mock_trade_execution_service,
        mock_rebalancing_service,
    ):
        """Test that step number > 5 is rejected."""
        from app.api.multi_step_recommendations import (
            execute_multi_step_recommendation_step,
        )

        with pytest.raises(HTTPException) as exc_info:
            await execute_multi_step_recommendation_step(
                6,  # Invalid step number
                mock_trade_repo,
                mock_position_repo,
                mock_settings_service,
                mock_safety_service,
                mock_trade_execution_service,
                mock_rebalancing_service,
            )

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent_step(
        self,
        mock_trade_repo,
        mock_position_repo,
        mock_settings_service,
        mock_safety_service,
        mock_trade_execution_service,
        mock_rebalancing_service,
    ):
        """Test that 404 is returned for step that doesn't exist."""
        from app.api.multi_step_recommendations import (
            execute_multi_step_recommendation_step,
        )

        mock_position_repo.get_all.return_value = []

        cached_data = {"steps": [{"step": 1, "symbol": "AAPL"}]}  # Only 1 step

        with patch("app.api.multi_step_recommendations.cache") as mock_cache:
            mock_cache.get.return_value = cached_data
            with patch(
                "app.domain.portfolio_hash.generate_recommendation_cache_key",
                return_value="test-key",
            ):
                with pytest.raises(HTTPException) as exc_info:
                    await execute_multi_step_recommendation_step(
                        3,  # Step doesn't exist
                        mock_trade_repo,
                        mock_position_repo,
                        mock_settings_service,
                        mock_safety_service,
                        mock_trade_execution_service,
                        mock_rebalancing_service,
                    )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_executes_step_successfully(
        self,
        mock_trade_repo,
        mock_position_repo,
        mock_settings_service,
        mock_safety_service,
        mock_trade_execution_service,
        mock_rebalancing_service,
    ):
        """Test successful step execution."""
        from app.api.multi_step_recommendations import (
            execute_multi_step_recommendation_step,
        )

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

        with patch("app.api.multi_step_recommendations.cache") as mock_cache:
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
                        result = await execute_multi_step_recommendation_step(
                            1,
                            mock_trade_repo,
                            mock_position_repo,
                            mock_settings_service,
                            mock_safety_service,
                            mock_trade_execution_service,
                            mock_rebalancing_service,
                        )

        assert result["status"] == "success"
        assert result["order_id"] == "order-123"


class TestExecuteAllMultiStepRecommendations:
    """Test the POST /multi-step/execute-all endpoint."""

    @pytest.mark.asyncio
    async def test_executes_all_steps(
        self,
        mock_trade_repo,
        mock_position_repo,
        mock_settings_service,
        mock_safety_service,
        mock_trade_execution_service,
        mock_rebalancing_service,
    ):
        """Test executing all steps successfully."""
        from app.api.multi_step_recommendations import (
            execute_all_multi_step_recommendations,
        )

        mock_position_repo.get_all.return_value = []
        mock_safety_service.check_cooldown.return_value = (False, None)
        mock_safety_service.check_pending_orders.return_value = False

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

        with patch("app.api.multi_step_recommendations.cache") as mock_cache:
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
                        result = await execute_all_multi_step_recommendations(
                            mock_trade_repo,
                            mock_position_repo,
                            mock_settings_service,
                            mock_safety_service,
                            mock_trade_execution_service,
                            mock_rebalancing_service,
                        )

        assert result["status"] == "complete"
        assert result["total_steps"] == 2
        assert result["successful"] == 2

    @pytest.mark.asyncio
    async def test_blocks_execution_on_cooldown(
        self,
        mock_trade_repo,
        mock_position_repo,
        mock_settings_service,
        mock_safety_service,
        mock_trade_execution_service,
        mock_rebalancing_service,
    ):
        """Test that execution is blocked when stocks are in cooldown."""
        from app.api.multi_step_recommendations import (
            execute_all_multi_step_recommendations,
        )

        mock_position_repo.get_all.return_value = []
        mock_safety_service.check_cooldown.return_value = (True, "Cooldown active")

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

        with patch("app.api.multi_step_recommendations.cache") as mock_cache:
            mock_cache.get.return_value = cached_data
            with patch(
                "app.domain.portfolio_hash.generate_recommendation_cache_key",
                return_value="test-key",
            ):
                with patch(
                    "app.infrastructure.external.tradernet_connection."
                    "ensure_tradernet_connected",
                    new_callable=AsyncMock,
                ):
                    with pytest.raises(HTTPException) as exc_info:
                        await execute_all_multi_step_recommendations(
                            mock_trade_repo,
                            mock_position_repo,
                            mock_settings_service,
                            mock_safety_service,
                            mock_trade_execution_service,
                            mock_rebalancing_service,
                        )

        assert exc_info.value.status_code == 400
        assert "cooldown" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_returns_404_when_no_steps(
        self,
        mock_trade_repo,
        mock_position_repo,
        mock_settings_service,
        mock_safety_service,
        mock_trade_execution_service,
        mock_rebalancing_service,
    ):
        """Test that 404 is returned when no steps available."""
        from app.api.multi_step_recommendations import (
            execute_all_multi_step_recommendations,
        )

        mock_position_repo.get_all.return_value = []
        mock_rebalancing_service.get_multi_step_recommendations.return_value = []

        with patch("app.api.multi_step_recommendations.cache") as mock_cache:
            mock_cache.get.return_value = None  # No cache
            with patch(
                "app.domain.portfolio_hash.generate_recommendation_cache_key",
                return_value="test-key",
            ):
                with patch(
                    "app.infrastructure.external.tradernet_connection."
                    "ensure_tradernet_connected",
                    new_callable=AsyncMock,
                ):
                    with pytest.raises(HTTPException) as exc_info:
                        await execute_all_multi_step_recommendations(
                            mock_trade_repo,
                            mock_position_repo,
                            mock_settings_service,
                            mock_safety_service,
                            mock_trade_execution_service,
                            mock_rebalancing_service,
                        )

        assert exc_info.value.status_code == 404


class TestRegenerateCacheFunction:
    """Test the _regenerate_multi_step_cache helper function."""

    @pytest.mark.asyncio
    async def test_regenerates_cache(
        self, mock_position_repo, mock_settings_service, mock_rebalancing_service
    ):
        """Test that cache is regenerated correctly."""
        from app.api.multi_step_recommendations import _regenerate_multi_step_cache

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

        mock_rebalancing_service.get_multi_step_recommendations.return_value = [
            mock_step
        ]

        with patch("app.api.multi_step_recommendations.cache") as mock_cache:
            with patch(
                "app.domain.portfolio_hash.generate_recommendation_cache_key",
                return_value="test-key",
            ):
                cached, cache_key = await _regenerate_multi_step_cache(
                    mock_position_repo, mock_settings_service, mock_rebalancing_service
                )

        assert cached["depth"] == 1
        assert len(cached["steps"]) == 1
        mock_cache.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_404_when_no_recommendations(
        self, mock_position_repo, mock_settings_service, mock_rebalancing_service
    ):
        """Test that 404 is raised when no recommendations available."""
        from app.api.multi_step_recommendations import _regenerate_multi_step_cache

        mock_position_repo.get_all.return_value = []
        mock_rebalancing_service.get_multi_step_recommendations.return_value = []

        with patch(
            "app.domain.portfolio_hash.generate_recommendation_cache_key",
            return_value="test-key",
        ):
            with pytest.raises(HTTPException) as exc_info:
                await _regenerate_multi_step_cache(
                    mock_position_repo, mock_settings_service, mock_rebalancing_service
                )

        assert exc_info.value.status_code == 404


class TestListStrategies:
    """Test the GET /multi-step/strategies endpoint."""

    @pytest.mark.asyncio
    async def test_returns_strategies(self):
        """Test that strategies are returned."""
        from app.api.multi_step_recommendations import list_recommendation_strategies

        result = await list_recommendation_strategies()

        assert "strategies" in result
        assert len(result["strategies"]) >= 1


class TestGetAllStrategyRecommendations:
    """Test the GET /multi-step/all endpoint."""

    @pytest.mark.asyncio
    async def test_returns_all_recommendations(
        self, mock_rebalancing_service, mock_recommendation_repo
    ):
        """Test that all strategy recommendations are returned."""
        from app.api.multi_step_recommendations import get_all_strategy_recommendations

        mock_recommendation_repo.get_pending_by_side.return_value = [
            {
                "uuid": "uuid-1",
                "symbol": "AAPL",
                "name": "Apple Inc.",
                "amount": 500.0,
                "reason": "High score",
            }
        ]

        result = await get_all_strategy_recommendations(
            mock_rebalancing_service, mock_recommendation_repo
        )

        assert "strategies" in result
        assert "portfolio-aware" in result["strategies"]


class TestCacheKeyGeneration:
    """Test cache key generation based on portfolio state."""

    @pytest.mark.asyncio
    async def test_cache_key_includes_portfolio_state(
        self, mock_position_repo, mock_settings_service, mock_rebalancing_service
    ):
        """Test that cache key is generated from portfolio state."""
        from app.api.multi_step_recommendations import get_multi_step_recommendations

        mock_pos = MagicMock()
        mock_pos.symbol = "AAPL"
        mock_pos.quantity = 10
        mock_position_repo.get_all.return_value = [mock_pos]

        mock_rebalancing_service.get_multi_step_recommendations.return_value = []

        with patch("app.api.multi_step_recommendations.cache") as mock_cache:
            mock_cache.get.return_value = None
            with patch(
                "app.domain.portfolio_hash.generate_recommendation_cache_key",
                return_value="portfolio-hash-123",
            ) as mock_gen:
                await get_multi_step_recommendations(
                    mock_position_repo, mock_settings_service, mock_rebalancing_service
                )

        # Verify cache key generation was called with position data
        mock_gen.assert_called_once()
        call_args = mock_gen.call_args[0]
        assert call_args[0] == [{"symbol": "AAPL", "quantity": 10}]
