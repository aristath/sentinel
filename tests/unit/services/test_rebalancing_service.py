"""Tests for rebalancing service.

These tests validate rebalancing trade calculation and orchestration.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain.models import MultiStepRecommendation, Recommendation
from app.domain.value_objects.currency import Currency
from app.domain.value_objects.recommendation_status import RecommendationStatus
from app.domain.value_objects.trade_side import TradeSide


class TestCalculateMinTradeAmount:
    """Test calculate_min_trade_amount function."""

    def test_calculates_minimum_for_standard_fees(self):
        """Test calculation with standard Freedom24 fees."""
        from app.modules.rebalancing.services.rebalancing_service import (
            calculate_min_trade_amount,
        )

        # Standard Freedom24: €2 fixed + 0.2% variable
        result = calculate_min_trade_amount(
            transaction_cost_fixed=2.0, transaction_cost_percent=0.002
        )

        # Should be around €400 (2 / (0.01 - 0.002) = 2 / 0.008 = 250)
        # Actually, let's check: 2 / (0.01 - 0.002) = 2 / 0.008 = 250
        assert result > 0
        assert result < 1000.0

    def test_returns_high_minimum_when_percent_exceeds_max_ratio(self):
        """Test that high minimum is returned when percent exceeds max ratio."""
        from app.modules.rebalancing.services.rebalancing_service import (
            calculate_min_trade_amount,
        )

        # If variable cost (0.02 = 2%) exceeds max ratio (0.01 = 1%)
        result = calculate_min_trade_amount(
            transaction_cost_fixed=2.0,
            transaction_cost_percent=0.02,  # 2% variable cost
            max_cost_ratio=0.01,  # 1% max ratio
        )

        assert result == 1000.0

    def test_handles_zero_fixed_cost(self):
        """Test handling when fixed cost is zero."""
        from app.modules.rebalancing.services.rebalancing_service import (
            calculate_min_trade_amount,
        )

        result = calculate_min_trade_amount(
            transaction_cost_fixed=0.0, transaction_cost_percent=0.002
        )

        assert result == 0.0

    def test_handles_different_max_cost_ratios(self):
        """Test with different max cost ratios."""
        from app.modules.rebalancing.services.rebalancing_service import (
            calculate_min_trade_amount,
        )

        result_1pct = calculate_min_trade_amount(
            transaction_cost_fixed=2.0,
            transaction_cost_percent=0.002,
            max_cost_ratio=0.01,
        )

        result_2pct = calculate_min_trade_amount(
            transaction_cost_fixed=2.0,
            transaction_cost_percent=0.002,
            max_cost_ratio=0.02,
        )

        # Higher max ratio should result in lower minimum
        assert result_2pct < result_1pct


@pytest.fixture
def mock_stock_repo():
    """Mock stock repository."""
    return AsyncMock()


@pytest.fixture
def mock_position_repo():
    """Mock position repository."""
    return AsyncMock()


@pytest.fixture
def mock_allocation_repo():
    """Mock allocation repository."""
    return AsyncMock()


@pytest.fixture
def mock_portfolio_repo():
    """Mock portfolio repository."""
    return AsyncMock()


@pytest.fixture
def mock_trade_repo():
    """Mock trade repository."""
    return AsyncMock()


@pytest.fixture
def mock_settings_repo():
    """Mock settings repository."""
    repo = AsyncMock()
    repo.get_float = AsyncMock(return_value=2.0)
    repo.get_int = AsyncMock(return_value=5)
    return repo


@pytest.fixture
def mock_recommendation_repo():
    """Mock recommendation repository."""
    return AsyncMock()


@pytest.fixture
def mock_db_manager():
    """Mock database manager."""
    return MagicMock()


@pytest.fixture
def mock_tradernet_client():
    """Mock Tradernet client."""
    client = MagicMock()
    client.is_connected = True
    client.get_total_cash_eur.return_value = 1000.0
    client.get_pending_orders.return_value = []
    client.get_cash_balances.return_value = []
    return client


@pytest.fixture
def mock_exchange_rate_service():
    """Mock exchange rate service."""
    service = AsyncMock()
    service.batch_convert_to_eur = AsyncMock(return_value={"EUR": 1000.0})
    return service


class TestCalculateRebalanceTrades:
    """Test calculate_rebalance_trades method."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_cash_below_minimum(
        self,
        mock_stock_repo,
        mock_position_repo,
        mock_allocation_repo,
        mock_portfolio_repo,
        mock_trade_repo,
        mock_settings_repo,
        mock_recommendation_repo,
        mock_db_manager,
        mock_tradernet_client,
        mock_exchange_rate_service,
    ):
        """Test that empty list is returned when cash is below minimum."""
        from app.modules.rebalancing.services.rebalancing_service import RebalancingService

        service = RebalancingService(
            stock_repo=mock_stock_repo,
            position_repo=mock_position_repo,
            allocation_repo=mock_allocation_repo,
            portfolio_repo=mock_portfolio_repo,
            trade_repo=mock_trade_repo,
            settings_repo=mock_settings_repo,
            recommendation_repo=mock_recommendation_repo,
            db_manager=mock_db_manager,
            tradernet_client=mock_tradernet_client,
            exchange_rate_service=mock_exchange_rate_service,
        )

        # Very low cash amount (below minimum trade)
        result = await service.calculate_rebalance_trades(available_cash=10.0)

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_recommendations(
        self,
        mock_stock_repo,
        mock_position_repo,
        mock_allocation_repo,
        mock_portfolio_repo,
        mock_trade_repo,
        mock_settings_repo,
        mock_recommendation_repo,
        mock_db_manager,
        mock_tradernet_client,
        mock_exchange_rate_service,
    ):
        """Test that empty list is returned when there are no recommendations."""
        from app.modules.rebalancing.services.rebalancing_service import RebalancingService

        service = RebalancingService(
            stock_repo=mock_stock_repo,
            position_repo=mock_position_repo,
            allocation_repo=mock_allocation_repo,
            portfolio_repo=mock_portfolio_repo,
            trade_repo=mock_trade_repo,
            settings_repo=mock_settings_repo,
            recommendation_repo=mock_recommendation_repo,
            db_manager=mock_db_manager,
            tradernet_client=mock_tradernet_client,
            exchange_rate_service=mock_exchange_rate_service,
        )

        service.get_recommendations = AsyncMock(return_value=[])

        result = await service.calculate_rebalance_trades(available_cash=1000.0)

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_buy_recommendations(
        self,
        mock_stock_repo,
        mock_position_repo,
        mock_allocation_repo,
        mock_portfolio_repo,
        mock_trade_repo,
        mock_settings_repo,
        mock_recommendation_repo,
        mock_db_manager,
        mock_tradernet_client,
        mock_exchange_rate_service,
    ):
        """Test that empty list is returned when there are no buy recommendations."""
        from app.modules.rebalancing.services.rebalancing_service import RebalancingService

        service = RebalancingService(
            stock_repo=mock_stock_repo,
            position_repo=mock_position_repo,
            allocation_repo=mock_allocation_repo,
            portfolio_repo=mock_portfolio_repo,
            trade_repo=mock_trade_repo,
            settings_repo=mock_settings_repo,
            recommendation_repo=mock_recommendation_repo,
            db_manager=mock_db_manager,
            tradernet_client=mock_tradernet_client,
            exchange_rate_service=mock_exchange_rate_service,
        )

        # Only SELL recommendations
        mock_step = MultiStepRecommendation(
            step=1,
            side=TradeSide.SELL,
            symbol="AAPL",
            name="Apple Inc.",
            quantity=10.0,
            estimated_price=100.0,
            estimated_value=1000.0,
            currency=Currency.USD,
            reason="Test sell",
            portfolio_score_before=50.0,
            portfolio_score_after=55.0,
            score_change=5.0,
            available_cash_before=1000.0,
            available_cash_after=2000.0,
        )

        service.get_recommendations = AsyncMock(return_value=[mock_step])

        result = await service.calculate_rebalance_trades(available_cash=1000.0)

        assert result == []

    @pytest.mark.asyncio
    async def test_converts_multistep_to_recommendation(
        self,
        mock_stock_repo,
        mock_position_repo,
        mock_allocation_repo,
        mock_portfolio_repo,
        mock_trade_repo,
        mock_settings_repo,
        mock_recommendation_repo,
        mock_db_manager,
        mock_tradernet_client,
        mock_exchange_rate_service,
    ):
        """Test that MultiStepRecommendation is converted to Recommendation."""
        from app.modules.rebalancing.services.rebalancing_service import RebalancingService

        service = RebalancingService(
            stock_repo=mock_stock_repo,
            position_repo=mock_position_repo,
            allocation_repo=mock_allocation_repo,
            portfolio_repo=mock_portfolio_repo,
            trade_repo=mock_trade_repo,
            settings_repo=mock_settings_repo,
            recommendation_repo=mock_recommendation_repo,
            db_manager=mock_db_manager,
            tradernet_client=mock_tradernet_client,
            exchange_rate_service=mock_exchange_rate_service,
        )

        # BUY recommendation
        mock_step = MultiStepRecommendation(
            step=1,
            side=TradeSide.BUY,
            symbol="AAPL",
            name="Apple Inc.",
            quantity=10.0,
            estimated_price=100.0,
            estimated_value=1000.0,
            currency=Currency.USD,
            reason="Test buy",
            portfolio_score_before=50.0,
            portfolio_score_after=55.0,
            score_change=5.0,
            available_cash_before=1000.0,
            available_cash_after=0.0,
        )

        service.get_recommendations = AsyncMock(return_value=[mock_step])

        result = await service.calculate_rebalance_trades(available_cash=1000.0)

        assert len(result) == 1
        assert isinstance(result[0], Recommendation)
        assert result[0].symbol == "AAPL"
        assert result[0].side == TradeSide.BUY
        assert result[0].quantity == 10.0
        assert result[0].status == RecommendationStatus.PENDING

    @pytest.mark.asyncio
    async def test_filters_invalid_recommendations(
        self,
        mock_stock_repo,
        mock_position_repo,
        mock_allocation_repo,
        mock_portfolio_repo,
        mock_trade_repo,
        mock_settings_repo,
        mock_recommendation_repo,
        mock_db_manager,
        mock_tradernet_client,
        mock_exchange_rate_service,
    ):
        """Test that invalid recommendations are filtered out."""
        from app.modules.rebalancing.services.rebalancing_service import RebalancingService

        service = RebalancingService(
            stock_repo=mock_stock_repo,
            position_repo=mock_position_repo,
            allocation_repo=mock_allocation_repo,
            portfolio_repo=mock_portfolio_repo,
            trade_repo=mock_trade_repo,
            settings_repo=mock_settings_repo,
            recommendation_repo=mock_recommendation_repo,
            db_manager=mock_db_manager,
            tradernet_client=mock_tradernet_client,
            exchange_rate_service=mock_exchange_rate_service,
        )

        # Valid recommendation
        valid_step = MultiStepRecommendation(
            step=1,
            side=TradeSide.BUY,
            symbol="AAPL",
            name="Apple Inc.",
            quantity=10.0,
            estimated_price=100.0,
            estimated_value=1000.0,
            currency=Currency.USD,
            reason="Valid",
            portfolio_score_before=50.0,
            portfolio_score_after=55.0,
            score_change=5.0,
            available_cash_before=1000.0,
            available_cash_after=0.0,
        )

        # Invalid recommendation (zero quantity that should be filtered)
        # MultiStepRecommendation allows invalid values, but they should be filtered
        # when converting to Recommendation
        invalid_step = MultiStepRecommendation(
            step=2,
            side=TradeSide.BUY,
            symbol="MSFT",
            name="Microsoft",
            quantity=0.0,  # Zero quantity, should be filtered
            estimated_price=100.0,
            estimated_value=0.0,
            currency=Currency.USD,
            reason="Invalid",
            portfolio_score_before=50.0,
            portfolio_score_after=50.0,
            score_change=0.0,
            available_cash_before=1000.0,
            available_cash_after=1000.0,
        )

        service.get_recommendations = AsyncMock(return_value=[valid_step, invalid_step])

        result = await service.calculate_rebalance_trades(available_cash=1000.0)

        assert len(result) == 1
        assert result[0].symbol == "AAPL"
