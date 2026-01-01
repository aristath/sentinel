"""Integration tests for modular planner feature parity.

Compares modular planner outputs with the original holistic_planner
to ensure identical behavior.
"""

import pytest

from app.domain.models import Position, Security
from app.domain.value_objects.product_type import ProductType
from app.modules.planning.domain.config.models import PlannerConfiguration
from app.modules.planning.domain.planner import HolisticPlanner
from app.modules.planning.domain.planner_adapter import create_holistic_plan_modular
from app.modules.scoring.domain.models import PortfolioContext
from app.repositories import SettingsRepository, TradeRepository


@pytest.fixture
def sample_portfolio_context():
    """Create a sample portfolio context for testing."""
    return PortfolioContext(
        country_weights={"USA": 0.6, "Germany": 0.3, "Japan": 0.1},
        industry_weights={"Technology": 0.4, "Healthcare": 0.3, "Finance": 0.3},
        positions={
            "AAPL": 5000.0,
            "MSFT": 4000.0,
            "JNJ": 3000.0,
        },
        total_value=12000.0,
        security_countries={
            "AAPL": "USA",
            "MSFT": "USA",
            "JNJ": "USA",
        },
        security_industries={
            "AAPL": "Technology",
            "MSFT": "Technology",
            "JNJ": "Healthcare",
        },
        security_scores={
            "AAPL": 0.85,
            "MSFT": 0.80,
            "JNJ": 0.75,
        },
        security_dividends={},
    )


@pytest.fixture
def sample_positions():
    """Create sample positions for testing."""
    from app.shared.domain.value_objects.currency import Currency

    return [
        Position(
            symbol="AAPL",
            quantity=50,
            avg_price=100.0,
            currency=Currency.USD,
            currency_rate=1.0,
        ),
        Position(
            symbol="MSFT",
            quantity=40,
            avg_price=100.0,
            currency=Currency.USD,
            currency_rate=1.0,
        ),
        Position(
            symbol="JNJ",
            quantity=30,
            avg_price=100.0,
            currency=Currency.USD,
            currency_rate=1.0,
        ),
    ]


@pytest.fixture
def sample_securities():
    """Create sample securities for testing."""
    return [
        Security(
            symbol="AAPL",
            name="Apple Inc.",
            product_type=ProductType.EQUITY,
            country="USA",
            industry="Technology",
            currency="USD",
            yahoo_symbol="AAPL",
            active=True,
        ),
        Security(
            symbol="MSFT",
            name="Microsoft Corp.",
            product_type=ProductType.EQUITY,
            country="USA",
            industry="Technology",
            currency="USD",
            yahoo_symbol="MSFT",
            active=True,
        ),
        Security(
            symbol="JNJ",
            name="Johnson & Johnson",
            product_type=ProductType.EQUITY,
            country="USA",
            industry="Healthcare",
            currency="USD",
            yahoo_symbol="JNJ",
            active=True,
        ),
        Security(
            symbol="SAP",
            name="SAP SE",
            product_type=ProductType.EQUITY,
            country="Germany",
            industry="Technology",
            currency="EUR",
            yahoo_symbol="SAP",
            active=True,
        ),
    ]


@pytest.mark.asyncio
async def test_modular_planner_basic_execution(
    sample_portfolio_context, sample_positions, sample_securities, db_manager
):
    """Test that modular planner executes without errors."""
    config = PlannerConfiguration(
        name="test_config",
        description="Test configuration",
        max_depth=2,
        max_opportunities_per_category=3,
        priority_threshold=0.5,
    )

    planner = HolisticPlanner(
        config=config,
        settings_repo=SettingsRepository(),
        trade_repo=TradeRepository(),
    )

    plan = await planner.create_plan(
        portfolio_context=sample_portfolio_context,
        positions=sample_positions,
        securities=sample_securities,
        available_cash=1000.0,
        current_prices={"AAPL": 150.0, "MSFT": 250.0, "JNJ": 160.0, "SAP": 120.0},
    )

    assert plan is not None
    assert hasattr(plan, "steps")
    assert hasattr(plan, "end_state_score")
    assert hasattr(plan, "current_score")


