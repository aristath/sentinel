"""Tests for jobs/processor.py - Job processor."""

import pytest
import pytest_asyncio
import asyncio
from datetime import datetime, timedelta

from sentinel.jobs.types import BaseJob, MarketTiming
from sentinel.jobs.queue import Queue
from sentinel.jobs.registry import Registry, RetryConfig
from sentinel.jobs.processor import Processor


class SuccessJob(BaseJob):
    """Job that succeeds."""

    def __init__(self, _id, _job_type, executed_callback=None, **kwargs):
        super().__init__(_id=_id, _job_type=_job_type, **kwargs)
        self.executed_callback = executed_callback
        self.was_executed = False

    async def execute(self) -> None:
        self.was_executed = True
        if self.executed_callback:
            self.executed_callback()


class FailJob(BaseJob):
    """Job that fails."""

    async def execute(self) -> None:
        raise Exception("Job failed intentionally")


class SlowJob(BaseJob):
    """Job that takes a long time."""

    async def execute(self) -> None:
        await asyncio.sleep(10)


class MockDB:
    """Mock database for testing."""

    def __init__(self, expired_jobs=None):
        self._expired = expired_jobs or set()
        self._last_run = {}
        self._logs = []
        self._schedules = {}  # job_type -> schedule dict

    async def is_job_expired(self, job_type: str, market_open: bool = False) -> bool:
        return job_type in self._expired

    async def set_job_last_run(self, job_type: str, timestamp: int) -> None:
        self._last_run[job_type] = timestamp
        if timestamp == 0:
            self._expired.add(job_type)

    async def mark_job_completed(self, job_type: str) -> None:
        self._last_run[job_type] = int(datetime.now().timestamp())
        self._expired.discard(job_type)

    async def mark_job_failed(self, job_type: str) -> None:
        self._last_run[job_type] = int(datetime.now().timestamp())

    async def get_job_schedule(self, job_type: str):
        return self._schedules.get(job_type)

    async def log_job_execution(
        self, job_id: str, job_type: str, status: str,
        error: str, duration_ms: int, retry_count: int
    ) -> None:
        self._logs.append({
            'job_id': job_id,
            'job_type': job_type,
            'status': status,
            'error': error,
            'duration_ms': duration_ms,
            'retry_count': retry_count,
        })


class MockMarketChecker:
    """Mock market checker."""

    def __init__(self, can_execute=True):
        self._can_execute = can_execute

    def is_any_market_open(self) -> bool:
        return not self._can_execute

    def is_security_market_open(self, symbol: str) -> bool:
        return not self._can_execute

    def are_all_markets_closed(self) -> bool:
        return self._can_execute


@pytest.fixture
def queue():
    return Queue()


@pytest.fixture
def db():
    return MockDB()


@pytest_asyncio.fixture
async def registry():
    reg = Registry()
    await reg.register('test', lambda p: SuccessJob(_id='test:job', _job_type='test'))
    await reg.register('fail', lambda p: FailJob(_id='fail:job', _job_type='fail'), RetryConfig(max_retries=2))
    return reg


@pytest.fixture
def market_checker():
    return MockMarketChecker(can_execute=True)


@pytest.fixture
def processor(db, queue, registry, market_checker):
    return Processor(db, queue, registry, market_checker)


@pytest.mark.asyncio
async def test_processor_starts_and_stops(processor):
    """Processor should start and stop cleanly."""
    await processor.start()
    assert processor._running is True

    await processor.stop()
    assert processor._running is False


@pytest.mark.asyncio
async def test_processor_executes_job(processor, queue, db):
    """Processor should execute enqueued jobs."""
    executed = []
    job = SuccessJob(
        _id='test:job',
        _job_type='test',
        executed_callback=lambda: executed.append(True),
    )

    await queue.enqueue(job)
    await processor.start()

    # Wait for job to be processed
    for _ in range(10):
        await asyncio.sleep(0.1)
        if len(db._logs) > 0:
            break

    await processor.stop()

    assert len(executed) == 1
    assert len(db._logs) == 1
    assert db._logs[0]['status'] == 'completed'


@pytest.mark.asyncio
async def test_processor_logs_success(processor, queue, db):
    """Processor should log successful execution."""
    job = SuccessJob(_id='test:job', _job_type='test')

    await queue.enqueue(job)
    await processor.start()

    for _ in range(10):
        await asyncio.sleep(0.1)
        if len(db._logs) > 0:
            break

    await processor.stop()

    assert len(db._logs) == 1
    assert db._logs[0]['job_id'] == 'test:job'
    assert db._logs[0]['status'] == 'completed'
    assert db._logs[0]['error'] is None


