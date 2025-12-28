"""Tests for stock discovery job.

These tests validate the stock discovery job logic for finding and adding new stocks.
CRITICAL: Tests catch real bugs that would cause poor stock selection or limit violations.
"""

from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.scoring.models import CalculatedStockScore


def create_candidate(
    symbol: str, exchange: str = "usa", volume: float = 5000000.0
) -> dict:
    """Helper to create mock candidate from discovery service."""
    return {
        "symbol": symbol,
        "exchange": exchange,
        "volume": volume,
        "name": f"{symbol} Inc.",
        "country": "US" if exchange == "usa" else "EU",
    }


def create_mock_score(symbol: str, total_score: float) -> CalculatedStockScore:
    """Helper to create mock CalculatedStockScore."""
    from datetime import datetime

    return CalculatedStockScore(
        symbol=symbol,
        total_score=total_score,
        volatility=0.2,
        calculated_at=datetime.now(),
        group_scores={},
        sub_scores={},
    )


@contextmanager
def mock_stock_discovery_dependencies(
    mock_stock_repo=None,
    mock_settings_repo=None,
    mock_discovery_service=None,
    mock_scoring_service=None,
):
    """Context manager to set up all mocks for stock discovery job."""
    if mock_stock_repo is None:
        mock_stock_repo = AsyncMock()
    if mock_settings_repo is None:
        mock_settings_repo = AsyncMock()
    if mock_discovery_service is None:
        mock_discovery_service = MagicMock()
    if mock_scoring_service is None:
        mock_scoring_service = AsyncMock()

    # Default settings - only set if not already configured by test
    if mock_settings_repo.get_float.side_effect is None:
        async def get_float(key, default):
            defaults = {
                "stock_discovery_enabled": 1.0,
                "stock_discovery_score_threshold": 0.75,
                "stock_discovery_max_per_month": 2.0,
                "stock_discovery_require_manual_review": 0.0,
            }
            return defaults.get(key, default)

        mock_settings_repo.get_float = AsyncMock(side_effect=get_float)

    # Always set get_by_symbol to return None to allow stock creation
    # Tests should explicitly set this if they need different behavior
    mock_stock_repo.get_by_symbol = AsyncMock(return_value=None)

    # Mock db_manager and tradernet_client
    mock_db_manager = MagicMock()
    mock_tradernet_client = MagicMock()
    mock_score_repo = MagicMock()

    with (
        patch("app.jobs.stock_discovery.StockRepository", return_value=mock_stock_repo),
        patch(
            "app.jobs.stock_discovery.SettingsRepository",
            return_value=mock_settings_repo,
        ),
        patch(
            "app.jobs.stock_discovery.StockDiscoveryService",
            return_value=mock_discovery_service,
        ),
        patch(
            "app.jobs.stock_discovery.ScoringService", return_value=mock_scoring_service
        ),
        patch(
            "app.jobs.stock_discovery.ScoreRepository", return_value=mock_score_repo
        ),
        patch(
            "app.jobs.stock_discovery.get_db_manager", return_value=mock_db_manager
        ),
        patch(
            "app.jobs.stock_discovery.get_tradernet_client",
            return_value=mock_tradernet_client,
        ),
    ):
        yield {
            "stock_repo": mock_stock_repo,
            "settings_repo": mock_settings_repo,
            "discovery_service": mock_discovery_service,
            "scoring_service": mock_scoring_service,
        }


