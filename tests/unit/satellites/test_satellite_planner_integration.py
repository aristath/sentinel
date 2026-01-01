"""Unit tests for satellite planner integration with PlannerLoader.

Tests the integration between SatellitePlannerService and the modular
planner configuration system.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.models import Position, Security
from app.modules.planning.domain.config.factory import ModularPlannerFactory
from app.modules.planning.domain.config.models import PlannerConfiguration
from app.modules.planning.domain.holistic_planner import HolisticPlan
from app.modules.satellites.domain.models import Bucket
from app.modules.satellites.planning.satellite_planner_service import (
    SatellitePlannerService,
)
from app.modules.scoring.domain.models import PortfolioContext


@pytest.fixture
def mock_bucket():
    """Create a mock satellite bucket."""
    return Bucket(
        id="sat-test",
        name="Test Satellite",
        type="satellite",
        status="active",
        target_allocation_pct=0.05,
        is_trading_allowed=True,
        high_water_mark=1000.0,
        current_value=800.0,
        balance_eur=200.0,
        created_at="2025-01-01T00:00:00",
        updated_at="2025-01-01T00:00:00",
    )


@pytest.fixture
def mock_bucket_settings():
    """Create mock bucket settings."""
    # Return a mock object instead of BucketSettings model
    return MagicMock(
        id="settings-1",
        bucket_id="sat-test",
        position_size_min=0.02,
        position_size_max=0.10,
        max_positions=5,
        hibernation_threshold=0.30,
        reawakening_threshold=0.80,
        aggression_base=0.50,
    )


@pytest.fixture
def mock_planner_config():
    """Create a mock planner configuration."""
    config = MagicMock(spec=PlannerConfiguration)
    config.name = "Test Planner Config"
    config.description = "Test configuration for satellite"
    config.max_depth = 3
    config.priority_threshold = 0.3
    config.transaction_cost_fixed = 2.0
    config.transaction_cost_percent = 0.002
    config.allow_buy = True
    config.allow_sell = True
    config.max_opportunities_per_category = 20
    config.get_enabled_calculators.return_value = ["momentum", "value"]
    config.get_enabled_patterns.return_value = ["single_buy"]
    config.get_enabled_generators.return_value = []
    config.get_enabled_filters.return_value = []
    config.get_calculator_params.return_value = {}
    config.get_pattern_params.return_value = {}
    return config


@pytest.fixture
def mock_factory(mock_planner_config):
    """Create a mock ModularPlannerFactory."""
    factory = MagicMock(spec=ModularPlannerFactory)
    factory.config = mock_planner_config
    factory.get_calculators.return_value = []
    factory.get_patterns.return_value = []
    factory.get_generators.return_value = []
    factory.get_filters.return_value = []
    return factory


@pytest.fixture
def mock_portfolio_context():
    """Create a mock portfolio context."""
    return PortfolioContext(
        total_value=10000.0,
        total_cash=1000.0,
        invested_value=9000.0,
        country_allocations={"US": 0.6, "EU": 0.4},
        sector_allocations={},
        security_scores={},
    )


@pytest.fixture
def empty_holistic_plan():
    """Create an empty holistic plan."""
    return HolisticPlan(
        steps=[],
        current_score=0.75,
        end_state_score=0.75,
        improvement=0.0,
        narrative_summary="No actions needed",
        score_breakdown={},
        cash_required=0.0,
        cash_generated=0.0,
        feasible=True,
    )


@pytest.mark.asyncio
async def test_uses_custom_planner_when_config_exists(
    mock_bucket,
    mock_bucket_settings,
    mock_factory,
    mock_portfolio_context,
    empty_holistic_plan,
):
    """Test that custom planner configuration is used when available."""
    service = SatellitePlannerService()

    # Mock dependencies
    with (
        patch.object(service.bucket_service, "get_bucket", return_value=mock_bucket),
        patch.object(
            service.bucket_service, "get_settings", return_value=mock_bucket_settings
        ),
        patch.object(service.balance_service, "get_all_balances", return_value=[]),
        patch(
            "app.modules.satellites.planning.satellite_planner_service.get_planner_loader"
        ) as mock_get_loader,
        patch(
            "app.modules.satellites.planning.satellite_planner_service.HolisticPlanner"
        ) as mock_holistic_planner_class,
        patch(
            "app.modules.satellites.planning.satellite_planner_service.create_holistic_plan"
        ) as mock_create_holistic_plan,
    ):
        # Setup planner loader to return factory with config
        mock_loader = AsyncMock()
        mock_loader.load_planner_for_bucket.return_value = mock_factory
        mock_get_loader.return_value = mock_loader

        # Setup modular planner to return empty plan
        mock_planner_instance = AsyncMock()
        mock_planner_instance.create_plan.return_value = empty_holistic_plan
        mock_holistic_planner_class.return_value = mock_planner_instance

        # Generate plan
        await service.generate_plan_for_bucket(
            bucket_id="sat-test",
            positions=[],
            all_securities=[],
            portfolio_context=mock_portfolio_context,
            current_prices={},
        )

        # Verify custom planner was used
        mock_loader.load_planner_for_bucket.assert_called_once_with("sat-test")
        mock_holistic_planner_class.assert_called_once()
        mock_planner_instance.create_plan.assert_called_once()

        # Verify fallback was NOT used
        mock_create_holistic_plan.assert_not_called()


@pytest.mark.asyncio
async def test_fallback_when_no_custom_config(
    mock_bucket,
    mock_bucket_settings,
    mock_portfolio_context,
    empty_holistic_plan,
):
    """Test that default planner is used when no custom config exists."""
    service = SatellitePlannerService()

    # Mock dependencies
    with (
        patch.object(service.bucket_service, "get_bucket", return_value=mock_bucket),
        patch.object(
            service.bucket_service, "get_settings", return_value=mock_bucket_settings
        ),
        patch.object(service.balance_service, "get_all_balances", return_value=[]),
        patch(
            "app.modules.satellites.planning.satellite_planner_service.get_planner_loader"
        ) as mock_get_loader,
        patch(
            "app.modules.satellites.planning.satellite_planner_service.HolisticPlanner"
        ) as mock_holistic_planner_class,
        patch(
            "app.modules.satellites.planning.satellite_planner_service.create_holistic_plan",
            return_value=empty_holistic_plan,
        ) as mock_create_holistic_plan,
    ):
        # Setup planner loader to return None (no config found)
        mock_loader = AsyncMock()
        mock_loader.load_planner_for_bucket.return_value = None
        mock_get_loader.return_value = mock_loader

        # Generate plan
        await service.generate_plan_for_bucket(
            bucket_id="sat-test",
            positions=[],
            all_securities=[],
            portfolio_context=mock_portfolio_context,
            current_prices={},
        )

        # Verify loader was called
        mock_loader.load_planner_for_bucket.assert_called_once_with("sat-test")

        # Verify fallback planner WAS used
        mock_create_holistic_plan.assert_called_once()

        # Verify custom planner was NOT used
        mock_holistic_planner_class.assert_not_called()


@pytest.mark.asyncio
async def test_fallback_when_factory_has_no_config(
    mock_bucket,
    mock_bucket_settings,
    mock_portfolio_context,
    empty_holistic_plan,
):
    """Test fallback when factory exists but has no config."""
    service = SatellitePlannerService()

    # Create factory with no config
    mock_factory_no_config = MagicMock(spec=ModularPlannerFactory)
    mock_factory_no_config.config = None

    # Mock dependencies
    with (
        patch.object(service.bucket_service, "get_bucket", return_value=mock_bucket),
        patch.object(
            service.bucket_service, "get_settings", return_value=mock_bucket_settings
        ),
        patch.object(service.balance_service, "get_all_balances", return_value=[]),
        patch(
            "app.modules.satellites.planning.satellite_planner_service.get_planner_loader"
        ) as mock_get_loader,
        patch(
            "app.modules.satellites.planning.satellite_planner_service.HolisticPlanner"
        ) as mock_holistic_planner_class,
        patch(
            "app.modules.satellites.planning.satellite_planner_service.create_holistic_plan",
            return_value=empty_holistic_plan,
        ) as mock_create_holistic_plan,
    ):
        # Setup planner loader to return factory without config
        mock_loader = AsyncMock()
        mock_loader.load_planner_for_bucket.return_value = mock_factory_no_config
        mock_get_loader.return_value = mock_loader

        # Generate plan
        await service.generate_plan_for_bucket(
            bucket_id="sat-test",
            positions=[],
            all_securities=[],
            portfolio_context=mock_portfolio_context,
            current_prices={},
        )

        # Verify fallback was used (factory exists but no config)
        mock_create_holistic_plan.assert_called_once()
        mock_holistic_planner_class.assert_not_called()


@pytest.mark.asyncio
async def test_custom_config_receives_correct_parameters(
    mock_bucket,
    mock_bucket_settings,
    mock_factory,
    mock_portfolio_context,
    empty_holistic_plan,
):
    """Test that custom planner receives correct parameters."""
    service = SatellitePlannerService()

    test_securities = [
        Security(
            symbol="AAPL",
            name="Apple Inc.",
            isin="US0378331005",
            currency="USD",
            exchange="NASDAQ",
            security_type="stock",
            bucket_id="sat-test",
        )
    ]

    test_positions = [
        Position(
            symbol="AAPL",
            quantity=10,
            average_cost=150.0,
            current_price=160.0,
            market_value_eur=1600.0,
        )
    ]

    test_prices = {"AAPL": 160.0}

    # Mock dependencies
    with (
        patch.object(service.bucket_service, "get_bucket", return_value=mock_bucket),
        patch.object(
            service.bucket_service, "get_settings", return_value=mock_bucket_settings
        ),
        patch.object(service.balance_service, "get_all_balances", return_value=[]),
        patch(
            "app.modules.satellites.planning.satellite_planner_service.get_planner_loader"
        ) as mock_get_loader,
        patch(
            "app.modules.satellites.planning.satellite_planner_service.HolisticPlanner"
        ) as mock_holistic_planner_class,
    ):
        # Setup planner loader
        mock_loader = AsyncMock()
        mock_loader.load_planner_for_bucket.return_value = mock_factory
        mock_get_loader.return_value = mock_loader

        # Setup modular planner
        mock_planner_instance = AsyncMock()
        mock_planner_instance.create_plan.return_value = empty_holistic_plan
        mock_holistic_planner_class.return_value = mock_planner_instance

        # Generate plan
        await service.generate_plan_for_bucket(
            bucket_id="sat-test",
            positions=test_positions,
            all_securities=test_securities,
            portfolio_context=mock_portfolio_context,
            current_prices=test_prices,
            transaction_cost_fixed=2.5,
            transaction_cost_percent=0.003,
        )

        # Verify HolisticPlanner.create_plan was called with correct parameters
        call_kwargs = mock_planner_instance.create_plan.call_args.kwargs

        assert call_kwargs["portfolio_context"] == mock_portfolio_context
        assert call_kwargs["positions"] == test_positions
        assert call_kwargs["securities"] == test_securities
        assert call_kwargs["available_cash"] >= 0  # Calculated from balances
        assert call_kwargs["current_prices"] == test_prices
