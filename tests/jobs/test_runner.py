"""Tests for APScheduler-based job runner."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    """Mock database for testing."""
    db = AsyncMock()
    db.get_job_schedules = AsyncMock(
        return_value=[
            {
                "job_type": "sync:portfolio",
                "interval_minutes": 30,
                "interval_market_open_minutes": 5,
                "market_timing": 0,
                "description": "Sync portfolio",
                "category": "sync",
            },
            {
                "job_type": "sync:prices",
                "interval_minutes": 30,
                "interval_market_open_minutes": 5,
                "market_timing": 0,
                "description": "Sync prices",
                "category": "sync",
            },
        ]
    )
    db.get_job_schedule = AsyncMock(
        return_value={
            "job_type": "sync:portfolio",
            "interval_minutes": 30,
            "interval_market_open_minutes": 5,
            "market_timing": 0,
        }
    )
    db.mark_job_completed = AsyncMock()
    db.mark_job_failed = AsyncMock()
    db.log_job_execution = AsyncMock()
    db.get_job_history = AsyncMock(
        return_value=[
            {"job_type": "sync:portfolio", "status": "completed", "executed_at": 1706500000},
            {"job_type": "sync:prices", "status": "completed", "executed_at": 1706499000},
            {"job_type": "sync:portfolio", "status": "failed", "executed_at": 1706498000},
        ]
    )
    return db


@pytest.fixture
def mock_broker():
    """Mock broker for testing."""
    broker = AsyncMock()
    broker.connected = True
    return broker


@pytest.fixture
def mock_portfolio():
    """Mock portfolio for testing."""
    portfolio = AsyncMock()
    portfolio.sync = AsyncMock()
    return portfolio


@pytest.fixture
def mock_analyzer():
    """Mock analyzer for testing."""
    analyzer = AsyncMock()
    analyzer.update_scores = AsyncMock(return_value=5)
    return analyzer


@pytest.fixture
def mock_detector():
    """Mock detector for testing."""
    detector = AsyncMock()
    detector.train_model = AsyncMock()
    return detector


@pytest.fixture
def mock_planner():
    """Mock planner for testing."""
    planner = AsyncMock()
    planner.get_recommendations = AsyncMock(return_value=[])
    planner.get_rebalance_summary = AsyncMock(return_value={"needs_rebalance": False})
    planner.calculate_ideal_portfolio = AsyncMock(return_value={})
    return planner


@pytest.fixture
def mock_retrainer():
    """Mock ML retrainer for testing."""
    retrainer = AsyncMock()
    retrainer.retrain_symbol = AsyncMock()
    return retrainer


@pytest.fixture
def mock_monitor():
    """Mock ML monitor for testing."""
    monitor = AsyncMock()
    monitor.track_symbol_performance = AsyncMock()
    return monitor


@pytest.fixture
def mock_cache():
    """Mock cache for testing."""
    cache = MagicMock()
    cache.clear = MagicMock(return_value=0)
    return cache


@pytest.fixture
def mock_market_checker():
    """Mock market checker for testing."""
    checker = MagicMock()
    checker.is_any_market_open = MagicMock(return_value=False)
    checker.are_all_markets_closed = MagicMock(return_value=True)
    checker.ensure_fresh = AsyncMock()
    return checker


class TestRunnerInit:
    """Tests for runner initialization."""

    @pytest.mark.asyncio
    async def test_init_creates_scheduler(
        self,
        mock_db,
        mock_broker,
        mock_portfolio,
        mock_analyzer,
        mock_planner,
        mock_cache,
        mock_market_checker,
    ):
        """Verify init creates and starts scheduler."""
        from sentinel.jobs import runner

        # Reset module state
        runner._scheduler = None
        runner._deps = {}
        runner._current_job = None

        with patch.object(runner, "AsyncIOScheduler") as MockScheduler:
            mock_sched = MagicMock()
            mock_sched.start = MagicMock()
            mock_sched.add_job = MagicMock()
            MockScheduler.return_value = mock_sched

            scheduler = await runner.init(
                mock_db,
                mock_broker,
                mock_portfolio,
                mock_analyzer,
                mock_planner,
                mock_cache,
                mock_market_checker,
            )

            assert scheduler is not None
            mock_sched.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_init_uses_intervals_from_db(
        self,
        mock_db,
        mock_broker,
        mock_portfolio,
        mock_analyzer,
        mock_planner,
        mock_cache,
        mock_market_checker,
    ):
        """Verify intervals are loaded from database."""
        from sentinel.jobs import runner

        runner._scheduler = None
        runner._deps = {}
        runner._current_job = None

        with patch.object(runner, "AsyncIOScheduler") as MockScheduler:
            mock_sched = MagicMock()
            mock_sched.start = MagicMock()
            mock_sched.add_job = MagicMock()
            MockScheduler.return_value = mock_sched

            await runner.init(
                mock_db,
                mock_broker,
                mock_portfolio,
                mock_analyzer,
                mock_planner,
                mock_cache,
                mock_market_checker,
            )

            # Verify get_job_schedules was called
            mock_db.get_job_schedules.assert_awaited_once()


class TestRunnerStop:
    """Tests for stopping the scheduler."""

    @pytest.mark.asyncio
    async def test_stop_shuts_down_scheduler(self):
        """Verify scheduler is shut down."""
        from sentinel.jobs import runner

        mock_sched = MagicMock()
        mock_sched.shutdown = MagicMock()
        runner._scheduler = mock_sched

        await runner.stop()

        mock_sched.shutdown.assert_called_once_with(wait=False)
        assert runner._scheduler is None


class TestRunnerReschedule:
    """Tests for rescheduling jobs."""

    @pytest.mark.asyncio
    async def test_reschedule_updates_job(self, mock_db):
        """Verify job is rescheduled with new interval."""
        from sentinel.jobs import runner

        mock_sched = MagicMock()
        mock_sched.reschedule_job = MagicMock()
        runner._scheduler = mock_sched

        await runner.reschedule("sync:portfolio", mock_db)

        mock_sched.reschedule_job.assert_called_once()


class TestRunNow:
    """Tests for immediate job execution."""

    @pytest.mark.asyncio
    async def test_run_now_executes_immediately(
        self,
        mock_db,
        mock_portfolio,
    ):
        """Verify task executes immediately."""
        from sentinel.jobs import runner

        runner._deps = {
            "db": mock_db,
            "portfolio": mock_portfolio,
        }
        runner._current_job = None

        result = await runner.run_now("sync:portfolio")

        assert result["status"] in ("completed", "failed")
        assert "duration_ms" in result

    @pytest.mark.asyncio
    async def test_run_now_unknown_type_returns_error(self):
        """Verify error for unknown job type."""
        from sentinel.jobs import runner

        runner._deps = {}

        result = await runner.run_now("unknown:job")

        assert result["status"] == "failed"
        assert "error" in result


class TestRunTask:
    """Tests for internal task execution."""

    @pytest.mark.asyncio
    async def test_run_task_checks_market_timing(self, mock_db, mock_market_checker):
        """Verify market timing is checked."""
        from sentinel.jobs import runner

        runner._deps = {
            "db": mock_db,
            "market_checker": mock_market_checker,
        }
        runner._current_job = None

        schedule = {
            "job_type": "trading:execute",
            "market_timing": 2,  # DURING_MARKET_OPEN
        }

        # Market is closed, so job should be skipped
        mock_market_checker.is_any_market_open.return_value = False

        result = await runner._run_task("trading:execute", schedule)

        assert result is None or result.get("skipped")

    @pytest.mark.asyncio
    async def test_run_task_logs_success_to_db(self, mock_db, mock_portfolio, mock_market_checker):
        """Verify DB logging on success."""
        from sentinel.jobs import runner

        mock_market_checker.is_any_market_open.return_value = True

        runner._deps = {
            "db": mock_db,
            "portfolio": mock_portfolio,
            "market_checker": mock_market_checker,
        }
        runner._current_job = None

        schedule = {
            "job_type": "sync:portfolio",
            "market_timing": 0,  # ANY_TIME
        }

        await runner._run_task("sync:portfolio", schedule)

        mock_db.mark_job_completed.assert_awaited()

    @pytest.mark.asyncio
    async def test_run_task_logs_failure_to_db(self, mock_db, mock_market_checker):
        """Verify DB logging on exception."""
        from sentinel.jobs import runner

        mock_portfolio = AsyncMock()
        mock_portfolio.sync = AsyncMock(side_effect=Exception("Test error"))
        mock_market_checker.is_any_market_open.return_value = True

        runner._deps = {
            "db": mock_db,
            "portfolio": mock_portfolio,
            "market_checker": mock_market_checker,
        }
        runner._current_job = None

        schedule = {
            "job_type": "sync:portfolio",
            "market_timing": 0,
        }

        await runner._run_task("sync:portfolio", schedule)

        mock_db.mark_job_failed.assert_awaited()

    @pytest.mark.asyncio
    async def test_run_task_sets_current_job(self, mock_db, mock_portfolio, mock_market_checker):
        """Verify _current_job is set during execution."""
        from sentinel.jobs import runner

        mock_market_checker.is_any_market_open.return_value = True

        runner._deps = {
            "db": mock_db,
            "portfolio": mock_portfolio,
            "market_checker": mock_market_checker,
        }
        runner._current_job = None

        captured_current = None

        original_sync = mock_portfolio.sync

        async def capture_current():
            nonlocal captured_current
            captured_current = runner._current_job
            return await original_sync()

        mock_portfolio.sync = capture_current

        schedule = {
            "job_type": "sync:portfolio",
            "market_timing": 0,
        }

        await runner._run_task("sync:portfolio", schedule)

        assert captured_current == "sync:portfolio"

    @pytest.mark.asyncio
    async def test_run_task_clears_current_job_after(self, mock_db, mock_portfolio, mock_market_checker):
        """Verify _current_job is cleared after execution."""
        from sentinel.jobs import runner

        mock_market_checker.is_any_market_open.return_value = True

        runner._deps = {
            "db": mock_db,
            "portfolio": mock_portfolio,
            "market_checker": mock_market_checker,
        }
        runner._current_job = "some:job"

        schedule = {
            "job_type": "sync:portfolio",
            "market_timing": 0,
        }

        await runner._run_task("sync:portfolio", schedule)

        assert runner._current_job is None


class TestGetStatus:
    """Tests for get_status function."""

    @pytest.mark.asyncio
    async def test_get_status_returns_current(self, mock_db):
        """Verify currently running job is returned."""
        from sentinel.jobs import runner

        runner._current_job = "sync:prices"
        runner._deps = {"db": mock_db}

        mock_sched = MagicMock()
        mock_sched.get_jobs = MagicMock(return_value=[])
        runner._scheduler = mock_sched

        status = await runner.get_status()

        assert status["current"] == "sync:prices"

    @pytest.mark.asyncio
    async def test_get_status_returns_upcoming(self, mock_db):
        """Verify upcoming jobs are returned sorted by next_run."""
        from sentinel.jobs import runner

        runner._current_job = None
        runner._deps = {"db": mock_db}

        mock_job1 = MagicMock()
        mock_job1.id = "sync:portfolio"
        mock_job1.next_run_time = datetime.now() + timedelta(minutes=5)

        mock_job2 = MagicMock()
        mock_job2.id = "sync:prices"
        mock_job2.next_run_time = datetime.now() + timedelta(minutes=10)

        mock_job3 = MagicMock()
        mock_job3.id = "sync:quotes"
        mock_job3.next_run_time = datetime.now() + timedelta(minutes=15)

        mock_sched = MagicMock()
        mock_sched.get_jobs = MagicMock(return_value=[mock_job2, mock_job1, mock_job3])
        runner._scheduler = mock_sched

        status = await runner.get_status()

        assert len(status["upcoming"]) == 3
        # Should be sorted by next_run time
        assert status["upcoming"][0]["job_type"] == "sync:portfolio"
        assert status["upcoming"][1]["job_type"] == "sync:prices"
        assert status["upcoming"][2]["job_type"] == "sync:quotes"

    @pytest.mark.asyncio
    async def test_get_status_returns_recent(self, mock_db):
        """Verify recent jobs are returned deduplicated by job_type."""
        from sentinel.jobs import runner

        runner._current_job = None
        runner._deps = {"db": mock_db}

        mock_sched = MagicMock()
        mock_sched.get_jobs = MagicMock(return_value=[])
        runner._scheduler = mock_sched

        status = await runner.get_status()

        # Should have recent entries (deduplicated)
        assert "recent" in status
        # The mock returns 3 entries but 2 are sync:portfolio, should dedupe to 2 unique
        recent_types = [r["job_type"] for r in status["recent"]]
        assert len(recent_types) == len(set(recent_types))


class TestMarketTimingCheck:
    """Tests for market timing checks."""

    def test_check_market_timing_any_time(self):
        """Verify ANY_TIME always returns True."""
        from sentinel.jobs.runner import _check_market_timing

        mock_checker = MagicMock()

        result = _check_market_timing(0, mock_checker)

        assert result is True

    def test_check_market_timing_during_market_open(self):
        """Verify DURING_MARKET_OPEN checks is_any_market_open."""
        from sentinel.jobs.runner import _check_market_timing

        mock_checker = MagicMock()
        mock_checker.is_any_market_open.return_value = True

        result = _check_market_timing(2, mock_checker)

        assert result is True
        mock_checker.is_any_market_open.assert_called_once()

    def test_check_market_timing_all_markets_closed(self):
        """Verify ALL_MARKETS_CLOSED checks are_all_markets_closed."""
        from sentinel.jobs.runner import _check_market_timing

        mock_checker = MagicMock()
        mock_checker.are_all_markets_closed.return_value = True

        result = _check_market_timing(3, mock_checker)

        assert result is True
        mock_checker.are_all_markets_closed.assert_called_once()
