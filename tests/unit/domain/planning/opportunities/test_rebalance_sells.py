"""Tests for rebalance sell opportunity identification.

These tests validate the rebalance sell opportunity logic.
"""

from unittest.mock import AsyncMock

import pytest

from app.domain.models import Position, Security
from app.modules.planning.domain.opportunities.rebalance_sells import (
    identify_rebalance_sell_opportunities,
)
from app.modules.scoring.domain.models import PortfolioContext


class TestIdentifyRebalanceSellOpportunities:
    """Test identify_rebalance_sell_opportunities function."""

    @pytest.fixture
    def sample_position(self):
        """Create a sample position."""
        return Position(
            symbol="AAPL.US",
            quantity=100,
            avg_price=150.0,
            current_price=160.0,
            market_value_eur=16000.0,
            currency="USD",
        )

    @pytest.fixture
    def sample_stock(self):
        """Create a sample stock."""
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
        """Create a portfolio context."""
        return PortfolioContext(
            country_weights={
                "OTHER": 0.0
            },  # Neutral weight (country maps to OTHER group if no mapping)
            industry_weights={},
            positions={"AAPL.US": 16000},
            total_value=20000,
            country_to_group={},  # Empty mapping means countries default to OTHER
        )

    @pytest.mark.asyncio
    async def test_identifies_overweight_country(
        self, sample_position, sample_stock, portfolio_context
    ):
        """Test identifying overweight country position."""
        stocks_by_symbol = {"AAPL.US": sample_stock}
        # country_allocations uses group names, not country names
        # Since country_to_group is empty, "United States" maps to "OTHER"
        country_allocations = {"OTHER": 0.80}  # 80% in OTHER group, target is 0%

        opportunities = await identify_rebalance_sell_opportunities(
            positions=[sample_position],
            stocks_by_symbol=stocks_by_symbol,
            portfolio_context=portfolio_context,
            country_allocations=country_allocations,
            total_value=20000,
        )

        assert len(opportunities) == 1
        assert opportunities[0].symbol == "AAPL.US"
        assert "Overweight" in opportunities[0].reason

    @pytest.mark.asyncio
    async def test_skips_stock_not_allowed_to_sell(self, sample_position):
        """Test skipping stocks not allowed to sell."""
        stock = Security(
            symbol="AAPL.US",
            name="Apple Inc",
            min_lot=1,
            allow_buy=True,
            allow_sell=False,
            currency="USD",
            country="United States",
        )
        portfolio_context = PortfolioContext(
            country_weights={"OTHER": 0.0},
            industry_weights={},
            positions={},
            total_value=20000,
            country_to_group={},
        )
        stocks_by_symbol = {"AAPL.US": stock}
        country_allocations = {"OTHER": 0.80}

        opportunities = await identify_rebalance_sell_opportunities(
            positions=[sample_position],
            stocks_by_symbol=stocks_by_symbol,
            portfolio_context=portfolio_context,
            country_allocations=country_allocations,
            total_value=20000,
        )

        assert len(opportunities) == 0

    @pytest.mark.asyncio
    async def test_skips_zero_value_position(self, sample_stock, portfolio_context):
        """Test skipping positions with zero market value."""
        position = Position(
            symbol="AAPL.US",
            quantity=0,
            avg_price=150.0,
            current_price=160.0,
            market_value_eur=0.0,
            currency="USD",
        )
        stocks_by_symbol = {"AAPL.US": sample_stock}
        country_allocations = {"OTHER": 0.80}

        opportunities = await identify_rebalance_sell_opportunities(
            positions=[position],
            stocks_by_symbol=stocks_by_symbol,
            portfolio_context=portfolio_context,
            country_allocations=country_allocations,
            total_value=20000,
        )

        assert len(opportunities) == 0

    @pytest.mark.asyncio
    async def test_skips_unknown_stock(self, sample_position, portfolio_context):
        """Test skipping positions for unknown stocks."""
        stocks_by_symbol = {}  # No stock info
        country_allocations = {"United States": 0.80}

        opportunities = await identify_rebalance_sell_opportunities(
            positions=[sample_position],
            stocks_by_symbol=stocks_by_symbol,
            portfolio_context=portfolio_context,
            country_allocations=country_allocations,
            total_value=20000,
        )

        assert len(opportunities) == 0

    @pytest.mark.asyncio
    async def test_skips_country_not_in_allocations(
        self, sample_position, sample_stock, portfolio_context
    ):
        """Test skipping when country not in allocations."""
        stocks_by_symbol = {"AAPL.US": sample_stock}
        country_allocations = {"EU": 0.50}  # No OTHER in allocations

        opportunities = await identify_rebalance_sell_opportunities(
            positions=[sample_position],
            stocks_by_symbol=stocks_by_symbol,
            portfolio_context=portfolio_context,
            country_allocations=country_allocations,
            total_value=20000,
        )

        assert len(opportunities) == 0

    @pytest.mark.asyncio
    async def test_skips_balanced_country(
        self, sample_position, sample_stock, portfolio_context
    ):
        """Test skipping when country is balanced."""
        stocks_by_symbol = {"AAPL.US": sample_stock}
        country_allocations = {
            "OTHER": 0.35
        }  # Near target of 0.33 (but portfolio_context has 0.0, so this is still overweight by 0.35)

        opportunities = await identify_rebalance_sell_opportunities(
            positions=[sample_position],
            stocks_by_symbol=stocks_by_symbol,
            portfolio_context=portfolio_context,
            country_allocations=country_allocations,
            total_value=20000,
        )

        assert len(opportunities) == 0

    @pytest.mark.asyncio
    async def test_uses_exchange_rate_service(
        self, sample_position, sample_stock, portfolio_context
    ):
        """Test using exchange rate service for non-EUR positions."""
        stocks_by_symbol = {"AAPL.US": sample_stock}
        country_allocations = {"OTHER": 0.80}

        mock_exchange_service = AsyncMock()
        mock_exchange_service.get_rate.return_value = 1.1

        opportunities = await identify_rebalance_sell_opportunities(
            positions=[sample_position],
            stocks_by_symbol=stocks_by_symbol,
            portfolio_context=portfolio_context,
            country_allocations=country_allocations,
            total_value=20000,
            exchange_rate_service=mock_exchange_service,
        )

        assert len(opportunities) == 1
        mock_exchange_service.get_rate.assert_called_once_with("USD", "EUR")

    @pytest.mark.asyncio
    async def test_includes_tags(
        self, sample_position, sample_stock, portfolio_context
    ):
        """Test that opportunities include appropriate tags."""
        stocks_by_symbol = {"AAPL.US": sample_stock}
        country_allocations = {"OTHER": 0.80}

        opportunities = await identify_rebalance_sell_opportunities(
            positions=[sample_position],
            stocks_by_symbol=stocks_by_symbol,
            portfolio_context=portfolio_context,
            country_allocations=country_allocations,
            total_value=20000,
        )

        assert len(opportunities) == 1
        assert "rebalance" in opportunities[0].tags
        assert "overweight_united states" in opportunities[0].tags

    @pytest.mark.asyncio
    async def test_priority_proportional_to_overweight(
        self, sample_position, sample_stock, portfolio_context
    ):
        """Test that priority is proportional to overweight amount."""
        stocks_by_symbol = {"AAPL.US": sample_stock}
        country_allocations = {"OTHER": 0.90}  # Very overweight

        opportunities = await identify_rebalance_sell_opportunities(
            positions=[sample_position],
            stocks_by_symbol=stocks_by_symbol,
            portfolio_context=portfolio_context,
            country_allocations=country_allocations,
            total_value=20000,
        )

        assert len(opportunities) == 1
        # Priority should be high due to large overweight
        assert opportunities[0].priority > 0.5
