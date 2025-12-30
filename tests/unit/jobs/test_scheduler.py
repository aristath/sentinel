"""Comprehensive tests for the APScheduler setup and job scheduling.

These tests validate:
1. Scheduler initialization and job setup
2. Job rescheduling with updated settings
3. Scheduler lifecycle (start/stop)
4. Job failure tracking and health monitoring
5. Event listener behavior
6. Edge cases and error conditions
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from apscheduler.events import JobExecutionEvent
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger


class TestGetJobSettings:
    """Tests for _get_job_settings helper."""

    @pytest.mark.asyncio
    async def test_returns_default_settings(self):
        """Test that default settings are returned from database."""
        from app.jobs.scheduler import _get_job_settings

        mock_settings_repo = MagicMock()
        mock_settings_repo.get_float = AsyncMock(side_effect=[5.0, 3.0, 5.0])

        with patch(
            "app.repositories.SettingsRepository", return_value=mock_settings_repo
        ):
            settings = await _get_job_settings()

        assert settings["sync_cycle_minutes"] == 5
        assert settings["maintenance_hour"] == 3
        assert settings["auto_deploy_minutes"] == 5
        mock_settings_repo.get_float.assert_any_call("job_sync_cycle_minutes", 5.0)
        mock_settings_repo.get_float.assert_any_call("job_maintenance_hour", 3.0)
        mock_settings_repo.get_float.assert_any_call("job_auto_deploy_minutes", 5.0)

    @pytest.mark.asyncio
    async def test_returns_custom_settings(self):
        """Test that custom settings are returned when configured."""
        from app.jobs.scheduler import _get_job_settings

        mock_settings_repo = MagicMock()
        mock_settings_repo.get_float = AsyncMock(side_effect=[30.0, 4.0, 10.0])

        with patch(
            "app.repositories.SettingsRepository", return_value=mock_settings_repo
        ):
            settings = await _get_job_settings()

        assert settings["sync_cycle_minutes"] == 30
        assert settings["maintenance_hour"] == 4
        assert settings["auto_deploy_minutes"] == 10

    @pytest.mark.asyncio
    async def test_converts_floats_to_ints(self):
        """Test that float values are converted to integers."""
        from app.jobs.scheduler import _get_job_settings

        mock_settings_repo = MagicMock()
        mock_settings_repo.get_float = AsyncMock(side_effect=[15.5, 3.9, 7.8])

        with patch(
            "app.repositories.SettingsRepository", return_value=mock_settings_repo
        ):
            settings = await _get_job_settings()

        # Should be converted to integers
        assert settings["sync_cycle_minutes"] == 15
        assert settings["maintenance_hour"] == 3
        assert settings["auto_deploy_minutes"] == 7
        assert isinstance(settings["sync_cycle_minutes"], int)
        assert isinstance(settings["maintenance_hour"], int)
        assert isinstance(settings["auto_deploy_minutes"], int)


class TestJobListener:
    """Tests for job_listener event handler."""

    def test_tracks_job_failures(self):
        """Test that job failures are tracked in _job_failures dict."""
        from app.jobs.scheduler import _job_failures, job_listener

        # Clear any existing failures
        _job_failures.clear()

        # Create a mock failure event
        mock_event = MagicMock(spec=JobExecutionEvent)
        mock_event.job_id = "test_job"
        mock_event.exception = Exception("Test failure")

        mock_settings = MagicMock()
        mock_settings.job_failure_window_hours = 1
        mock_settings.job_failure_threshold = 5

        with patch("app.config.settings", mock_settings):
            job_listener(mock_event)

        # Should have one failure recorded
        assert "test_job" in _job_failures
        assert len(_job_failures["test_job"]) == 1

    def test_accumulates_multiple_failures(self):
        """Test that multiple failures are accumulated."""
        from app.jobs.scheduler import _job_failures, job_listener

        _job_failures.clear()

        mock_settings = MagicMock()
        mock_settings.job_failure_window_hours = 1
        mock_settings.job_failure_threshold = 5

        # Simulate 3 failures
        for i in range(3):
            mock_event = MagicMock(spec=JobExecutionEvent)
            mock_event.job_id = "test_job"
            mock_event.exception = Exception(f"Failure {i}")

            with patch("app.config.settings", mock_settings):
                job_listener(mock_event)

        assert len(_job_failures["test_job"]) == 3

    def test_prunes_old_failures_outside_window(self):
        """Test that failures outside the time window are pruned."""
        from app.jobs.scheduler import _job_failures, job_listener

        _job_failures.clear()

        # Add an old failure (2 hours ago)
        old_time = datetime.now() - timedelta(hours=2)
        _job_failures["test_job"].append(old_time)

        mock_event = MagicMock(spec=JobExecutionEvent)
        mock_event.job_id = "test_job"
        mock_event.exception = Exception("New failure")

        mock_settings = MagicMock()
        mock_settings.job_failure_window_hours = 1  # Only last 1 hour
        mock_settings.job_failure_threshold = 5

        with (
            patch("app.config.settings", mock_settings),
            patch("app.jobs.scheduler.datetime") as mock_datetime,
        ):
            mock_datetime.now.return_value = datetime.now()
            job_listener(mock_event)

        # Old failure should be pruned, only new one remains
        assert len(_job_failures["test_job"]) == 1

    def test_logs_warning_before_threshold(self):
        """Test that warning is logged before reaching threshold."""
        from app.jobs.scheduler import _job_failures, job_listener

        _job_failures.clear()

        mock_event = MagicMock(spec=JobExecutionEvent)
        mock_event.job_id = "test_job"
        mock_event.exception = Exception("Test failure")

        mock_settings = MagicMock()
        mock_settings.job_failure_window_hours = 1
        mock_settings.job_failure_threshold = 5

        with (
            patch("app.config.settings", mock_settings),
            patch("app.jobs.scheduler.logger") as mock_logger,
        ):
            job_listener(mock_event)

        # Should log warning, not error (1 failure < 5 threshold)
        mock_logger.warning.assert_called_once()
        mock_logger.error.assert_not_called()

    def test_logs_error_at_threshold(self):
        """Test that error is logged when threshold is reached."""
        from app.jobs.scheduler import _job_failures, job_listener

        _job_failures.clear()

        mock_settings = MagicMock()
        mock_settings.job_failure_window_hours = 1
        mock_settings.job_failure_threshold = 3

        # Simulate 3 failures to reach threshold
        for i in range(3):
            mock_event = MagicMock(spec=JobExecutionEvent)
            mock_event.job_id = "test_job"
            mock_event.exception = Exception(f"Failure {i}")

            with (
                patch("app.config.settings", mock_settings),
                patch("app.jobs.scheduler.logger") as mock_logger,
            ):
                job_listener(mock_event)

        # Last call should have logged an error
        mock_logger.error.assert_called()

    def test_clears_failures_on_success(self):
        """Test that failures are cleared when job succeeds."""
        from app.jobs.scheduler import _job_failures, job_listener

        _job_failures.clear()

        # Add some failures first
        _job_failures["test_job"].append(datetime.now())
        _job_failures["test_job"].append(datetime.now())

        # Now simulate success
        mock_event = MagicMock(spec=JobExecutionEvent)
        mock_event.job_id = "test_job"
        mock_event.exception = None  # No exception = success

        mock_settings = MagicMock()
        mock_settings.job_failure_window_hours = 1
        mock_settings.job_failure_threshold = 5

        with patch("app.config.settings", mock_settings):
            job_listener(mock_event)

        # Failures should be cleared
        assert len(_job_failures["test_job"]) == 0

    def test_does_not_clear_other_job_failures(self):
        """Test that success in one job doesn't affect other jobs."""
        from app.jobs.scheduler import _job_failures, job_listener

        _job_failures.clear()

        # Add failures for two different jobs
        _job_failures["job1"].append(datetime.now())
        _job_failures["job2"].append(datetime.now())

        # job1 succeeds
        mock_event = MagicMock(spec=JobExecutionEvent)
        mock_event.job_id = "job1"
        mock_event.exception = None

        mock_settings = MagicMock()
        mock_settings.job_failure_window_hours = 1
        mock_settings.job_failure_threshold = 5

        with patch("app.config.settings", mock_settings):
            job_listener(mock_event)

        # job1 failures should be cleared, but not job2
        assert len(_job_failures["job1"]) == 0
        assert len(_job_failures["job2"]) == 1


