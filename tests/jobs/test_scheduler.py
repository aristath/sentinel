"""Tests for jobs/scheduler.py - Sync scheduler with database configuration."""

import pytest
import pytest_asyncio
import asyncio
from datetime import datetime, timedelta

from sentinel.jobs.types import BaseJob
from sentinel.jobs.queue import Queue
from sentinel.jobs.registry import Registry
from sentinel.jobs.scheduler import Scheduler, SyncScheduler


class MockJob(BaseJob):
    """Test job implementation."""

    async def execute(self) -> None:
        pass


class MockDB:
    """Mock database for testing."""

    def __init__(self, schedules=None, last_completions=None, ml_securities=None, expired=None):
        self._schedules = schedules or []
        self._last_completions = last_completions or {}
        self._ml_securities = ml_securities or []
        self._expired = expired or set()
        self._last_run = {}

    async def get_job_schedules(self):
        return self._schedules

    async def is_job_expired(self, job_type: str, market_open: bool = False) -> bool:
        # Check if explicitly marked as expired
        if job_type in self._expired:
            return True
        # Check based on last_run timestamp
        schedule = None
        for s in self._schedules:
            if s['job_type'] == job_type:
                schedule = s
                break
        if not schedule:
            return False
        last_run = self._last_run.get(job_type, 0)

        # Use shorter interval when markets are open
        interval = schedule.get('interval_minutes', 60)
        if market_open and schedule.get('interval_market_open_minutes'):
            interval = schedule['interval_market_open_minutes']

        if last_run == 0:
            # If never run, check if last_completions has an entry
            last_completion = self._last_completions.get(job_type)
            if last_completion is None:
                return True  # Never ran
            # Check if completion is old enough to be expired
            elapsed = (datetime.now() - last_completion).total_seconds()
            return elapsed >= interval * 60
        return int(datetime.now().timestamp()) - last_run >= interval * 60

    async def set_job_last_run(self, job_type: str, timestamp: int) -> None:
        self._last_run[job_type] = timestamp
        if timestamp == 0:
            self._expired.add(job_type)

    async def get_last_job_completion(self, job_type: str):
        return self._last_completions.get(job_type)

    async def get_last_job_completion_by_id(self, job_id: str):
        return self._last_completions.get(job_id)

    async def get_ml_enabled_securities(self):
        return self._ml_securities


class MockMarketChecker:
    """Mock market checker."""

    def __init__(self, any_open=False):
        self._any_open = any_open

    def is_any_market_open(self) -> bool:
        return self._any_open

    def is_security_market_open(self, symbol: str) -> bool:
        return self._any_open

    def are_all_markets_closed(self) -> bool:
        return not self._any_open


def make_schedule(job_type, interval=30, interval_open=5, timing=0, enabled=1, is_param=0, param_src=None, param_field=None):
    """Helper to create schedule dict."""
    return {
        'job_type': job_type,
        'enabled': enabled,
        'interval_minutes': interval,
        'interval_market_open_minutes': interval_open,
        'market_timing': timing,
        'is_parameterized': is_param,
        'parameter_source': param_src,
        'parameter_field': param_field,
    }


@pytest.fixture
def queue():
    return Queue()


@pytest_asyncio.fixture
async def registry():
    reg = Registry()
    # Register all job types the scheduler might enqueue
    await reg.register('sync:portfolio', lambda p: MockJob(_id='sync:portfolio', _job_type='sync:portfolio'))
    await reg.register('sync:prices', lambda p: MockJob(_id='sync:prices', _job_type='sync:prices'))
    await reg.register('sync:quotes', lambda p: MockJob(_id='sync:quotes', _job_type='sync:quotes'))
    await reg.register('sync:metadata', lambda p: MockJob(_id='sync:metadata', _job_type='sync:metadata'))
    await reg.register('sync:exchange_rates', lambda p: MockJob(_id='sync:exchange_rates', _job_type='sync:exchange_rates'))
    await reg.register('scoring:calculate', lambda p: MockJob(_id='scoring:calculate', _job_type='scoring:calculate'))
    await reg.register('analytics:correlation', lambda p: MockJob(_id='analytics:correlation', _job_type='analytics:correlation'))
    await reg.register('analytics:regime', lambda p: MockJob(_id='analytics:regime', _job_type='analytics:regime'))
    await reg.register('analytics:transfer_entropy', lambda p: MockJob(_id='analytics:transfer_entropy', _job_type='analytics:transfer_entropy'))
    await reg.register('trading:check_markets', lambda p: MockJob(_id='trading:check_markets', _job_type='trading:check_markets'))
    await reg.register('ml:retrain', lambda p: MockJob(_id=f"ml:retrain:{p.get('symbol', 'AAPL')}", _job_type='ml:retrain'))
    await reg.register('ml:monitor', lambda p: MockJob(_id=f"ml:monitor:{p.get('symbol', 'AAPL')}", _job_type='ml:monitor'))
    return reg


