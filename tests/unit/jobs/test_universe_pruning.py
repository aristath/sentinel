"""Tests for universe pruning job.

These tests validate automatic stock universe pruning logic.
CRITICAL: Tests catch real bugs that would cause poor portfolio quality.
"""

from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.models import Stock, StockScore


def create_stock(symbol: str, active: bool = True) -> Stock:
    """Helper to create stock."""
    from app.domain.value_objects.currency import Currency

    return Stock(
        symbol=symbol,
        name=f"{symbol} Inc.",
        active=active,
        currency=Currency.EUR,
    )


def create_stock_score(
    symbol: str, total_score: float, calculated_at: Optional[str] = None
) -> StockScore:
    """Helper to create stock score."""
    if calculated_at is None:
        calculated_at = datetime.now().isoformat()

    return StockScore(
        symbol=symbol,
        total_score=total_score,
        calculated_at=datetime.fromisoformat(calculated_at),
    )


@contextmanager
def mock_universe_pruning_dependencies(
    mock_stock_repo=None,
    mock_score_repo=None,
    mock_settings_repo=None,
    mock_tradernet_client=None,
):
    """Context manager to set up all mocks for universe pruning job."""
    # Default mocks
    if mock_stock_repo is None:
        mock_stock_repo = AsyncMock()
    if mock_score_repo is None:
        mock_score_repo = AsyncMock()
    if mock_settings_repo is None:
        mock_settings_repo = AsyncMock()
    if mock_tradernet_client is None:
        mock_tradernet_client = MagicMock()

    # Setup default settings - only if not already configured by test
    if mock_settings_repo.get_float.side_effect is None:
        async def get_float(key, default):
            defaults = {
                "universe_pruning_enabled": 1.0,
                "universe_pruning_score_threshold": 0.50,
                "universe_pruning_months": 3.0,
                "universe_pruning_min_samples": 2.0,
                "universe_pruning_check_delisted": 1.0,
            }
            return defaults.get(key, default)

        mock_settings_repo.get_float = AsyncMock(side_effect=get_float)

    with (
        patch(
            "app.jobs.universe_pruning.StockRepository", return_value=mock_stock_repo
        ),
        patch(
            "app.jobs.universe_pruning.ScoreRepository", return_value=mock_score_repo
        ),
        patch(
            "app.jobs.universe_pruning.SettingsRepository",
            return_value=mock_settings_repo,
        ),
        patch(
            "app.jobs.universe_pruning.get_tradernet_client",
            return_value=mock_tradernet_client,
        ),
    ):
        yield {
            "stock_repo": mock_stock_repo,
            "score_repo": mock_score_repo,
            "settings_repo": mock_settings_repo,
            "tradernet_client": mock_tradernet_client,
        }


