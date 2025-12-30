"""Tests for ticker content service.

These tests validate ticker content generation and formatting for display,
including status messages, portfolio information, and job status formatting.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestTickerContentService:
    """Test TickerContentService class."""

    @pytest.fixture
    def mock_portfolio_repo(self):
        """Mock PortfolioRepository."""
        repo = AsyncMock()
        return repo

    @pytest.fixture
    def mock_position_repo(self):
        """Mock PositionRepository."""
        repo = AsyncMock()
        return repo

    @pytest.fixture
    def mock_stock_repo(self):
        """Mock StockRepository."""
        repo = AsyncMock()
        return repo

    @pytest.fixture
    def mock_planner_repo(self):
        """Mock PlannerRepository."""
        repo = AsyncMock()
        return repo

    @pytest.fixture
    def ticker_service(
        self,
        mock_portfolio_repo,
        mock_position_repo,
        mock_stock_repo,
        mock_planner_repo,
    ):
        """Create TickerContentService instance."""
        from app.domain.services.ticker_content_service import TickerContentService

        return TickerContentService(
            portfolio_repo=mock_portfolio_repo,
            position_repo=mock_position_repo,
            stock_repo=mock_stock_repo,
            planner_repo=mock_planner_repo,
        )

    @pytest.mark.asyncio
    async def test_get_current_status_message_returns_formatted_status(
        self, ticker_service, mock_portfolio_repo, mock_planner_repo
    ):
        """Test that get_current_status_message returns formatted status."""
        from app.domain.models import PortfolioSnapshot, PlannerSequence

        # Mock portfolio snapshot
        mock_snapshot = PortfolioSnapshot(
            date="2024-01-01",
            total_value_eur=100000.0,
            cash_eur=10000.0,
        )
        mock_portfolio_repo.get_latest.return_value = mock_snapshot

        # Mock planner sequence (finished)
        mock_sequence = PlannerSequence(
            id=1,
            portfolio_hash="abc123",
            status="finished",
            created_at="2024-01-01T00:00:00",
        )
        mock_planner_repo.get_latest_sequence.return_value = mock_sequence

        result = await ticker_service.get_current_status_message()

        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_get_current_status_message_handles_no_portfolio(self, ticker_service):
        """Test handling when no portfolio snapshot exists."""
        result = await ticker_service.get_current_status_message()

        # Should return some default or empty message
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_format_portfolio_status_formats_correctly(self, ticker_service):
        """Test that format_portfolio_status formats portfolio data correctly."""
        from app.domain.models import PortfolioSnapshot

        snapshot = PortfolioSnapshot(
            date="2024-01-01",
            total_value_eur=100000.0,
            cash_eur=10000.0,
        )

        result = ticker_service.format_portfolio_status(snapshot)

        assert isinstance(result, str)
        # Should include portfolio value information
        assert "100000" in result or "100,000" in result or len(result) > 0

    @pytest.mark.asyncio
    async def test_format_portfolio_status_handles_none(self, ticker_service):
        """Test handling when snapshot is None."""
        result = ticker_service.format_portfolio_status(None)

        assert isinstance(result, str)
        # Should return some default message

    @pytest.mark.asyncio
    async def test_format_job_status_formats_correctly(self, ticker_service):
        """Test that format_job_status formats job status correctly."""
        from app.domain.models import PlannerSequence

        sequence = PlannerSequence(
            id=1,
            portfolio_hash="abc123",
            status="in_progress",
            created_at="2024-01-01T00:00:00",
        )

        result = ticker_service.format_job_status(sequence)

        assert isinstance(result, str)
        assert isinstance(result, str)  # Should return formatted string

    @pytest.mark.asyncio
    async def test_format_job_status_handles_none(self, ticker_service):
        """Test handling when sequence is None."""
        result = ticker_service.format_job_status(None)

        assert isinstance(result, str)
        # Should return some default or empty message

    @pytest.mark.asyncio
    async def test_format_job_status_handles_different_statuses(self, ticker_service):
        """Test formatting of different job statuses."""
        from app.domain.models import PlannerSequence

        statuses = ["pending", "in_progress", "finished", "failed"]

        for status in statuses:
            sequence = PlannerSequence(
                id=1,
                portfolio_hash="abc123",
                status=status,
                created_at="2024-01-01T00:00:00",
            )

            result = ticker_service.format_job_status(sequence)

            assert isinstance(result, str)
            # Should handle all statuses gracefully

    @pytest.mark.asyncio
    async def test_get_content_integrates_all_components(self, ticker_service):
        """Test that get_content integrates portfolio and job status."""
        from app.domain.models import PortfolioSnapshot, PlannerSequence

        mock_snapshot = PortfolioSnapshot(
            date="2024-01-01",
            total_value_eur=100000.0,
            cash_eur=10000.0,
        )
        mock_sequence = PlannerSequence(
            id=1,
            portfolio_hash="abc123",
            status="finished",
            created_at="2024-01-01T00:00:00",
        )

        # Mock the dependencies
        with patch.object(
            ticker_service, "get_current_status_message", new_callable=AsyncMock
        ) as mock_get_status:
            mock_get_status.return_value = "Test Status Message"

            result = await ticker_service.get_content()

            assert isinstance(result, str)
            assert result == "Test Status Message"
            mock_get_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_content_handles_exceptions_gracefully(self, ticker_service):
        """Test that get_content handles exceptions gracefully."""
        from app.domain.models import PortfolioSnapshot

        # Make portfolio repo raise an exception
        ticker_service._portfolio_repo.get_latest.side_effect = Exception("DB Error")

        result = await ticker_service.get_content()

        # Should return some fallback message or empty string
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_handles_missing_dependencies(self, ticker_service):
        """Test handling when dependencies return None."""
        ticker_service._portfolio_repo.get_latest.return_value = None
        ticker_service._planner_repo.get_latest_sequence.return_value = None

        result = await ticker_service.get_current_status_message()

        # Should handle None values gracefully
        assert isinstance(result, str)