class TestScoringAndFiltering:
    """Test scoring and filtering logic."""

    @pytest.mark.asyncio
    async def test_adds_stock_when_score_above_threshold(self):
        """Test that stock is added when score is above threshold.

        Bug caught: High-quality stocks not added.
        """
        from app.jobs.stock_discovery import discover_new_stocks

        candidates = [create_candidate("AAPL")]
        score = create_mock_score("AAPL", 0.80)  # Above 0.75 threshold

        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_all_active = AsyncMock(return_value=[])
        mock_stock_repo.create = AsyncMock()

        mock_discovery_service = MagicMock()
        mock_discovery_service.discover_candidates = AsyncMock(return_value=candidates)

        mock_scoring_service = AsyncMock()
        mock_scoring_service.calculate_and_save_score = AsyncMock(return_value=score)

        with mock_stock_discovery_dependencies(
            mock_stock_repo=mock_stock_repo,
            mock_discovery_service=mock_discovery_service,
            mock_scoring_service=mock_scoring_service,
        ):
            await discover_new_stocks()

        # Verify stock was added
        mock_stock_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_stock_when_score_below_threshold(self):
        """Test that stock is skipped when score is below threshold.

        Bug caught: Low-quality stocks added.
        """
        from app.jobs.stock_discovery import discover_new_stocks

        candidates = [create_candidate("AAPL")]
        score = create_mock_score("AAPL", 0.70)  # Below 0.75 threshold

        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_all_active = AsyncMock(return_value=[])

        mock_discovery_service = MagicMock()
        mock_discovery_service.discover_candidates = AsyncMock(return_value=candidates)

        mock_scoring_service = AsyncMock()
        mock_scoring_service.calculate_and_save_score = AsyncMock(return_value=score)

        with mock_stock_discovery_dependencies(
            mock_stock_repo=mock_stock_repo,
            mock_discovery_service=mock_discovery_service,
            mock_scoring_service=mock_scoring_service,
        ):
            await discover_new_stocks()

        # Verify stock was NOT added
        mock_stock_repo.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_exactly_at_score_threshold_adds_stock(self):
        """Test that stock is added when score is exactly at threshold.

        Bug caught: Off-by-one at threshold.
        """
        from app.jobs.stock_discovery import discover_new_stocks

        candidates = [create_candidate("AAPL")]
        score = create_mock_score("AAPL", 0.75)  # Exactly at threshold

        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_all_active = AsyncMock(return_value=[])
        mock_stock_repo.create = AsyncMock()

        mock_discovery_service = MagicMock()
        mock_discovery_service.discover_candidates = AsyncMock(return_value=candidates)

        mock_scoring_service = AsyncMock()
        mock_scoring_service.calculate_and_save_score = AsyncMock(return_value=score)

        with mock_stock_discovery_dependencies(
            mock_stock_repo=mock_stock_repo,
            mock_discovery_service=mock_discovery_service,
            mock_scoring_service=mock_scoring_service,
        ):
            await discover_new_stocks()

        # Verify stock was added (>= threshold)
        mock_stock_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_scores_all_candidates_before_filtering(self):
        """Test that all candidates are scored before filtering.

        Bug caught: Filters before scoring, misses opportunities.
        """
        from app.jobs.stock_discovery import discover_new_stocks

        candidates = [
            create_candidate("AAPL"),
            create_candidate("MSFT"),
            create_candidate("GOOGL"),
        ]
        scores = [
            create_mock_score("AAPL", 0.80),
            create_mock_score("MSFT", 0.70),  # Below threshold
            create_mock_score("GOOGL", 0.85),
        ]

        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_all_active = AsyncMock(return_value=[])

        mock_discovery_service = MagicMock()
        mock_discovery_service.discover_candidates = AsyncMock(return_value=candidates)

        mock_scoring_service = AsyncMock()
        mock_scoring_service.calculate_and_save_score = AsyncMock(side_effect=scores)

        with mock_stock_discovery_dependencies(
            mock_stock_repo=mock_stock_repo,
            mock_discovery_service=mock_discovery_service,
            mock_scoring_service=mock_scoring_service,
        ):
            await discover_new_stocks()

        # Verify all candidates were scored
        assert mock_scoring_service.calculate_and_save_score.call_count == 3


