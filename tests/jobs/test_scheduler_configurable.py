"""Tests for configurable job scheduler."""

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
    """Mock database for testing configurable scheduler."""

    def __init__(self, schedules=None, completions=None, entities=None, expired=None):
        self._schedules = schedules or []
        self._completions = completions or {}
        self._entities = entities or {}
        self._expired = expired or set()
        self._last_run = {}

    async def get_job_schedules(self):
        return self._schedules

    async def get_job_schedule(self, job_type: str):
        for s in self._schedules:
            if s['job_type'] == job_type:
                return s
        return None

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
        if last_run == 0:
            return True
        # Use shorter interval when markets are open
        interval = schedule.get('interval_minutes', 60)
        if market_open and schedule.get('interval_market_open_minutes'):
            interval = schedule['interval_market_open_minutes']
        return int(datetime.now().timestamp()) - last_run >= interval * 60

    async def set_job_last_run(self, job_type: str, timestamp: int) -> None:
        self._last_run[job_type] = timestamp
        if timestamp == 0:
            self._expired.add(job_type)

    async def get_last_job_completion(self, job_type: str):
        return self._completions.get(job_type)

    async def get_last_job_completion_by_id(self, job_id: str):
        return self._completions.get(job_id)

    async def get_ml_enabled_securities(self):
        return self._entities.get('ml_enabled_securities', [])


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


@pytest.fixture
def queue():
    return Queue()


@pytest_asyncio.fixture
async def registry():
    reg = Registry()
    await reg.register('sync:portfolio', lambda p: MockJob(_id='sync:portfolio', _job_type='sync:portfolio'))
    await reg.register('sync:prices', lambda p: MockJob(_id='sync:prices', _job_type='sync:prices'))
    await reg.register('analytics:correlation', lambda p: MockJob(_id='analytics:correlation', _job_type='analytics:correlation'))
    await reg.register('ml:retrain', lambda p: MockJob(_id=f"ml:retrain:{p.get('symbol', 'AAPL')}", _job_type='ml:retrain'))
    await reg.register('ml:monitor', lambda p: MockJob(_id=f"ml:monitor:{p.get('symbol', 'AAPL')}", _job_type='ml:monitor'))
    return reg


@pytest.mark.asyncio
async def test_scheduler_reads_schedules_from_db(queue, registry):
    """Scheduler should read job schedules from database."""
    schedules = [
        {
            'job_type': 'sync:portfolio',
            'enabled': 1,
            'interval_minutes': 30,
            'interval_market_open_minutes': 5,
            'market_timing': 0,
            'is_parameterized': 0,
            'parameter_source': None,
            'parameter_field': None,
        }
    ]
    db = MockDB(schedules=schedules, expired={'sync:portfolio'})
    market = MockMarketChecker()
    scheduler = Scheduler(db, queue, registry, market)

    await scheduler.start()
    await asyncio.sleep(0.1)
    await scheduler.stop()

    assert queue.contains('sync:portfolio')


@pytest.mark.asyncio
async def test_scheduler_respects_enabled_flag(queue, registry):
    """Scheduler should skip disabled jobs."""
    schedules = [
        {
            'job_type': 'sync:portfolio',
            'enabled': 0,  # Disabled
            'interval_minutes': 30,
            'interval_market_open_minutes': 5,
            'market_timing': 0,
            'is_parameterized': 0,
            'parameter_source': None,
            'parameter_field': None,
        },
        {
            'job_type': 'sync:prices',
            'enabled': 1,  # Enabled
            'interval_minutes': 30,
            'interval_market_open_minutes': 5,
            'market_timing': 0,
            'is_parameterized': 0,
            'parameter_source': None,
            'parameter_field': None,
        }
    ]
    db = MockDB(schedules=schedules, expired={'sync:portfolio', 'sync:prices'})
    market = MockMarketChecker()
    scheduler = Scheduler(db, queue, registry, market)

    await scheduler.start()
    await asyncio.sleep(0.1)
    await scheduler.stop()

    assert not queue.contains('sync:portfolio')  # Disabled
    assert queue.contains('sync:prices')  # Enabled


@pytest.mark.asyncio
async def test_scheduler_only_enqueues_expired_jobs(queue, registry):
    """Scheduler should only enqueue jobs that are expired."""
    schedules = [
        {
            'job_type': 'sync:portfolio',
            'enabled': 1,
            'interval_minutes': 60,
            'interval_market_open_minutes': None,
            'market_timing': 0,
            'is_parameterized': 0,
            'parameter_source': None,
            'parameter_field': None,
        }
    ]
    # Set last_run to recent (not expired)
    db = MockDB(schedules=schedules)
    db._last_run['sync:portfolio'] = int(datetime.now().timestamp()) - 10  # 10 sec ago
    market = MockMarketChecker(any_open=False)
    scheduler = Scheduler(db, queue, registry, market)

    await scheduler.start()
    await asyncio.sleep(0.1)
    await scheduler.stop()

    # Not expired yet (10 sec < 60 min interval)
    assert not queue.contains('sync:portfolio')


