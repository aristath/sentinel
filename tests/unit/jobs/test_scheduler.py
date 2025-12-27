"""Tests for job scheduler.

These tests validate job scheduling, failure tracking,
and scheduler management.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestGetAllJobSettings:
    """Test getting job settings from database."""

    @pytest.mark.asyncio
    async def test_returns_job_settings(self):
        """Test that job settings are returned."""
        from app.jobs.scheduler import _get_all_job_settings

        mock_settings = {
            "job_portfolio_sync_minutes": 5,
            "job_trade_sync_minutes": 10,
            "job_price_sync_minutes": 15,
            "job_score_refresh_minutes": 30,
            "job_rebalance_check_minutes": 5,
            "job_cash_flow_sync_hour": 22,
            "job_historical_sync_hour": 23,
            "job_maintenance_hour": 3,
        }

        with (
            patch(
                "app.infrastructure.dependencies.get_settings_repository"
            ) as mock_get_repo,
            patch(
                "app.api.settings.get_job_settings",
                new_callable=AsyncMock,
            ) as mock_get_settings,
        ):
            mock_get_settings.return_value = mock_settings

            result = await _get_all_job_settings()

            assert result == mock_settings
            mock_get_repo.assert_called_once()


class TestInitScheduler:
    """Test scheduler initialization."""

    @pytest.mark.asyncio
    async def test_creates_scheduler(self):
        """Test that scheduler is created."""
        from app.jobs.scheduler import init_scheduler

        mock_settings = {
            "job_portfolio_sync_minutes": 5,
            "job_trade_sync_minutes": 10,
            "job_price_sync_minutes": 15,
            "job_score_refresh_minutes": 30,
            "job_rebalance_check_minutes": 5,
            "job_cash_flow_sync_hour": 22,
            "job_historical_sync_hour": 23,
            "job_maintenance_hour": 3,
        }

        with (
            patch("app.jobs.scheduler._get_all_job_settings") as mock_get_settings,
            patch("app.jobs.scheduler.AsyncIOScheduler") as mock_scheduler_class,
        ):
            mock_get_settings.return_value = mock_settings
            mock_scheduler = MagicMock()
            mock_scheduler_class.return_value = mock_scheduler

            result = await init_scheduler()

            mock_scheduler_class.assert_called_once()
            # Should add listener and multiple jobs
            mock_scheduler.add_listener.assert_called_once()
            assert mock_scheduler.add_job.call_count >= 10

    @pytest.mark.asyncio
    async def test_adds_all_job_types(self):
        """Test that all job types are added."""
        from app.jobs.scheduler import init_scheduler

        mock_settings = {
            "job_portfolio_sync_minutes": 5,
            "job_trade_sync_minutes": 10,
            "job_price_sync_minutes": 15,
            "job_score_refresh_minutes": 30,
            "job_rebalance_check_minutes": 5,
            "job_cash_flow_sync_hour": 22,
            "job_historical_sync_hour": 23,
            "job_maintenance_hour": 3,
        }

        with (
            patch("app.jobs.scheduler._get_all_job_settings") as mock_get_settings,
            patch("app.jobs.scheduler.AsyncIOScheduler") as mock_scheduler_class,
        ):
            mock_get_settings.return_value = mock_settings
            mock_scheduler = MagicMock()
            mock_scheduler_class.return_value = mock_scheduler

            await init_scheduler()

            # Verify expected job IDs are added
            job_ids = [call.kwargs["id"] for call in mock_scheduler.add_job.call_args_list]
            expected_jobs = [
                "portfolio_sync",
                "trade_sync",
                "price_sync",
                "cash_rebalance_check",
                "score_refresh",
                "cash_flow_sync",
                "historical_data_sync",
                "metrics_calculation",
                "daily_maintenance",
                "weekly_maintenance",
                "health_check",
                "ticker_text_generator",
            ]
            for job_id in expected_jobs:
                assert job_id in job_ids


class TestRescheduleAllJobs:
    """Test rescheduling all jobs."""

    @pytest.mark.asyncio
    async def test_skips_when_no_scheduler(self):
        """Test that reschedule is skipped when scheduler not initialized."""
        from app.jobs.scheduler import reschedule_all_jobs

        with patch("app.jobs.scheduler.scheduler", None):
            # Should not raise
            await reschedule_all_jobs()

    @pytest.mark.asyncio
    async def test_reschedules_all_jobs(self):
        """Test that all jobs are rescheduled."""
        from app.jobs.scheduler import reschedule_all_jobs

        mock_settings = {
            "job_portfolio_sync_minutes": 10,
            "job_trade_sync_minutes": 15,
            "job_price_sync_minutes": 20,
            "job_score_refresh_minutes": 45,
            "job_rebalance_check_minutes": 10,
            "job_cash_flow_sync_hour": 21,
            "job_historical_sync_hour": 22,
            "job_maintenance_hour": 4,
        }

        mock_scheduler = MagicMock()

        with (
            patch("app.jobs.scheduler.scheduler", mock_scheduler),
            patch("app.jobs.scheduler._get_all_job_settings") as mock_get_settings,
        ):
            mock_get_settings.return_value = mock_settings

            await reschedule_all_jobs()

            # Should reschedule multiple jobs
            assert mock_scheduler.reschedule_job.call_count >= 10


class TestStartScheduler:
    """Test starting the scheduler."""

    def test_starts_scheduler_when_not_running(self):
        """Test starting scheduler when not already running."""
        from app.jobs.scheduler import start_scheduler

        mock_scheduler = MagicMock()
        mock_scheduler.running = False

        with patch("app.jobs.scheduler.scheduler", mock_scheduler):
            start_scheduler()

            mock_scheduler.start.assert_called_once()

    def test_skips_when_already_running(self):
        """Test that start is skipped when already running."""
        from app.jobs.scheduler import start_scheduler

        mock_scheduler = MagicMock()
        mock_scheduler.running = True

        with patch("app.jobs.scheduler.scheduler", mock_scheduler):
            start_scheduler()

            mock_scheduler.start.assert_not_called()

    def test_skips_when_no_scheduler(self):
        """Test that start is skipped when scheduler not initialized."""
        from app.jobs.scheduler import start_scheduler

        with patch("app.jobs.scheduler.scheduler", None):
            # Should not raise
            start_scheduler()


class TestStopScheduler:
    """Test stopping the scheduler."""

    def test_stops_scheduler_when_running(self):
        """Test stopping scheduler when running."""
        from app.jobs.scheduler import stop_scheduler

        mock_scheduler = MagicMock()
        mock_scheduler.running = True

        with patch("app.jobs.scheduler.scheduler", mock_scheduler):
            stop_scheduler()

            mock_scheduler.shutdown.assert_called_once()

    def test_skips_when_not_running(self):
        """Test that stop is skipped when not running."""
        from app.jobs.scheduler import stop_scheduler

        mock_scheduler = MagicMock()
        mock_scheduler.running = False

        with patch("app.jobs.scheduler.scheduler", mock_scheduler):
            stop_scheduler()

            mock_scheduler.shutdown.assert_not_called()

    def test_skips_when_no_scheduler(self):
        """Test that stop is skipped when scheduler not initialized."""
        from app.jobs.scheduler import stop_scheduler

        with patch("app.jobs.scheduler.scheduler", None):
            # Should not raise
            stop_scheduler()


class TestGetScheduler:
    """Test getting the scheduler instance."""

    def test_returns_scheduler(self):
        """Test that scheduler is returned."""
        from app.jobs.scheduler import get_scheduler

        mock_scheduler = MagicMock()

        with patch("app.jobs.scheduler.scheduler", mock_scheduler):
            result = get_scheduler()

            assert result == mock_scheduler

    def test_returns_none_when_not_initialized(self):
        """Test that None is returned when not initialized."""
        from app.jobs.scheduler import get_scheduler

        with patch("app.jobs.scheduler.scheduler", None):
            result = get_scheduler()

            assert result is None


class TestJobListener:
    """Test job event listener."""

    def test_tracks_job_failure(self):
        """Test that job failures are tracked."""
        from app.jobs.scheduler import _job_failures, job_listener

        # Clear any existing failures
        _job_failures.clear()

        # Create a mock event with an exception
        event = MagicMock()
        event.job_id = "test_job"
        event.exception = Exception("Test error")

        with patch("app.config.settings") as mock_settings:
            mock_settings.job_failure_window_hours = 1
            mock_settings.job_failure_threshold = 3
            job_listener(event)

        assert "test_job" in _job_failures
        assert len(_job_failures["test_job"]) == 1

    def test_clears_failures_on_success(self):
        """Test that failures are cleared on successful execution."""
        from app.jobs.scheduler import _job_failures, job_listener

        # Add some failures
        _job_failures["test_job"] = [datetime.now()]

        # Create a mock event without exception
        event = MagicMock()
        event.job_id = "test_job"
        event.exception = None

        job_listener(event)

        assert len(_job_failures["test_job"]) == 0

    def test_removes_old_failures(self):
        """Test that old failures outside window are removed."""
        from app.jobs.scheduler import _job_failures, job_listener

        _job_failures.clear()

        # Add an old failure
        old_time = datetime.now() - timedelta(hours=2)
        _job_failures["test_job"] = [old_time]

        # Create new failure
        event = MagicMock()
        event.job_id = "test_job"
        event.exception = Exception("New error")

        with patch("app.config.settings") as mock_settings:
            mock_settings.job_failure_window_hours = 1
            mock_settings.job_failure_threshold = 3
            job_listener(event)

        # Old failure should be removed, only new one remains
        assert len(_job_failures["test_job"]) == 1


class TestGetJobHealthStatus:
    """Test job health status retrieval."""

    def test_returns_job_status(self):
        """Test that job status is returned correctly."""
        from app.jobs.scheduler import get_job_health_status

        with patch("app.jobs.scheduler.scheduler") as mock_scheduler:
            mock_job = MagicMock()
            mock_job.id = "portfolio_sync"
            mock_job.next_run_time = datetime.now() + timedelta(minutes=5)

            mock_scheduler.get_jobs.return_value = [mock_job]

            result = get_job_health_status()

        assert "portfolio_sync" in result
        assert "next_run" in result["portfolio_sync"]

    def test_handles_no_scheduler(self):
        """Test handling when scheduler is not initialized."""
        from app.jobs.scheduler import get_job_health_status

        with patch("app.jobs.scheduler.scheduler", None):
            result = get_job_health_status()

        assert result == {}
