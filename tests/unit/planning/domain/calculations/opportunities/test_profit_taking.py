"""Unit tests for profit-taking opportunity calculator."""

from unittest.mock import AsyncMock, patch

import pytest

from app.domain.models import Position, Security
from app.domain.value_objects.product_type import ProductType
from app.domain.value_objects.trade_side import TradeSide
from app.modules.planning.domain.calculations.opportunities.base import (
    OpportunityContext,
)
from app.modules.planning.domain.calculations.opportunities.profit_taking import (
    ProfitTakingCalculator,
)


@pytest.fixture
def mock_exchange_rate_service():
    """Mock exchange rate service."""
    service = AsyncMock()
    service.get_rate = AsyncMock(return_value=1.1)
    return service


@pytest.fixture
def basic_security():
    """Create a basic security for testing."""
    return Security(
        symbol="AAPL",
        name="Apple Inc.",
        product_type=ProductType.EQUITY,
        currency="USD",
        allow_buy=True,
        allow_sell=True,
        priority_multiplier=1.0,
        min_lot=1,
    )


@pytest.fixture
def basic_position():
    """Create a basic position for testing."""
    return Position(
        symbol="AAPL",
        quantity=100,
        avg_price=150.0,
        current_price=200.0,
        market_value_eur=18181.82,
        currency="USD",
        first_bought_at="2024-01-01",
    )


