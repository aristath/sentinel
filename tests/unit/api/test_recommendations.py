"""Comprehensive tests for unified recommendations API endpoint.

These tests validate the unified recommendations endpoint that replaces
the separate buy/sell/multi-step endpoints. The endpoint always executes
the first step only.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.domain.value_objects.trade_side import TradeSide


@pytest.fixture(autouse=True)
def mock_internal_repos():
    """Auto-mock repositories that are created directly inside get_recommendations.

    These repositories are created via direct constructor calls rather than
    dependency injection, so we need to mock them at the module level.
    The imports happen inside the function, so we patch at the source.
    """
    with patch("app.repositories.SettingsRepository") as mock_settings:
        mock_settings_instance = AsyncMock()
        mock_settings_instance.get_float.return_value = 0.0  # Disable incremental mode
        mock_settings.return_value = mock_settings_instance
        with patch(
            "app.modules.planning.database.planner_repository.PlannerRepository"
        ) as mock_planner:
            mock_planner_instance = AsyncMock()
            mock_planner_instance.get_best_result.return_value = None
            mock_planner_instance.get_evaluation_count.return_value = 0
            mock_planner.return_value = mock_planner_instance
            with patch("app.repositories.RecommendationRepository") as mock_rec_repo:
                mock_rec_repo_instance = AsyncMock()
                mock_rec_repo_instance.get_pending_by_portfolio_hash = AsyncMock(
                    return_value=[]
                )
                mock_rec_repo.return_value = mock_rec_repo_instance
                yield


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
    service = AsyncMock()
    service.validate_trade = AsyncMock()
    service.check_pending_orders = AsyncMock(return_value=False)
    return service


@pytest.fixture
def mock_trade_execution_service():
    """Mock trade execution service."""
    service = AsyncMock()
    service.record_trade = AsyncMock()
    return service


@pytest.fixture
def mock_trade_repo():
    """Mock trade repository."""
    return AsyncMock()


@pytest.fixture
def mock_step():
    """Create a mock recommendation step."""
    step = MagicMock()
    step.step = 1
    step.side = TradeSide.BUY
    step.symbol = "AAPL"
    step.name = "Apple Inc."
    step.quantity = 5
    step.estimated_price = 160.0
    step.estimated_value = 800.0
    step.currency = "USD"
    step.reason = "High score"
    step.portfolio_score_before = 70.0
    step.portfolio_score_after = 75.0
    step.score_change = 5.0
    step.available_cash_before = 2000.0
    step.available_cash_after = 1200.0
    return step


@pytest.fixture
def mock_stock_repo():
    """Mock security repository."""
    repo = AsyncMock()
    repo.get_all_active.return_value = []
    return repo


@pytest.fixture
def mock_allocation_repo():
    """Mock allocation repository."""
    repo = AsyncMock()
    repo.get_all.return_value = []
    return repo


@pytest.fixture
def mock_tradernet_client():
    """Mock Tradernet client."""
    client = MagicMock()
    mock_result = MagicMock()
    mock_result.order_id = "order-123"
    mock_result.price = 160.0
    client.place_order.return_value = mock_result
    client.is_connected = True
    client.get_cash_balances.return_value = []
    return client


class TestGetRecommendations:
    """Test GET /api/trades/recommendations endpoint."""

    @pytest.mark.asyncio
    async def test_returns_recommendation_sequence(
        self,
        mock_position_repo,
        mock_settings_service,
        mock_rebalancing_service,
        mock_stock_repo,
        mock_allocation_repo,
        mock_tradernet_client,
        mock_step,
    ):
        """Test that GET /recommendations returns sequence from holistic planner."""
        from app.modules.planning.api.recommendations import get_recommendations

        mock_position_repo.get_all.return_value = []
        mock_rebalancing_service.get_recommendations.return_value = [mock_step]

        with patch("app.modules.planning.api.recommendations.cache") as mock_cache:
            mock_cache.get.return_value = None
            with patch(
                "app.domain.portfolio_hash.generate_recommendation_cache_key",
                return_value="test-key",
            ):
                result = await get_recommendations(
                    mock_position_repo,
                    mock_settings_service,
                    mock_rebalancing_service,
                    mock_stock_repo,
                    mock_allocation_repo,
                    mock_tradernet_client,
                )

        assert result["depth"] == 1
        assert len(result["steps"]) == 1
        assert result["steps"][0]["symbol"] == "AAPL"
        assert result["steps"][0]["side"] == TradeSide.BUY

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_recommendations(
        self,
        mock_position_repo,
        mock_settings_service,
        mock_rebalancing_service,
        mock_stock_repo,
        mock_allocation_repo,
        mock_tradernet_client,
    ):
        """Test that empty result is returned when no recommendations available."""
        from app.modules.planning.api.recommendations import get_recommendations

        mock_position_repo.get_all.return_value = []
        mock_rebalancing_service.get_recommendations.return_value = []

        with patch("app.modules.planning.api.recommendations.cache") as mock_cache:
            mock_cache.get.return_value = None
            with patch(
                "app.domain.portfolio_hash.generate_recommendation_cache_key",
                return_value="test-key",
            ):
                result = await get_recommendations(
                    mock_position_repo,
                    mock_settings_service,
                    mock_rebalancing_service,
                    mock_stock_repo,
                    mock_allocation_repo,
                    mock_tradernet_client,
                )

        assert result["depth"] == 0
        assert result["steps"] == []
        assert result["total_score_improvement"] == 0.0
        assert result["final_available_cash"] == 0.0

    @pytest.mark.asyncio
    async def test_uses_recommendations_cache_key(
        self,
        mock_position_repo,
        mock_settings_service,
        mock_rebalancing_service,
        mock_stock_repo,
        mock_allocation_repo,
        mock_tradernet_client,
    ):
        """Test that cache key uses 'recommendations:' prefix, not 'multi_step_recommendations:'."""
        from app.modules.planning.api.recommendations import get_recommendations

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

        with patch("app.modules.planning.api.recommendations.cache") as mock_cache:
            mock_cache.get.return_value = cached_data
            with patch(
                "app.domain.portfolio_hash.generate_recommendation_cache_key",
                return_value="test-key",
            ):
                await get_recommendations(
                    mock_position_repo,
                    mock_settings_service,
                    mock_rebalancing_service,
                    mock_stock_repo,
                    mock_allocation_repo,
                    mock_tradernet_client,
                )

        # Verify cache key uses 'recommendations:' prefix
        cache_key_calls = [call[0][0] for call in mock_cache.get.call_args_list]
        assert any("recommendations:test-key" in str(call) for call in cache_key_calls)
        assert not any(
            "multi_step_recommendations:" in str(call) for call in cache_key_calls
        )

    @pytest.mark.asyncio
    async def test_returns_cached_data_when_available(
        self,
        mock_position_repo,
        mock_settings_service,
        mock_rebalancing_service,
        mock_stock_repo,
        mock_allocation_repo,
        mock_tradernet_client,
    ):
        """Test that cached data is returned when available."""
        from app.modules.planning.api.recommendations import get_recommendations

        mock_position_repo.get_all.return_value = []

        cached_data = {
            "depth": 1,
            "steps": [{"step": 1, "symbol": "CACHED", "side": TradeSide.BUY}],
            "total_score_improvement": 3.0,
            "final_available_cash": 500.0,
        }

        with patch("app.modules.planning.api.recommendations.cache") as mock_cache:
            mock_cache.get.return_value = cached_data
            with patch(
                "app.domain.portfolio_hash.generate_recommendation_cache_key",
                return_value="test-key",
            ):
                result = await get_recommendations(
                    mock_position_repo,
                    mock_settings_service,
                    mock_rebalancing_service,
                    mock_stock_repo,
                    mock_allocation_repo,
                    mock_tradernet_client,
                )

        # Should not call rebalancing service when cache hit
        mock_rebalancing_service.get_recommendations.assert_not_called()
        assert result["steps"][0]["symbol"] == "CACHED"

    @pytest.mark.asyncio
    async def test_caches_result_with_ttl(
        self,
        mock_position_repo,
        mock_settings_service,
        mock_rebalancing_service,
        mock_stock_repo,
        mock_allocation_repo,
        mock_tradernet_client,
        mock_step,
    ):
        """Test that result is cached with 5 minute TTL."""
        from app.modules.planning.api.recommendations import get_recommendations

        mock_position_repo.get_all.return_value = []
        mock_rebalancing_service.get_recommendations.return_value = [mock_step]

        with patch("app.modules.planning.api.recommendations.cache") as mock_cache:
            mock_cache.get.return_value = None
            with patch(
                "app.domain.portfolio_hash.generate_recommendation_cache_key",
                return_value="test-key",
            ):
                await get_recommendations(
                    mock_position_repo,
                    mock_settings_service,
                    mock_rebalancing_service,
                    mock_stock_repo,
                    mock_allocation_repo,
                    mock_tradernet_client,
                )

        # Verify cache.set was called with correct TTL
        mock_cache.set.assert_called_once()
        call_args = mock_cache.set.call_args
        assert call_args[0][0] == "recommendations:test-key"
        assert call_args[1]["ttl_seconds"] == 300

    @pytest.mark.asyncio
    async def test_handles_multiple_steps(
        self,
        mock_position_repo,
        mock_settings_service,
        mock_rebalancing_service,
        mock_stock_repo,
        mock_allocation_repo,
        mock_tradernet_client,
    ):
        """Test handling of multi-step recommendations."""
        from app.modules.planning.api.recommendations import get_recommendations

        mock_position_repo.get_all.return_value = []

        step1 = MagicMock()
        step1.step = 1
        step1.side = TradeSide.SELL
        step1.symbol = "GOOGL"
        step1.name = "Alphabet Inc."
        step1.quantity = 3
        step1.estimated_price = 140.0
        step1.estimated_value = 420.0
        step1.currency = "USD"
        step1.reason = "Rebalance"
        step1.portfolio_score_before = 70.0
        step1.portfolio_score_after = 72.0
        step1.score_change = 2.0
        step1.available_cash_before = 1000.0
        step1.available_cash_after = 1420.0

        step2 = MagicMock()
        step2.step = 2
        step2.side = TradeSide.BUY
        step2.symbol = "AAPL"
        step2.name = "Apple Inc."
        step2.quantity = 5
        step2.estimated_price = 160.0
        step2.estimated_value = 800.0
        step2.currency = "USD"
        step2.reason = "High score"
        step2.portfolio_score_before = 72.0
        step2.portfolio_score_after = 77.0
        step2.score_change = 5.0
        step2.available_cash_before = 1420.0
        step2.available_cash_after = 620.0

        mock_rebalancing_service.get_recommendations.return_value = [step1, step2]

        with patch("app.modules.planning.api.recommendations.cache") as mock_cache:
            mock_cache.get.return_value = None
            with patch(
                "app.domain.portfolio_hash.generate_recommendation_cache_key",
                return_value="test-key",
            ):
                result = await get_recommendations(
                    mock_position_repo,
                    mock_settings_service,
                    mock_rebalancing_service,
                    mock_stock_repo,
                    mock_allocation_repo,
                    mock_tradernet_client,
                )

        assert result["depth"] == 2
        assert len(result["steps"]) == 2
        # total_score_improvement = final_score - initial_score = 77.0 - 70.0 = 7.0
        assert result["total_score_improvement"] == 7.0
        assert result["final_available_cash"] == 620.0  # Last step's cash

    @pytest.mark.asyncio
    async def test_rounds_numeric_values(
        self,
        mock_position_repo,
        mock_settings_service,
        mock_rebalancing_service,
        mock_stock_repo,
        mock_allocation_repo,
        mock_tradernet_client,
    ):
        """Test that numeric values are properly rounded."""
        from app.modules.planning.api.recommendations import get_recommendations

        mock_position_repo.get_all.return_value = []

        step = MagicMock()
        step.step = 1
        step.side = TradeSide.BUY
        step.symbol = "AAPL"
        step.name = "Apple Inc."
        step.quantity = 5
        step.estimated_price = 160.12345
        step.estimated_value = 800.56789
        step.currency = "USD"
        step.reason = "Test"
        step.portfolio_score_before = 70.123
        step.portfolio_score_after = 75.456
        step.score_change = 5.333
        step.available_cash_before = 2000.99
        step.available_cash_after = 1200.44

        mock_rebalancing_service.get_recommendations.return_value = [step]

        with patch("app.modules.planning.api.recommendations.cache") as mock_cache:
            mock_cache.get.return_value = None
            with patch(
                "app.domain.portfolio_hash.generate_recommendation_cache_key",
                return_value="test-key",
            ):
                result = await get_recommendations(
                    mock_position_repo,
                    mock_settings_service,
                    mock_rebalancing_service,
                    mock_stock_repo,
                    mock_allocation_repo,
                    mock_tradernet_client,
                )

        step_result = result["steps"][0]
        assert step_result["estimated_price"] == 160.12
        assert step_result["estimated_value"] == 800.57
        assert step_result["portfolio_score_before"] == 70.1
        assert step_result["portfolio_score_after"] == 75.5
        assert step_result["score_change"] == 5.33
        assert step_result["available_cash_before"] == 2000.99
        assert step_result["available_cash_after"] == 1200.44

    @pytest.mark.asyncio
    async def test_handles_service_exception(
        self,
        mock_position_repo,
        mock_settings_service,
        mock_rebalancing_service,
        mock_stock_repo,
        mock_allocation_repo,
        mock_tradernet_client,
    ):
        """Test that service exceptions are converted to HTTPException."""
        from app.modules.planning.api.recommendations import get_recommendations

        mock_position_repo.get_all.return_value = []
        mock_rebalancing_service.get_recommendations.side_effect = Exception(
            "Service error"
        )

        with patch("app.modules.planning.api.recommendations.cache") as mock_cache:
            mock_cache.get.return_value = None
            with patch(
                "app.domain.portfolio_hash.generate_recommendation_cache_key",
                return_value="test-key",
            ):
                with pytest.raises(HTTPException) as exc_info:
                    await get_recommendations(
                        mock_position_repo,
                        mock_settings_service,
                        mock_rebalancing_service,
                        mock_stock_repo,
                        mock_allocation_repo,
                        mock_tradernet_client,
                    )

        assert exc_info.value.status_code == 500
        assert "Service error" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_propagates_http_exception(
        self,
        mock_position_repo,
        mock_settings_service,
        mock_rebalancing_service,
        mock_stock_repo,
        mock_allocation_repo,
        mock_tradernet_client,
    ):
        """Test that HTTPException is propagated without wrapping."""
        from app.modules.planning.api.recommendations import get_recommendations

        mock_position_repo.get_all.return_value = []
        http_exc = HTTPException(status_code=404, detail="Not found")
        mock_rebalancing_service.get_recommendations.side_effect = http_exc

        with patch("app.modules.planning.api.recommendations.cache") as mock_cache:
            mock_cache.get.return_value = None
            with patch(
                "app.domain.portfolio_hash.generate_recommendation_cache_key",
                return_value="test-key",
            ):
                with pytest.raises(HTTPException) as exc_info:
                    await get_recommendations(
                        mock_position_repo,
                        mock_settings_service,
                        mock_rebalancing_service,
                        mock_stock_repo,
                        mock_allocation_repo,
                        mock_tradernet_client,
                    )

        assert exc_info.value is http_exc

    @pytest.mark.asyncio
    async def test_generates_portfolio_aware_cache_key(
        self,
        mock_position_repo,
        mock_settings_service,
        mock_rebalancing_service,
        mock_stock_repo,
        mock_allocation_repo,
        mock_tradernet_client,
        mock_step,
    ):
        """Test that cache key is generated from portfolio state."""
        from app.modules.planning.api.recommendations import get_recommendations

        pos1 = MagicMock()
        pos1.symbol = "AAPL"
        pos1.quantity = 10
        pos2 = MagicMock()
        pos2.symbol = "GOOGL"
        pos2.quantity = 5
        mock_position_repo.get_all.return_value = [pos1, pos2]

        mock_rebalancing_service.get_recommendations.return_value = [mock_step]

        with patch("app.modules.planning.api.recommendations.cache") as mock_cache:
            mock_cache.get.return_value = None
            with patch(
                "app.domain.portfolio_hash.generate_recommendation_cache_key"
            ) as mock_hash:
                mock_hash.return_value = "hash-123"
                await get_recommendations(
                    mock_position_repo,
                    mock_settings_service,
                    mock_rebalancing_service,
                    mock_stock_repo,
                    mock_allocation_repo,
                    mock_tradernet_client,
                )

        # Verify hash was called with position data, settings, securities, and cash
        mock_hash.assert_called_once()
        call_args = mock_hash.call_args[0]
        positions_arg = call_args[0]
        settings_arg = call_args[1]

        assert len(positions_arg) == 2
        assert positions_arg[0]["symbol"] == "AAPL"
        assert positions_arg[0]["quantity"] == 10
        assert settings_arg == {"min_hold_days": 90}


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
        mock_stock_repo,
        mock_allocation_repo,
        mock_tradernet_client,
    ):
        """Test that execute endpoint always executes first step (no step_number parameter)."""
        from app.modules.planning.api.recommendations import execute_recommendation

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

        with patch("app.modules.planning.api.recommendations.cache") as mock_cache:
            mock_cache.get.return_value = cached_data
            with patch(
                "app.domain.portfolio_hash.generate_recommendation_cache_key",
                return_value="test-key",
            ):
                with patch(
                    "app.infrastructure.external.tradernet_connection."
                    "ensure_tradernet_connected",
                    new_callable=AsyncMock,
                    return_value=mock_tradernet_client,
                ):
                    with patch(
                        "app.infrastructure.cache_invalidation."
                        "get_cache_invalidation_service"
                    ) as mock_invalidation:
                        mock_cache_service = MagicMock()
                        mock_invalidation.return_value = mock_cache_service

                        result = await execute_recommendation(
                            mock_trade_repo,
                            mock_position_repo,
                            mock_settings_service,
                            mock_safety_service,
                            mock_trade_execution_service,
                            mock_rebalancing_service,
                            mock_stock_repo,
                            mock_allocation_repo,
                            mock_tradernet_client,
                        )

        # Should execute first step (step 1), not step 2
        assert result["status"] == "success"
        assert result["order_id"] == "order-123"
        assert result["symbol"] == "AAPL"  # First step
        assert result["step"] == 1  # Always step 1
        # Verify only first step was executed
        assert mock_tradernet_client.place_order.call_count == 1

    @pytest.mark.asyncio
    async def test_no_step_number_parameter(self):
        """Test that execute_recommendation function doesn't take step_number parameter."""
        import inspect

        from app.modules.planning.api.recommendations import execute_recommendation

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
        mock_stock_repo,
        mock_allocation_repo,
        mock_tradernet_client,
    ):
        """Test that execute uses 'recommendations:' cache key."""
        from app.modules.planning.api.recommendations import execute_recommendation

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

        with patch("app.modules.planning.api.recommendations.cache") as mock_cache:
            mock_cache.get.return_value = cached_data
            with patch(
                "app.domain.portfolio_hash.generate_recommendation_cache_key",
                return_value="test-key",
            ):
                with patch(
                    "app.infrastructure.external.tradernet_connection."
                    "ensure_tradernet_connected",
                    new_callable=AsyncMock,
                    return_value=mock_tradernet_client,
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
                            mock_stock_repo,
                            mock_allocation_repo,
                            mock_tradernet_client,
                        )

        # Verify cache key uses 'recommendations:' prefix
        cache_key_calls = [call[0][0] for call in mock_cache.get.call_args_list]
        assert any("recommendations:test-key" in str(call) for call in cache_key_calls)
        assert not any(
            "multi_step_recommendations:" in str(call) for call in cache_key_calls
        )

    @pytest.mark.asyncio
    async def test_regenerates_cache_on_miss(
        self,
        mock_trade_repo,
        mock_position_repo,
        mock_settings_service,
        mock_safety_service,
        mock_trade_execution_service,
        mock_rebalancing_service,
        mock_stock_repo,
        mock_allocation_repo,
        mock_tradernet_client,
    ):
        """Test that recommendations are regenerated when cache misses."""
        from app.modules.planning.api.recommendations import execute_recommendation

        mock_position_repo.get_all.return_value = []

        step = MagicMock()
        step.step = 1
        step.side = TradeSide.BUY
        step.symbol = "AAPL"
        step.name = "Apple Inc."
        step.quantity = 5
        step.estimated_price = 160.0
        step.estimated_value = 800.0
        step.currency = "USD"
        step.reason = "High score"
        step.portfolio_score_before = 70.0
        step.portfolio_score_after = 75.0
        step.score_change = 5.0
        step.available_cash_before = 2000.0
        step.available_cash_after = 1200.0

        mock_rebalancing_service.get_recommendations.return_value = [step]

        with patch("app.modules.planning.api.recommendations.cache") as mock_cache:
            mock_cache.get.return_value = None  # Cache miss
            with patch(
                "app.domain.portfolio_hash.generate_recommendation_cache_key",
                return_value="test-key",
            ):
                with patch(
                    "app.infrastructure.external.tradernet_connection."
                    "ensure_tradernet_connected",
                    new_callable=AsyncMock,
                    return_value=mock_tradernet_client,
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
                            mock_stock_repo,
                            mock_allocation_repo,
                            mock_tradernet_client,
                        )

        # Verify rebalancing service was called
        mock_rebalancing_service.get_recommendations.assert_called_once()
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_raises_404_when_no_recommendations(
        self,
        mock_trade_repo,
        mock_position_repo,
        mock_settings_service,
        mock_safety_service,
        mock_trade_execution_service,
        mock_rebalancing_service,
        mock_stock_repo,
        mock_allocation_repo,
        mock_tradernet_client,
    ):
        """Test that 404 is raised when no recommendations available."""
        from app.modules.planning.api.recommendations import execute_recommendation

        mock_position_repo.get_all.return_value = []
        mock_rebalancing_service.get_recommendations.return_value = []

        with patch("app.modules.planning.api.recommendations.cache") as mock_cache:
            mock_cache.get.return_value = None
            with patch(
                "app.domain.portfolio_hash.generate_recommendation_cache_key",
                return_value="test-key",
            ):
                with pytest.raises(HTTPException) as exc_info:
                    await execute_recommendation(
                        mock_trade_repo,
                        mock_position_repo,
                        mock_settings_service,
                        mock_safety_service,
                        mock_trade_execution_service,
                        mock_rebalancing_service,
                        mock_stock_repo,
                        mock_allocation_repo,
                        mock_tradernet_client,
                    )

        assert exc_info.value.status_code == 404
        assert "No recommendations available" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_validates_trade_before_execution(
        self,
        mock_trade_repo,
        mock_position_repo,
        mock_settings_service,
        mock_safety_service,
        mock_trade_execution_service,
        mock_rebalancing_service,
        mock_stock_repo,
        mock_allocation_repo,
        mock_tradernet_client,
    ):
        """Test that trade is validated before execution."""
        from app.modules.planning.api.recommendations import execute_recommendation

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

        with patch("app.modules.planning.api.recommendations.cache") as mock_cache:
            mock_cache.get.return_value = cached_data
            with patch(
                "app.domain.portfolio_hash.generate_recommendation_cache_key",
                return_value="test-key",
            ):
                with patch(
                    "app.infrastructure.external.tradernet_connection."
                    "ensure_tradernet_connected",
                    new_callable=AsyncMock,
                    return_value=mock_tradernet_client,
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
                            mock_stock_repo,
                            mock_allocation_repo,
                            mock_tradernet_client,
                        )

        # Verify safety check was called
        mock_safety_service.validate_trade.assert_called_once_with(
            symbol="AAPL",
            side=TradeSide.BUY,
            quantity=5,
            client=mock_tradernet_client,
            raise_on_error=True,
        )

    @pytest.mark.asyncio
    async def test_records_trade_after_execution(
        self,
        mock_trade_repo,
        mock_position_repo,
        mock_settings_service,
        mock_safety_service,
        mock_trade_execution_service,
        mock_rebalancing_service,
        mock_stock_repo,
        mock_allocation_repo,
        mock_tradernet_client,
    ):
        """Test that trade is recorded after successful execution."""
        from app.modules.planning.api.recommendations import execute_recommendation

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

        with patch("app.modules.planning.api.recommendations.cache") as mock_cache:
            mock_cache.get.return_value = cached_data
            with patch(
                "app.domain.portfolio_hash.generate_recommendation_cache_key",
                return_value="test-key",
            ):
                with patch(
                    "app.infrastructure.external.tradernet_connection."
                    "ensure_tradernet_connected",
                    new_callable=AsyncMock,
                    return_value=mock_tradernet_client,
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
                            mock_stock_repo,
                            mock_allocation_repo,
                            mock_tradernet_client,
                        )

        # Verify trade was recorded
        mock_trade_execution_service.record_trade.assert_called_once_with(
            symbol="AAPL",
            side=TradeSide.BUY,
            quantity=5,
            price=160.0,
            order_id="order-123",
        )

    @pytest.mark.asyncio
    async def test_invalidates_caches_after_execution(
        self,
        mock_trade_repo,
        mock_position_repo,
        mock_settings_service,
        mock_safety_service,
        mock_trade_execution_service,
        mock_rebalancing_service,
        mock_stock_repo,
        mock_allocation_repo,
        mock_tradernet_client,
    ):
        """Test that caches are invalidated after execution."""
        from app.modules.planning.api.recommendations import execute_recommendation

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

        with patch("app.modules.planning.api.recommendations.cache") as mock_cache:
            mock_cache.get.return_value = cached_data
            with patch(
                "app.domain.portfolio_hash.generate_recommendation_cache_key",
                return_value="test-key",
            ):
                with patch(
                    "app.infrastructure.external.tradernet_connection."
                    "ensure_tradernet_connected",
                    new_callable=AsyncMock,
                    return_value=mock_tradernet_client,
                ):
                    with patch(
                        "app.infrastructure.cache_invalidation."
                        "get_cache_invalidation_service"
                    ) as mock_invalidation:
                        mock_cache_service = MagicMock()
                        mock_invalidation.return_value = mock_cache_service

                        await execute_recommendation(
                            mock_trade_repo,
                            mock_position_repo,
                            mock_settings_service,
                            mock_safety_service,
                            mock_trade_execution_service,
                            mock_rebalancing_service,
                            mock_stock_repo,
                            mock_allocation_repo,
                            mock_tradernet_client,
                        )

        # Verify cache invalidation was called
        mock_cache_service.invalidate_trade_caches.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_500_when_order_fails(
        self,
        mock_trade_repo,
        mock_position_repo,
        mock_settings_service,
        mock_safety_service,
        mock_trade_execution_service,
        mock_rebalancing_service,
        mock_stock_repo,
        mock_allocation_repo,
        mock_tradernet_client,
    ):
        """Test that 500 is raised when order placement fails."""
        from app.modules.planning.api.recommendations import execute_recommendation

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
        mock_client.place_order.return_value = None  # Failed order
        mock_client.is_connected = True
        mock_client.get_cash_balances.return_value = []

        with patch("app.modules.planning.api.recommendations.cache") as mock_cache:
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
                    with pytest.raises(HTTPException) as exc_info:
                        await execute_recommendation(
                            mock_trade_repo,
                            mock_position_repo,
                            mock_settings_service,
                            mock_safety_service,
                            mock_trade_execution_service,
                            mock_rebalancing_service,
                            mock_stock_repo,
                            mock_allocation_repo,
                            mock_client,
                        )

        assert exc_info.value.status_code == 500
        assert "Trade execution failed" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_handles_exception_during_execution(
        self,
        mock_trade_repo,
        mock_position_repo,
        mock_settings_service,
        mock_safety_service,
        mock_trade_execution_service,
        mock_rebalancing_service,
        mock_stock_repo,
        mock_allocation_repo,
        mock_tradernet_client,
    ):
        """Test that exceptions during execution are handled."""
        from app.modules.planning.api.recommendations import execute_recommendation

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

        with patch("app.modules.planning.api.recommendations.cache") as mock_cache:
            mock_cache.get.return_value = cached_data
            with patch(
                "app.domain.portfolio_hash.generate_recommendation_cache_key",
                return_value="test-key",
            ):
                with patch(
                    "app.infrastructure.external.tradernet_connection."
                    "ensure_tradernet_connected",
                    new_callable=AsyncMock,
                    side_effect=Exception("Connection error"),
                ):
                    with pytest.raises(HTTPException) as exc_info:
                        await execute_recommendation(
                            mock_trade_repo,
                            mock_position_repo,
                            mock_settings_service,
                            mock_safety_service,
                            mock_trade_execution_service,
                            mock_rebalancing_service,
                            mock_stock_repo,
                            mock_allocation_repo,
                            mock_tradernet_client,
                        )

        assert exc_info.value.status_code == 500
        assert "Connection error" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_propagates_http_exception_from_safety_check(
        self,
        mock_trade_repo,
        mock_position_repo,
        mock_settings_service,
        mock_safety_service,
        mock_trade_execution_service,
        mock_rebalancing_service,
        mock_stock_repo,
        mock_allocation_repo,
        mock_tradernet_client,
    ):
        """Test that HTTPException from safety check is propagated."""
        from app.modules.planning.api.recommendations import execute_recommendation

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

        http_exc = HTTPException(status_code=400, detail="Invalid trade")
        mock_safety_service.validate_trade.side_effect = http_exc

        with patch("app.modules.planning.api.recommendations.cache") as mock_cache:
            mock_cache.get.return_value = cached_data
            with patch(
                "app.domain.portfolio_hash.generate_recommendation_cache_key",
                return_value="test-key",
            ):
                with patch(
                    "app.infrastructure.external.tradernet_connection."
                    "ensure_tradernet_connected",
                    new_callable=AsyncMock,
                    return_value=mock_tradernet_client,
                ):
                    with pytest.raises(HTTPException) as exc_info:
                        await execute_recommendation(
                            mock_trade_repo,
                            mock_position_repo,
                            mock_settings_service,
                            mock_safety_service,
                            mock_trade_execution_service,
                            mock_rebalancing_service,
                            mock_stock_repo,
                            mock_allocation_repo,
                            mock_tradernet_client,
                        )

        assert exc_info.value is http_exc