class TestMonthlyLimit:
    """Test monthly limit enforcement."""

    @pytest.mark.asyncio
    async def test_enforces_max_per_month_limit(self):
        """Test that max_per_month limit is enforced.

        Bug caught: Too many stocks added, universe grows too fast.
        """
        from app.jobs.stock_discovery import discover_new_stocks

        # 5 candidates, but limit is 2
        candidates = [
            create_candidate("AAPL"),
            create_candidate("MSFT"),
            create_candidate("GOOGL"),
            create_candidate("AMZN"),
            create_candidate("META"),
        ]
        scores = [create_mock_score(c["symbol"], 0.80) for c in candidates]

        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_all_active = AsyncMock(return_value=[])
        mock_stock_repo.create = AsyncMock()

        mock_discovery_service = MagicMock()
        mock_discovery_service.discover_candidates = AsyncMock(return_value=candidates)

        mock_scoring_service = AsyncMock()
        mock_scoring_service.calculate_and_save_score = AsyncMock(side_effect=scores)

        mock_settings_repo = AsyncMock()

        async def get_float(key, default):
            return {
                "stock_discovery_enabled": 1.0,
                "stock_discovery_score_threshold": 0.75,
                "stock_discovery_max_per_month": 2.0,  # Limit to 2
                "stock_discovery_require_manual_review": 0.0,
            }.get(key, default)

        mock_settings_repo.get_float = AsyncMock(side_effect=get_float)

        with mock_stock_discovery_dependencies(
            mock_stock_repo=mock_stock_repo,
            mock_settings_repo=mock_settings_repo,
            mock_discovery_service=mock_discovery_service,
            mock_scoring_service=mock_scoring_service,
        ):
            await discover_new_stocks()

        # Verify only 2 stocks were added (respecting limit)
        assert mock_stock_repo.create.call_count == 2

    @pytest.mark.asyncio
    async def test_adds_best_stocks_when_limit_reached(self):
        """Test that best stocks are added when limit is reached.

        Bug caught: Adds first N instead of best N.
        """
        from app.jobs.stock_discovery import discover_new_stocks

        candidates = [
            create_candidate("LOW"),
            create_candidate("HIGH"),
            create_candidate("MED"),
        ]
        scores = [
            create_mock_score("LOW", 0.76),  # Just above threshold
            create_mock_score("HIGH", 0.95),  # Best score
            create_mock_score("MED", 0.80),  # Medium score
        ]

        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_all_active = AsyncMock(return_value=[])
        mock_stock_repo.create = AsyncMock()

        mock_discovery_service = MagicMock()
        mock_discovery_service.discover_candidates = AsyncMock(return_value=candidates)

        mock_scoring_service = AsyncMock()
        mock_scoring_service.calculate_and_save_score = AsyncMock(side_effect=scores)

        mock_settings_repo = AsyncMock()

        async def get_float(key, default):
            return {
                "stock_discovery_enabled": 1.0,
                "stock_discovery_score_threshold": 0.75,
                "stock_discovery_max_per_month": 2.0,  # Limit to 2
                "stock_discovery_require_manual_review": 0.0,
            }.get(key, default)

        mock_settings_repo.get_float = AsyncMock(side_effect=get_float)

        with mock_stock_discovery_dependencies(
            mock_stock_repo=mock_stock_repo,
            mock_settings_repo=mock_settings_repo,
            mock_discovery_service=mock_discovery_service,
            mock_scoring_service=mock_scoring_service,
        ):
            await discover_new_stocks()

        # Verify best stocks were added (HIGH and MED, not LOW)
        create_calls = [
            call[0][0].symbol for call in mock_stock_repo.create.call_args_list
        ]
        assert "HIGH" in create_calls
        assert "MED" in create_calls
        assert "LOW" not in create_calls


