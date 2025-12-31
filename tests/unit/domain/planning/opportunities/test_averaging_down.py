"""Tests for averaging down opportunity identification.

These tests validate the averaging down opportunity logic.
"""

from unittest.mock import AsyncMock

import pytest

from app.domain.models import Security
from app.modules.planning.domain.opportunities.averaging_down import (
    identify_averaging_down_opportunities,
)
from app.modules.scoring.domain.models import PortfolioContext


class TestIdentifyAveragingDownOpportunities:
    """Test identify_averaging_down_opportunities function."""

    @pytest.fixture
    def sample_stock(self):
        """Create a sample security."""
        return Security(
            symbol="AAPL.US",
            name="Apple Inc",
            min_lot=1,
            allow_buy=True,
            allow_sell=True,
            currency="USD",
            country="United States",
        )

    @pytest.fixture
    def portfolio_context(self):
        """Create a portfolio context with positions."""
        return PortfolioContext(
            country_weights={"US": 0.0},
            industry_weights={},
            positions={"AAPL.US": 5000},
            total_value=10000,
            position_avg_prices={"AAPL.US": 150.0},
            current_prices={"AAPL.US": 110.0},
            security_scores={"AAPL.US": 0.75},
        )

    @pytest.mark.asyncio
    async def test_identifies_quality_dip(self, sample_stock, portfolio_context):
        """Test identifying quality security that is down 20%+."""
        securities = [sample_stock]
        batch_prices = {"AAPL.US": 110.0}  # 26% down from avg of 150

        opportunities = await identify_averaging_down_opportunities(
            securities=securities,
            portfolio_context=portfolio_context,
            batch_prices=batch_prices,
            base_trade_amount=1000,
        )

        assert len(opportunities) == 1
        assert opportunities[0].symbol == "AAPL.US"
        assert "averaging down" in opportunities[0].reason

    @pytest.mark.asyncio
    async def test_skips_stock_not_allowed_to_buy(self, portfolio_context):
        """Test skipping securities that are not allowed to buy."""
        security = Security(
            symbol="AAPL.US",
            name="Apple Inc",
            min_lot=1,
            allow_buy=False,
            allow_sell=True,
            country="United States",
        )
        batch_prices = {"AAPL.US": 110.0}

        opportunities = await identify_averaging_down_opportunities(
            securities=[security],
            portfolio_context=portfolio_context,
            batch_prices=batch_prices,
            base_trade_amount=1000,
        )

        assert len(opportunities) == 0

    @pytest.mark.asyncio
    async def test_skips_stock_without_price(self, sample_stock, portfolio_context):
        """Test skipping securities without price data."""
        batch_prices = {}  # No price

        opportunities = await identify_averaging_down_opportunities(
            securities=[sample_stock],
            portfolio_context=portfolio_context,
            batch_prices=batch_prices,
            base_trade_amount=1000,
        )

        assert len(opportunities) == 0

    @pytest.mark.asyncio
    async def test_skips_low_quality_stock(self, sample_stock):
        """Test skipping low quality securities."""
        portfolio_context = PortfolioContext(
            country_weights={},
            industry_weights={},
            positions={"AAPL.US": 5000},
            total_value=10000,
            position_avg_prices={"AAPL.US": 150.0},
            security_scores={"AAPL.US": 0.4},  # Low quality
        )
        batch_prices = {"AAPL.US": 110.0}

        opportunities = await identify_averaging_down_opportunities(
            securities=[sample_stock],
            portfolio_context=portfolio_context,
            batch_prices=batch_prices,
            base_trade_amount=1000,
        )

        assert len(opportunities) == 0

    @pytest.mark.asyncio
    async def test_skips_stock_not_owned(self, sample_stock):
        """Test skipping securities not currently owned."""
        portfolio_context = PortfolioContext(
            country_weights={},
            industry_weights={},
            positions={},  # No position
            total_value=10000,
            position_avg_prices={},
            security_scores={"AAPL.US": 0.8},
        )
        batch_prices = {"AAPL.US": 110.0}

        opportunities = await identify_averaging_down_opportunities(
            securities=[sample_stock],
            portfolio_context=portfolio_context,
            batch_prices=batch_prices,
            base_trade_amount=1000,
        )

        assert len(opportunities) == 0

    @pytest.mark.asyncio
    async def test_skips_stock_not_down_enough(self, sample_stock):
        """Test skipping securities that aren't down 20%+."""
        portfolio_context = PortfolioContext(
            country_weights={},
            industry_weights={},
            positions={"AAPL.US": 5000},
            total_value=10000,
            position_avg_prices={"AAPL.US": 150.0},
            security_scores={"AAPL.US": 0.8},
        )
        batch_prices = {"AAPL.US": 140.0}  # Only 7% down

        opportunities = await identify_averaging_down_opportunities(
            securities=[sample_stock],
            portfolio_context=portfolio_context,
            batch_prices=batch_prices,
            base_trade_amount=1000,
        )

        assert len(opportunities) == 0

    @pytest.mark.asyncio
    async def test_uses_exchange_rate_service(self, sample_stock, portfolio_context):
        """Test using exchange rate service for non-EUR securities."""
        batch_prices = {"AAPL.US": 110.0}

        mock_exchange_service = AsyncMock()
        mock_exchange_service.get_rate.return_value = 1.1  # 1 USD = 1.1 EUR

        opportunities = await identify_averaging_down_opportunities(
            securities=[sample_stock],
            portfolio_context=portfolio_context,
            batch_prices=batch_prices,
            base_trade_amount=1000,
            exchange_rate_service=mock_exchange_service,
        )

        assert len(opportunities) == 1
        mock_exchange_service.get_rate.assert_called_once_with("USD", "EUR")

    @pytest.mark.asyncio
    async def test_priority_based_on_quality_and_dip(self, sample_stock):
        """Test that priority is based on quality score and dip size."""
        portfolio_context = PortfolioContext(
            country_weights={},
            industry_weights={},
            positions={"AAPL.US": 5000},
            total_value=10000,
            position_avg_prices={"AAPL.US": 150.0},
            security_scores={"AAPL.US": 0.8},
        )
        batch_prices = {"AAPL.US": 100.0}  # 33% down

        opportunities = await identify_averaging_down_opportunities(
            securities=[sample_stock],
            portfolio_context=portfolio_context,
            batch_prices=batch_prices,
            base_trade_amount=1000,
        )

        assert len(opportunities) == 1
        # Priority = quality (0.8) + abs(dip) (0.33) = 1.13
        assert opportunities[0].priority > 1.0

    @pytest.mark.asyncio
    async def test_includes_tags(self, sample_stock, portfolio_context):
        """Test that opportunities include appropriate tags."""
        batch_prices = {"AAPL.US": 110.0}

        opportunities = await identify_averaging_down_opportunities(
            securities=[sample_stock],
            portfolio_context=portfolio_context,
            batch_prices=batch_prices,
            base_trade_amount=1000,
        )

        assert len(opportunities) == 1
        assert "averaging_down" in opportunities[0].tags
        assert "buy_low" in opportunities[0].tags