@pytest.mark.asyncio
async def test_scheduler_handles_parameterized_jobs(queue, registry):
    """Scheduler should create multiple instances for parameterized jobs."""
    schedules = [
        {
            'job_type': 'ml:retrain',
            'enabled': 1,
            'interval_minutes': 10080,
            'interval_market_open_minutes': None,
            'market_timing': 0,
            'is_parameterized': 1,
            'parameter_source': 'ml_enabled_securities',
            'parameter_field': 'symbol',
        }
    ]
    db = MockDB(
        schedules=schedules,
        entities={'ml_enabled_securities': [
            {'symbol': 'AAPL.US'},
            {'symbol': 'MSFT.US'},
        ]}
    )
    market = MockMarketChecker()
    scheduler = Scheduler(db, queue, registry, market)

    await scheduler.start()
    await asyncio.sleep(0.1)
    await scheduler.stop()

    assert queue.contains('ml:retrain:AAPL.US')
    assert queue.contains('ml:retrain:MSFT.US')


@pytest.mark.asyncio
async def test_scheduler_looks_up_parameter_source(queue, registry):
    """Scheduler should call correct db method for parameter_source."""
    schedules = [
        {
            'job_type': 'ml:retrain',
            'enabled': 1,
            'interval_minutes': 10080,
            'interval_market_open_minutes': None,
            'market_timing': 0,
            'is_parameterized': 1,
            'parameter_source': 'ml_enabled_securities',
            'parameter_field': 'symbol',
        }
    ]
    db = MockDB(
        schedules=schedules,
        entities={'ml_enabled_securities': [{'symbol': 'TEST.US'}]}
    )
    market = MockMarketChecker()
    scheduler = Scheduler(db, queue, registry, market)

    await scheduler.start()
    await asyncio.sleep(0.1)
    await scheduler.stop()

    assert queue.contains('ml:retrain:TEST.US')


@pytest.mark.asyncio
async def test_scheduler_skips_unknown_parameter_source(queue, registry):
    """Scheduler should skip parameterized job with unknown parameter_source."""
    schedules = [
        {
            'job_type': 'ml:retrain',
            'enabled': 1,
            'interval_minutes': 10080,
            'interval_market_open_minutes': None,
            'market_timing': 0,
            'is_parameterized': 1,
            'parameter_source': 'unknown_method',  # Does not exist
            'parameter_field': 'symbol',
        }
    ]
    db = MockDB(schedules=schedules)
    market = MockMarketChecker()
    scheduler = Scheduler(db, queue, registry, market)

    await scheduler.start()
    await asyncio.sleep(0.1)
    await scheduler.stop()

    # Should not crash, just skip silently
    assert len(queue) == 0


@pytest.mark.asyncio
async def test_scheduler_uses_correct_job_id_for_parameterized(queue, registry):
    """Parameterized jobs should have ID format job_type:param_value."""
    schedules = [
        {
            'job_type': 'ml:retrain',
            'enabled': 1,
            'interval_minutes': 10080,
            'interval_market_open_minutes': None,
            'market_timing': 0,
            'is_parameterized': 1,
            'parameter_source': 'ml_enabled_securities',
            'parameter_field': 'symbol',
        }
    ]
    db = MockDB(
        schedules=schedules,
        entities={'ml_enabled_securities': [{'symbol': 'GOOG.US'}]}
    )
    market = MockMarketChecker()
    scheduler = Scheduler(db, queue, registry, market)

    await scheduler.start()
    await asyncio.sleep(0.1)
    await scheduler.stop()

    # Job ID should include the parameter value
    ids = queue.list()
    assert 'ml:retrain:GOOG.US' in ids


@pytest.mark.asyncio
async def test_scheduler_parameterized_job_respects_interval(queue, registry):
    """Parameterized jobs should respect per-instance interval."""
    # AAPL completed recently, MSFT never ran
    recent = datetime.now() - timedelta(minutes=10)
    schedules = [
        {
            'job_type': 'ml:retrain',
            'enabled': 1,
            'interval_minutes': 10080,  # 7 days
            'interval_market_open_minutes': None,
            'market_timing': 0,
            'is_parameterized': 1,
            'parameter_source': 'ml_enabled_securities',
            'parameter_field': 'symbol',
        }
    ]
    db = MockDB(
        schedules=schedules,
        completions={'ml:retrain:AAPL.US': recent},  # AAPL ran recently
        entities={'ml_enabled_securities': [
            {'symbol': 'AAPL.US'},
            {'symbol': 'MSFT.US'},
        ]}
    )
    market = MockMarketChecker()
    scheduler = Scheduler(db, queue, registry, market)

    await scheduler.start()
    await asyncio.sleep(0.1)
    await scheduler.stop()

    # AAPL should not run (10 min < 7 days), MSFT should (never ran)
    assert not queue.contains('ml:retrain:AAPL.US')
    assert queue.contains('ml:retrain:MSFT.US')


