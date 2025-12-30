"""Tests for score refresh job.

These tests validate the periodic stock scoring system that calculates
and stores scores for all active stocks.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestRefreshAllScores:
    """Test main score refresh function."""

    @pytest.mark.asyncio
    async def test_uses_file_lock(self):
        """Test that score refresh uses file locking."""
        from app.jobs.score_refresh import refresh_all_scores

        with patch("app.jobs.score_refresh.file_lock") as mock_lock:
            mock_lock.return_value.__aenter__ = AsyncMock()
            mock_lock.return_value.__aexit__ = AsyncMock()
            with patch(
                "app.jobs.score_refresh._refresh_all_scores_internal",
                new_callable=AsyncMock,
            ):
                await refresh_all_scores()

        mock_lock.assert_called_once_with("score_refresh", timeout=300.0)


class TestRefreshAllScoresInternal:
    """Test internal score refresh implementation."""

    @pytest.mark.asyncio
    async def test_handles_no_active_stocks(self):
        """Test graceful handling when no stocks to score."""
        from app.jobs.score_refresh import _refresh_all_scores_internal

        mock_db = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = []
        mock_db.config.execute.return_value = mock_cursor

        with patch("app.jobs.score_refresh.get_db_manager", return_value=mock_db):
            with patch("app.jobs.score_refresh.emit"):
                with patch("app.jobs.score_refresh.set_processing"):
                    with patch("app.jobs.score_refresh.clear_processing"):
                        await _refresh_all_scores_internal()

        # Should not crash when no stocks

    @pytest.mark.asyncio
    async def test_emits_events(self):
        """Test that events are emitted during score refresh."""
        from app.jobs.score_refresh import _refresh_all_scores_internal

        mock_db = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = []
        mock_db.config.execute.return_value = mock_cursor

        with patch("app.jobs.score_refresh.get_db_manager", return_value=mock_db):
            with patch("app.jobs.score_refresh.emit") as mock_emit:
                with patch("app.jobs.score_refresh.set_processing"):
                    with patch("app.jobs.score_refresh.clear_processing"):
                        await _refresh_all_scores_internal()

        # Should emit start and end events
        assert mock_emit.call_count >= 2

    @pytest.mark.asyncio
    async def test_skips_stocks_with_insufficient_data(self):
        """Test that stocks with insufficient data are skipped."""
        from app.jobs.score_refresh import _refresh_all_scores_internal

        mock_db = AsyncMock()
        mock_cursor = AsyncMock()
        # One stock with symbol, yahoo_symbol, country, industry
        mock_cursor.fetchall.return_value = [
            ("TEST.US", "TEST", "United States", "Consumer Electronics")
        ]
        mock_db.config.execute.return_value = mock_cursor
        mock_db.state = AsyncMock()
        mock_db.state.execute.return_value = mock_cursor

        with patch("app.jobs.score_refresh.get_db_manager", return_value=mock_db):
            with patch(
                "app.jobs.score_refresh._build_portfolio_context",
                new_callable=AsyncMock,
                return_value=MagicMock(),
            ):
                with patch(
                    "app.jobs.score_refresh._get_daily_prices",
                    new_callable=AsyncMock,
                    return_value=[],  # Insufficient data
                ):
                    with patch("app.jobs.score_refresh.emit"):
                        with patch("app.jobs.score_refresh.set_processing"):
                            with patch("app.jobs.score_refresh.clear_processing"):
                                await _refresh_all_scores_internal()

        # Should not crash with insufficient data

    @pytest.mark.asyncio
    async def test_handles_scoring_errors_gracefully(self):
        """Test that scoring errors don't crash the entire job."""
        from app.jobs.score_refresh import _refresh_all_scores_internal

        mock_db = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = [
            ("TEST.US", "TEST", "United States", "Consumer Electronics")
        ]
        mock_db.config.execute.return_value = mock_cursor
        mock_db.state = AsyncMock()
        mock_db.state.execute.return_value = mock_cursor

        with patch("app.jobs.score_refresh.get_db_manager", return_value=mock_db):
            with patch(
                "app.jobs.score_refresh._build_portfolio_context",
                new_callable=AsyncMock,
                side_effect=Exception("Test error"),
            ):
                with patch("app.jobs.score_refresh.emit"):
                    with patch("app.jobs.score_refresh.set_processing"):
                        with patch("app.jobs.score_refresh.clear_processing"):
                            with patch("app.jobs.score_refresh.set_error"):
                                await _refresh_all_scores_internal()

        # Should not raise, just log error


