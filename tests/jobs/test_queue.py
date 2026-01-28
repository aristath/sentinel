"""Tests for jobs/queue.py - Simple FIFO job queue."""

import pytest

from sentinel.jobs.types import BaseJob
from sentinel.jobs.queue import Queue


class MockJob(BaseJob):
    """Test job implementation."""

    async def execute(self) -> None:
        pass


@pytest.fixture
def queue():
    """Create a fresh queue for each test."""
    return Queue()


@pytest.fixture
def job():
    """Create a test job."""
    return MockJob(_id="test:job", _job_type="test")


@pytest.mark.asyncio
async def test_enqueue_adds_job_to_queue(queue, job):
    """Enqueue should add job to the queue."""
    result = await queue.enqueue(job)
    assert result is True
    assert len(queue) == 1
    assert queue.contains("test:job")


@pytest.mark.asyncio
async def test_enqueue_deduplicates_by_id(queue, job):
    """Enqueue should not add duplicate jobs."""
    result1 = await queue.enqueue(job)
    result2 = await queue.enqueue(job)

    assert result1 is True
    assert result2 is False
    assert len(queue) == 1


@pytest.mark.asyncio
async def test_peek_returns_first_job(queue):
    """Peek should return the first job without removing it."""
    job1 = MockJob(_id="job:1", _job_type="test")
    job2 = MockJob(_id="job:2", _job_type="test")

    await queue.enqueue(job1)
    await queue.enqueue(job2)

    peeked = queue.peek()
    assert peeked.id() == "job:1"
    assert len(queue) == 2  # Still 2, not removed


@pytest.mark.asyncio
async def test_peek_returns_none_when_empty(queue):
    """Peek should return None when queue is empty."""
    result = queue.peek()
    assert result is None


@pytest.mark.asyncio
async def test_remove_deletes_job(queue, job):
    """Remove should delete job from queue."""
    await queue.enqueue(job)
    assert queue.contains("test:job")

    removed = await queue.remove("test:job")
    assert removed is not None
    assert removed.id() == "test:job"
    assert not queue.contains("test:job")
    assert len(queue) == 0


@pytest.mark.asyncio
async def test_remove_returns_none_if_not_found(queue):
    """Remove should return None if job not in queue."""
    removed = await queue.remove("nonexistent")
    assert removed is None


@pytest.mark.asyncio
async def test_contains_returns_correct_status(queue, job):
    """contains should return correct status."""
    assert not queue.contains("test:job")

    await queue.enqueue(job)
    assert queue.contains("test:job")

    await queue.remove("test:job")
    assert not queue.contains("test:job")


@pytest.mark.asyncio
async def test_list_returns_job_ids_in_order(queue):
    """list should return job IDs in order."""
    job1 = MockJob(_id="job:1", _job_type="test")
    job2 = MockJob(_id="job:2", _job_type="test")
    job3 = MockJob(_id="job:3", _job_type="test")

    await queue.enqueue(job1)
    await queue.enqueue(job2)
    await queue.enqueue(job3)

    ids = queue.list()
    assert ids == ["job:1", "job:2", "job:3"]


@pytest.mark.asyncio
async def test_get_all_returns_jobs_in_order(queue):
    """get_all should return jobs in order."""
    job1 = MockJob(_id="job:1", _job_type="test")
    job2 = MockJob(_id="job:2", _job_type="test")

    await queue.enqueue(job1)
    await queue.enqueue(job2)

    jobs = queue.get_all()
    assert len(jobs) == 2
    assert jobs[0].id() == "job:1"
    assert jobs[1].id() == "job:2"


@pytest.mark.asyncio
async def test_len_returns_queue_size(queue):
    """len should return queue size."""
    assert len(queue) == 0

    job1 = MockJob(_id="job:1", _job_type="test")
    job2 = MockJob(_id="job:2", _job_type="test")

    await queue.enqueue(job1)
    assert len(queue) == 1

    await queue.enqueue(job2)
    assert len(queue) == 2

    await queue.remove("job:1")
    assert len(queue) == 1


@pytest.mark.asyncio
async def test_fifo_order_maintained(queue):
    """Queue should maintain FIFO order."""
    job1 = MockJob(_id="job:1", _job_type="test")
    job2 = MockJob(_id="job:2", _job_type="test")
    job3 = MockJob(_id="job:3", _job_type="test")

    await queue.enqueue(job1)
    await queue.enqueue(job2)
    await queue.enqueue(job3)

    # Peek returns first
    assert queue.peek().id() == "job:1"

    # Remove first
    removed = await queue.remove("job:1")
    assert removed.id() == "job:1"

    # Now job:2 is first
    assert queue.peek().id() == "job:2"
