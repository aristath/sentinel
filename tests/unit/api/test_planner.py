"""Tests for planner API endpoints.

These tests validate sequence regeneration, status retrieval, and SSE streaming
for the holistic planner.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.domain.models import Security
from app.shared.domain.value_objects.currency import Currency


@pytest.fixture
def mock_position_repo():
    """Mock position repository."""
    repo = AsyncMock()
    mock_position = MagicMock()
    mock_position.symbol = "AAPL"
    mock_position.quantity = 10
    repo.get_all.return_value = [mock_position]
    return repo


@pytest.fixture
def mock_stock_repo():
    """Mock stock repository."""
    repo = AsyncMock()
    mock_stock = Security(
        symbol="AAPL",
        name="Apple Inc.",
        country="United States",
        currency=Currency.USD,
    )
    repo.get_all_active.return_value = [mock_stock]
    return repo


@pytest.fixture
def mock_tradernet_client():
    """Mock Tradernet client."""
    client = MagicMock()
    client.is_connected = True
    client.get_pending_orders.return_value = []
    mock_cash_balance = MagicMock()
    mock_cash_balance.currency = "EUR"
    mock_cash_balance.amount = 1000.0
    client.get_cash_balances.return_value = [mock_cash_balance]
    return client


@pytest.fixture
def mock_planner_repo():
    """Mock planner repository."""
    repo = AsyncMock()
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.commit = AsyncMock()
    repo._get_db = AsyncMock(return_value=mock_db)
    repo.delete_sequences_only = AsyncMock()
    repo.has_sequences = AsyncMock(return_value=False)
    repo.get_total_sequence_count = AsyncMock(return_value=0)
    repo.get_evaluation_count = AsyncMock(return_value=0)
    repo.are_all_sequences_evaluated = AsyncMock(return_value=True)
    return repo


class TestRegenerateSequences:
    """Test regenerate_sequences endpoint."""

    @pytest.mark.asyncio
    async def test_regenerates_sequences_successfully(
        self, mock_position_repo, mock_stock_repo, mock_tradernet_client
    ):
        """Test successful sequence regeneration."""
        from app.modules.planning.api.planner import regenerate_sequences

        with patch("app.api.planner.PlannerRepository") as mock_planner_class:
            mock_planner_repo = AsyncMock()
            mock_db = AsyncMock()
            mock_db.execute = AsyncMock()
            mock_db.commit = AsyncMock()
            mock_planner_repo._get_db = AsyncMock(return_value=mock_db)
            mock_planner_repo.delete_sequences_only = AsyncMock()
            mock_planner_class.return_value = mock_planner_repo

            result = await regenerate_sequences(
                mock_position_repo, mock_stock_repo, mock_tradernet_client
            )

            assert result["status"] == "success"
            assert "portfolio_hash" in result
            assert "message" in result
            mock_planner_repo.delete_sequences_only.assert_called_once()
            mock_db.execute.assert_called_once()
            mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_generates_portfolio_hash(
        self, mock_position_repo, mock_stock_repo, mock_tradernet_client
    ):
        """Test that portfolio hash is generated correctly."""
        from app.modules.planning.api.planner import regenerate_sequences

        with patch("app.api.planner.PlannerRepository") as mock_planner_class:
            mock_planner_repo = AsyncMock()
            mock_db = AsyncMock()
            mock_db.execute = AsyncMock()
            mock_db.commit = AsyncMock()
            mock_planner_repo._get_db = AsyncMock(return_value=mock_db)
            mock_planner_repo.delete_sequences_only = AsyncMock()
            mock_planner_class.return_value = mock_planner_repo

            result = await regenerate_sequences(
                mock_position_repo, mock_stock_repo, mock_tradernet_client
            )

            # Portfolio hash should be 8 characters
            assert len(result["portfolio_hash"]) == 8
            assert result["portfolio_hash"].isalnum()

    @pytest.mark.asyncio
    async def test_handles_tradernet_not_connected(
        self, mock_position_repo, mock_stock_repo
    ):
        """Test handling when Tradernet is not connected."""
        from app.modules.planning.api.planner import regenerate_sequences

        disconnected_client = MagicMock()
        disconnected_client.is_connected = False

        with patch("app.api.planner.PlannerRepository") as mock_planner_class:
            mock_planner_repo = AsyncMock()
            mock_db = AsyncMock()
            mock_db.execute = AsyncMock()
            mock_db.commit = AsyncMock()
            mock_planner_repo._get_db = AsyncMock(return_value=mock_db)
            mock_planner_repo.delete_sequences_only = AsyncMock()
            mock_planner_class.return_value = mock_planner_repo

            result = await regenerate_sequences(
                mock_position_repo, mock_stock_repo, disconnected_client
            )

            assert result["status"] == "success"
            # Should still work without tradernet connection
            disconnected_client.get_pending_orders.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_tradernet_errors_gracefully(
        self, mock_position_repo, mock_stock_repo
    ):
        """Test handling when Tradernet API calls fail."""
        from app.modules.planning.api.planner import regenerate_sequences

        error_client = MagicMock()
        error_client.is_connected = True
        error_client.get_pending_orders.side_effect = Exception("API Error")
        error_client.get_cash_balances.side_effect = Exception("API Error")

        with patch("app.api.planner.PlannerRepository") as mock_planner_class:
            mock_planner_repo = AsyncMock()
            mock_db = AsyncMock()
            mock_db.execute = AsyncMock()
            mock_db.commit = AsyncMock()
            mock_planner_repo._get_db = AsyncMock(return_value=mock_db)
            mock_planner_repo.delete_sequences_only = AsyncMock()
            mock_planner_class.return_value = mock_planner_repo

            # Should not raise, should handle errors gracefully
            result = await regenerate_sequences(
                mock_position_repo, mock_stock_repo, error_client
            )

            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_deletes_sequences_and_best_result(
        self, mock_position_repo, mock_stock_repo, mock_tradernet_client
    ):
        """Test that sequences are deleted and best_result is cleared."""
        from app.modules.planning.api.planner import regenerate_sequences

        with patch("app.api.planner.PlannerRepository") as mock_planner_class:
            mock_planner_repo = AsyncMock()
            mock_db = AsyncMock()
            mock_db.execute = AsyncMock()
            mock_db.commit = AsyncMock()
            mock_planner_repo._get_db = AsyncMock(return_value=mock_db)
            mock_planner_repo.delete_sequences_only = AsyncMock()
            mock_planner_class.return_value = mock_planner_repo

            await regenerate_sequences(
                mock_position_repo, mock_stock_repo, mock_tradernet_client
            )

            # Should delete sequences
            mock_planner_repo.delete_sequences_only.assert_called_once()
            # Should clear best_result
            mock_db.execute.assert_called_once()
            assert "DELETE FROM best_result" in str(mock_db.execute.call_args)

    @pytest.mark.asyncio
    async def test_handles_repository_errors(
        self, mock_position_repo, mock_stock_repo, mock_tradernet_client
    ):
        """Test handling of repository errors."""
        from app.modules.planning.api.planner import regenerate_sequences

        with patch("app.api.planner.PlannerRepository") as mock_planner_class:
            mock_planner_repo = AsyncMock()
            mock_planner_repo.delete_sequences_only.side_effect = Exception(
                "Database error"
            )
            mock_planner_class.return_value = mock_planner_repo

            with pytest.raises(HTTPException) as exc_info:
                await regenerate_sequences(
                    mock_position_repo, mock_stock_repo, mock_tradernet_client
                )

            assert exc_info.value.status_code == 500
            assert "Database error" in str(exc_info.value.detail)


class TestGetPlannerStatus:
    """Test get_planner_status endpoint."""

    @pytest.mark.asyncio
    async def test_returns_status_when_no_sequences(
        self, mock_position_repo, mock_stock_repo, mock_tradernet_client
    ):
        """Test status when no sequences exist."""
        from app.modules.planning.api.planner import get_planner_status

        with patch("app.api.planner.PlannerRepository") as mock_planner_class:
            mock_planner_repo = AsyncMock()
            mock_planner_repo.has_sequences = AsyncMock(return_value=False)
            mock_planner_repo.get_total_sequence_count = AsyncMock(return_value=0)
            mock_planner_repo.get_evaluation_count = AsyncMock(return_value=0)
            mock_planner_repo.are_all_sequences_evaluated = AsyncMock(return_value=True)
            mock_planner_class.return_value = mock_planner_repo

            with patch("app.api.planner.get_scheduler") as mock_get_scheduler:
                mock_scheduler = MagicMock()
                mock_scheduler.running = True
                mock_scheduler.get_jobs.return_value = []
                mock_get_scheduler.return_value = mock_scheduler

                result = await get_planner_status(
                    mock_position_repo, mock_stock_repo, mock_tradernet_client
                )

                assert result["has_sequences"] is False
                assert result["total_sequences"] == 0
                assert result["evaluated_count"] == 0
                assert result["is_finished"] is True
                assert result["progress_percentage"] == 0.0
                assert "portfolio_hash" in result

    @pytest.mark.asyncio
    async def test_returns_status_with_sequences(
        self, mock_position_repo, mock_stock_repo, mock_tradernet_client
    ):
        """Test status when sequences exist."""
        from app.modules.planning.api.planner import get_planner_status

        with patch("app.api.planner.PlannerRepository") as mock_planner_class:
            mock_planner_repo = AsyncMock()
            mock_planner_repo.has_sequences = AsyncMock(return_value=True)
            mock_planner_repo.get_total_sequence_count = AsyncMock(return_value=100)
            mock_planner_repo.get_evaluation_count = AsyncMock(return_value=50)
            mock_planner_repo.are_all_sequences_evaluated = AsyncMock(
                return_value=False
            )
            mock_planner_class.return_value = mock_planner_repo

            with patch("app.api.planner.get_scheduler") as mock_get_scheduler:
                mock_scheduler = MagicMock()
                mock_scheduler.running = True
                mock_job = MagicMock()
                mock_job.id = "planner_batch"
                mock_scheduler.get_jobs.return_value = [mock_job]
                mock_get_scheduler.return_value = mock_scheduler

                result = await get_planner_status(
                    mock_position_repo, mock_stock_repo, mock_tradernet_client
                )

                assert result["has_sequences"] is True
                assert result["total_sequences"] == 100
                assert result["evaluated_count"] == 50
                assert result["is_finished"] is False
                assert result["progress_percentage"] == 50.0
                assert result["is_planning"] is True

    @pytest.mark.asyncio
    async def test_calculates_progress_percentage(
        self, mock_position_repo, mock_stock_repo, mock_tradernet_client
    ):
        """Test that progress percentage is calculated correctly."""
        from app.modules.planning.api.planner import get_planner_status

        with patch("app.api.planner.PlannerRepository") as mock_planner_class:
            mock_planner_repo = AsyncMock()
            mock_planner_repo.has_sequences = AsyncMock(return_value=True)
            mock_planner_repo.get_total_sequence_count = AsyncMock(return_value=200)
            mock_planner_repo.get_evaluation_count = AsyncMock(return_value=75)
            mock_planner_repo.are_all_sequences_evaluated = AsyncMock(
                return_value=False
            )
            mock_planner_class.return_value = mock_planner_repo

            with patch("app.api.planner.get_scheduler") as mock_get_scheduler:
                mock_scheduler = MagicMock()
                mock_scheduler.running = True
                mock_scheduler.get_jobs.return_value = []
                mock_get_scheduler.return_value = mock_scheduler

                result = await get_planner_status(
                    mock_position_repo, mock_stock_repo, mock_tradernet_client
                )

                # 75/200 = 37.5%
                assert result["progress_percentage"] == 37.5

    @pytest.mark.asyncio
    async def test_detects_planning_active_with_scheduler_job(
        self, mock_position_repo, mock_stock_repo, mock_tradernet_client
    ):
        """Test that is_planning is True when scheduler job exists."""
        from app.modules.planning.api.planner import get_planner_status

        with patch("app.api.planner.PlannerRepository") as mock_planner_class:
            mock_planner_repo = AsyncMock()
            mock_planner_repo.has_sequences = AsyncMock(return_value=True)
            mock_planner_repo.get_total_sequence_count = AsyncMock(return_value=100)
            mock_planner_repo.get_evaluation_count = AsyncMock(return_value=50)
            mock_planner_repo.are_all_sequences_evaluated = AsyncMock(
                return_value=False
            )
            mock_planner_class.return_value = mock_planner_repo

            with patch("app.api.planner.get_scheduler") as mock_get_scheduler:
                mock_scheduler = MagicMock()
                mock_scheduler.running = True
                mock_job = MagicMock()
                mock_job.id = "planner_batch"
                mock_scheduler.get_jobs.return_value = [mock_job]
                mock_get_scheduler.return_value = mock_scheduler

                result = await get_planner_status(
                    mock_position_repo, mock_stock_repo, mock_tradernet_client
                )

                assert result["is_planning"] is True

    @pytest.mark.asyncio
    async def test_detects_planning_inactive_when_finished(
        self, mock_position_repo, mock_stock_repo, mock_tradernet_client
    ):
        """Test that is_planning is False when all sequences are evaluated."""
        from app.modules.planning.api.planner import get_planner_status

        with patch("app.api.planner.PlannerRepository") as mock_planner_class:
            mock_planner_repo = AsyncMock()
            mock_planner_repo.has_sequences = AsyncMock(return_value=True)
            mock_planner_repo.get_total_sequence_count = AsyncMock(return_value=100)
            mock_planner_repo.get_evaluation_count = AsyncMock(return_value=100)
            mock_planner_repo.are_all_sequences_evaluated = AsyncMock(return_value=True)
            mock_planner_class.return_value = mock_planner_repo

            with patch("app.api.planner.get_scheduler") as mock_get_scheduler:
                mock_scheduler = MagicMock()
                mock_scheduler.running = True
                mock_job = MagicMock()
                mock_job.id = "planner_batch"
                mock_scheduler.get_jobs.return_value = [mock_job]
                mock_get_scheduler.return_value = mock_scheduler

                result = await get_planner_status(
                    mock_position_repo, mock_stock_repo, mock_tradernet_client
                )

                assert result["is_planning"] is False
                assert result["is_finished"] is True

    @pytest.mark.asyncio
    async def test_handles_scheduler_not_available(
        self, mock_position_repo, mock_stock_repo, mock_tradernet_client
    ):
        """Test handling when scheduler is not available."""
        from app.modules.planning.api.planner import get_planner_status

        with patch("app.api.planner.PlannerRepository") as mock_planner_class:
            mock_planner_repo = AsyncMock()
            mock_planner_repo.has_sequences = AsyncMock(return_value=True)
            mock_planner_repo.get_total_sequence_count = AsyncMock(return_value=100)
            mock_planner_repo.get_evaluation_count = AsyncMock(return_value=50)
            mock_planner_repo.are_all_sequences_evaluated = AsyncMock(
                return_value=False
            )
            mock_planner_class.return_value = mock_planner_repo

            with patch("app.api.planner.get_scheduler") as mock_get_scheduler:
                mock_get_scheduler.side_effect = Exception("Scheduler error")

                result = await get_planner_status(
                    mock_position_repo, mock_stock_repo, mock_tradernet_client
                )

                # Should assume planning is active if we can't check scheduler
                assert result["is_planning"] is True

    @pytest.mark.asyncio
    async def test_handles_errors_gracefully(
        self, mock_position_repo, mock_stock_repo, mock_tradernet_client
    ):
        """Test error handling."""
        from app.modules.planning.api.planner import get_planner_status

        with patch("app.api.planner.PlannerRepository") as mock_planner_class:
            mock_planner_repo = AsyncMock()
            mock_planner_repo.has_sequences.side_effect = Exception("Database error")
            mock_planner_class.return_value = mock_planner_repo

            with pytest.raises(HTTPException) as exc_info:
                await get_planner_status(
                    mock_position_repo, mock_stock_repo, mock_tradernet_client
                )

            assert exc_info.value.status_code == 500


class TestStreamPlannerStatus:
    """Test stream_planner_status endpoint."""

    @pytest.mark.asyncio
    async def test_streams_initial_status(
        self, mock_position_repo, mock_stock_repo, mock_tradernet_client
    ):
        """Test that initial status is streamed."""
        from app.modules.planning.api.planner import stream_planner_status

        mock_status = {
            "has_sequences": True,
            "total_sequences": 100,
            "evaluated_count": 50,
            "is_planning": True,
            "is_finished": False,
            "portfolio_hash": "abc12345",
            "progress_percentage": 50.0,
        }

        with patch("app.api.planner._get_planner_status_internal") as mock_get_status:
            mock_get_status.return_value = mock_status

            with patch("app.infrastructure.planner_events") as mock_events:
                mock_events.set_current_status = AsyncMock()
                mock_events.subscribe_planner_events = AsyncMock()

                async def mock_subscribe():
                    yield mock_status

                mock_events.subscribe_planner_events.return_value = mock_subscribe()

                response = await stream_planner_status(
                    mock_position_repo, mock_stock_repo, mock_tradernet_client
                )

                assert response.media_type == "text/event-stream"
                assert "Cache-Control" in response.headers
                assert response.headers["Cache-Control"] == "no-cache"

    @pytest.mark.asyncio
    async def test_streams_sse_format(
        self, mock_position_repo, mock_stock_repo, mock_tradernet_client
    ):
        """Test that events are formatted as SSE."""
        from app.modules.planning.api.planner import stream_planner_status

        mock_status = {"has_sequences": False, "total_sequences": 0}

        with patch("app.api.planner._get_planner_status_internal") as mock_get_status:
            mock_get_status.return_value = mock_status

            with patch("app.infrastructure.planner_events") as mock_events:
                mock_events.set_current_status = AsyncMock()

                async def mock_subscribe():
                    yield mock_status

                mock_events.subscribe_planner_events.return_value = mock_subscribe()

                response = await stream_planner_status(
                    mock_position_repo, mock_stock_repo, mock_tradernet_client
                )

                # Get the generator and check first event
                events = []
                async for event in response.body_iterator:
                    events.append(event)

                assert len(events) > 0
                # Check SSE format: "data: {json}\n\n"
                assert events[0].startswith("data: ")

    @pytest.mark.asyncio
    async def test_handles_stream_errors(
        self, mock_position_repo, mock_stock_repo, mock_tradernet_client
    ):
        """Test error handling in stream."""
        from app.modules.planning.api.planner import stream_planner_status

        with patch("app.api.planner._get_planner_status_internal") as mock_get_status:
            mock_get_status.side_effect = Exception("Status error")

            with patch("app.infrastructure.planner_events") as mock_events:
                mock_events.set_current_status = AsyncMock()
                mock_events.subscribe_planner_events = AsyncMock()

                async def mock_subscribe():
                    raise Exception("Stream error")

                mock_events.subscribe_planner_events.return_value = mock_subscribe()

                response = await stream_planner_status(
                    mock_position_repo, mock_stock_repo, mock_tradernet_client
                )

                # Should return error event
                events = []
                async for event in response.body_iterator:
                    events.append(event)

                assert len(events) > 0
                assert "error" in events[-1].lower()
