"""Unit tests for averaging down opportunity calculator."""

from unittest.mock import AsyncMock

import pytest

from app.domain.models import Position, Security
from app.domain.value_objects.product_type import ProductType
from app.domain.value_objects.trade_side import TradeSide
from app.modules.planning.domain.calculations.opportunities.averaging_down import (
    AveragingDownCalculator,
)
from app.modules.planning.domain.calculations.opportunities.base import (
    OpportunityContext,
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
def down_position():
    """Create a position that is down from avg price."""
    return Position(
        symbol="AAPL",
        quantity=100,
        avg_price=200.0,
        current_price=170.0,  # Down 15%
        market_value_eur=15454.55,
        currency="USD",
    )


class TestAveragingDownCalculator:
    """Test AveragingDownCalculator class."""

    def test_name_property(self):
        """Test that calculator has correct name."""
        calculator = AveragingDownCalculator()
        assert calculator.name == "averaging_down"

    def test_default_params(self):
        """Test default parameters structure."""
        calculator = AveragingDownCalculator()
        params = calculator.default_params()

        assert isinstance(params, dict)
        assert "max_drawdown" in params
        assert "min_quality_score" in params
        assert "priority_weight" in params
        assert "base_trade_amount_eur" in params
        assert params["max_drawdown"] == -0.15
        assert params["min_quality_score"] == 0.6
        assert params["priority_weight"] == 0.9
        assert params["base_trade_amount_eur"] == 1000.0

    @pytest.mark.asyncio
    async def test_calculate_with_empty_context(self):
        """Test calculator with empty context returns no opportunities."""
        calculator = AveragingDownCalculator()
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
    async def test_calculate_skips_security_without_position(self, basic_security):
        """Test that securities not owned are skipped."""
        calculator = AveragingDownCalculator()
        context = OpportunityContext(
            positions=[],  # No positions
            securities=[basic_security],
            stocks_by_symbol={"AAPL": basic_security},
            available_cash_eur=10000.0,
            total_portfolio_value_eur=50000.0,
        )

        opportunities = await calculator.calculate(context, calculator.default_params())
        assert opportunities == []

    @pytest.mark.asyncio
    async def test_calculate_skips_security_when_buy_not_allowed(
        self, down_position, basic_security
    ):
        """Test that securities are skipped when buy not allowed."""
        basic_security.allow_buy = False

        calculator = AveragingDownCalculator()
        context = OpportunityContext(
            positions=[down_position],
            securities=[basic_security],
            stocks_by_symbol={"AAPL": basic_security},
            available_cash_eur=10000.0,
            total_portfolio_value_eur=50000.0,
        )

        opportunities = await calculator.calculate(context, calculator.default_params())
        assert opportunities == []

    @pytest.mark.asyncio
    async def test_calculate_skips_position_that_is_up(self, basic_security):
        """Test that positions up from avg price are skipped."""
        up_position = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=150.0,
            current_price=200.0,  # Up 33%
            market_value_eur=20000.0,
            currency="EUR",
        )

        calculator = AveragingDownCalculator()
        context = OpportunityContext(
            positions=[up_position],
            securities=[basic_security],
            stocks_by_symbol={"AAPL": basic_security},
            available_cash_eur=10000.0,
            total_portfolio_value_eur=50000.0,
        )

        opportunities = await calculator.calculate(context, calculator.default_params())
        assert opportunities == []

    @pytest.mark.asyncio
    async def test_calculate_skips_position_down_too_much(self, basic_security):
        """Test that positions down more than max_drawdown are skipped."""
        severely_down_position = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=200.0,
            current_price=100.0,  # Down 50% (exceeds -15% max)
            market_value_eur=10000.0,
            currency="EUR",
        )

        calculator = AveragingDownCalculator()
        context = OpportunityContext(
            positions=[severely_down_position],
            securities=[basic_security],
            stocks_by_symbol={"AAPL": basic_security},
            available_cash_eur=10000.0,
            total_portfolio_value_eur=50000.0,
        )

        opportunities = await calculator.calculate(context, calculator.default_params())
        assert opportunities == []

    @pytest.mark.asyncio
    async def test_calculate_skips_low_quality_security(
        self, down_position, basic_security
    ):
        """Test that low quality securities are skipped."""
        calculator = AveragingDownCalculator()
        context = OpportunityContext(
            positions=[down_position],
            securities=[basic_security],
            stocks_by_symbol={"AAPL": basic_security},
            available_cash_eur=10000.0,
            total_portfolio_value_eur=50000.0,
            security_scores={"AAPL": 0.3},  # Below min_quality_score of 0.6
        )

        opportunities = await calculator.calculate(context, calculator.default_params())
        assert opportunities == []

    @pytest.mark.asyncio
    async def test_calculate_creates_opportunity_for_quality_dip(
        self, down_position, basic_security, mock_exchange_rate_service
    ):
        """Test that quality position dip creates buy opportunity."""
        calculator = AveragingDownCalculator(
            exchange_rate_service=mock_exchange_rate_service
        )
        context = OpportunityContext(
            positions=[down_position],
            securities=[basic_security],
            stocks_by_symbol={"AAPL": basic_security},
            available_cash_eur=10000.0,
            total_portfolio_value_eur=50000.0,
            security_scores={"AAPL": 0.75},  # High quality
        )

        opportunities = await calculator.calculate(context, calculator.default_params())

        assert len(opportunities) == 1
        opp = opportunities[0]

        # Verify opportunity structure
        assert opp.side == TradeSide.BUY
        assert opp.symbol == "AAPL"
        assert opp.name == "Apple Inc."
        assert opp.quantity > 0
        assert opp.price == 170.0
        assert opp.currency == "USD"
        assert "averaging_down" in opp.tags
        assert "buy_low" in opp.tags
        assert "down 15%" in opp.reason

    @pytest.mark.asyncio
    async def test_calculate_priority_based_on_quality_and_drop(
        self, down_position, basic_security
    ):
        """Test that priority is calculated from quality + drop amount."""
        calculator = AveragingDownCalculator()
        context = OpportunityContext(
            positions=[down_position],
            securities=[basic_security],
            stocks_by_symbol={"AAPL": basic_security},
            available_cash_eur=10000.0,
            total_portfolio_value_eur=50000.0,
            security_scores={"AAPL": 0.7},
        )

        opportunities = await calculator.calculate(context, calculator.default_params())

        assert len(opportunities) == 1
        # base_priority = quality + abs(loss_pct) = 0.7 + 0.15 = 0.85
        # priority_weight = 0.9, security_multiplier = 1.0
        # final = 0.85 * 0.9 * 1.0 = 0.765
        assert opportunities[0].priority == pytest.approx(0.765, rel=0.01)

    @pytest.mark.asyncio
    async def test_calculate_respects_priority_weight_param(
        self, down_position, basic_security
    ):
        """Test that priority_weight parameter affects final priority."""
        calculator = AveragingDownCalculator()
        context = OpportunityContext(
            positions=[down_position],
            securities=[basic_security],
            stocks_by_symbol={"AAPL": basic_security},
            available_cash_eur=10000.0,
            total_portfolio_value_eur=50000.0,
            security_scores={"AAPL": 0.7},
        )

        # Test with custom priority_weight
        params = {
            "max_drawdown": -0.15,
            "min_quality_score": 0.6,
            "priority_weight": 1.5,
            "base_trade_amount_eur": 1000.0,
        }
        opportunities = await calculator.calculate(context, params)

        assert len(opportunities) == 1
        # base = 0.7 + 0.15 = 0.85, weight = 1.5, security = 1.0
        # final = 0.85 * 1.5 * 1.0 = 1.275
        assert opportunities[0].priority == pytest.approx(1.275, rel=0.01)

    @pytest.mark.asyncio
    async def test_calculate_respects_security_priority_multiplier(
        self, down_position, basic_security
    ):
        """Test that security priority_multiplier affects final priority."""
        basic_security.priority_multiplier = 2.0

        calculator = AveragingDownCalculator()
        context = OpportunityContext(
            positions=[down_position],
            securities=[basic_security],
            stocks_by_symbol={"AAPL": basic_security},
            available_cash_eur=10000.0,
            total_portfolio_value_eur=50000.0,
            security_scores={"AAPL": 0.7},
        )

        opportunities = await calculator.calculate(context, calculator.default_params())

        assert len(opportunities) == 1
        # base = 0.7 + 0.15 = 0.85, weight = 0.9, security = 2.0
        # final = 0.85 * 0.9 * 2.0 = 1.53
        assert opportunities[0].priority == pytest.approx(1.53, rel=0.01)

    @pytest.mark.asyncio
    async def test_calculate_uses_default_quality_when_scores_not_provided(
        self, down_position, basic_security
    ):
        """Test that default quality score (0.5) is used when scores not provided."""
        calculator = AveragingDownCalculator()
        context = OpportunityContext(
            positions=[down_position],
            securities=[basic_security],
            stocks_by_symbol={"AAPL": basic_security},
            available_cash_eur=10000.0,
            total_portfolio_value_eur=50000.0,
            # No security_scores provided
        )

        # Lower min_quality_score to allow default 0.5
        params = {
            "max_drawdown": -0.15,
            "min_quality_score": 0.4,
            "priority_weight": 0.9,
            "base_trade_amount_eur": 1000.0,
        }
        opportunities = await calculator.calculate(context, params)

        assert len(opportunities) == 1
        # Should use default quality 0.5
        # base = 0.5 + 0.15 = 0.65, weight = 0.9, security = 1.0
        # final = 0.65 * 0.9 * 1.0 = 0.585
        assert opportunities[0].priority == pytest.approx(0.585, rel=0.01)

    @pytest.mark.asyncio
    async def test_calculate_skips_position_with_zero_current_price(
        self, basic_security
    ):
        """Test that positions with zero current price are skipped."""
        zero_price_position = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=200.0,
            current_price=0.0,
            market_value_eur=0.0,
            currency="EUR",
        )

        calculator = AveragingDownCalculator()
        context = OpportunityContext(
            positions=[zero_price_position],
            securities=[basic_security],
            stocks_by_symbol={"AAPL": basic_security},
            available_cash_eur=10000.0,
            total_portfolio_value_eur=50000.0,
            security_scores={"AAPL": 0.75},
        )

        opportunities = await calculator.calculate(context, calculator.default_params())
        assert opportunities == []

    @pytest.mark.asyncio
    async def test_calculate_respects_base_trade_amount_param(
        self, down_position, basic_security
    ):
        """Test that base_trade_amount_eur parameter affects trade size."""
        calculator = AveragingDownCalculator()
        context = OpportunityContext(
            positions=[down_position],
            securities=[basic_security],
            stocks_by_symbol={"AAPL": basic_security},
            available_cash_eur=10000.0,
            total_portfolio_value_eur=50000.0,
            security_scores={"AAPL": 0.7},
        )

        # Test with larger trade amount
        params = {
            "max_drawdown": -0.15,
            "min_quality_score": 0.6,
            "priority_weight": 0.9,
            "base_trade_amount_eur": 5000.0,  # Larger trade
        }
        opportunities = await calculator.calculate(context, params)

        assert len(opportunities) == 1
        # Trade sizing should reflect larger base amount
        # 5000 EUR should buy more shares than 1000 EUR
        assert opportunities[0].value_eur > 1000.0

    def test_repr(self):
        """Test __repr__ method."""
        calculator = AveragingDownCalculator()
        repr_str = repr(calculator)

        assert "AveragingDownCalculator" in repr_str
        assert "averaging_down" in repr_str
