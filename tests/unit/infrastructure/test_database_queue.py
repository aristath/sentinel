"""Tests for database query queue.

These tests validate the serialized write operation queue.
"""

import asyncio
from datetime import datetime

import pytest

from app.core.database.queue import Priority, QueryQueue, QueuedOperation


class TestPriority:
    """Test priority levels."""

    def test_priority_ordering(self):
        """Test that lower numbers are higher priority."""
        assert Priority.CRITICAL < Priority.HIGH
        assert Priority.HIGH < Priority.NORMAL
        assert Priority.NORMAL < Priority.LOW
        assert Priority.LOW < Priority.BACKGROUND

    def test_priority_values(self):
        """Test specific priority values."""
        assert Priority.CRITICAL == 0
        assert Priority.BACKGROUND == 200


class TestQueuedOperation:
    """Test queued operation data class."""

    def test_creates_operation_with_defaults(self):
        """Test creating operation with default values."""
        op = QueuedOperation(
            priority=Priority.NORMAL,
            timestamp=datetime.now(),
        )

        assert op.priority == Priority.NORMAL
        assert op.name == ""
        assert op.retry_count == 0
        assert op.max_retries == 3
        assert op.operation_id is not None

    def test_operations_order_by_priority(self):
        """Test that operations are ordered by priority first."""
        now = datetime.now()
        op1 = QueuedOperation(priority=Priority.LOW, timestamp=now)
        op2 = QueuedOperation(priority=Priority.HIGH, timestamp=now)

        assert op2 < op1  # Higher priority (lower number) comes first

    def test_operations_order_by_timestamp_when_same_priority(self):
        """Test that operations with same priority are ordered by timestamp."""
        from datetime import timedelta

        now = datetime.now()
        earlier = now - timedelta(seconds=1)

        op1 = QueuedOperation(priority=Priority.NORMAL, timestamp=now)
        op2 = QueuedOperation(priority=Priority.NORMAL, timestamp=earlier)

        assert op2 < op1  # Earlier timestamp comes first


class TestQueryQueueInit:
    """Test query queue initialization."""

    def test_init_with_defaults(self):
        """Test initializing with default values."""
        queue = QueryQueue()

        assert queue._max_retries == 3
        assert queue._retry_delay == 1.0
        assert queue._running is False
        assert queue._processed_count == 0
        assert queue._failed_count == 0

    def test_init_with_custom_values(self):
        """Test initializing with custom values."""
        queue = QueryQueue(max_retries=5, retry_delay=2.0)

        assert queue._max_retries == 5
        assert queue._retry_delay == 2.0


class TestQueryQueueStartStop:
    """Test queue start and stop."""

    @pytest.mark.asyncio
    async def test_start_sets_running(self):
        """Test that start sets running flag."""
        queue = QueryQueue()

        await queue.start()

        assert queue._running is True
        assert queue._worker_task is not None

        await queue.stop()

    @pytest.mark.asyncio
    async def test_start_idempotent(self):
        """Test that start is idempotent."""
        queue = QueryQueue()

        await queue.start()
        task1 = queue._worker_task
        await queue.start()  # Should not create new task
        task2 = queue._worker_task

        assert task1 is task2

        await queue.stop()

    @pytest.mark.asyncio
    async def test_stop_clears_running(self):
        """Test that stop clears running flag."""
        queue = QueryQueue()

        await queue.start()
        await queue.stop()

        assert queue._running is False

    @pytest.mark.asyncio
    async def test_stop_idempotent(self):
        """Test that stop is idempotent."""
        queue = QueryQueue()

        await queue.start()
        await queue.stop()
        await queue.stop()  # Should not raise

        assert queue._running is False


class TestQueryQueueEnqueue:
    """Test enqueueing operations."""

    @pytest.mark.asyncio
    async def test_enqueue_executes_function(self):
        """Test that enqueue executes the function."""
        queue = QueryQueue()
        await queue.start()

        executed = False

        async def test_func():
            nonlocal executed
            executed = True
            return "result"

        result = await queue.enqueue(test_func, name="test")

        assert executed
        assert result == "result"

        await queue.stop()

    @pytest.mark.asyncio
    async def test_enqueue_returns_function_result(self):
        """Test that enqueue returns the function's result."""
        queue = QueryQueue()
        await queue.start()

        async def test_func():
            return {"data": 123}

        result = await queue.enqueue(test_func)

        assert result == {"data": 123}

        await queue.stop()

    @pytest.mark.asyncio
    async def test_enqueue_propagates_exception(self):
        """Test that exceptions are propagated after retries."""
        queue = QueryQueue(max_retries=1, retry_delay=0.01)
        await queue.start()

        async def failing_func():
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            await queue.enqueue(failing_func, name="failing")

        await queue.stop()


class TestQueryQueueEnqueueNowait:
    """Test non-waiting enqueue."""

    @pytest.mark.asyncio
    async def test_enqueue_nowait_returns_future(self):
        """Test that enqueue_nowait returns a future."""
        queue = QueryQueue()
        await queue.start()

        async def test_func():
            return "result"

        future = queue.enqueue_nowait(test_func)

        assert isinstance(future, asyncio.Future)

        result = await future
        assert result == "result"

        await queue.stop()