class TestPruningLogic:
    """Test core pruning logic."""

    @pytest.mark.asyncio
    async def test_prunes_stock_with_consistently_low_scores(self):
        """Test that stocks with consistently low scores are pruned.

        Bug caught: Low-quality stocks not removed.
        """
        from app.jobs.universe_pruning import prune_universe

        # Stock with consistently low scores
        stock = create_stock("LOWQUAL.US", active=True)
        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_all_active = AsyncMock(return_value=[stock])
        mock_stock_repo.mark_inactive = AsyncMock()

        # Scores below threshold for required period
        now = datetime.now()
        scores = [
            create_stock_score(
                "LOWQUAL.US", 0.30, (now - timedelta(days=90)).isoformat()
            ),
            create_stock_score(
                "LOWQUAL.US", 0.35, (now - timedelta(days=60)).isoformat()
            ),
            create_stock_score(
                "LOWQUAL.US", 0.40, (now - timedelta(days=30)).isoformat()
            ),
        ]
        mock_score_repo = AsyncMock()
        mock_score_repo.get_recent_scores = AsyncMock(return_value=scores)

        mock_settings_repo = AsyncMock()

        async def get_float(key, default):
            return {
                "universe_pruning_enabled": 1.0,
                "universe_pruning_score_threshold": 0.50,
                "universe_pruning_months": 3.0,
                "universe_pruning_min_samples": 2.0,
            }.get(key, default)

        mock_settings_repo.get_float = AsyncMock(side_effect=get_float)

        with mock_universe_pruning_dependencies(
            mock_stock_repo=mock_stock_repo,
            mock_score_repo=mock_score_repo,
            mock_settings_repo=mock_settings_repo,
        ):
            await prune_universe()

        # Verify stock was marked inactive
        mock_stock_repo.mark_inactive.assert_called_once_with("LOWQUAL.US")

    @pytest.mark.asyncio
    async def test_keeps_stock_with_recent_high_score(self):
        """Test that stocks with recent high scores are kept.

        Bug caught: Good stocks incorrectly pruned.
        """
        from app.jobs.universe_pruning import prune_universe

        # Stock with recent high score
        stock = create_stock("GOODSTOCK.US", active=True)
        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_all_active = AsyncMock(return_value=[stock])
        mock_stock_repo.mark_inactive = AsyncMock()

        # Average score must be >= threshold (0.50) to prevent pruning
        # 0.40 + 0.45 + 0.75 = 1.60, avg = 0.533 >= 0.50
        now = datetime.now()
        scores = [
            create_stock_score(
                "GOODSTOCK.US", 0.40, (now - timedelta(days=90)).isoformat()
            ),
            create_stock_score(
                "GOODSTOCK.US", 0.45, (now - timedelta(days=60)).isoformat()
            ),
            create_stock_score(
                "GOODSTOCK.US", 0.75, (now - timedelta(days=10)).isoformat()
            ),  # Recent high score helps bring average above threshold
        ]
        mock_score_repo = AsyncMock()
        mock_score_repo.get_recent_scores = AsyncMock(return_value=scores)

        with mock_universe_pruning_dependencies(
            mock_stock_repo=mock_stock_repo,
            mock_score_repo=mock_score_repo,
        ):
            await prune_universe()

        # Verify stock was NOT marked inactive
        mock_stock_repo.mark_inactive.assert_not_called()

    @pytest.mark.asyncio
    async def test_requires_minimum_samples_before_pruning(self):
        """Test that pruning requires minimum number of samples.

        Bug caught: Pruning with insufficient data.
        """
        from app.jobs.universe_pruning import prune_universe

        stock = create_stock("INSUFFICIENT.US", active=True)
        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_all_active = AsyncMock(return_value=[stock])
        mock_stock_repo.mark_inactive = AsyncMock()

        # Only 1 score (below min_samples=2)
        now = datetime.now()
        scores = [
            create_stock_score(
                "INSUFFICIENT.US", 0.30, (now - timedelta(days=30)).isoformat()
            ),
        ]
        mock_score_repo = AsyncMock()
        mock_score_repo.get_recent_scores = AsyncMock(return_value=scores)

        mock_settings_repo = AsyncMock()

        async def get_float(key, default):
            return {
                "universe_pruning_enabled": 1.0,
                "universe_pruning_score_threshold": 0.50,
                "universe_pruning_months": 3.0,
                "universe_pruning_min_samples": 2.0,  # Requires 2 samples
            }.get(key, default)

        mock_settings_repo.get_float = AsyncMock(side_effect=get_float)

        with mock_universe_pruning_dependencies(
            mock_stock_repo=mock_stock_repo,
            mock_score_repo=mock_score_repo,
            mock_settings_repo=mock_settings_repo,
        ):
            await prune_universe()

        # Verify stock was NOT pruned (insufficient samples)
        mock_stock_repo.mark_inactive.assert_not_called()

    @pytest.mark.asyncio
    async def test_checks_score_over_required_months(self):
        """Test that pruning checks scores over the required time window.

        Bug caught: Using wrong time window.
        """
        from app.jobs.universe_pruning import prune_universe

        stock = create_stock("TIMEWINDOW.US", active=True)
        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_all_active = AsyncMock(return_value=[stock])
        mock_stock_repo.mark_inactive = AsyncMock()

        # Scores within 3 months window
        now = datetime.now()
        scores = [
            create_stock_score(
                "TIMEWINDOW.US", 0.30, (now - timedelta(days=80)).isoformat()
            ),
            create_stock_score(
                "TIMEWINDOW.US", 0.35, (now - timedelta(days=50)).isoformat()
            ),
        ]
        mock_score_repo = AsyncMock()
        mock_score_repo.get_recent_scores = AsyncMock(return_value=scores)

        mock_settings_repo = AsyncMock()

        async def get_float(key, default):
            return {
                "universe_pruning_enabled": 1.0,
                "universe_pruning_score_threshold": 0.50,
                "universe_pruning_months": 3.0,  # 3 months window
                "universe_pruning_min_samples": 2.0,
            }.get(key, default)

        mock_settings_repo.get_float = AsyncMock(side_effect=get_float)

        with mock_universe_pruning_dependencies(
            mock_stock_repo=mock_stock_repo,
            mock_score_repo=mock_score_repo,
            mock_settings_repo=mock_settings_repo,
        ):
            await prune_universe()

        # Verify get_recent_scores was called with correct months parameter
        call_args = mock_score_repo.get_recent_scores.call_args
        assert call_args[0][1] == 3.0  # months parameter