@pytest.mark.asyncio
async def test_scheduler_skips_unregistered_jobs(queue, registry):
    """Scheduler should skip jobs not registered in the registry."""
    schedules = [
        {
            'job_type': 'unknown:job',  # Not registered
            'enabled': 1,
            'interval_minutes': 30,
            'interval_market_open_minutes': None,
            'market_timing': 0,
            'is_parameterized': 0,
            'parameter_source': None,
            'parameter_field': None,
        }
    ]
    db = MockDB(schedules=schedules, expired={'unknown:job'})
    market = MockMarketChecker()
    scheduler = Scheduler(db, queue, registry, market)

    await scheduler.start()
    await asyncio.sleep(0.1)
    await scheduler.stop()

    # Should not crash, just skip
    assert len(queue) == 0


@pytest.mark.asyncio
async def test_scheduler_applies_market_timing_from_schedule(queue, registry):
    """Scheduler should apply market_timing from database schedule to job."""
    from sentinel.jobs.types import MarketTiming

    schedules = [
        {
            'job_type': 'sync:portfolio',
            'enabled': 1,
            'interval_minutes': 30,
            'interval_market_open_minutes': 5,
            'market_timing': 2,  # DURING_MARKET_OPEN
            'dependencies': '[]',
            'is_parameterized': 0,
            'parameter_source': None,
            'parameter_field': None,
        }
    ]
    db = MockDB(schedules=schedules, expired={'sync:portfolio'})
    market = MockMarketChecker()
    scheduler = Scheduler(db, queue, registry, market)

    await scheduler.start()
    await asyncio.sleep(0.1)
    await scheduler.stop()

    # Get the enqueued job
    jobs = queue.get_all()
    assert len(jobs) == 1
    job = jobs[0]
    assert job.market_timing() == MarketTiming.DURING_MARKET_OPEN


@pytest.mark.asyncio
async def test_scheduler_applies_dependencies_from_schedule(queue, registry):
    """Scheduler should apply dependencies from database schedule to job."""
    schedules = [
        {
            'job_type': 'sync:portfolio',
            'enabled': 1,
            'interval_minutes': 30,
            'interval_market_open_minutes': 5,
            'market_timing': 0,
            'dependencies': '["sync:prices", "sync:quotes"]',
            'is_parameterized': 0,
            'parameter_source': None,
            'parameter_field': None,
        }
    ]
    db = MockDB(schedules=schedules, expired={'sync:portfolio'})
    market = MockMarketChecker()
    scheduler = Scheduler(db, queue, registry, market)

    await scheduler.start()
    await asyncio.sleep(0.1)
    await scheduler.stop()

    # Get the enqueued job
    jobs = queue.get_all()
    assert len(jobs) == 1
    job = jobs[0]
    assert job.dependencies() == ['sync:prices', 'sync:quotes']


@pytest.mark.asyncio
async def test_scheduler_applies_config_to_parameterized_jobs(queue, registry):
    """Scheduler should apply schedule config to parameterized jobs."""
    from sentinel.jobs.types import MarketTiming

    schedules = [
        {
            'job_type': 'ml:retrain',
            'enabled': 1,
            'interval_minutes': 10080,
            'interval_market_open_minutes': None,
            'market_timing': 3,  # ALL_MARKETS_CLOSED
            'dependencies': '["sync:prices"]',
            'is_parameterized': 1,
            'parameter_source': 'ml_enabled_securities',
            'parameter_field': 'symbol',
        }
    ]
    db = MockDB(
        schedules=schedules,
        entities={'ml_enabled_securities': [{'symbol': 'AAPL.US'}]}
    )
    market = MockMarketChecker()
    scheduler = Scheduler(db, queue, registry, market)

    await scheduler.start()
    await asyncio.sleep(0.1)
    await scheduler.stop()

    # Get the enqueued job
    jobs = queue.get_all()
    assert len(jobs) == 1
    job = jobs[0]
    assert job.market_timing() == MarketTiming.ALL_MARKETS_CLOSED
    assert job.dependencies() == ['sync:prices']


@pytest.mark.asyncio
async def test_syncscheduler_alias_works(queue, registry):
    """SyncScheduler should be an alias for Scheduler."""
    schedules = [
        {
            'job_type': 'sync:portfolio',
            'enabled': 1,
            'interval_minutes': 30,
            'market_timing': 0,
            'is_parameterized': 0,
            'parameter_source': None,
            'parameter_field': None,
        }
    ]
    db = MockDB(schedules=schedules, expired={'sync:portfolio'})
    market = MockMarketChecker()
    scheduler = SyncScheduler(db, queue, registry, market)

    await scheduler.start()
    await asyncio.sleep(0.1)
    await scheduler.stop()

    assert queue.contains('sync:portfolio')