class TestQueryQueueRetry:
    """Test retry behavior."""

    @pytest.mark.asyncio
    async def test_retries_on_failure(self):
        """Test that operations are retried on failure."""
        queue = QueryQueue(max_retries=3, retry_delay=0.01)
        await queue.start()

        call_count = 0

        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("transient error")
            return "success"

        result = await queue.enqueue(flaky_func)

        assert result == "success"
        assert call_count == 3  # First attempt + 2 retries

        await queue.stop()

    @pytest.mark.asyncio
    async def test_fails_after_max_retries(self):
        """Test that operation fails after max retries."""
        queue = QueryQueue(max_retries=2, retry_delay=0.01)
        await queue.start()

        call_count = 0

        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise ValueError("persistent error")

        with pytest.raises(ValueError):
            await queue.enqueue(always_fails)

        # First attempt + max_retries
        assert call_count == 3  # 1 + 2 retries

        await queue.stop()


class TestQueryQueuePriority:
    """Test priority ordering."""

    @pytest.mark.asyncio
    async def test_processes_higher_priority_first(self):
        """Test that higher priority operations are processed first."""
        queue = QueryQueue()
        # Don't start worker yet - we want to control processing

        results = []

        async def track(name):
            results.append(name)
            return name

        # Enqueue in reverse priority order
        queue.enqueue_nowait(lambda: track("low"), priority=Priority.LOW)
        queue.enqueue_nowait(lambda: track("critical"), priority=Priority.CRITICAL)
        queue.enqueue_nowait(lambda: track("normal"), priority=Priority.NORMAL)

        # Process all
        await queue.start()
        await asyncio.sleep(0.1)  # Allow processing
        await queue.stop()

        # Should be processed in priority order
        assert results == ["critical", "normal", "low"]


class TestQueryQueueMetrics:
    """Test queue metrics."""

    def test_queue_size(self):
        """Test queue_size property."""
        queue = QueryQueue()

        assert queue.queue_size == 0

    def test_is_running(self):
        """Test is_running property."""
        queue = QueryQueue()

        assert queue.is_running is False

    @pytest.mark.asyncio
    async def test_get_metrics(self):
        """Test get_metrics method."""
        queue = QueryQueue()
        await queue.start()

        async def success_func():
            return True

        await queue.enqueue(success_func)

        metrics = queue.get_metrics()

        assert "queue_size" in metrics
        assert "processed_count" in metrics
        assert "failed_count" in metrics
        assert "retry_count" in metrics
        assert "running" in metrics
        assert metrics["processed_count"] == 1
        assert metrics["running"] is True

        await queue.stop()


class TestGetQueryQueue:
    """Test get_query_queue function."""

    def test_raises_when_not_initialized(self):
        """Test that get_query_queue raises when not initialized."""
        import app.infrastructure.database.queue as module

        original = module._query_queue
        module._query_queue = None

        try:
            from app.core.database.queue import get_query_queue

            with pytest.raises(RuntimeError, match="not initialized"):
                get_query_queue()
        finally:
            module._query_queue = original


class TestInitQueryQueue:
    """Test init_query_queue function."""

    @pytest.mark.asyncio
    async def test_initializes_and_starts_queue(self):
        """Test that init_query_queue creates and starts queue."""
        import app.infrastructure.database.queue as module

        original = module._query_queue

        try:
            from app.core.database.queue import init_query_queue

            queue = await init_query_queue()

            assert queue is not None
            assert queue.is_running is True
            assert module._query_queue is queue

            await queue.stop()
        finally:
            module._query_queue = original


class TestShutdownQueryQueue:
    """Test shutdown_query_queue function."""

    @pytest.mark.asyncio
    async def test_stops_and_clears_queue(self):
        """Test that shutdown stops and clears the queue."""
        import app.infrastructure.database.queue as module

        original = module._query_queue

        try:
            from app.core.database.queue import (
                init_query_queue,
                shutdown_query_queue,
            )

            await init_query_queue()
            await shutdown_query_queue()

            assert module._query_queue is None
        finally:
            module._query_queue = original

    @pytest.mark.asyncio
    async def test_handles_none_queue(self):
        """Test that shutdown handles None queue gracefully."""
        import app.infrastructure.database.queue as module

        original = module._query_queue
        module._query_queue = None

        try:
            from app.core.database.queue import shutdown_query_queue

            # Should not raise
            await shutdown_query_queue()
        finally:
            module._query_queue = original


class TestEnqueueConvenienceFunction:
    """Test the enqueue convenience function."""

    @pytest.mark.asyncio
    async def test_enqueue_uses_global_queue(self):
        """Test that enqueue uses the global queue."""
        import app.infrastructure.database.queue as module

        original = module._query_queue

        try:
            from app.core.database.queue import (
                enqueue,
                init_query_queue,
                shutdown_query_queue,
            )

            await init_query_queue()

            async def test_func():
                return "result"

            result = await enqueue(test_func, name="test")

            assert result == "result"

            await shutdown_query_queue()
        finally:
            module._query_queue = original