class TestProfitTakingCalculator:
    """Test ProfitTakingCalculator class."""

    def test_name_property(self):
        """Test that calculator has correct name."""
        calculator = ProfitTakingCalculator()
        assert calculator.name == "profit_taking"

    def test_default_params(self):
        """Test default parameters structure."""
        calculator = ProfitTakingCalculator()
        params = calculator.default_params()

        assert isinstance(params, dict)
        assert "windfall_threshold" in params
        assert "priority_weight" in params
        assert params["windfall_threshold"] == 0.30
        assert params["priority_weight"] == 1.2

    @pytest.mark.asyncio
    async def test_calculate_with_empty_context(self):
        """Test calculator with empty context returns no opportunities."""
        calculator = ProfitTakingCalculator()
        context = OpportunityContext(
            positions=[],
            securities=[],
            stocks_by_symbol={},
            available_cash_eur=0.0,
            total_portfolio_value_eur=0.0,
        )

        opportunities = await calculator.calculate(context, calculator.default_params())
        assert opportunities == []

    @pytest.mark.asyncio
    async def test_calculate_skips_position_without_security(self, basic_position):
        """Test that positions without matching security are skipped."""
        calculator = ProfitTakingCalculator()
        context = OpportunityContext(
            positions=[basic_position],
            securities=[],
            stocks_by_symbol={},  # No matching security
            available_cash_eur=10000.0,
            total_portfolio_value_eur=50000.0,
        )

        opportunities = await calculator.calculate(context, calculator.default_params())
        assert opportunities == []

    @pytest.mark.asyncio
    async def test_calculate_skips_position_when_sell_not_allowed(
        self, basic_position, basic_security
    ):
        """Test that positions are skipped when security doesn't allow sell."""
        basic_security.allow_sell = False

        calculator = ProfitTakingCalculator()
        context = OpportunityContext(
            positions=[basic_position],
            securities=[basic_security],
            stocks_by_symbol={"AAPL": basic_security},
            available_cash_eur=10000.0,
            total_portfolio_value_eur=50000.0,
        )

        opportunities = await calculator.calculate(context, calculator.default_params())
        assert opportunities == []

    @pytest.mark.asyncio
    async def test_calculate_skips_position_with_zero_value(self, basic_security):
        """Test that positions with zero or negative value are skipped."""
        zero_value_position = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=150.0,
            current_price=0.0,
            market_value_eur=0.0,
            currency="USD",
        )

        calculator = ProfitTakingCalculator()
        context = OpportunityContext(
            positions=[zero_value_position],
            securities=[basic_security],
            stocks_by_symbol={"AAPL": basic_security},
            available_cash_eur=10000.0,
            total_portfolio_value_eur=50000.0,
        )

        opportunities = await calculator.calculate(context, calculator.default_params())
        assert opportunities == []

    @pytest.mark.asyncio
    @patch(
        "app.modules.planning.domain.calculations.opportunities.profit_taking.get_windfall_recommendation"
    )
    async def test_calculate_creates_opportunity_for_windfall_position(
        self,
        mock_windfall,
        basic_position,
        basic_security,
        mock_exchange_rate_service,
    ):
        """Test that windfall position creates sell opportunity."""
        # Mock windfall recommendation
        mock_windfall.return_value = {
            "recommendation": {
                "take_profits": True,
                "suggested_sell_pct": 25.0,
                "reason": "Strong windfall gain of 33%",
            },
            "windfall_score": 0.6,
        }

        calculator = ProfitTakingCalculator(
            exchange_rate_service=mock_exchange_rate_service
        )
        context = OpportunityContext(
            positions=[basic_position],
            securities=[basic_security],
            stocks_by_symbol={"AAPL": basic_security},
            available_cash_eur=10000.0,
            total_portfolio_value_eur=50000.0,
        )

        opportunities = await calculator.calculate(context, calculator.default_params())

        assert len(opportunities) == 1
        opp = opportunities[0]

        # Verify opportunity structure
        assert opp.side == TradeSide.SELL
        assert opp.symbol == "AAPL"
        assert opp.name == "Apple Inc."
        assert opp.quantity == 25  # 25% of 100
        assert opp.price == 200.0
        assert opp.currency == "USD"
        assert "windfall" in opp.tags
        assert "profit_taking" in opp.tags
        assert "Strong windfall gain" in opp.reason

        # Verify priority calculation
        # base = 0.6 + 0.5 = 1.1, multiplier = 1.2, security = 1.0
        # final = (1.1 * 1.2) / 1.0 = 1.32
        assert opp.priority == pytest.approx(1.32, rel=0.01)

    @pytest.mark.asyncio
    @patch(
        "app.modules.planning.domain.calculations.opportunities.profit_taking.get_windfall_recommendation"
    )
    async def test_calculate_skips_position_without_windfall(
        self, mock_windfall, basic_position, basic_security
    ):
        """Test that positions without windfall are skipped."""
        # Mock windfall recommendation - no profit taking
        mock_windfall.return_value = {
            "recommendation": {
                "take_profits": False,
                "suggested_sell_pct": 0.0,
                "reason": "No windfall detected",
            },
            "windfall_score": 0.0,
        }

        calculator = ProfitTakingCalculator()
        context = OpportunityContext(
            positions=[basic_position],
            securities=[basic_security],
            stocks_by_symbol={"AAPL": basic_security},
            available_cash_eur=10000.0,
            total_portfolio_value_eur=50000.0,
        )

        opportunities = await calculator.calculate(context, calculator.default_params())
        assert len(opportunities) == 0

    @pytest.mark.asyncio
    @patch(
        "app.modules.planning.domain.calculations.opportunities.profit_taking.get_windfall_recommendation"
    )
    async def test_calculate_respects_priority_weight_param(
        self, mock_windfall, basic_position, basic_security
    ):
        """Test that priority_weight parameter affects final priority."""
        mock_windfall.return_value = {
            "recommendation": {
                "take_profits": True,
                "suggested_sell_pct": 25.0,
                "reason": "Windfall gain",
            },
            "windfall_score": 0.5,
        }

        calculator = ProfitTakingCalculator()
        context = OpportunityContext(
            positions=[basic_position],
            securities=[basic_security],
            stocks_by_symbol={"AAPL": basic_security},
            available_cash_eur=10000.0,
            total_portfolio_value_eur=50000.0,
        )

        # Test with custom priority_weight
        params = {"priority_weight": 2.0, "windfall_threshold": 0.30}
        opportunities = await calculator.calculate(context, params)

        assert len(opportunities) == 1
        # base = 0.5 + 0.5 = 1.0, multiplier = 2.0, security = 1.0
        # final = (1.0 * 2.0) / 1.0 = 2.0
        assert opportunities[0].priority == pytest.approx(2.0, rel=0.01)

    @pytest.mark.asyncio
    @patch(
        "app.modules.planning.domain.calculations.opportunities.profit_taking.get_windfall_recommendation"
    )
    async def test_calculate_respects_security_priority_multiplier(
        self, mock_windfall, basic_position, basic_security
    ):
        """Test that security priority_multiplier affects final priority."""
        mock_windfall.return_value = {
            "recommendation": {
                "take_profits": True,
                "suggested_sell_pct": 25.0,
                "reason": "Windfall gain",
            },
            "windfall_score": 0.5,
        }

        # Set security priority multiplier
        basic_security.priority_multiplier = 2.0

        calculator = ProfitTakingCalculator()
        context = OpportunityContext(
            positions=[basic_position],
            securities=[basic_security],
            stocks_by_symbol={"AAPL": basic_security},
            available_cash_eur=10000.0,
            total_portfolio_value_eur=50000.0,
        )

        opportunities = await calculator.calculate(context, calculator.default_params())

        assert len(opportunities) == 1
        # base = 0.5 + 0.5 = 1.0, multiplier = 1.2, security = 2.0
        # final = (1.0 * 1.2) / 2.0 = 0.6
        assert opportunities[0].priority == pytest.approx(0.6, rel=0.01)

    @pytest.mark.asyncio
    @patch(
        "app.modules.planning.domain.calculations.opportunities.profit_taking.get_windfall_recommendation"
    )
    async def test_calculate_handles_eur_currency_without_exchange_service(
        self, mock_windfall, basic_security
    ):
        """Test that EUR currency works without exchange rate service."""
        eur_position = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=150.0,
            current_price=200.0,
            market_value_eur=20000.0,
            currency="EUR",
        )

        mock_windfall.return_value = {
            "recommendation": {
                "take_profits": True,
                "suggested_sell_pct": 25.0,
                "reason": "Windfall gain",
            },
            "windfall_score": 0.5,
        }

        calculator = ProfitTakingCalculator()  # No exchange service
        context = OpportunityContext(
            positions=[eur_position],
            securities=[basic_security],
            stocks_by_symbol={"AAPL": basic_security},
            available_cash_eur=10000.0,
            total_portfolio_value_eur=50000.0,
        )

        opportunities = await calculator.calculate(context, calculator.default_params())

        assert len(opportunities) == 1
        # Should use 1.0 exchange rate for EUR
        # 25 * 200.0 / 1.0 = 5000.0
        assert opportunities[0].value_eur == pytest.approx(5000.0, rel=0.01)

    @pytest.mark.asyncio
    @patch(
        "app.modules.planning.domain.calculations.opportunities.profit_taking.get_windfall_recommendation"
    )
    async def test_calculate_handles_missing_current_price(
        self, mock_windfall, basic_security
    ):
        """Test that missing current_price falls back to avg_price."""
        position_no_current = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=150.0,
            current_price=None,
            market_value_eur=15000.0,
            currency="EUR",
        )

        mock_windfall.return_value = {
            "recommendation": {
                "take_profits": True,
                "suggested_sell_pct": 25.0,
                "reason": "Windfall gain",
            },
            "windfall_score": 0.5,
        }

        calculator = ProfitTakingCalculator()
        context = OpportunityContext(
            positions=[position_no_current],
            securities=[basic_security],
            stocks_by_symbol={"AAPL": basic_security},
            available_cash_eur=10000.0,
            total_portfolio_value_eur=50000.0,
        )

        opportunities = await calculator.calculate(context, calculator.default_params())

        assert len(opportunities) == 1
        # Should use avg_price when current_price is None
        assert opportunities[0].price == 150.0

    def test_repr(self):
        """Test __repr__ method."""
        calculator = ProfitTakingCalculator()
        repr_str = repr(calculator)

        assert "ProfitTakingCalculator" in repr_str
        assert "profit_taking" in repr_str