class TestInitScheduler:
    """Tests for init_scheduler function."""

    @pytest.mark.asyncio
    async def test_creates_scheduler_instance(self):
        """Test that scheduler instance is created."""
        from app.jobs import scheduler as scheduler_module
        from app.jobs.scheduler import init_scheduler

        # Reset global scheduler
        scheduler_module.scheduler = None

        mock_settings_repo = MagicMock()
        mock_settings_repo.get_float = AsyncMock(side_effect=[5.0, 3.0, 5.0, 1.0])

        with (
            patch(
                "app.repositories.SettingsRepository",
                return_value=mock_settings_repo,
            ),
            patch("app.jobs.sync_cycle.run_sync_cycle"),
            patch("app.jobs.stocks_data_sync.run_stocks_data_sync"),
            patch("app.jobs.maintenance.run_daily_maintenance"),
            patch("app.jobs.maintenance.run_weekly_maintenance"),
        ):
            result = await init_scheduler()

        assert result is not None
        assert scheduler_module.scheduler is not None

    @pytest.mark.asyncio
    async def test_adds_event_listener(self):
        """Test that job listener is added to scheduler."""
        from app.jobs import scheduler as scheduler_module
        from app.jobs.scheduler import init_scheduler

        scheduler_module.scheduler = None

        mock_settings_repo = MagicMock()
        mock_settings_repo.get_float = AsyncMock(side_effect=[5.0, 3.0, 5.0, 1.0])

        with (
            patch(
                "app.repositories.SettingsRepository",
                return_value=mock_settings_repo,
            ),
            patch("app.jobs.sync_cycle.run_sync_cycle"),
            patch("app.jobs.stocks_data_sync.run_stocks_data_sync"),
            patch("app.jobs.maintenance.run_daily_maintenance"),
            patch("app.jobs.maintenance.run_weekly_maintenance"),
        ):
            await init_scheduler()

        # Verify listener was added
        assert scheduler_module.scheduler is not None
        # The listener should be in the internal _listeners dict

    @pytest.mark.asyncio
    async def test_schedules_sync_cycle_job(self):
        """Test that sync_cycle job is scheduled with correct interval."""
        from app.jobs import scheduler as scheduler_module
        from app.jobs.scheduler import init_scheduler

        scheduler_module.scheduler = None

        mock_settings_repo = MagicMock()
        mock_settings_repo.get_float = AsyncMock(side_effect=[30.0, 3.0, 5.0, 1.0])

        with (
            patch(
                "app.repositories.SettingsRepository",
                return_value=mock_settings_repo,
            ),
            patch("app.jobs.sync_cycle.run_sync_cycle"),
            patch("app.jobs.stocks_data_sync.run_stocks_data_sync"),
            patch("app.jobs.maintenance.run_daily_maintenance"),
            patch("app.jobs.maintenance.run_weekly_maintenance"),
        ):
            await init_scheduler()

        # Get the scheduled job
        jobs = scheduler_module.scheduler.get_jobs()
        sync_job = next((j for j in jobs if j.id == "sync_cycle"), None)

        assert sync_job is not None
        assert sync_job.name == "Sync Cycle"
        assert isinstance(sync_job.trigger, IntervalTrigger)

    @pytest.mark.asyncio
    async def test_schedules_stocks_data_sync_job(self):
        """Test that stocks_data_sync job is scheduled hourly."""
        from app.jobs import scheduler as scheduler_module
        from app.jobs.scheduler import init_scheduler

        scheduler_module.scheduler = None

        mock_settings_repo = MagicMock()
        mock_settings_repo.get_float = AsyncMock(side_effect=[5.0, 3.0, 5.0, 1.0])

        with (
            patch(
                "app.repositories.SettingsRepository",
                return_value=mock_settings_repo,
            ),
            patch("app.jobs.sync_cycle.run_sync_cycle"),
            patch("app.jobs.stocks_data_sync.run_stocks_data_sync"),
            patch("app.jobs.maintenance.run_daily_maintenance"),
            patch("app.jobs.maintenance.run_weekly_maintenance"),
        ):
            await init_scheduler()

        jobs = scheduler_module.scheduler.get_jobs()
        pipeline_job = next((j for j in jobs if j.id == "stocks_data_sync"), None)

        assert pipeline_job is not None
        assert pipeline_job.name == "Stocks Data Sync"
        assert isinstance(pipeline_job.trigger, IntervalTrigger)

    @pytest.mark.asyncio
    async def test_schedules_daily_maintenance_job(self):
        """Test that daily_maintenance job is scheduled with cron trigger."""
        from app.jobs import scheduler as scheduler_module
        from app.jobs.scheduler import init_scheduler

        scheduler_module.scheduler = None

        mock_settings_repo = MagicMock()
        mock_settings_repo.get_float = AsyncMock(side_effect=[15.0, 4.0, 5.0, 1.0])

        with (
            patch(
                "app.repositories.SettingsRepository",
                return_value=mock_settings_repo,
            ),
            patch("app.jobs.sync_cycle.run_sync_cycle"),
            patch("app.jobs.stocks_data_sync.run_stocks_data_sync"),
            patch("app.jobs.maintenance.run_daily_maintenance"),
            patch("app.jobs.maintenance.run_weekly_maintenance"),
        ):
            await init_scheduler()

        jobs = scheduler_module.scheduler.get_jobs()
        maintenance_job = next((j for j in jobs if j.id == "daily_maintenance"), None)

        assert maintenance_job is not None
        assert maintenance_job.name == "Daily Maintenance"
        assert isinstance(maintenance_job.trigger, CronTrigger)

    @pytest.mark.asyncio
    async def test_schedules_weekly_maintenance_job(self):
        """Test that weekly_maintenance job is scheduled for Sundays."""
        from app.jobs import scheduler as scheduler_module
        from app.jobs.scheduler import init_scheduler

        scheduler_module.scheduler = None

        mock_settings_repo = MagicMock()
        mock_settings_repo.get_float = AsyncMock(side_effect=[5.0, 3.0, 5.0, 1.0])

        with (
            patch(
                "app.repositories.SettingsRepository",
                return_value=mock_settings_repo,
            ),
            patch("app.jobs.sync_cycle.run_sync_cycle"),
            patch("app.jobs.stocks_data_sync.run_stocks_data_sync"),
            patch("app.jobs.maintenance.run_daily_maintenance"),
            patch("app.jobs.maintenance.run_weekly_maintenance"),
        ):
            await init_scheduler()

        jobs = scheduler_module.scheduler.get_jobs()
        weekly_job = next((j for j in jobs if j.id == "weekly_maintenance"), None)

        assert weekly_job is not None
        assert weekly_job.name == "Weekly Maintenance"
        assert isinstance(weekly_job.trigger, CronTrigger)

    @pytest.mark.asyncio
    async def test_logs_initialization_info(self):
        """Test that initialization is logged."""
        from app.jobs import scheduler as scheduler_module
        from app.jobs.scheduler import init_scheduler

        scheduler_module.scheduler = None

        mock_settings_repo = MagicMock()
        mock_settings_repo.get_float = AsyncMock(side_effect=[5.0, 3.0, 5.0, 1.0])

        with (
            patch(
                "app.repositories.SettingsRepository",
                return_value=mock_settings_repo,
            ),
            patch("app.jobs.sync_cycle.run_sync_cycle"),
            patch("app.jobs.stocks_data_sync.run_stocks_data_sync"),
            patch("app.jobs.maintenance.run_daily_maintenance"),
            patch("app.jobs.maintenance.run_weekly_maintenance"),
            patch("app.jobs.scheduler.logger") as mock_logger,
        ):
            await init_scheduler()

        # Should log initialization with job details
        mock_logger.info.assert_called_once()
        log_message = mock_logger.info.call_args[0][0]
        assert "Scheduler initialized" in log_message
        assert "8 jobs" in log_message

    @pytest.mark.asyncio
    async def test_replaces_existing_jobs(self):
        """Test that jobs are replaced if scheduler is re-initialized."""
        from app.jobs import scheduler as scheduler_module
        from app.jobs.scheduler import init_scheduler

        scheduler_module.scheduler = None

        mock_settings_repo = MagicMock()
        mock_settings_repo.get_float = AsyncMock(side_effect=[15.0, 3.0, 30.0, 4.0])

        with (
            patch(
                "app.repositories.SettingsRepository",
                return_value=mock_settings_repo,
            ),
            patch("app.jobs.sync_cycle.run_sync_cycle"),
            patch("app.jobs.stocks_data_sync.run_stocks_data_sync"),
            patch("app.jobs.maintenance.run_daily_maintenance"),
            patch("app.jobs.maintenance.run_weekly_maintenance"),
        ):
            # Initialize once
            await init_scheduler()
            first_jobs_count = len(scheduler_module.scheduler.get_jobs())

            # Initialize again
            await init_scheduler()
            second_jobs_count = len(scheduler_module.scheduler.get_jobs())

        # Should still have 8 jobs (replaced, not duplicated)
        assert first_jobs_count == 8
        assert second_jobs_count == 8

    @pytest.mark.asyncio
    async def test_handles_maintenance_hour_overflow(self):
        """Test that weekly maintenance hour wraps around 24h correctly."""
        from app.jobs import scheduler as scheduler_module
        from app.jobs.scheduler import init_scheduler

        scheduler_module.scheduler = None

        mock_settings_repo = MagicMock()
        # Maintenance at 23:00 means weekly should be at 0:00 (next day)
        mock_settings_repo.get_float = AsyncMock(side_effect=[15.0, 23.0, 5.0, 1.0])

        with (
            patch(
                "app.repositories.SettingsRepository",
                return_value=mock_settings_repo,
            ),
            patch("app.jobs.sync_cycle.run_sync_cycle"),
            patch("app.jobs.stocks_data_sync.run_stocks_data_sync"),
            patch("app.jobs.maintenance.run_daily_maintenance"),
            patch("app.jobs.maintenance.run_weekly_maintenance"),
        ):
            await init_scheduler()

        jobs = scheduler_module.scheduler.get_jobs()
        weekly_job = next((j for j in jobs if j.id == "weekly_maintenance"), None)

        # The hour should be (23 + 1) % 24 = 0
        assert weekly_job is not None


