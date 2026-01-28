"""Tests for jobs/types.py - Core job types and protocols."""

import pytest
from datetime import datetime, timedelta

from sentinel.jobs.types import (
    MarketTiming,
    Job,
    BaseJob,
    JobWrapper,
)


def test_market_timing_enum_values():
    """MarketTiming enum should have correct integer values."""
    assert MarketTiming.ANY_TIME == 0
    assert MarketTiming.AFTER_MARKET_CLOSE == 1
    assert MarketTiming.DURING_MARKET_OPEN == 2
    assert MarketTiming.ALL_MARKETS_CLOSED == 3


class ConcreteJob(BaseJob):
    """Concrete implementation for testing."""

    async def execute(self) -> None:
        pass


def test_base_job_implements_protocol():
    """BaseJob concrete subclass should satisfy Job protocol."""
    job = ConcreteJob(
        _id="test:job",
        _job_type="test",
    )
    # Protocol compliance check - should have all required methods
    assert hasattr(job, 'id')
    assert hasattr(job, 'type')
    assert hasattr(job, 'execute')
    assert hasattr(job, 'dependencies')
    assert hasattr(job, 'timeout')
    assert hasattr(job, 'market_timing')
    assert hasattr(job, 'subject')


def test_base_job_id_returns_correct_value():
    """BaseJob.id() should return the configured ID."""
    job = ConcreteJob(
        _id="sync:portfolio",
        _job_type="sync",
    )
    assert job.id() == "sync:portfolio"


def test_base_job_type_returns_correct_value():
    """BaseJob.type() should return the configured type."""
    job = ConcreteJob(
        _id="sync:portfolio",
        _job_type="sync:portfolio",
    )
    assert job.type() == "sync:portfolio"


def test_base_job_dependencies_returns_list():
    """BaseJob.dependencies() should return the configured list."""
    job = ConcreteJob(
        _id="scoring:calculate",
        _job_type="scoring",
        _dependencies=["sync:prices", "sync:portfolio"],
    )
    assert job.dependencies() == ["sync:prices", "sync:portfolio"]


def test_base_job_dependencies_defaults_to_empty():
    """BaseJob.dependencies() should default to empty list."""
    job = ConcreteJob(
        _id="test:job",
        _job_type="test",
    )
    assert job.dependencies() == []


def test_base_job_timeout_returns_timedelta():
    """BaseJob.timeout() should return the configured timeout."""
    job = ConcreteJob(
        _id="test:job",
        _job_type="test",
        _timeout=timedelta(minutes=10),
    )
    assert job.timeout() == timedelta(minutes=10)


def test_base_job_timeout_defaults_to_5_minutes():
    """BaseJob.timeout() should default to 5 minutes."""
    job = ConcreteJob(
        _id="test:job",
        _job_type="test",
    )
    assert job.timeout() == timedelta(minutes=5)


def test_base_job_market_timing_returns_configured():
    """BaseJob.market_timing() should return configured timing."""
    job = ConcreteJob(
        _id="test:job",
        _job_type="test",
        _market_timing=MarketTiming.AFTER_MARKET_CLOSE,
    )
    assert job.market_timing() == MarketTiming.AFTER_MARKET_CLOSE


def test_base_job_market_timing_defaults_to_any_time():
    """BaseJob.market_timing() should default to ANY_TIME."""
    job = ConcreteJob(
        _id="test:job",
        _job_type="test",
    )
    assert job.market_timing() == MarketTiming.ANY_TIME


def test_base_job_subject_returns_configured():
    """BaseJob.subject() should return configured subject."""
    job = ConcreteJob(
        _id="ml:retrain:AAPL.US",
        _job_type="ml:retrain",
        _subject="AAPL.US",
    )
    assert job.subject() == "AAPL.US"


def test_base_job_subject_defaults_to_empty():
    """BaseJob.subject() should default to empty string."""
    job = ConcreteJob(
        _id="test:job",
        _job_type="test",
    )
    assert job.subject() == ""


def test_job_wrapper_stores_enqueued_at():
    """JobWrapper should store enqueue timestamp."""
    job = ConcreteJob(_id="test:job", _job_type="test")
    before = datetime.now()
    wrapper = JobWrapper(job=job)
    after = datetime.now()

    assert before <= wrapper.enqueued_at <= after


def test_job_wrapper_wraps_job():
    """JobWrapper should wrap a job instance."""
    job = ConcreteJob(_id="test:job", _job_type="test")
    wrapper = JobWrapper(job=job)

    assert wrapper.job is job
    assert wrapper.job.id() == "test:job"
    assert wrapper.job.type() == "test"