class TestExecuteSingleStep:
    """Test _execute_single_step helper function."""

    @pytest.mark.asyncio
    async def test_executes_step_successfully(
        self, mock_safety_service, mock_trade_execution_service, mock_tradernet_client
    ):
        """Test successful step execution."""
        from app.modules.planning.api.recommendations import _execute_single_step

        step = {
            "symbol": "AAPL",
            "side": TradeSide.BUY,
            "quantity": 5,
            "estimated_value": 800.0,
        }

        result = await _execute_single_step(
            idx=1,
            step=step,
            client=mock_tradernet_client,
            safety_service=mock_safety_service,
            trade_execution_service=mock_trade_execution_service,
        )

        assert result["step"] == 1
        assert result["status"] == "success"
        assert result["order_id"] == "order-123"
        assert result["symbol"] == "AAPL"
        assert result["price"] == 160.0

    @pytest.mark.asyncio
    async def test_blocks_when_pending_order_exists(
        self, mock_safety_service, mock_trade_execution_service, mock_tradernet_client
    ):
        """Test that step is blocked when pending order exists."""
        from app.modules.planning.api.recommendations import _execute_single_step

        mock_safety_service.check_pending_orders.return_value = True

        step = {
            "symbol": "AAPL",
            "side": TradeSide.BUY,
            "quantity": 5,
            "estimated_value": 800.0,
        }

        result = await _execute_single_step(
            idx=2,
            step=step,
            client=mock_tradernet_client,
            safety_service=mock_safety_service,
            trade_execution_service=mock_trade_execution_service,
        )

        assert result["step"] == 2
        assert result["status"] == "blocked"
        assert "pending order" in result["error"].lower()
        # Should not place order
        mock_tradernet_client.place_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_failed_order(
        self, mock_safety_service, mock_trade_execution_service
    ):
        """Test handling of failed order placement."""
        from app.modules.planning.api.recommendations import _execute_single_step

        mock_client = MagicMock()
        mock_client.place_order.return_value = None  # Failed

        step = {
            "symbol": "AAPL",
            "side": TradeSide.BUY,
            "quantity": 5,
            "estimated_value": 800.0,
        }

        result = await _execute_single_step(
            idx=1,
            step=step,
            client=mock_client,
            safety_service=mock_safety_service,
            trade_execution_service=mock_trade_execution_service,
        )

        assert result["step"] == 1
        assert result["status"] == "failed"
        assert "execution failed" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_handles_exception_during_execution(
        self, mock_safety_service, mock_trade_execution_service
    ):
        """Test handling of exception during step execution."""
        from app.modules.planning.api.recommendations import _execute_single_step

        mock_client = MagicMock()
        mock_client.place_order.side_effect = Exception("Network error")

        step = {
            "symbol": "AAPL",
            "side": TradeSide.BUY,
            "quantity": 5,
            "estimated_value": 800.0,
        }

        result = await _execute_single_step(
            idx=3,
            step=step,
            client=mock_client,
            safety_service=mock_safety_service,
            trade_execution_service=mock_trade_execution_service,
        )

        assert result["step"] == 3
        assert result["status"] == "failed"
        assert "Network error" in result["error"]

    @pytest.mark.asyncio
    async def test_records_trade_after_successful_order(
        self, mock_safety_service, mock_trade_execution_service, mock_tradernet_client
    ):
        """Test that trade is recorded after successful order."""
        from app.modules.planning.api.recommendations import _execute_single_step

        step = {
            "symbol": "AAPL",
            "side": TradeSide.BUY,
            "quantity": 5,
            "estimated_value": 800.0,
        }

        await _execute_single_step(
            idx=1,
            step=step,
            client=mock_tradernet_client,
            safety_service=mock_safety_service,
            trade_execution_service=mock_trade_execution_service,
        )

        mock_trade_execution_service.record_trade.assert_called_once_with(
            symbol="AAPL",
            side=TradeSide.BUY,
            quantity=5,
            price=160.0,
            order_id="order-123",
        )