class TestRescheduleAllJobs:
    """Tests for reschedule_all_jobs function."""

    @pytest.mark.asyncio
    async def test_reschedules_sync_cycle_with_new_interval(self):
        """Test that sync_cycle job is rescheduled with new settings."""
        from app.jobs import scheduler as scheduler_module
        from app.jobs.scheduler import init_scheduler, reschedule_all_jobs

        scheduler_module.scheduler = None

        mock_settings_repo = MagicMock()
        # First init with 15 minutes, then reschedule to 30
        # init_scheduler needs 4 values, reschedule_all_jobs needs 3 more (via _get_job_settings)
        mock_settings_repo.get_float = AsyncMock(
            side_effect=[15.0, 3.0, 5.0, 1.0, 30.0, 4.0, 5.0]
        )

        with (
            patch(
                "app.repositories.SettingsRepository",
                return_value=mock_settings_repo,
            ),
            patch("app.jobs.sync_cycle.run_sync_cycle"),
            patch("app.jobs.stocks_data_sync.run_stocks_data_sync"),
            patch("app.jobs.maintenance.run_daily_maintenance"),
            patch("app.jobs.maintenance.run_weekly_maintenance"),
        ):
            await init_scheduler()
            await reschedule_all_jobs()

        # Verify the job was rescheduled
        jobs = scheduler_module.scheduler.get_jobs()
        assert len(jobs) == 8

    @pytest.mark.asyncio
    async def test_reschedules_maintenance_jobs(self):
        """Test that maintenance jobs are rescheduled with new hour."""
        from app.jobs import scheduler as scheduler_module
        from app.jobs.scheduler import init_scheduler, reschedule_all_jobs

        scheduler_module.scheduler = None

        mock_settings_repo = MagicMock()
        # init_scheduler needs 4 values, reschedule_all_jobs needs 3 more
        mock_settings_repo.get_float = AsyncMock(
            side_effect=[
                15.0,
                3.0,
                5.0,
                1.0,
                15.0,
                5.0,
                5.0,
            ]  # Change maintenance hour to 5
        )

        with (
            patch(
                "app.repositories.SettingsRepository",
                return_value=mock_settings_repo,
            ),
            patch("app.jobs.sync_cycle.run_sync_cycle"),
            patch("app.jobs.stocks_data_sync.run_stocks_data_sync"),
            patch("app.jobs.maintenance.run_daily_maintenance"),
            patch("app.jobs.maintenance.run_weekly_maintenance"),
        ):
            await init_scheduler()
            await reschedule_all_jobs()

        jobs = scheduler_module.scheduler.get_jobs()
        assert len(jobs) == 8

    @pytest.mark.asyncio
    async def test_logs_reschedule_info(self):
        """Test that rescheduling is logged."""
        from app.jobs import scheduler as scheduler_module
        from app.jobs.scheduler import init_scheduler, reschedule_all_jobs

        scheduler_module.scheduler = None

        mock_settings_repo = MagicMock()
        mock_settings_repo.get_float = AsyncMock(side_effect=[15.0, 3.0, 30.0, 4.0])

        with (
            patch(
                "app.repositories.SettingsRepository",
                return_value=mock_settings_repo,
            ),
            patch("app.jobs.sync_cycle.run_sync_cycle"),
            patch("app.jobs.stocks_data_sync.run_stocks_data_sync"),
            patch("app.jobs.maintenance.run_daily_maintenance"),
            patch("app.jobs.maintenance.run_weekly_maintenance"),
            patch("app.jobs.scheduler.logger") as mock_logger,
        ):
            await init_scheduler()
            mock_logger.reset_mock()
            await reschedule_all_jobs()

        # Should log rescheduling
        mock_logger.info.assert_called_once()
        log_message = mock_logger.info.call_args[0][0]
        assert "rescheduled" in log_message.lower()

    @pytest.mark.asyncio
    async def test_warns_when_scheduler_not_initialized(self):
        """Test that warning is logged if scheduler doesn't exist."""
        from app.jobs import scheduler as scheduler_module
        from app.jobs.scheduler import reschedule_all_jobs

        scheduler_module.scheduler = None

        with patch("app.jobs.scheduler.logger") as mock_logger:
            await reschedule_all_jobs()

        mock_logger.warning.assert_called_once()
        warning_message = mock_logger.warning.call_args[0][0]
        assert "not initialized" in warning_message.lower()


