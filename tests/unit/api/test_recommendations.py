"""Tests for recommendations API endpoints.

These tests validate the trade recommendation system, including
buy/sell recommendations, dismissal, and execution.
CRITICAL: These endpoints drive all trading decisions.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException


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


class TestDebugRecommendations:
    """Test the debug recommendations endpoint."""

    @pytest.mark.asyncio
    async def test_returns_debug_info(self, mock_rebalancing_service):
        """Test that debug info is returned."""
        from app.api.recommendations import debug_recommendations

        mock_rebalancing_service.get_recommendations_debug.return_value = {
            "filtered_stocks": ["AAPL", "GOOGL"],
            "reasons": {"AAPL": "below min score"},
        }

        result = await debug_recommendations(mock_rebalancing_service)

        assert "filtered_stocks" in result
        mock_rebalancing_service.get_recommendations_debug.assert_called_once()


class TestGetRecommendations:
    """Test the GET /recommendations endpoint."""

    @pytest.mark.asyncio
    async def test_returns_cached_recommendations_with_uuid(
        self, mock_rebalancing_service, mock_recommendation_repo
    ):
        """Test that cached recommendations are returned if they have UUIDs."""
        from app.api.recommendations import get_recommendations

        cached_data = {
            "recommendations": [
                {
                    "uuid": "test-uuid-1",
                    "symbol": "AAPL",
                    "name": "Apple Inc.",
                    "amount": 500.0,
                }
            ]
        }

        with patch("app.api.recommendations.cache") as mock_cache:
            mock_cache.get.return_value = cached_data

            result = await get_recommendations(
                mock_rebalancing_service, mock_recommendation_repo, limit=3
            )

        assert result == cached_data

    @pytest.mark.asyncio
    async def test_invalidates_cache_without_uuid(
        self, mock_rebalancing_service, mock_recommendation_repo
    ):
        """Test that cache is invalidated if recommendations lack UUIDs."""
        from app.api.recommendations import get_recommendations

        # Old format without UUIDs
        cached_data = {"recommendations": [{"symbol": "AAPL", "name": "Apple Inc."}]}

        mock_recommendation_repo.get_pending_by_side.return_value = []

        with patch("app.api.recommendations.cache") as mock_cache:
            mock_cache.get.return_value = cached_data

            await get_recommendations(
                mock_rebalancing_service, mock_recommendation_repo, limit=3
            )

        mock_cache.invalidate.assert_called()

    @pytest.mark.asyncio
    async def test_generates_and_stores_recommendations(
        self, mock_rebalancing_service, mock_recommendation_repo
    ):
        """Test that recommendations are generated and stored."""
        from app.api.recommendations import get_recommendations

        mock_recommendation_repo.get_pending_by_side.return_value = [
            {
                "uuid": "uuid-1",
                "symbol": "AAPL",
                "name": "Apple Inc.",
                "amount": 500.0,
                "reason": "High score",
                "geography": "US",
                "industry": "Technology",
                "priority": 1,
            }
        ]

        with patch("app.api.recommendations.cache") as mock_cache:
            mock_cache.get.return_value = None  # No cache

            result = await get_recommendations(
                mock_rebalancing_service, mock_recommendation_repo, limit=3
            )

        assert len(result["recommendations"]) == 1
        assert result["recommendations"][0]["symbol"] == "AAPL"
        mock_rebalancing_service.get_recommendations.assert_called_once_with(limit=3)

    @pytest.mark.asyncio
    async def test_handles_service_error(
        self, mock_rebalancing_service, mock_recommendation_repo
    ):
        """Test error handling when service fails."""
        from app.api.recommendations import get_recommendations

        mock_rebalancing_service.get_recommendations.side_effect = Exception(
            "Service error"
        )

        with patch("app.api.recommendations.cache") as mock_cache:
            mock_cache.get.return_value = None

            with pytest.raises(HTTPException) as exc_info:
                await get_recommendations(
                    mock_rebalancing_service, mock_recommendation_repo, limit=3
                )

        assert exc_info.value.status_code == 500


class TestDismissRecommendation:
    """Test the POST /recommendations/{uuid}/dismiss endpoint."""

    @pytest.mark.asyncio
    async def test_dismisses_recommendation(self, mock_recommendation_repo):
        """Test successful dismissal of a recommendation."""
        from app.api.recommendations import dismiss_recommendation

        mock_recommendation_repo.get_by_uuid.return_value = {"uuid": "test-uuid"}

        with patch(
            "app.infrastructure.cache_invalidation.get_cache_invalidation_service"
        ) as mock_cache_service:
            mock_service = MagicMock()
            mock_cache_service.return_value = mock_service

            result = await dismiss_recommendation("test-uuid", mock_recommendation_repo)

        assert result["status"] == "success"
        assert result["uuid"] == "test-uuid"
        mock_recommendation_repo.mark_dismissed.assert_called_once_with("test-uuid")

    @pytest.mark.asyncio
    async def test_returns_404_for_unknown_uuid(self, mock_recommendation_repo):
        """Test that 404 is returned for unknown UUID."""
        from app.api.recommendations import dismiss_recommendation

        mock_recommendation_repo.get_by_uuid.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await dismiss_recommendation("unknown-uuid", mock_recommendation_repo)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_handles_dismissal_error(self, mock_recommendation_repo):
        """Test error handling during dismissal."""
        from app.api.recommendations import dismiss_recommendation

        mock_recommendation_repo.get_by_uuid.return_value = {"uuid": "test-uuid"}
        mock_recommendation_repo.mark_dismissed.side_effect = Exception("DB error")

        with patch(
            "app.infrastructure.cache_invalidation.get_cache_invalidation_service"
        ):
            with pytest.raises(HTTPException) as exc_info:
                await dismiss_recommendation("test-uuid", mock_recommendation_repo)

        assert exc_info.value.status_code == 500


class TestGetSellRecommendations:
    """Test the GET /recommendations/sell endpoint."""

    @pytest.mark.asyncio
    async def test_returns_sell_recommendations(
        self, mock_rebalancing_service, mock_recommendation_repo
    ):
        """Test that sell recommendations are returned."""
        from app.api.recommendations import get_sell_recommendations

        mock_recommendation_repo.get_pending_by_side.return_value = [
            {
                "uuid": "sell-uuid-1",
                "symbol": "WEAK",
                "name": "Weak Stock",
                "amount": 1000.0,
                "reason": "Low score",
                "quantity": 10,
            }
        ]

        with patch("app.api.recommendations.cache") as mock_cache:
            mock_cache.get.return_value = None

            result = await get_sell_recommendations(
                mock_rebalancing_service, mock_recommendation_repo, limit=3
            )

        assert len(result["recommendations"]) == 1
        assert result["recommendations"][0]["symbol"] == "WEAK"
        mock_rebalancing_service.calculate_sell_recommendations.assert_called_once()

    @pytest.mark.asyncio
    async def test_uses_cached_sell_recommendations(
        self, mock_rebalancing_service, mock_recommendation_repo
    ):
        """Test that cached sell recommendations are used."""
        from app.api.recommendations import get_sell_recommendations

        cached_data = {
            "recommendations": [
                {"uuid": "sell-uuid", "symbol": "WEAK", "amount": 1000.0}
            ]
        }

        with patch("app.api.recommendations.cache") as mock_cache:
            mock_cache.get.return_value = cached_data

            result = await get_sell_recommendations(
                mock_rebalancing_service, mock_recommendation_repo, limit=3
            )

        assert result == cached_data


class TestDismissSellRecommendation:
    """Test the POST /recommendations/sell/{uuid}/dismiss endpoint."""

    @pytest.mark.asyncio
    async def test_dismisses_sell_recommendation(self, mock_recommendation_repo):
        """Test successful dismissal of a sell recommendation."""
        from app.api.recommendations import dismiss_sell_recommendation

        mock_recommendation_repo.get_by_uuid.return_value = {"uuid": "sell-uuid"}

        with patch(
            "app.infrastructure.cache_invalidation.get_cache_invalidation_service"
        ) as mock_cache_service:
            mock_service = MagicMock()
            mock_cache_service.return_value = mock_service

            result = await dismiss_sell_recommendation(
                "sell-uuid", mock_recommendation_repo
            )

        assert result["status"] == "success"
        mock_recommendation_repo.mark_dismissed.assert_called_once_with("sell-uuid")


class TestListStrategies:
    """Test the GET /recommendations/strategies endpoint."""

    @pytest.mark.asyncio
    async def test_returns_strategies(self):
        """Test that available strategies are returned."""
        from app.api.recommendations import list_recommendation_strategies

        result = await list_recommendation_strategies()

        assert "strategies" in result
        assert len(result["strategies"]) >= 1
        assert result["strategies"][0]["name"] == "portfolio-aware"


class TestGetAllStrategyRecommendations:
    """Test the GET /recommendations/all endpoint."""

    @pytest.mark.asyncio
    async def test_returns_all_strategy_recommendations(
        self, mock_rebalancing_service, mock_recommendation_repo
    ):
        """Test that all strategy recommendations are returned."""
        from app.api.recommendations import get_all_strategy_recommendations

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


class TestExecuteSellRecommendation:
    """Test the POST /recommendations/sell/{symbol}/execute endpoint."""

    @pytest.mark.asyncio
    async def test_executes_sell_recommendation(
        self,
        mock_rebalancing_service,
        mock_safety_service,
        mock_trade_execution_service,
    ):
        """Test successful execution of a sell recommendation."""
        from app.api.recommendations import execute_sell_recommendation

        mock_rec = MagicMock()
        mock_rec.symbol = "WEAK"
        mock_rec.quantity = 10
        mock_rec.estimated_value = 1000.0

        mock_rebalancing_service.calculate_sell_recommendations.return_value = [
            mock_rec
        ]

        mock_client = MagicMock()
        mock_order_result = MagicMock()
        mock_order_result.order_id = "order-123"
        mock_order_result.price = 100.0
        mock_client.place_order.return_value = mock_order_result

        with patch(
            "app.infrastructure.external.tradernet_connection.ensure_tradernet_connected",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            with patch(
                "app.infrastructure.cache_invalidation.get_cache_invalidation_service"
            ):
                result = await execute_sell_recommendation(
                    "WEAK",
                    mock_rebalancing_service,
                    mock_safety_service,
                    mock_trade_execution_service,
                )

        assert result["status"] == "success"
        assert result["order_id"] == "order-123"
        assert result["symbol"] == "WEAK"

    @pytest.mark.asyncio
    async def test_returns_404_when_no_recommendation(
        self,
        mock_rebalancing_service,
        mock_safety_service,
        mock_trade_execution_service,
    ):
        """Test that 404 is returned when no recommendation found."""
        from app.api.recommendations import execute_sell_recommendation

        mock_rebalancing_service.calculate_sell_recommendations.return_value = []

        with pytest.raises(HTTPException) as exc_info:
            await execute_sell_recommendation(
                "UNKNOWN",
                mock_rebalancing_service,
                mock_safety_service,
                mock_trade_execution_service,
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_validates_safety_before_execution(
        self,
        mock_rebalancing_service,
        mock_safety_service,
        mock_trade_execution_service,
    ):
        """Test that safety validation is performed before execution."""
        from app.api.recommendations import execute_sell_recommendation

        mock_rec = MagicMock()
        mock_rec.symbol = "WEAK"
        mock_rec.quantity = 10

        mock_rebalancing_service.calculate_sell_recommendations.return_value = [
            mock_rec
        ]
        mock_safety_service.validate_trade.side_effect = HTTPException(
            status_code=400, detail="Trade blocked by safety rules"
        )

        mock_client = MagicMock()

        with patch(
            "app.infrastructure.external.tradernet_connection.ensure_tradernet_connected",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await execute_sell_recommendation(
                    "WEAK",
                    mock_rebalancing_service,
                    mock_safety_service,
                    mock_trade_execution_service,
                )

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_handles_order_failure(
        self,
        mock_rebalancing_service,
        mock_safety_service,
        mock_trade_execution_service,
    ):
        """Test handling when order placement fails."""
        from app.api.recommendations import execute_sell_recommendation

        mock_rec = MagicMock()
        mock_rec.symbol = "WEAK"
        mock_rec.quantity = 10

        mock_rebalancing_service.calculate_sell_recommendations.return_value = [
            mock_rec
        ]

        mock_client = MagicMock()
        mock_client.place_order.return_value = None  # Order failed

        with patch(
            "app.infrastructure.external.tradernet_connection.ensure_tradernet_connected",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await execute_sell_recommendation(
                    "WEAK",
                    mock_rebalancing_service,
                    mock_safety_service,
                    mock_trade_execution_service,
                )

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_converts_symbol_to_uppercase(
        self,
        mock_rebalancing_service,
        mock_safety_service,
        mock_trade_execution_service,
    ):
        """Test that symbol is converted to uppercase."""
        from app.api.recommendations import execute_sell_recommendation

        mock_rec = MagicMock()
        mock_rec.symbol = "WEAK"
        mock_rec.quantity = 10
        mock_rec.estimated_value = 1000.0

        mock_rebalancing_service.calculate_sell_recommendations.return_value = [
            mock_rec
        ]

        mock_client = MagicMock()
        mock_order_result = MagicMock()
        mock_order_result.order_id = "order-123"
        mock_order_result.price = 100.0
        mock_client.place_order.return_value = mock_order_result

        with patch(
            "app.infrastructure.external.tradernet_connection.ensure_tradernet_connected",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            with patch(
                "app.infrastructure.cache_invalidation.get_cache_invalidation_service"
            ):
                result = await execute_sell_recommendation(
                    "weak",  # lowercase
                    mock_rebalancing_service,
                    mock_safety_service,
                    mock_trade_execution_service,
                )

        assert result["symbol"] == "WEAK"  # Should be uppercase


class TestRecommendationCaching:
    """Test recommendation caching behavior."""

    @pytest.mark.asyncio
    async def test_caches_recommendations_for_5_minutes(
        self, mock_rebalancing_service, mock_recommendation_repo
    ):
        """Test that recommendations are cached for 5 minutes."""
        from app.api.recommendations import get_recommendations

        mock_recommendation_repo.get_pending_by_side.return_value = []

        with patch("app.api.recommendations.cache") as mock_cache:
            mock_cache.get.return_value = None

            await get_recommendations(
                mock_rebalancing_service, mock_recommendation_repo, limit=3
            )

        mock_cache.set.assert_called_once()
        # Check TTL is 300 seconds (5 minutes)
        call_args = mock_cache.set.call_args
        assert call_args[1]["ttl_seconds"] == 300

    @pytest.mark.asyncio
    async def test_cache_key_includes_limit(
        self, mock_rebalancing_service, mock_recommendation_repo
    ):
        """Test that cache key includes the limit parameter."""
        from app.api.recommendations import get_recommendations

        mock_recommendation_repo.get_pending_by_side.return_value = []

        with patch("app.api.recommendations.cache") as mock_cache:
            mock_cache.get.return_value = None

            await get_recommendations(
                mock_rebalancing_service, mock_recommendation_repo, limit=5
            )

        # Cache key should include limit
        mock_cache.get.assert_called_with("recommendations:5")