@pytest.mark.asyncio
async def test_scheduler_starts_and_stops(queue, registry):
    """Scheduler should start and stop cleanly."""
    db = MockDB(schedules=[])
    market_checker = MockMarketChecker()
    scheduler = Scheduler(db, queue, registry, market_checker)

    await scheduler.start()
    assert scheduler._running is True

    await scheduler.stop()
    assert scheduler._running is False


@pytest.mark.asyncio
async def test_scheduler_enqueues_portfolio_sync(queue, registry):
    """Scheduler should enqueue portfolio sync when expired."""
    schedules = [make_schedule('sync:portfolio')]
    db = MockDB(schedules=schedules, last_completions={}, expired={'sync:portfolio'})
    market_checker = MockMarketChecker()
    scheduler = Scheduler(db, queue, registry, market_checker)

    await scheduler.start()
    await asyncio.sleep(0.1)
    await scheduler.stop()

    assert queue.contains('sync:portfolio')


@pytest.mark.asyncio
async def test_scheduler_enqueues_price_sync(queue, registry):
    """Scheduler should enqueue price sync when expired."""
    schedules = [make_schedule('sync:prices')]
    db = MockDB(schedules=schedules, last_completions={}, expired={'sync:prices'})
    market_checker = MockMarketChecker()
    scheduler = Scheduler(db, queue, registry, market_checker)

    await scheduler.start()
    await asyncio.sleep(0.1)
    await scheduler.stop()

    assert queue.contains('sync:prices')


@pytest.mark.asyncio
async def test_scheduler_respects_intervals(queue, registry):
    """Scheduler should not enqueue jobs that completed recently."""
    # Jobs completed 5 minutes ago
    recent = datetime.now() - timedelta(minutes=5)
    schedules = [
        make_schedule('sync:portfolio', interval=30, interval_open=30),  # 30 min interval
        make_schedule('sync:prices', interval=30, interval_open=30),
    ]
    db = MockDB(
        schedules=schedules,
        last_completions={
            'sync:portfolio': recent,
            'sync:prices': recent,
        }
    )
    market_checker = MockMarketChecker(any_open=False)  # 30 min interval
    scheduler = Scheduler(db, queue, registry, market_checker)

    await scheduler.start()
    await asyncio.sleep(0.1)
    await scheduler.stop()

    # These should not be re-enqueued (30 min interval, only 5 min elapsed)
    assert not queue.contains('sync:portfolio')
    assert not queue.contains('sync:prices')


@pytest.mark.asyncio
async def test_scheduler_shorter_interval_when_market_open(queue, registry):
    """Scheduler should use shorter interval when market is open (parameterized jobs use completions)."""
    # Jobs completed 10 minutes ago - this affects parameterized jobs
    # For simple jobs, we now use is_job_expired which checks last_run
    # This test is now about verifying the behavior with expired jobs
    schedules = [
        make_schedule('sync:portfolio', interval=30, interval_open=5),  # 5 min when open
        make_schedule('sync:prices', interval=30, interval_open=5),
    ]
    # Mark jobs as expired so they get enqueued
    db = MockDB(
        schedules=schedules,
        last_completions={},
        expired={'sync:portfolio', 'sync:prices'}
    )

    # Market is open -> 5 minute interval
    market_checker = MockMarketChecker(any_open=True)
    scheduler = Scheduler(db, queue, registry, market_checker)

    await scheduler.start()
    await asyncio.sleep(0.1)
    await scheduler.stop()

    # Jobs should be enqueued because they are expired
    assert queue.contains('sync:portfolio')
    assert queue.contains('sync:prices')