class TestBuildPortfolioContext:
    """Test portfolio context building for scoring."""

    @pytest.mark.asyncio
    async def test_builds_context_with_positions(self):
        """Test that portfolio context includes positions."""
        from app.jobs.score_refresh import _build_portfolio_context

        mock_db = MagicMock()

        # Mock state cursor (positions)
        mock_state_cursor = AsyncMock()
        mock_state_cursor.fetchall.return_value = [
            ("AAPL.US", 5000.0),
            ("MSFT.US", 3000.0),
        ]
        mock_db.state = AsyncMock()
        mock_db.state.execute.return_value = mock_state_cursor

        # Mock config cursor (stock data)
        mock_config_cursor = AsyncMock()
        mock_config_cursor.fetchall.return_value = []
        mock_db.config = AsyncMock()

        # Mock calculations cursor (scores)
        mock_calculations_cursor = AsyncMock()
        mock_calculations_cursor.fetchall.return_value = []
        mock_db.calculations = AsyncMock()
        mock_db.calculations.execute.return_value = mock_calculations_cursor

        # Setup execute to return different cursors based on query
        call_count = [0]

        async def mock_config_execute(*args):
            call_count[0] += 1
            return mock_config_cursor

        mock_db.config.execute = mock_config_execute

        # Mock repositories
        with (
            patch(
                "app.jobs.score_refresh.AllocationRepository"
            ) as mock_alloc_repo_class,
            patch(
                "app.jobs.score_refresh.GroupingRepository"
            ) as mock_grouping_repo_class,
        ):
            mock_alloc_repo = AsyncMock()
            mock_alloc_repo.get_country_group_targets = AsyncMock(return_value={})
            mock_alloc_repo.get_industry_group_targets = AsyncMock(return_value={})
            mock_alloc_repo_class.return_value = mock_alloc_repo

            mock_grouping_repo = AsyncMock()
            mock_grouping_repo.get_country_groups = AsyncMock(return_value={})
            mock_grouping_repo.get_industry_groups = AsyncMock(return_value={})
            mock_grouping_repo_class.return_value = mock_grouping_repo

            context = await _build_portfolio_context(mock_db)

        assert context.positions == {"AAPL.US": 5000.0, "MSFT.US": 3000.0}
        assert context.total_value == 8000.0

    @pytest.mark.asyncio
    async def test_builds_context_with_allocation_targets(self):
        """Test that portfolio context includes allocation targets."""
        from app.jobs.score_refresh import _build_portfolio_context

        mock_db = MagicMock()

        # Mock positions cursor
        mock_positions_cursor = AsyncMock()
        mock_positions_cursor.fetchall.return_value = []

        # Mock targets cursor
        mock_targets_cursor = AsyncMock()
        mock_targets_cursor.fetchall.return_value = [
            ("United States", 0.5, "country"),
            ("Germany", 0.3, "country"),
            ("Consumer Electronics", 0.2, "industry"),
        ]

        # Mock stock data cursor
        mock_stocks_cursor = AsyncMock()
        mock_stocks_cursor.fetchall.return_value = []

        # Mock scores cursor
        mock_scores_cursor = AsyncMock()
        mock_scores_cursor.fetchall.return_value = []

        mock_db.state = AsyncMock()
        mock_db.config = AsyncMock()
        mock_db.calculations = AsyncMock()

        # Setup execute to return different cursors
        async def mock_state_execute(*args):
            return mock_positions_cursor

        async def mock_config_execute(*args):
            return mock_stocks_cursor

        async def mock_calculations_execute(*args):
            return mock_scores_cursor

        mock_db.state.execute = mock_state_execute
        mock_db.config.execute = mock_config_execute
        mock_db.calculations.execute = mock_calculations_execute

        # Mock repositories
        with (
            patch(
                "app.jobs.score_refresh.AllocationRepository"
            ) as mock_alloc_repo_class,
            patch(
                "app.jobs.score_refresh.GroupingRepository"
            ) as mock_grouping_repo_class,
        ):
            mock_alloc_repo = AsyncMock()
            # get_country_group_targets returns group names, not individual countries
            mock_alloc_repo.get_country_group_targets = AsyncMock(
                return_value={"US": 0.5, "EU": 0.3}
            )
            mock_alloc_repo.get_industry_group_targets = AsyncMock(
                return_value={"Technology": 0.2}
            )
            mock_alloc_repo_class.return_value = mock_alloc_repo

            mock_grouping_repo = AsyncMock()
            mock_grouping_repo.get_country_groups = AsyncMock(return_value={})
            mock_grouping_repo.get_industry_groups = AsyncMock(return_value={})
            mock_grouping_repo_class.return_value = mock_grouping_repo

            context = await _build_portfolio_context(mock_db)

        assert context.country_weights == {"US": 0.5, "EU": 0.3}
        assert context.industry_weights == {"Technology": 0.2}