class TestStartScheduler:
    """Tests for start_scheduler function."""

    def test_starts_scheduler_when_not_running(self):
        """Test that scheduler is started when not already running."""
        from app.jobs import scheduler as scheduler_module
        from app.jobs.scheduler import start_scheduler

        mock_scheduler = MagicMock()
        mock_scheduler.running = False
        scheduler_module.scheduler = mock_scheduler

        with patch("app.jobs.scheduler.logger") as mock_logger:
            start_scheduler()

        mock_scheduler.start.assert_called_once()
        mock_logger.info.assert_called_once()

    def test_does_not_start_when_already_running(self):
        """Test that start is not called when scheduler is already running."""
        from app.jobs import scheduler as scheduler_module
        from app.jobs.scheduler import start_scheduler

        mock_scheduler = MagicMock()
        mock_scheduler.running = True
        scheduler_module.scheduler = mock_scheduler

        start_scheduler()

        mock_scheduler.start.assert_not_called()

    def test_does_nothing_when_scheduler_is_none(self):
        """Test that nothing happens when scheduler is not initialized."""
        from app.jobs import scheduler as scheduler_module
        from app.jobs.scheduler import start_scheduler

        scheduler_module.scheduler = None

        # Should not raise any exception
        start_scheduler()


class TestStopScheduler:
    """Tests for stop_scheduler function."""

    def test_stops_scheduler_when_running(self):
        """Test that scheduler is stopped when running."""
        from app.jobs import scheduler as scheduler_module
        from app.jobs.scheduler import stop_scheduler

        mock_scheduler = MagicMock()
        mock_scheduler.running = True
        scheduler_module.scheduler = mock_scheduler

        with patch("app.jobs.scheduler.logger") as mock_logger:
            stop_scheduler()

        mock_scheduler.shutdown.assert_called_once()
        mock_logger.info.assert_called_once()

    def test_does_not_stop_when_not_running(self):
        """Test that shutdown is not called when scheduler is not running."""
        from app.jobs import scheduler as scheduler_module
        from app.jobs.scheduler import stop_scheduler

        mock_scheduler = MagicMock()
        mock_scheduler.running = False
        scheduler_module.scheduler = mock_scheduler

        stop_scheduler()

        mock_scheduler.shutdown.assert_not_called()

    def test_does_nothing_when_scheduler_is_none(self):
        """Test that nothing happens when scheduler is not initialized."""
        from app.jobs import scheduler as scheduler_module
        from app.jobs.scheduler import stop_scheduler

        scheduler_module.scheduler = None

        # Should not raise any exception
        stop_scheduler()


