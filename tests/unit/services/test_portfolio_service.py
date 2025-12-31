"""Tests for portfolio_service module - validates allocation calculations.

These tests ensure portfolio allocations are calculated correctly.
Wrong allocations could cause the rebalancer to make incorrect decisions.
"""

from unittest.mock import AsyncMock

import pytest

from app.modules.portfolio.services.portfolio_service import PortfolioService


class TestPortfolioServiceCalculations:
    """Tests for portfolio allocation calculations.

    The portfolio service aggregates positions and calculates:
    - Country allocation percentages
    - Industry allocation percentages (with multi-industry splitting)
    - Deviation from targets

    Bug this catches: Wrong allocation calculations would cause
    incorrect rebalancing decisions.
    """

    @pytest.fixture
    def mock_repos(self):
        """Create mock repositories for testing."""
        portfolio_repo = AsyncMock()
        position_repo = AsyncMock()
        allocation_repo = AsyncMock()
        stock_repo = AsyncMock()

        # Default: empty portfolio
        portfolio_repo.get_latest_cash_balance.return_value = 0.0
        position_repo.get_with_stock_info.return_value = []
        allocation_repo.get_all.return_value = {}

        return portfolio_repo, position_repo, allocation_repo, stock_repo

    @pytest.mark.asyncio
    async def test_single_country_100_percent(self, mock_repos):
        """Single country should be 100% of portfolio.

        Bug caught: Division errors or wrong percentage calculation.
        """
        portfolio_repo, position_repo, allocation_repo, stock_repo = mock_repos

        position_repo.get_with_stock_info.return_value = [
            {
                "symbol": "TEST",
                "market_value_eur": 1000,
                "country": "Germany",
                "industry": "Consumer Electronics",
            }
        ]

        service = PortfolioService(
            portfolio_repo, position_repo, allocation_repo, stock_repo
        )
        summary = await service.get_portfolio_summary()

        assert summary.total_value == 1000
        assert len(summary.country_allocations) == 1
        assert summary.country_allocations[0].name == "Germany"
        assert summary.country_allocations[0].current_pct == 1.0

    @pytest.mark.asyncio
    async def test_multiple_countries_split_correctly(self, mock_repos):
        """Multiple countries should split by value.

        Bug caught: Aggregation errors across positions.
        """
        portfolio_repo, position_repo, allocation_repo, stock_repo = mock_repos

        position_repo.get_with_stock_info.return_value = [
            {
                "symbol": "EU1",
                "market_value_eur": 600,
                "country": "Germany",
                "industry": "Consumer Electronics",
            },
            {
                "symbol": "US1",
                "market_value_eur": 400,
                "country": "United States",
                "industry": "Consumer Electronics",
            },
        ]

        service = PortfolioService(
            portfolio_repo, position_repo, allocation_repo, stock_repo
        )
        summary = await service.get_portfolio_summary()

        assert summary.total_value == 1000

        # Find Germany and United States allocations
        country_by_name = {c.name: c for c in summary.country_allocations}

        assert country_by_name["Germany"].current_pct == pytest.approx(0.6, abs=0.01)
        assert country_by_name["United States"].current_pct == pytest.approx(
            0.4, abs=0.01
        )

    @pytest.mark.asyncio
    async def test_multi_industry_splits_value_equally(self, mock_repos):
        """Stock in multiple industries should split value equally.

        A stock with "Technology, Defense" should count 50% to each industry.

        Bug caught: Multi-industry stocks being double-counted or ignored.
        """
        portfolio_repo, position_repo, allocation_repo, stock_repo = mock_repos

        position_repo.get_with_stock_info.return_value = [
            {
                "symbol": "MULTI",
                "market_value_eur": 1000,
                "country": "United States",
                "industry": "Technology, Defense",
            },
        ]

        service = PortfolioService(
            portfolio_repo, position_repo, allocation_repo, stock_repo
        )
        summary = await service.get_portfolio_summary()

        ind_by_name = {i.name: i for i in summary.industry_allocations}

        # Each industry should get 50% of the value
        assert ind_by_name["Technology"].current_value == pytest.approx(500, abs=1)
        assert ind_by_name["Defense"].current_value == pytest.approx(500, abs=1)
        assert ind_by_name["Technology"].current_pct == pytest.approx(0.5, abs=0.01)
        assert ind_by_name["Defense"].current_pct == pytest.approx(0.5, abs=0.01)

    @pytest.mark.asyncio
    async def test_empty_portfolio_returns_zero(self, mock_repos):
        """Empty portfolio should have zero total value.

        Bug caught: Division by zero when portfolio is empty.
        """
        portfolio_repo, position_repo, allocation_repo, stock_repo = mock_repos

        position_repo.get_with_stock_info.return_value = []

        service = PortfolioService(
            portfolio_repo, position_repo, allocation_repo, stock_repo
        )
        summary = await service.get_portfolio_summary()

        assert summary.total_value == 0
        # Should not crash with empty allocations

    @pytest.mark.asyncio
    async def test_missing_country_handled(self, mock_repos):
        """Position with no country should not crash.

        Bug caught: NoneType errors when data is incomplete.
        """
        portfolio_repo, position_repo, allocation_repo, stock_repo = mock_repos

        position_repo.get_with_stock_info.return_value = [
            {
                "symbol": "NO_COUNTRY",
                "market_value_eur": 1000,
                "country": None,
                "industry": "Consumer Electronics",
            },
        ]

        service = PortfolioService(
            portfolio_repo, position_repo, allocation_repo, stock_repo
        )
        summary = await service.get_portfolio_summary()

        # Should have value but no country allocation
        assert summary.total_value == 1000
        # No country allocations since the only position has None

    @pytest.mark.asyncio
    async def test_missing_industry_handled(self, mock_repos):
        """Position with no industry should not crash.

        Bug caught: parse_industries(None) or empty string handling.
        """
        portfolio_repo, position_repo, allocation_repo, stock_repo = mock_repos

        position_repo.get_with_stock_info.return_value = [
            {
                "symbol": "NO_IND",
                "market_value_eur": 1000,
                "country": "Germany",
                "industry": "",
            },
        ]

        service = PortfolioService(
            portfolio_repo, position_repo, allocation_repo, stock_repo
        )
        summary = await service.get_portfolio_summary()

        # Should have value and country but no industry allocation
        assert summary.total_value == 1000
        assert len(summary.country_allocations) > 0

    @pytest.mark.asyncio
    async def test_fallback_to_price_calculation_when_no_eur_value(self, mock_repos):
        """When market_value_eur is missing, should calculate from price.

        Bug caught: Missing EUR value causing zero allocation.
        """
        portfolio_repo, position_repo, allocation_repo, stock_repo = mock_repos

        position_repo.get_with_stock_info.return_value = [
            {
                "symbol": "USD_STOCK",
                "market_value_eur": None,
                "quantity": 10,
                "current_price": 50,
                "country": "United States",
                "industry": "Consumer Electronics",
            },
        ]

        service = PortfolioService(
            portfolio_repo, position_repo, allocation_repo, stock_repo
        )
        summary = await service.get_portfolio_summary()

        # Should fallback to quantity * current_price = 10 * 50 = 500
        assert summary.total_value == 500

    @pytest.mark.asyncio
    async def test_cash_balance_included(self, mock_repos):
        """Cash balance should be fetched and included.

        Bug caught: Cash balance not being retrieved.
        """
        portfolio_repo, position_repo, allocation_repo, stock_repo = mock_repos

        portfolio_repo.get_latest_cash_balance.return_value = 5000.50
        position_repo.get_with_stock_info.return_value = [
            {
                "symbol": "TEST",
                "market_value_eur": 1000,
                "country": "Germany",
                "industry": "Consumer Electronics",
            },
        ]

        service = PortfolioService(
            portfolio_repo, position_repo, allocation_repo, stock_repo
        )
        summary = await service.get_portfolio_summary()

        assert summary.cash_balance == 5000.50
        assert summary.total_value == 1000  # Cash not included in total_value

    @pytest.mark.asyncio
    async def test_deviation_calculated_correctly(self, mock_repos):
        """Deviation should be current_pct - target_weight.

        Bug caught: Wrong deviation calculation affecting rebalancing.
        """
        portfolio_repo, position_repo, allocation_repo, stock_repo = mock_repos

        # Target weight 0.5 for Germany
        allocation_repo.get_all.return_value = {"country:Germany": 0.5}

        position_repo.get_with_stock_info.return_value = [
            {
                "symbol": "EU1",
                "market_value_eur": 700,
                "country": "Germany",
                "industry": "Consumer Electronics",
            },
            {
                "symbol": "US1",
                "market_value_eur": 300,
                "country": "United States",
                "industry": "Consumer Electronics",
            },
        ]

        service = PortfolioService(
            portfolio_repo, position_repo, allocation_repo, stock_repo
        )
        summary = await service.get_portfolio_summary()

        country_by_name = {c.name: c for c in summary.country_allocations}

        # Germany is at 70%, target weight is 0.5
        # Deviation = 0.7 - 0.5 = 0.2 (overweight)
        assert country_by_name["Germany"].current_pct == pytest.approx(0.7, abs=0.01)
        assert country_by_name["Germany"].deviation == pytest.approx(0.2, abs=0.01)

    @pytest.mark.asyncio
    async def test_values_rounded_correctly(self, mock_repos):
        """Values should be rounded to avoid floating point noise.

        Bug caught: Floating point precision issues in display.
        """
        portfolio_repo, position_repo, allocation_repo, stock_repo = mock_repos

        # Values that could cause floating point issues
        position_repo.get_with_stock_info.return_value = [
            {
                "symbol": "TEST1",
                "market_value_eur": 333.333333,
                "country": "Germany",
                "industry": "Consumer Electronics",
            },
            {
                "symbol": "TEST2",
                "market_value_eur": 666.666667,
                "country": "Germany",
                "industry": "Consumer Electronics",
            },
        ]

        service = PortfolioService(
            portfolio_repo, position_repo, allocation_repo, stock_repo
        )
        summary = await service.get_portfolio_summary()

        # Total should be rounded
        assert summary.total_value == 1000.0  # Rounded to 2 decimal places

        # Percentages should be rounded to 4 decimal places
        country = summary.country_allocations[0]
        assert country.current_pct == 1.0  # Should be exactly 1.0