@pytest.mark.asyncio
async def test_processor_handles_exception(db, queue, registry, market_checker):
    """Processor should handle job exceptions."""
    await registry.register(
        'fail',
        lambda p: FailJob(_id='fail:job', _job_type='fail'),
        RetryConfig(max_retries=0),
    )

    processor = Processor(db, queue, registry, market_checker)
    job = FailJob(_id='fail:job', _job_type='fail')
    await queue.enqueue(job)
    await processor.start()

    for _ in range(10):
        await asyncio.sleep(0.1)
        if len(db._logs) > 0:
            break

    await processor.stop()

    assert len(db._logs) >= 1
    assert db._logs[0]['status'] == 'failed'
    assert 'intentionally' in db._logs[0]['error']


@pytest.mark.asyncio
async def test_processor_removes_job_when_deps_not_satisfied(queue, registry, market_checker):
    """Processor should remove jobs with incomplete dependencies from queue."""
    db = MockDB(expired_jobs={'sync:prices'})  # Dependency is expired
    processor = Processor(db, queue, registry, market_checker)

    job = SuccessJob(
        _id='scoring:calculate',
        _job_type='scoring',
        _dependencies=['sync:prices'],
    )

    await queue.enqueue(job)
    await processor.start()

    # Wait for job to be processed
    await asyncio.sleep(0.2)
    await processor.stop()

    # Job should have been removed (deps not satisfied)
    # Heartbeat would re-add it later when deps are satisfied
    assert not queue.contains('scoring:calculate')
    assert len(db._logs) == 0  # Job was not executed


@pytest.mark.asyncio
async def test_processor_marks_expired_dep_for_immediate_run(queue, registry, market_checker):
    """Processor should set last_run=0 for expired dependencies."""
    db = MockDB(expired_jobs={'sync:prices'})
    processor = Processor(db, queue, registry, market_checker)

    job = SuccessJob(
        _id='scoring:calculate',
        _job_type='scoring',
        _dependencies=['sync:prices'],
    )

    await queue.enqueue(job)
    await processor.start()

    await asyncio.sleep(0.2)
    await processor.stop()

    # Dependency should have been marked for immediate run
    assert db._last_run.get('sync:prices') == 0


@pytest.mark.asyncio
async def test_processor_skips_wrong_market_timing(db, queue, registry):
    """Processor should skip jobs with wrong market timing."""
    # Market checker that says markets are open (so ALL_MARKETS_CLOSED fails)
    market_checker = MockMarketChecker(can_execute=False)
    processor = Processor(db, queue, registry, market_checker)

    job = SuccessJob(
        _id='analytics:job',
        _job_type='test',
        _market_timing=MarketTiming.ALL_MARKETS_CLOSED,
    )

    await queue.enqueue(job)
    await processor.start()

    await asyncio.sleep(0.2)
    await processor.stop()

    # Job should have been removed (wrong market timing)
    assert not queue.contains('analytics:job')
    assert len(db._logs) == 0


@pytest.mark.asyncio
async def test_processor_tracks_current_job(db, queue, registry, market_checker):
    """Processor should track the current job being processed."""
    processor = Processor(db, queue, registry, market_checker)

    # Initially no current job
    assert processor._current_job is None

    job = SuccessJob(_id='test:job', _job_type='test')
    await queue.enqueue(job)

    await processor.start()
    for _ in range(10):
        await asyncio.sleep(0.1)
        if len(db._logs) > 0:
            break
    await processor.stop()

    # After processing, current job should be cleared
    assert processor._current_job is None


@pytest.mark.asyncio
async def test_processor_graceful_shutdown(db, queue, registry, market_checker):
    """Processor should wait for current job to complete on shutdown."""
    processor = Processor(db, queue, registry, market_checker)

    await processor.start()
    assert processor._running is True

    # Stop should complete cleanly
    await processor.stop()
    assert processor._running is False


class FailingLogDB:
    """Mock database that fails on log_job_execution."""

    def __init__(self):
        self._expired = set()
        self._last_run = {}
        self._schedules = {}

    async def is_job_expired(self, job_type: str, market_open: bool = False) -> bool:
        return job_type in self._expired

    async def set_job_last_run(self, job_type: str, timestamp: int) -> None:
        self._last_run[job_type] = timestamp

    async def mark_job_completed(self, job_type: str) -> None:
        self._last_run[job_type] = int(datetime.now().timestamp())

    async def mark_job_failed(self, job_type: str) -> None:
        self._last_run[job_type] = int(datetime.now().timestamp())

    async def get_job_schedule(self, job_type: str):
        return self._schedules.get(job_type)

    async def log_job_execution(self, *args, **kwargs) -> None:
        raise Exception("Database logging failed")


@pytest.mark.asyncio
async def test_processor_does_not_crash_on_log_failure(queue, registry, market_checker):
    """Processor should not crash when only logging fails."""
    failing_db = FailingLogDB()
    processor = Processor(failing_db, queue, registry, market_checker)

    job = SuccessJob(_id='test:job', _job_type='test')
    await queue.enqueue(job)

    await processor.start()
    await asyncio.sleep(0.3)
    await processor.stop()

    # Job was executed (removed from queue)
    assert job.was_executed is True
    assert not queue.contains('test:job')