class TestRegenerateRecommendationsCache:
    """Test _regenerate_recommendations_cache helper function."""

    @pytest.mark.asyncio
    async def test_regenerates_cache_successfully(
        self,
        mock_position_repo,
        mock_settings_service,
        mock_rebalancing_service,
        mock_stock_repo,
        mock_allocation_repo,
        mock_tradernet_client,
    ):
        """Test successful cache regeneration."""
        from app.modules.planning.api.recommendations import (
            _regenerate_recommendations_cache,
        )

        mock_position_repo.get_all.return_value = []

        step = MagicMock()
        step.step = 1
        step.side = TradeSide.BUY
        step.symbol = "AAPL"
        step.name = "Apple Inc."
        step.quantity = 5
        step.estimated_price = 160.0
        step.estimated_value = 800.0
        step.currency = "USD"
        step.reason = "High score"
        step.portfolio_score_before = 70.0
        step.portfolio_score_after = 75.0
        step.score_change = 5.0
        step.available_cash_before = 2000.0
        step.available_cash_after = 1200.0

        mock_rebalancing_service.get_recommendations.return_value = [step]

        with patch("app.modules.planning.api.recommendations.cache"):
            with patch(
                "app.domain.portfolio_hash.generate_recommendation_cache_key",
                return_value="test-key",
            ):
                cached, cache_key = await _regenerate_recommendations_cache(
                    mock_position_repo,
                    mock_settings_service,
                    mock_rebalancing_service,
                    mock_stock_repo,
                    mock_allocation_repo,
                    mock_tradernet_client,
                )

        assert cache_key == "recommendations:test-key"
        assert cached["depth"] == 1
        assert len(cached["steps"]) == 1
        assert cached["steps"][0]["symbol"] == "AAPL"

    @pytest.mark.asyncio
    async def test_raises_404_when_no_recommendations(
        self,
        mock_position_repo,
        mock_settings_service,
        mock_rebalancing_service,
        mock_stock_repo,
        mock_allocation_repo,
        mock_tradernet_client,
    ):
        """Test that 404 is raised when no recommendations available."""
        from app.modules.planning.api.recommendations import (
            _regenerate_recommendations_cache,
        )

        mock_position_repo.get_all.return_value = []
        mock_rebalancing_service.get_recommendations.return_value = []

        with patch("app.modules.planning.api.recommendations.cache"):
            with patch(
                "app.domain.portfolio_hash.generate_recommendation_cache_key",
                return_value="test-key",
            ):
                with pytest.raises(HTTPException) as exc_info:
                    await _regenerate_recommendations_cache(
                        mock_position_repo,
                        mock_settings_service,
                        mock_rebalancing_service,
                        mock_stock_repo,
                        mock_allocation_repo,
                        mock_tradernet_client,
                    )

        assert exc_info.value.status_code == 404
        assert "No recommendations available" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_caches_regenerated_data(
        self,
        mock_position_repo,
        mock_settings_service,
        mock_rebalancing_service,
        mock_stock_repo,
        mock_allocation_repo,
        mock_tradernet_client,
    ):
        """Test that regenerated data is cached."""
        from app.modules.planning.api.recommendations import (
            _regenerate_recommendations_cache,
        )

        mock_position_repo.get_all.return_value = []

        step = MagicMock()
        step.step = 1
        step.side = TradeSide.BUY
        step.symbol = "AAPL"
        step.name = "Apple Inc."
        step.quantity = 5
        step.estimated_price = 160.0
        step.estimated_value = 800.0
        step.currency = "USD"
        step.reason = "High score"
        step.portfolio_score_before = 70.0
        step.portfolio_score_after = 75.0
        step.score_change = 5.0
        step.available_cash_before = 2000.0
        step.available_cash_after = 1200.0

        mock_rebalancing_service.get_recommendations.return_value = [step]

        with patch("app.modules.planning.api.recommendations.cache") as mock_cache:
            with patch(
                "app.domain.portfolio_hash.generate_recommendation_cache_key",
                return_value="test-key",
            ):
                await _regenerate_recommendations_cache(
                    mock_position_repo,
                    mock_settings_service,
                    mock_rebalancing_service,
                    mock_stock_repo,
                    mock_allocation_repo,
                    mock_tradernet_client,
                )

        # Verify cache was set
        mock_cache.set.assert_called_once()
        call_args = mock_cache.set.call_args
        assert call_args[0][0] == "recommendations:test-key"
        assert call_args[1]["ttl_seconds"] == 300


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