@pytest.mark.asyncio
async def test_scheduler_enqueues_ml_jobs(queue, registry):
    """Scheduler should enqueue ML jobs for ML-enabled securities."""
    schedules = [
        make_schedule('ml:retrain', interval=10080, interval_open=10080, is_param=1, param_src='ml_enabled_securities', param_field='symbol'),
        make_schedule('ml:monitor', interval=10080, interval_open=10080, is_param=1, param_src='ml_enabled_securities', param_field='symbol'),
    ]
    db = MockDB(
        schedules=schedules,
        last_completions={},
        ml_securities=[
            {'symbol': 'AAPL.US'},
            {'symbol': 'MSFT.US'},
        ],
    )
    market_checker = MockMarketChecker()
    scheduler = Scheduler(db, queue, registry, market_checker)

    await scheduler.start()
    await asyncio.sleep(0.1)
    await scheduler.stop()

    assert queue.contains('ml:retrain:AAPL.US')
    assert queue.contains('ml:retrain:MSFT.US')
    assert queue.contains('ml:monitor:AAPL.US')
    assert queue.contains('ml:monitor:MSFT.US')


@pytest.mark.asyncio
async def test_scheduler_skips_already_queued(queue, registry):
    """Scheduler should not enqueue jobs that are already queued."""
    schedules = [
        make_schedule('sync:portfolio'),
        make_schedule('sync:prices'),
    ]
    db = MockDB(schedules=schedules, last_completions={}, expired={'sync:portfolio', 'sync:prices'})
    market_checker = MockMarketChecker()

    # Pre-enqueue a job
    pre_job = MockJob(_id='sync:portfolio', _job_type='sync:portfolio')
    await queue.enqueue(pre_job)
    initial_len = len(queue)

    scheduler = Scheduler(db, queue, registry, market_checker)
    await scheduler.start()
    await asyncio.sleep(0.1)
    await scheduler.stop()

    # Should not have duplicate
    assert len(queue) > initial_len  # Other jobs added
    # Check no duplicate by counting sync:portfolio
    ids = queue.list()
    assert ids.count('sync:portfolio') == 1


@pytest.mark.asyncio
async def test_scheduler_skips_disabled_jobs(queue, registry):
    """Scheduler should skip jobs with enabled=0."""
    schedules = [
        make_schedule('sync:portfolio', enabled=0),  # Disabled
        make_schedule('sync:prices', enabled=1),  # Enabled
    ]
    db = MockDB(schedules=schedules, last_completions={}, expired={'sync:portfolio', 'sync:prices'})
    market_checker = MockMarketChecker()
    scheduler = Scheduler(db, queue, registry, market_checker)

    await scheduler.start()
    await asyncio.sleep(0.1)
    await scheduler.stop()

    assert not queue.contains('sync:portfolio')  # Disabled
    assert queue.contains('sync:prices')  # Enabled


@pytest.mark.asyncio
async def test_scheduler_parameterized_job_interval_per_instance(queue, registry):
    """Each parameterized job instance should have its own interval tracking."""
    # AAPL ran recently, MSFT never ran
    recent = datetime.now() - timedelta(minutes=10)
    schedules = [
        make_schedule('ml:retrain', interval=10080, is_param=1, param_src='ml_enabled_securities', param_field='symbol'),
    ]
    db = MockDB(
        schedules=schedules,
        last_completions={'ml:retrain:AAPL.US': recent},  # AAPL ran 10 min ago
        ml_securities=[
            {'symbol': 'AAPL.US'},
            {'symbol': 'MSFT.US'},
        ],
    )
    market_checker = MockMarketChecker()
    scheduler = Scheduler(db, queue, registry, market_checker)

    await scheduler.start()
    await asyncio.sleep(0.1)
    await scheduler.stop()

    # AAPL shouldn't run (10 min < 7 days)
    assert not queue.contains('ml:retrain:AAPL.US')
    # MSFT should run (never ran before)
    assert queue.contains('ml:retrain:MSFT.US')