@pytest.mark.asyncio
async def test_modular_adapter_execution(
    sample_portfolio_context, sample_positions, sample_securities, db_manager
):
    """Test that modular adapter executes without errors."""
    plan = await create_holistic_plan_modular(
        portfolio_context=sample_portfolio_context,
        available_cash=1000.0,
        securities=sample_securities,
        positions=sample_positions,
        current_prices={"AAPL": 150.0, "MSFT": 250.0, "JNJ": 160.0, "SAP": 120.0},
        max_plan_depth=2,
        max_opportunities_per_category=3,
    )

    assert plan is not None
    assert hasattr(plan, "steps")
    assert hasattr(plan, "end_state_score")
    assert hasattr(plan, "current_score")


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires full feature parity implementation")
async def test_modular_vs_monolithic_identical_output(
    sample_portfolio_context, sample_positions, sample_securities
):
    """
    Test that modular planner produces identical output to monolithic planner.

    This test is currently skipped because:
    1. Full feature parity requires all modules to be used
    2. Deterministic output requires identical RNG seeds and ordering
    3. Some advanced features may not be implemented yet

    TODO: Enable this test once:
    - All modules are fully integrated
    - Deterministic seed support is added
    - Feature parity is validated
    """
    from app.modules.planning.domain.holistic_planner import create_holistic_plan

    # Run monolithic planner
    monolithic_plan = await create_holistic_plan(
        portfolio_context=sample_portfolio_context,
        available_cash=1000.0,
        securities=sample_securities,
        positions=sample_positions,
        current_prices={"AAPL": 150.0, "MSFT": 250.0, "JNJ": 160.0, "SAP": 120.0},
        max_plan_depth=2,
        max_opportunities_per_category=3,
        enable_combinatorial=False,  # Disable for deterministic comparison
    )

    # Run modular planner
    modular_plan = await create_holistic_plan_modular(
        portfolio_context=sample_portfolio_context,
        available_cash=1000.0,
        securities=sample_securities,
        positions=sample_positions,
        current_prices={"AAPL": 150.0, "MSFT": 250.0, "JNJ": 160.0, "SAP": 120.0},
        max_plan_depth=2,
        max_opportunities_per_category=3,
        enable_combinatorial=False,
    )

    # Compare outputs
    assert len(monolithic_plan.steps) == len(
        modular_plan.steps
    ), "Plan length should be identical"
    assert (
        abs(monolithic_plan.end_state_score - modular_plan.end_state_score) < 0.01
    ), "End state scores should be nearly identical"

    # Compare each step
    for i, (mono_step, mod_step) in enumerate(
        zip(monolithic_plan.steps, modular_plan.steps)
    ):
        assert mono_step.symbol == mod_step.symbol, f"Step {i}: symbols should match"
        assert mono_step.side == mod_step.side, f"Step {i}: sides should match"
        assert (
            abs(mono_step.quantity - mod_step.quantity) < 0.01
        ), f"Step {i}: quantities should be nearly identical"


@pytest.mark.asyncio
async def test_modular_planner_empty_portfolio(sample_securities, db_manager):
    """Test modular planner with empty portfolio."""
    empty_context = PortfolioContext(
        country_weights={},
        industry_weights={},
        positions={},
        total_value=0.0,
        security_countries={},
        security_industries={},
        security_scores={},
        security_dividends={},
    )

    config = PlannerConfiguration(
        name="test_config",
        max_depth=1,
        max_opportunities_per_category=2,
    )

    planner = HolisticPlanner(
        config=config,
        settings_repo=SettingsRepository(),
        trade_repo=TradeRepository(),
    )

    plan = await planner.create_plan(
        portfolio_context=empty_context,
        positions=[],
        securities=sample_securities,
        available_cash=5000.0,
        current_prices={"AAPL": 150.0, "MSFT": 250.0, "JNJ": 160.0, "SAP": 120.0},
    )

    assert plan is not None
    # With empty portfolio and cash, should identify buy opportunities
    # (assuming opportunity calculators are working)


@pytest.mark.asyncio
async def test_modular_planner_no_cash(
    sample_portfolio_context, sample_positions, sample_securities, db_manager
):
    """Test modular planner with no available cash."""
    config = PlannerConfiguration(
        name="test_config",
        max_depth=2,
        max_opportunities_per_category=3,
    )

    planner = HolisticPlanner(
        config=config,
        settings_repo=SettingsRepository(),
        trade_repo=TradeRepository(),
    )

    plan = await planner.create_plan(
        portfolio_context=sample_portfolio_context,
        positions=sample_positions,
        securities=sample_securities,
        available_cash=0.0,  # No cash
        current_prices={"AAPL": 150.0, "MSFT": 250.0, "JNJ": 160.0, "SAP": 120.0},
    )

    assert plan is not None
    # With no cash, should only identify sell opportunities
    # or sell-then-buy sequences
