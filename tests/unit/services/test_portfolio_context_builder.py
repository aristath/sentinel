"""Tests for portfolio context builder.

These tests validate the construction of PortfolioContext objects
for use in scoring and recommendation generation.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.models import Stock
from app.domain.scoring import PortfolioContext
from app.domain.value_objects.currency import Currency


@pytest.fixture
def mock_position_repo():
    """Mock position repository."""
    repo = AsyncMock()
    mock_position = MagicMock()
    mock_position.symbol = "AAPL"
    mock_position.quantity = 10
    mock_position.market_value_eur = 1000.0
    repo.get_all.return_value = [mock_position]
    repo.get_total_value.return_value = 5000.0
    return repo


@pytest.fixture
def mock_stock_repo():
    """Mock stock repository."""
    repo = AsyncMock()
    mock_stock = Stock(
        symbol="AAPL",
        name="Apple Inc.",
        country="United States",
        currency=Currency.USD,
        industry="Technology",
    )
    repo.get_all_active.return_value = [mock_stock]
    return repo


@pytest.fixture
def mock_allocation_repo():
    """Mock allocation repository."""
    repo = AsyncMock()
    repo.get_country_group_targets = AsyncMock(return_value={"US": 0.5, "EU": 0.4})
    repo.get_industry_group_targets = AsyncMock(
        return_value={"Technology": 0.3, "Finance": 0.2}
    )
    return repo


@pytest.fixture
def mock_db_manager():
    """Mock database manager."""
    manager = MagicMock()
    mock_state_db = AsyncMock()
    mock_row = MagicMock()
    mock_row.__getitem__ = lambda self, key: {"AAPL": 0.8}.get(key, 0.0)
    mock_row.__contains__ = lambda self, key: key in ["symbol", "quality_score"]
    mock_state_db.fetchall = AsyncMock(return_value=[mock_row])
    manager.state = mock_state_db
    return manager


class TestBuildPortfolioContext:
    """Test build_portfolio_context function."""

    @pytest.mark.asyncio
    async def test_builds_context_with_positions(
        self, mock_position_repo, mock_stock_repo, mock_allocation_repo, mock_db_manager
    ):
        """Test that context is built correctly with positions."""
        from app.application.services.recommendation.portfolio_context_builder import (
            build_portfolio_context,
        )

        # Setup stock score row
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {
            "symbol": "AAPL",
            "quality_score": 0.8,
        }.get(key)
        mock_row.__contains__ = lambda self, key: key in ["symbol", "quality_score"]
        mock_db_manager.state.fetchall = AsyncMock(return_value=[mock_row])

        with patch(
            "app.application.services.recommendation.portfolio_context_builder.GroupingRepository"
        ) as mock_grouping_repo_class:
            mock_grouping_repo = AsyncMock()
            mock_grouping_repo.get_country_groups = AsyncMock(
                return_value={"US": ["United States"]}
            )
            mock_grouping_repo.get_industry_groups = AsyncMock(
                return_value={"Technology": ["Technology"]}
            )
            mock_grouping_repo_class.return_value = mock_grouping_repo

            context = await build_portfolio_context(
                mock_position_repo,
                mock_stock_repo,
                mock_allocation_repo,
                mock_db_manager,
            )

            assert isinstance(context, PortfolioContext)
            assert context.total_value == 5000.0
            assert "AAPL" in context.positions
            assert context.positions["AAPL"] == 1000.0
            assert context.country_weights["US"] == 0.5
            assert context.industry_weights["Technology"] == 0.3

    @pytest.mark.asyncio
    async def test_builds_context_with_allocation_targets(
        self, mock_position_repo, mock_stock_repo, mock_allocation_repo, mock_db_manager
    ):
        """Test that allocation targets are included in context."""
        from app.application.services.recommendation.portfolio_context_builder import (
            build_portfolio_context,
        )

        mock_db_manager.state.fetchall = AsyncMock(return_value=[])

        with patch(
            "app.application.services.recommendation.portfolio_context_builder.GroupingRepository"
        ) as mock_grouping_repo_class:
            mock_grouping_repo = AsyncMock()
            mock_grouping_repo.get_country_groups = AsyncMock(
                return_value={"US": ["United States"], "EU": ["Germany", "France"]}
            )
            mock_grouping_repo.get_industry_groups = AsyncMock(
                return_value={"Technology": ["Technology"], "Finance": ["Banking"]}
            )
            mock_grouping_repo_class.return_value = mock_grouping_repo

            context = await build_portfolio_context(
                mock_position_repo,
                mock_stock_repo,
                mock_allocation_repo,
                mock_db_manager,
            )

            assert context.country_weights["US"] == 0.5
            assert context.country_weights["EU"] == 0.4
            assert context.industry_weights["Technology"] == 0.3
            assert context.industry_weights["Finance"] == 0.2

    @pytest.mark.asyncio
    async def test_builds_country_to_group_mapping(
        self, mock_position_repo, mock_stock_repo, mock_allocation_repo, mock_db_manager
    ):
        """Test that country to group mapping is built correctly."""
        from app.application.services.recommendation.portfolio_context_builder import (
            build_portfolio_context,
        )

        mock_db_manager.state.fetchall = AsyncMock(return_value=[])

        with patch(
            "app.application.services.recommendation.portfolio_context_builder.GroupingRepository"
        ) as mock_grouping_repo_class:
            mock_grouping_repo = AsyncMock()
            mock_grouping_repo.get_country_groups = AsyncMock(
                return_value={"US": ["United States", "Canada"]}
            )
            mock_grouping_repo.get_industry_groups = AsyncMock(return_value={})
            mock_grouping_repo_class.return_value = mock_grouping_repo

            context = await build_portfolio_context(
                mock_position_repo,
                mock_stock_repo,
                mock_allocation_repo,
                mock_db_manager,
            )

            assert context.country_to_group is not None
            assert context.country_to_group["United States"] == "US"
            assert context.country_to_group["Canada"] == "US"

    @pytest.mark.asyncio
    async def test_builds_industry_to_group_mapping(
        self, mock_position_repo, mock_stock_repo, mock_allocation_repo, mock_db_manager
    ):
        """Test that industry to group mapping is built correctly."""
        from app.application.services.recommendation.portfolio_context_builder import (
            build_portfolio_context,
        )

        mock_db_manager.state.fetchall = AsyncMock(return_value=[])

        with patch(
            "app.application.services.recommendation.portfolio_context_builder.GroupingRepository"
        ) as mock_grouping_repo_class:
            mock_grouping_repo = AsyncMock()
            mock_grouping_repo.get_country_groups = AsyncMock(return_value={})
            mock_grouping_repo.get_industry_groups = AsyncMock(
                return_value={"Tech": ["Technology", "Software"]}
            )
            mock_grouping_repo_class.return_value = mock_grouping_repo

            context = await build_portfolio_context(
                mock_position_repo,
                mock_stock_repo,
                mock_allocation_repo,
                mock_db_manager,
            )

            assert context.industry_to_group is not None
            assert context.industry_to_group["Technology"] == "Tech"
            assert context.industry_to_group["Software"] == "Tech"

    @pytest.mark.asyncio
    async def test_includes_stock_scores(
        self, mock_position_repo, mock_stock_repo, mock_allocation_repo, mock_db_manager
    ):
        """Test that stock scores are included in context."""
        from app.application.services.recommendation.portfolio_context_builder import (
            build_portfolio_context,
        )

        # Setup score row
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {
            "symbol": "AAPL",
            "quality_score": 0.85,
        }.get(key)
        mock_row.__contains__ = lambda self, key: key in ["symbol", "quality_score"]
        mock_db_manager.state.fetchall = AsyncMock(return_value=[mock_row])

        with patch(
            "app.application.services.recommendation.portfolio_context_builder.GroupingRepository"
        ) as mock_grouping_repo_class:
            mock_grouping_repo = AsyncMock()
            mock_grouping_repo.get_country_groups = AsyncMock(return_value={})
            mock_grouping_repo.get_industry_groups = AsyncMock(return_value={})
            mock_grouping_repo_class.return_value = mock_grouping_repo

            context = await build_portfolio_context(
                mock_position_repo,
                mock_stock_repo,
                mock_allocation_repo,
                mock_db_manager,
            )

            assert context.stock_scores is not None
            assert context.stock_scores["AAPL"] == 0.85

    @pytest.mark.asyncio
    async def test_handles_empty_positions(
        self, mock_stock_repo, mock_allocation_repo, mock_db_manager
    ):
        """Test handling when there are no positions."""
        from app.application.services.recommendation.portfolio_context_builder import (
            build_portfolio_context,
        )

        mock_position_repo = AsyncMock()
        mock_position_repo.get_all.return_value = []
        mock_position_repo.get_total_value.return_value = 0.0

        mock_db_manager.state.fetchall = AsyncMock(return_value=[])

        with patch(
            "app.application.services.recommendation.portfolio_context_builder.GroupingRepository"
        ) as mock_grouping_repo_class:
            mock_grouping_repo = AsyncMock()
            mock_grouping_repo.get_country_groups = AsyncMock(return_value={})
            mock_grouping_repo.get_industry_groups = AsyncMock(return_value={})
            mock_grouping_repo_class.return_value = mock_grouping_repo

            context = await build_portfolio_context(
                mock_position_repo,
                mock_stock_repo,
                mock_allocation_repo,
                mock_db_manager,
            )

            assert context.total_value == 1.0  # Should default to 1.0 if 0
            assert len(context.positions) == 0

    @pytest.mark.asyncio
    async def test_defaults_total_value_to_one_if_zero(
        self, mock_stock_repo, mock_allocation_repo, mock_db_manager
    ):
        """Test that total_value defaults to 1.0 if zero."""
        from app.application.services.recommendation.portfolio_context_builder import (
            build_portfolio_context,
        )

        mock_position_repo = AsyncMock()
        mock_position_repo.get_all.return_value = []
        mock_position_repo.get_total_value.return_value = 0.0

        mock_db_manager.state.fetchall = AsyncMock(return_value=[])

        with patch(
            "app.application.services.recommendation.portfolio_context_builder.GroupingRepository"
        ) as mock_grouping_repo_class:
            mock_grouping_repo = AsyncMock()
            mock_grouping_repo.get_country_groups = AsyncMock(return_value={})
            mock_grouping_repo.get_industry_groups = AsyncMock(return_value={})
            mock_grouping_repo_class.return_value = mock_grouping_repo

            context = await build_portfolio_context(
                mock_position_repo,
                mock_stock_repo,
                mock_allocation_repo,
                mock_db_manager,
            )

            assert context.total_value == 1.0

    @pytest.mark.asyncio
    async def test_includes_stock_countries_and_industries(
        self, mock_position_repo, mock_stock_repo, mock_allocation_repo, mock_db_manager
    ):
        """Test that stock countries and industries are included."""
        from app.application.services.recommendation.portfolio_context_builder import (
            build_portfolio_context,
        )

        mock_db_manager.state.fetchall = AsyncMock(return_value=[])

        with patch(
            "app.application.services.recommendation.portfolio_context_builder.GroupingRepository"
        ) as mock_grouping_repo_class:
            mock_grouping_repo = AsyncMock()
            mock_grouping_repo.get_country_groups = AsyncMock(return_value={})
            mock_grouping_repo.get_industry_groups = AsyncMock(return_value={})
            mock_grouping_repo_class.return_value = mock_grouping_repo

            context = await build_portfolio_context(
                mock_position_repo,
                mock_stock_repo,
                mock_allocation_repo,
                mock_db_manager,
            )

            assert context.stock_countries is not None
            assert context.stock_countries["AAPL"] == "United States"
            assert context.stock_industries is not None
            assert context.stock_industries["AAPL"] == "Technology"

    @pytest.mark.asyncio
    async def test_handles_stocks_without_country_or_industry(
        self, mock_position_repo, mock_allocation_repo, mock_db_manager
    ):
        """Test handling of stocks without country or industry."""
        from app.application.services.recommendation.portfolio_context_builder import (
            build_portfolio_context,
        )

        mock_stock_repo = AsyncMock()
        mock_stock = Stock(
            symbol="UNKNOWN",
            name="Unknown Stock",
            country=None,
            currency=Currency.USD,
            industry=None,
        )
        mock_stock_repo.get_all_active.return_value = [mock_stock]

        mock_db_manager.state.fetchall = AsyncMock(return_value=[])

        with patch(
            "app.application.services.recommendation.portfolio_context_builder.GroupingRepository"
        ) as mock_grouping_repo_class:
            mock_grouping_repo = AsyncMock()
            mock_grouping_repo.get_country_groups = AsyncMock(return_value={})
            mock_grouping_repo.get_industry_groups = AsyncMock(return_value={})
            mock_grouping_repo_class.return_value = mock_grouping_repo

            context = await build_portfolio_context(
                mock_position_repo,
                mock_stock_repo,
                mock_allocation_repo,
                mock_db_manager,
            )

            # Stock without country/industry should not be in the maps
            assert "UNKNOWN" not in context.stock_countries
            assert "UNKNOWN" not in context.stock_industries

    @pytest.mark.asyncio
    async def test_handles_empty_allocation_targets(
        self, mock_position_repo, mock_stock_repo, mock_db_manager
    ):
        """Test handling when there are no allocation targets."""
        from app.application.services.recommendation.portfolio_context_builder import (
            build_portfolio_context,
        )

        mock_allocation_repo = AsyncMock()
        mock_allocation_repo.get_country_group_targets = AsyncMock(return_value={})
        mock_allocation_repo.get_industry_group_targets = AsyncMock(return_value={})

        mock_db_manager.state.fetchall = AsyncMock(return_value=[])

        with patch(
            "app.application.services.recommendation.portfolio_context_builder.GroupingRepository"
        ) as mock_grouping_repo_class:
            mock_grouping_repo = AsyncMock()
            mock_grouping_repo.get_country_groups = AsyncMock(return_value={})
            mock_grouping_repo.get_industry_groups = AsyncMock(return_value={})
            mock_grouping_repo_class.return_value = mock_grouping_repo

            context = await build_portfolio_context(
                mock_position_repo,
                mock_stock_repo,
                mock_allocation_repo,
                mock_db_manager,
            )

            assert context.country_weights == {}
            assert context.industry_weights == {}

    @pytest.mark.asyncio
    async def test_handles_scores_with_none_quality_score(
        self, mock_position_repo, mock_stock_repo, mock_allocation_repo, mock_db_manager
    ):
        """Test handling when quality_score is None."""
        from app.application.services.recommendation.portfolio_context_builder import (
            build_portfolio_context,
        )

        # Setup score row with None quality_score
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {
            "symbol": "AAPL",
            "quality_score": None,
        }.get(key)
        mock_row.__contains__ = lambda self, key: key in ["symbol", "quality_score"]
        mock_db_manager.state.fetchall = AsyncMock(return_value=[mock_row])

        with patch(
            "app.application.services.recommendation.portfolio_context_builder.GroupingRepository"
        ) as mock_grouping_repo_class:
            mock_grouping_repo = AsyncMock()
            mock_grouping_repo.get_country_groups = AsyncMock(return_value={})
            mock_grouping_repo.get_industry_groups = AsyncMock(return_value={})
            mock_grouping_repo_class.return_value = mock_grouping_repo

            context = await build_portfolio_context(
                mock_position_repo,
                mock_stock_repo,
                mock_allocation_repo,
                mock_db_manager,
            )

            # Should not include score if quality_score is None
            assert context.stock_scores is None or "AAPL" not in context.stock_scores