class TestManualReview:
    """Test manual review flagging."""

    @pytest.mark.asyncio
    async def test_auto_adds_when_require_manual_review_false(self):
        """Test that stocks are auto-added when require_manual_review is false.

        Bug caught: Flags when should auto-add.
        """
        from app.jobs.stock_discovery import discover_new_stocks

        candidates = [create_candidate("AAPL")]
        score = create_mock_score("AAPL", 0.80)

        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_all_active = AsyncMock(return_value=[])
        mock_stock_repo.create = AsyncMock()

        mock_discovery_service = MagicMock()
        mock_discovery_service.discover_candidates = AsyncMock(return_value=candidates)

        mock_scoring_service = AsyncMock()
        mock_scoring_service.calculate_and_save_score = AsyncMock(return_value=score)

        mock_settings_repo = AsyncMock()

        async def get_float(key, default):
            return {
                "stock_discovery_enabled": 1.0,
                "stock_discovery_score_threshold": 0.75,
                "stock_discovery_max_per_month": 2.0,
                "stock_discovery_require_manual_review": 0.0,  # Auto-add
            }.get(key, default)

        mock_settings_repo.get_float = AsyncMock(side_effect=get_float)

        with mock_stock_discovery_dependencies(
            mock_stock_repo=mock_stock_repo,
            mock_settings_repo=mock_settings_repo,
            mock_discovery_service=mock_discovery_service,
            mock_scoring_service=mock_scoring_service,
        ):
            await discover_new_stocks()

        # Verify stock was added (not flagged for review)
        mock_stock_repo.create.assert_called_once()


class TestStateVerification:
    """Test state verification and database consistency."""

    @pytest.mark.asyncio
    async def test_adds_stock_to_database(self):
        """Test that stock is added to database.

        Bug caught: In-memory state doesn't match database.
        """
        from app.jobs.stock_discovery import discover_new_stocks

        candidates = [create_candidate("AAPL")]
        score = create_mock_score("AAPL", 0.80)

        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_all_active = AsyncMock(return_value=[])
        mock_stock_repo.create = AsyncMock()

        mock_discovery_service = MagicMock()
        mock_discovery_service.discover_candidates = AsyncMock(return_value=candidates)

        mock_scoring_service = AsyncMock()
        mock_scoring_service.calculate_and_save_score = AsyncMock(return_value=score)

        with mock_stock_discovery_dependencies(
            mock_stock_repo=mock_stock_repo,
            mock_discovery_service=mock_discovery_service,
            mock_scoring_service=mock_scoring_service,
        ):
            await discover_new_stocks()

        # Verify create was called (database write)
        mock_stock_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_marks_stock_as_active(self):
        """Test that stock is marked as active when added.

        Bug caught: Stock added but inactive.
        """
        from app.jobs.stock_discovery import discover_new_stocks

        candidates = [create_candidate("AAPL")]
        score = create_mock_score("AAPL", 0.80)

        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_all_active = AsyncMock(return_value=[])
        mock_stock_repo.create = AsyncMock()

        mock_discovery_service = MagicMock()
        mock_discovery_service.discover_candidates = AsyncMock(return_value=candidates)

        mock_scoring_service = AsyncMock()
        mock_scoring_service.calculate_and_save_score = AsyncMock(return_value=score)

        with mock_stock_discovery_dependencies(
            mock_stock_repo=mock_stock_repo,
            mock_discovery_service=mock_discovery_service,
            mock_scoring_service=mock_scoring_service,
        ):
            await discover_new_stocks()

        # Verify stock was created with active=True
        create_call = mock_stock_repo.create.call_args[0][0]
        assert create_call.active is True


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_zero_candidates_handles_gracefully(self):
        """Test that zero candidates are handled gracefully.

        Bug caught: Crashes on empty list.
        """
        from app.jobs.stock_discovery import discover_new_stocks

        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_all_active = AsyncMock(return_value=[])

        mock_discovery_service = MagicMock()
        mock_discovery_service.discover_candidates = AsyncMock(return_value=[])

        mock_scoring_service = AsyncMock()

        with mock_stock_discovery_dependencies(
            mock_stock_repo=mock_stock_repo,
            mock_discovery_service=mock_discovery_service,
            mock_scoring_service=mock_scoring_service,
        ):
            # Should not raise exception
            await discover_new_stocks()

        # Verify no stocks were added
        mock_stock_repo.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_all_candidates_below_threshold_adds_none(self):
        """Test that no stocks are added when all below threshold.

        Bug caught: Adds low-quality stocks.
        """
        from app.jobs.stock_discovery import discover_new_stocks

        candidates = [
            create_candidate("LOW1"),
            create_candidate("LOW2"),
        ]
        scores = [
            create_mock_score("LOW1", 0.70),  # Below threshold
            create_mock_score("LOW2", 0.65),  # Below threshold
        ]

        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_all_active = AsyncMock(return_value=[])

        mock_discovery_service = MagicMock()
        mock_discovery_service.discover_candidates = AsyncMock(return_value=candidates)

        mock_scoring_service = AsyncMock()
        mock_scoring_service.calculate_and_save_score = AsyncMock(side_effect=scores)

        with mock_stock_discovery_dependencies(
            mock_stock_repo=mock_stock_repo,
            mock_discovery_service=mock_discovery_service,
            mock_scoring_service=mock_scoring_service,
        ):
            await discover_new_stocks()

        # Verify no stocks were added
        mock_stock_repo.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_scoring_failure_skips_candidate_continues(self):
        """Test that scoring failure skips candidate but continues.

        Bug caught: One failure blocks all discovery.
        """
        from app.jobs.stock_discovery import discover_new_stocks

        candidates = [
            create_candidate("FAIL"),
            create_candidate("SUCCESS"),
        ]
        scores = [
            None,  # Scoring failed
            create_mock_score("SUCCESS", 0.80),
        ]

        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_all_active = AsyncMock(return_value=[])
        mock_stock_repo.create = AsyncMock()

        mock_discovery_service = MagicMock()
        mock_discovery_service.discover_candidates = AsyncMock(return_value=candidates)

        mock_scoring_service = AsyncMock()
        mock_scoring_service.calculate_and_save_score = AsyncMock(side_effect=scores)

        with mock_stock_discovery_dependencies(
            mock_stock_repo=mock_stock_repo,
            mock_discovery_service=mock_discovery_service,
            mock_scoring_service=mock_scoring_service,
        ):
            await discover_new_stocks()

        # Verify SUCCESS stock was added (failure didn't block)
        assert mock_stock_repo.create.call_count == 1