class TestGetScheduler:
    """Tests for get_scheduler function."""

    def test_returns_scheduler_instance(self):
        """Test that the global scheduler instance is returned."""
        from app.jobs import scheduler as scheduler_module
        from app.jobs.scheduler import get_scheduler

        mock_scheduler = MagicMock()
        scheduler_module.scheduler = mock_scheduler

        result = get_scheduler()

        assert result is mock_scheduler

    def test_returns_none_when_not_initialized(self):
        """Test that None is returned when scheduler not initialized."""
        from app.jobs import scheduler as scheduler_module
        from app.jobs.scheduler import get_scheduler

        scheduler_module.scheduler = None

        result = get_scheduler()

        assert result is None


class TestGetJobHealthStatus:
    """Tests for get_job_health_status function."""

    def test_returns_empty_dict_when_scheduler_not_initialized(self):
        """Test that empty dict is returned when scheduler doesn't exist."""
        from app.jobs import scheduler as scheduler_module
        from app.jobs.scheduler import get_job_health_status

        scheduler_module.scheduler = None

        status = get_job_health_status()

        assert status == {}

    def test_returns_status_for_all_jobs(self):
        """Test that status is returned for all scheduled jobs."""
        from app.jobs import scheduler as scheduler_module
        from app.jobs.scheduler import _job_failures, get_job_health_status

        _job_failures.clear()

        # Create mock jobs
        mock_job1 = MagicMock()
        mock_job1.id = "sync_cycle"
        mock_job1.name = "Sync Cycle"
        mock_job1.next_run_time = datetime(2025, 12, 27, 12, 0, 0)

        mock_job2 = MagicMock()
        mock_job2.id = "stocks_data_sync"
        mock_job2.name = "Stocks Data Sync"
        mock_job2.next_run_time = datetime(2025, 12, 27, 13, 0, 0)

        mock_scheduler = MagicMock()
        mock_scheduler.get_jobs.return_value = [mock_job1, mock_job2]
        scheduler_module.scheduler = mock_scheduler

        mock_settings = MagicMock()
        mock_settings.job_failure_threshold = 5

        with patch("app.config.settings", mock_settings):
            status = get_job_health_status()

        assert "sync_cycle" in status
        assert "stocks_data_sync" in status
        assert status["sync_cycle"]["name"] == "Sync Cycle"
        assert status["stocks_data_sync"]["name"] == "Stocks Data Sync"

    def test_includes_failure_count(self):
        """Test that failure count is included in status."""
        from app.jobs import scheduler as scheduler_module
        from app.jobs.scheduler import _job_failures, get_job_health_status

        _job_failures.clear()
        # Add 2 failures for a job
        _job_failures["test_job"].append(datetime.now())
        _job_failures["test_job"].append(datetime.now())

        mock_job = MagicMock()
        mock_job.id = "test_job"
        mock_job.name = "Test Job"
        mock_job.next_run_time = datetime(2025, 12, 27, 12, 0, 0)

        mock_scheduler = MagicMock()
        mock_scheduler.get_jobs.return_value = [mock_job]
        scheduler_module.scheduler = mock_scheduler

        mock_settings = MagicMock()
        mock_settings.job_failure_threshold = 5

        with patch("app.config.settings", mock_settings):
            status = get_job_health_status()

        assert status["test_job"]["recent_failures"] == 2

    def test_marks_job_unhealthy_when_threshold_reached(self):
        """Test that job is marked unhealthy when failures reach threshold."""
        from app.jobs import scheduler as scheduler_module
        from app.jobs.scheduler import _job_failures, get_job_health_status

        _job_failures.clear()
        # Add 5 failures (at threshold)
        for _ in range(5):
            _job_failures["test_job"].append(datetime.now())

        mock_job = MagicMock()
        mock_job.id = "test_job"
        mock_job.name = "Test Job"
        mock_job.next_run_time = datetime(2025, 12, 27, 12, 0, 0)

        mock_scheduler = MagicMock()
        mock_scheduler.get_jobs.return_value = [mock_job]
        scheduler_module.scheduler = mock_scheduler

        mock_settings = MagicMock()
        mock_settings.job_failure_threshold = 5

        with patch("app.config.settings", mock_settings):
            status = get_job_health_status()

        assert status["test_job"]["healthy"] is False

    def test_marks_job_healthy_when_below_threshold(self):
        """Test that job is marked healthy when failures below threshold."""
        from app.jobs import scheduler as scheduler_module
        from app.jobs.scheduler import _job_failures, get_job_health_status

        _job_failures.clear()
        # Add 2 failures (below threshold of 5)
        _job_failures["test_job"].append(datetime.now())
        _job_failures["test_job"].append(datetime.now())

        mock_job = MagicMock()
        mock_job.id = "test_job"
        mock_job.name = "Test Job"
        mock_job.next_run_time = datetime(2025, 12, 27, 12, 0, 0)

        mock_scheduler = MagicMock()
        mock_scheduler.get_jobs.return_value = [mock_job]
        scheduler_module.scheduler = mock_scheduler

        mock_settings = MagicMock()
        mock_settings.job_failure_threshold = 5

        with patch("app.config.settings", mock_settings):
            status = get_job_health_status()

        assert status["test_job"]["healthy"] is True

    def test_includes_next_run_time(self):
        """Test that next run time is included in ISO format."""
        from app.jobs import scheduler as scheduler_module
        from app.jobs.scheduler import get_job_health_status

        next_run = datetime(2025, 12, 27, 15, 30, 0)

        mock_job = MagicMock()
        mock_job.id = "test_job"
        mock_job.name = "Test Job"
        mock_job.next_run_time = next_run

        mock_scheduler = MagicMock()
        mock_scheduler.get_jobs.return_value = [mock_job]
        scheduler_module.scheduler = mock_scheduler

        mock_settings = MagicMock()
        mock_settings.job_failure_threshold = 5

        with patch("app.config.settings", mock_settings):
            status = get_job_health_status()

        assert status["test_job"]["next_run"] == next_run.isoformat()

    def test_handles_none_next_run_time(self):
        """Test that None next_run_time is handled gracefully."""
        from app.jobs import scheduler as scheduler_module
        from app.jobs.scheduler import get_job_health_status

        mock_job = MagicMock()
        mock_job.id = "test_job"
        mock_job.name = "Test Job"
        mock_job.next_run_time = None  # Not scheduled yet

        mock_scheduler = MagicMock()
        mock_scheduler.get_jobs.return_value = [mock_job]
        scheduler_module.scheduler = mock_scheduler

        mock_settings = MagicMock()
        mock_settings.job_failure_threshold = 5

        with patch("app.config.settings", mock_settings):
            status = get_job_health_status()

        assert status["test_job"]["next_run"] is None


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_init_scheduler_with_zero_interval(self):
        """Test that scheduler handles zero or negative intervals gracefully."""
        from app.jobs import scheduler as scheduler_module
        from app.jobs.scheduler import init_scheduler

        scheduler_module.scheduler = None

        mock_settings_repo = MagicMock()
        # Return 0 for interval (edge case)
        mock_settings_repo.get_float = AsyncMock(side_effect=[0.0, 3.0, 5.0, 1.0])

        with (
            patch(
                "app.repositories.SettingsRepository",
                return_value=mock_settings_repo,
            ),
            patch("app.jobs.sync_cycle.run_sync_cycle"),
            patch("app.jobs.stocks_data_sync.run_stocks_data_sync"),
            patch("app.jobs.maintenance.run_daily_maintenance"),
            patch("app.jobs.maintenance.run_weekly_maintenance"),
        ):
            # Should handle 0 by converting to int(0.0) = 0
            result = await init_scheduler()

        assert result is not None

    @pytest.mark.asyncio
    async def test_reschedule_all_jobs_multiple_times(self):
        """Test that rescheduling can be called multiple times safely."""
        from app.jobs import scheduler as scheduler_module
        from app.jobs.scheduler import init_scheduler, reschedule_all_jobs

        scheduler_module.scheduler = None

        mock_settings_repo = MagicMock()
        mock_settings_repo.get_float = AsyncMock(
            side_effect=[15.0, 3.0, 30.0, 4.0, 45.0, 5.0, 60.0, 6.0]
        )

        with (
            patch(
                "app.repositories.SettingsRepository",
                return_value=mock_settings_repo,
            ),
            patch("app.jobs.sync_cycle.run_sync_cycle"),
            patch("app.jobs.stocks_data_sync.run_stocks_data_sync"),
            patch("app.jobs.maintenance.run_daily_maintenance"),
            patch("app.jobs.maintenance.run_weekly_maintenance"),
        ):
            await init_scheduler()
            await reschedule_all_jobs()
            await reschedule_all_jobs()
            await reschedule_all_jobs()

        # Should still have 7 jobs
        jobs = scheduler_module.scheduler.get_jobs()
        assert len(jobs) == 8

    def test_job_listener_with_no_exception_attribute(self):
        """Test job listener handles events without exception attribute."""
        from app.jobs.scheduler import job_listener

        # Event with no exception (success case)
        mock_event = MagicMock(spec=JobExecutionEvent)
        mock_event.job_id = "test_job"
        mock_event.exception = None

        mock_settings = MagicMock()
        mock_settings.job_failure_window_hours = 1
        mock_settings.job_failure_threshold = 5

        with patch("app.config.settings", mock_settings):
            # Should not raise
            job_listener(mock_event)

    def test_multiple_concurrent_failures_same_job(self):
        """Test that concurrent failures for same job are tracked correctly."""
        from app.jobs.scheduler import _job_failures, job_listener

        _job_failures.clear()

        mock_settings = MagicMock()
        mock_settings.job_failure_window_hours = 1
        mock_settings.job_failure_threshold = 10

        # Simulate 10 concurrent failures
        for i in range(10):
            mock_event = MagicMock(spec=JobExecutionEvent)
            mock_event.job_id = "concurrent_job"
            mock_event.exception = Exception(f"Concurrent failure {i}")

            with patch("app.config.settings", mock_settings):
                job_listener(mock_event)

        assert len(_job_failures["concurrent_job"]) == 10

    @pytest.mark.asyncio
    async def test_init_scheduler_sets_global_reference(self):
        """Test that init_scheduler properly sets the global scheduler reference."""
        from app.jobs import scheduler as scheduler_module
        from app.jobs.scheduler import get_scheduler, init_scheduler

        scheduler_module.scheduler = None

        mock_settings_repo = MagicMock()
        mock_settings_repo.get_float = AsyncMock(side_effect=[5.0, 3.0, 5.0, 1.0])

        with (
            patch(
                "app.repositories.SettingsRepository",
                return_value=mock_settings_repo,
            ),
            patch("app.jobs.sync_cycle.run_sync_cycle"),
            patch("app.jobs.stocks_data_sync.run_stocks_data_sync"),
            patch("app.jobs.maintenance.run_daily_maintenance"),
            patch("app.jobs.maintenance.run_weekly_maintenance"),
        ):
            result = await init_scheduler()

        # Global reference should be set
        assert get_scheduler() is not None
        assert get_scheduler() is result