class TestGetDailyPrices:
    """Test daily price retrieval."""

    @pytest.mark.asyncio
    async def test_returns_local_data_if_sufficient(self):
        """Test that local data is returned when sufficient."""
        from app.jobs.score_refresh import _get_daily_prices

        mock_db = MagicMock()
        mock_history_db = AsyncMock()
        mock_cursor = AsyncMock()
        # 50+ days of data
        mock_cursor.fetchall.return_value = [
            ("2024-01-01", 100, 105, 95, 102, 1000000)
        ] * 50
        mock_history_db.execute.return_value = mock_cursor
        mock_db.history = AsyncMock(return_value=mock_history_db)

        prices = await _get_daily_prices(mock_db, "TEST.US", "TEST")

        assert len(prices) == 50

    @pytest.mark.asyncio
    async def test_fetches_from_yahoo_if_insufficient(self):
        """Test that Yahoo is called when local data is insufficient."""
        from app.jobs.score_refresh import _get_daily_prices

        mock_db = MagicMock()
        mock_history_db = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = [
            ("2024-01-01", 100, 105, 95, 102, 1000000)
        ] * 10  # Only 10 days
        mock_history_db.execute.return_value = mock_cursor
        mock_db.history = AsyncMock(return_value=mock_history_db)

        # Mock transaction context manager
        mock_history_db.transaction = MagicMock()
        mock_history_db.transaction.return_value.__aenter__ = AsyncMock()
        mock_history_db.transaction.return_value.__aexit__ = AsyncMock()

        mock_price = MagicMock()
        mock_price.date = MagicMock()
        mock_price.date.strftime = MagicMock(return_value="2024-01-01")
        mock_price.open = 100
        mock_price.high = 105
        mock_price.low = 95
        mock_price.close = 102
        mock_price.volume = 1000000

        with patch(
            "app.jobs.score_refresh.yahoo.get_historical_prices",
            return_value=[mock_price],
        ):
            prices = await _get_daily_prices(mock_db, "TEST.US", "TEST")

        assert prices is not None


class TestGetMonthlyPrices:
    """Test monthly price retrieval."""

    @pytest.mark.asyncio
    async def test_returns_local_data_if_sufficient(self):
        """Test that local monthly data is returned when sufficient."""
        from app.jobs.score_refresh import _get_monthly_prices

        mock_db = MagicMock()
        mock_history_db = AsyncMock()
        mock_cursor = AsyncMock()
        # 12+ months of data
        mock_cursor.fetchall.return_value = [("2024-01", 100.0)] * 12
        mock_history_db.execute.return_value = mock_cursor
        mock_db.history = AsyncMock(return_value=mock_history_db)

        prices = await _get_monthly_prices(mock_db, "TEST.US", "TEST")

        assert len(prices) == 12
        assert prices[0]["year_month"] == "2024-01"

    @pytest.mark.asyncio
    async def test_aggregates_from_yahoo_if_insufficient(self):
        """Test that Yahoo data is aggregated to monthly if local is insufficient."""
        from app.jobs.score_refresh import _get_monthly_prices

        mock_db = MagicMock()
        mock_history_db = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = [("2024-01", 100.0)] * 5  # Only 5 months
        mock_history_db.execute.return_value = mock_cursor
        mock_db.history = AsyncMock(return_value=mock_history_db)

        # Mock transaction
        mock_history_db.transaction = MagicMock()
        mock_history_db.transaction.return_value.__aenter__ = AsyncMock()
        mock_history_db.transaction.return_value.__aexit__ = AsyncMock()

        with patch(
            "app.jobs.score_refresh.yahoo.get_historical_prices", return_value=[]
        ):
            prices = await _get_monthly_prices(mock_db, "TEST.US", "TEST")

        assert prices == []  # Empty because Yahoo returned nothing