class TestErrorHandling:
    """Test error handling."""

    @pytest.mark.asyncio
    async def test_discovery_service_failure_handles_gracefully(self):
        """Test that discovery service failure is handled gracefully.

        Bug caught: Job crashes on service failure.
        """
        from app.jobs.stock_discovery import discover_new_stocks

        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_all_active = AsyncMock(return_value=[])

        mock_discovery_service = MagicMock()
        mock_discovery_service.discover_candidates = AsyncMock(
            side_effect=Exception("Discovery service error")
        )

        mock_scoring_service = AsyncMock()

        with mock_stock_discovery_dependencies(
            mock_stock_repo=mock_stock_repo,
            mock_discovery_service=mock_discovery_service,
            mock_scoring_service=mock_scoring_service,
        ):
            # Should not raise exception
            await discover_new_stocks()

        # Verify no stocks were added
        mock_stock_repo.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_respects_enabled_flag(self):
        """Test that job respects enabled flag.

        Bug caught: Job runs when disabled.
        """
        from app.jobs.stock_discovery import discover_new_stocks

        mock_stock_repo = AsyncMock()
        mock_discovery_service = MagicMock()
        mock_scoring_service = AsyncMock()

        mock_settings_repo = AsyncMock()

        async def get_float(key, default):
            return {
                "stock_discovery_enabled": 0.0,  # Disabled
            }.get(key, default)

        mock_settings_repo.get_float = AsyncMock(side_effect=get_float)

        with mock_stock_discovery_dependencies(
            mock_stock_repo=mock_stock_repo,
            mock_settings_repo=mock_settings_repo,
            mock_discovery_service=mock_discovery_service,
            mock_scoring_service=mock_scoring_service,
        ):
            await discover_new_stocks()

        # Verify discovery service was NOT called
        mock_discovery_service.discover_candidates.assert_not_called()
