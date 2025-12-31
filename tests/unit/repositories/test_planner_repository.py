"""Tests for PlannerRepository."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestAreAllSequencesEvaluated:
    """Tests for are_all_sequences_evaluated method."""

    @pytest.mark.asyncio
    async def test_returns_true_when_all_sequences_evaluated(self):
        """Test that method returns True when all sequences are evaluated."""
        from app.modules.planning.database.planner_repository import PlannerRepository

        repo = PlannerRepository()
        mock_db = MagicMock()
        mock_db.fetchone = AsyncMock(return_value={"total": 10, "completed": 10})

        with patch.object(repo, "_get_db", return_value=mock_db):
            result = await repo.are_all_sequences_evaluated("test_hash")

        assert result is True
        mock_db.fetchone.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_false_when_not_all_sequences_evaluated(self):
        """Test that method returns False when not all sequences are evaluated."""
        from app.modules.planning.database.planner_repository import PlannerRepository

        repo = PlannerRepository()
        mock_db = MagicMock()
        mock_db.fetchone = AsyncMock(return_value={"total": 10, "completed": 5})

        with patch.object(repo, "_get_db", return_value=mock_db):
            result = await repo.are_all_sequences_evaluated("test_hash")

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_no_sequences(self):
        """Test that method returns False when no sequences exist."""
        from app.modules.planning.database.planner_repository import PlannerRepository

        repo = PlannerRepository()
        mock_db = MagicMock()
        mock_db.fetchone = AsyncMock(return_value={"total": 0, "completed": 0})

        with patch.object(repo, "_get_db", return_value=mock_db):
            result = await repo.are_all_sequences_evaluated("test_hash")

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_row_is_none(self):
        """Test that method returns False when database returns None."""
        from app.modules.planning.database.planner_repository import PlannerRepository

        repo = PlannerRepository()
        mock_db = MagicMock()
        mock_db.fetchone = AsyncMock(return_value=None)

        with patch.object(repo, "_get_db", return_value=mock_db):
            result = await repo.are_all_sequences_evaluated("test_hash")

        assert result is False

    @pytest.mark.asyncio
    async def test_handles_partial_evaluation(self):
        """Test that method correctly handles partial evaluation."""
        from app.modules.planning.database.planner_repository import PlannerRepository

        repo = PlannerRepository()
        mock_db = MagicMock()
        mock_db.fetchone = AsyncMock(return_value={"total": 100, "completed": 75})

        with patch.object(repo, "_get_db", return_value=mock_db):
            result = await repo.are_all_sequences_evaluated("test_hash")

        assert result is False

    @pytest.mark.asyncio
    async def test_uses_correct_portfolio_hash(self):
        """Test that method uses the correct portfolio hash in query."""
        from app.modules.planning.database.planner_repository import PlannerRepository

        repo = PlannerRepository()
        mock_db = MagicMock()
        mock_db.fetchone = AsyncMock(return_value={"total": 10, "completed": 10})

        test_hash = "abc123def456"

        with patch.object(repo, "_get_db", return_value=mock_db):
            await repo.are_all_sequences_evaluated(test_hash)

        # Verify the query was called with the correct hash
        call_args = mock_db.fetchone.call_args
        assert call_args is not None
        # The query should include the portfolio hash
        assert test_hash in str(call_args)