class TestBoundaryConditions:
    """Test boundary conditions and edge cases."""

    @pytest.mark.asyncio
    async def test_exactly_at_score_threshold_keeps_stock(self):
        """Test that stock exactly at threshold is kept.

        Bug caught: Off-by-one at threshold.
        """
        from app.jobs.universe_pruning import prune_universe

        stock = create_stock("THRESHOLD.US", active=True)
        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_all_active = AsyncMock(return_value=[stock])
        mock_stock_repo.mark_inactive = AsyncMock()

        # Scores exactly at threshold (0.50)
        now = datetime.now()
        scores = [
            create_stock_score(
                "THRESHOLD.US", 0.50, (now - timedelta(days=60)).isoformat()
            ),
            create_stock_score(
                "THRESHOLD.US", 0.50, (now - timedelta(days=30)).isoformat()
            ),
        ]
        mock_score_repo = AsyncMock()
        mock_score_repo.get_recent_scores = AsyncMock(return_value=scores)

        with mock_universe_pruning_dependencies(
            mock_stock_repo=mock_stock_repo,
            mock_score_repo=mock_score_repo,
        ):
            await prune_universe()

        # Verify stock was NOT pruned (at threshold, should keep)
        mock_stock_repo.mark_inactive.assert_not_called()

    @pytest.mark.asyncio
    async def test_stock_with_no_scores_handles_gracefully(self):
        """Test that stock with no scores is handled gracefully.

        Bug caught: Crashes on missing data.
        """
        from app.jobs.universe_pruning import prune_universe

        stock = create_stock("NOSCORES.US", active=True)
        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_all_active = AsyncMock(return_value=[stock])
        mock_stock_repo.mark_inactive = AsyncMock()

        # No scores
        mock_score_repo = AsyncMock()
        mock_score_repo.get_recent_scores = AsyncMock(return_value=[])

        with mock_universe_pruning_dependencies(
            mock_stock_repo=mock_stock_repo,
            mock_score_repo=mock_score_repo,
        ):
            # Should not raise exception
            await prune_universe()

        # Stock with no scores should not be pruned (insufficient data)
        mock_stock_repo.mark_inactive.assert_not_called()


class TestSettingsIntegration:
    """Test settings integration."""

    @pytest.mark.asyncio
    async def test_respects_enabled_flag(self):
        """Test that pruning is skipped when disabled.

        Bug caught: Pruning runs when disabled.
        """
        from app.jobs.universe_pruning import prune_universe

        stock = create_stock("DISABLED.US", active=True)
        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_all_active = AsyncMock(return_value=[stock])
        mock_stock_repo.mark_inactive = AsyncMock()

        mock_score_repo = AsyncMock()
        mock_score_repo.get_recent_scores = AsyncMock(return_value=[])

        mock_settings_repo = AsyncMock()

        async def get_float(key, default):
            return {
                "universe_pruning_enabled": 0.0,  # Disabled
                "universe_pruning_score_threshold": 0.50,
                "universe_pruning_months": 3.0,
                "universe_pruning_min_samples": 2.0,
            }.get(key, default)

        mock_settings_repo.get_float = AsyncMock(side_effect=get_float)

        with mock_universe_pruning_dependencies(
            mock_stock_repo=mock_stock_repo,
            mock_score_repo=mock_score_repo,
            mock_settings_repo=mock_settings_repo,
        ):
            await prune_universe()

        # Verify no pruning occurred (feature disabled)
        mock_stock_repo.get_all_active.assert_not_called()

    @pytest.mark.asyncio
    async def test_uses_custom_score_threshold(self):
        """Test that custom score threshold is used.

        Bug caught: Ignores user settings.
        """
        from app.jobs.universe_pruning import prune_universe

        stock = create_stock("CUSTOM.US", active=True)
        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_all_active = AsyncMock(return_value=[stock])
        mock_stock_repo.mark_inactive = AsyncMock()

        # Scores above default (0.50) but below custom threshold (0.70)
        now = datetime.now()
        scores = [
            create_stock_score(
                "CUSTOM.US", 0.60, (now - timedelta(days=60)).isoformat()
            ),
            create_stock_score(
                "CUSTOM.US", 0.65, (now - timedelta(days=30)).isoformat()
            ),
        ]
        mock_score_repo = AsyncMock()
        mock_score_repo.get_recent_scores = AsyncMock(return_value=scores)

        mock_settings_repo = AsyncMock()

        async def get_float(key, default):
            return {
                "universe_pruning_enabled": 1.0,
                "universe_pruning_score_threshold": 0.70,  # Custom threshold
                "universe_pruning_months": 3.0,
                "universe_pruning_min_samples": 2.0,
            }.get(key, default)

        mock_settings_repo.get_float = AsyncMock(side_effect=get_float)

        with mock_universe_pruning_dependencies(
            mock_stock_repo=mock_stock_repo,
            mock_score_repo=mock_score_repo,
            mock_settings_repo=mock_settings_repo,
        ):
            await prune_universe()

        # Verify stock was pruned (below custom threshold)
        mock_stock_repo.mark_inactive.assert_called_once_with("CUSTOM.US")


class TestStateVerification:
    """Test database state verification."""

    @pytest.mark.asyncio
    async def test_marks_stock_inactive_in_database(self):
        """Test that stock is marked inactive in database.

        Bug caught: In-memory state doesn't match database.
        """
        from app.jobs.universe_pruning import prune_universe

        stock = create_stock("DBTEST.US", active=True)
        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_all_active = AsyncMock(return_value=[stock])
        mock_stock_repo.mark_inactive = AsyncMock()

        now = datetime.now()
        scores = [
            create_stock_score(
                "DBTEST.US", 0.30, (now - timedelta(days=60)).isoformat()
            ),
            create_stock_score(
                "DBTEST.US", 0.35, (now - timedelta(days=30)).isoformat()
            ),
        ]
        mock_score_repo = AsyncMock()
        mock_score_repo.get_recent_scores = AsyncMock(return_value=scores)

        with mock_universe_pruning_dependencies(
            mock_stock_repo=mock_stock_repo,
            mock_score_repo=mock_score_repo,
        ):
            await prune_universe()

        # Verify mark_inactive was called with correct symbol
        mock_stock_repo.mark_inactive.assert_called_once_with("DBTEST.US")

    @pytest.mark.asyncio
    async def test_does_not_delete_stock_records(self):
        """Test that stock records are not deleted, only marked inactive.

        Bug caught: Data loss from deletion instead of deactivation.
        """
        from app.jobs.universe_pruning import prune_universe

        stock = create_stock("NODELETE.US", active=True)
        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_all_active = AsyncMock(return_value=[stock])
        mock_stock_repo.mark_inactive = AsyncMock()
        mock_stock_repo.delete = AsyncMock()  # Should not be called

        now = datetime.now()
        scores = [
            create_stock_score(
                "NODELETE.US", 0.30, (now - timedelta(days=60)).isoformat()
            ),
            create_stock_score(
                "NODELETE.US", 0.35, (now - timedelta(days=30)).isoformat()
            ),
        ]
        mock_score_repo = AsyncMock()
        mock_score_repo.get_recent_scores = AsyncMock(return_value=scores)

        with mock_universe_pruning_dependencies(
            mock_stock_repo=mock_stock_repo,
            mock_score_repo=mock_score_repo,
        ):
            await prune_universe()

        # Verify mark_inactive was called (not delete)
        mock_stock_repo.mark_inactive.assert_called_once()
        mock_stock_repo.delete.assert_not_called()


class TestErrorHandling:
    """Test error handling and failure modes."""

    @pytest.mark.asyncio
    async def test_api_failure_does_not_crash_job(self):
        """Test that API failure doesn't crash the job.

        Bug caught: Job crashes on external API failure.
        """
        from app.jobs.universe_pruning import prune_universe

        stock = create_stock("APIFAIL.US", active=True)
        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_all_active = AsyncMock(return_value=[stock])

        mock_score_repo = AsyncMock()
        mock_score_repo.get_recent_scores = AsyncMock(
            side_effect=Exception("Database error")
        )

        with mock_universe_pruning_dependencies(
            mock_stock_repo=mock_stock_repo,
            mock_score_repo=mock_score_repo,
        ):
            # Should not raise exception, should log and continue
            await prune_universe()

        # Job should complete without crashing

    @pytest.mark.asyncio
    async def test_invalid_score_data_skips_stock_continues(self):
        """Test that invalid score data for one stock doesn't block others.

        Bug caught: One bad stock blocks all pruning.
        """
        from app.jobs.universe_pruning import prune_universe

        stocks = [
            create_stock("BADSCORE.US", active=True),
            create_stock("GOODSTOCK.US", active=True),
        ]
        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_all_active = AsyncMock(return_value=stocks)
        mock_stock_repo.mark_inactive = AsyncMock()

        def get_scores_side_effect(symbol, months):
            if symbol == "BADSCORE.US":
                raise ValueError("Invalid score data")
            # Good stock with low scores (should be pruned)
            now = datetime.now()
            return [
                create_stock_score(
                    "GOODSTOCK.US", 0.30, (now - timedelta(days=60)).isoformat()
                ),
                create_stock_score(
                    "GOODSTOCK.US", 0.35, (now - timedelta(days=30)).isoformat()
                ),
            ]

        mock_score_repo = AsyncMock()
        mock_score_repo.get_recent_scores = AsyncMock(
            side_effect=get_scores_side_effect
        )

        with mock_universe_pruning_dependencies(
            mock_stock_repo=mock_stock_repo,
            mock_score_repo=mock_score_repo,
        ):
            await prune_universe()

        # Verify GOODSTOCK was pruned despite BADSCORE error
        mock_stock_repo.mark_inactive.assert_called_once_with("GOODSTOCK.US")
