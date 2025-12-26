"""
Query Queue - Serialized write operations for database reliability.

This module provides:
1. Single-writer pattern to prevent concurrent write conflicts
2. Priority ordering (trades before background sync)
3. Automatic retry for transient failures
4. Idempotent operation design

All write operations should go through the queue to prevent corruption.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import Any, Callable, Coroutine, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class Priority(IntEnum):
    """
    Operation priority levels.

    Lower number = higher priority (processed first).
    """

    CRITICAL = 0  # Trade execution, order placement
    HIGH = 10  # Portfolio sync, position updates
    NORMAL = 50  # Score calculation, price updates
    LOW = 100  # Historical data sync, maintenance
    BACKGROUND = 200  # Cleanup, aggregation


@dataclass(order=True)
class QueuedOperation:
    """
    A queued database operation.

    Operations are ordered by:
    1. Priority (lower = first)
    2. Timestamp (earlier = first)
    """

    priority: int
    timestamp: datetime = field(compare=True)
    operation_id: str = field(default_factory=lambda: str(uuid4()), compare=False)
    name: str = field(default="", compare=False)
    func: Callable[[], Coroutine] = field(compare=False, default=None)
    result_future: asyncio.Future = field(compare=False, default=None)
    retry_count: int = field(default=0, compare=False)
    max_retries: int = field(default=3, compare=False)

    def __post_init__(self):
        if self.result_future is None:
            self.result_future = asyncio.get_event_loop().create_future()


class QueryQueue:
    """
    Serializes all write operations to prevent concurrent conflicts.

    Features:
    - Single writer: Only one operation executes at a time
    - Priority queue: Critical operations (trades) go first
    - Retry logic: Transient failures are retried with backoff
    - Metrics: Track queue depth, latency, failure rates

    Usage:
        queue = QueryQueue()
        await queue.start()

        # Enqueue operations
        result = await queue.enqueue(
            func=lambda: db.execute("INSERT ..."),
            name="insert_trade",
            priority=Priority.CRITICAL
        )
    """

    def __init__(self, max_retries: int = 3, retry_delay: float = 1.0):
        self._queue: asyncio.PriorityQueue[QueuedOperation] = asyncio.PriorityQueue()
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None
        self._max_retries = max_retries
        self._retry_delay = retry_delay

        # Metrics
        self._processed_count = 0
        self._failed_count = 0
        self._retry_count = 0

    async def start(self):
        """Start the queue worker."""
        if self._running:
            return

        self._running = True
        self._worker_task = asyncio.create_task(self._worker())
        logger.info("Query queue started")

    async def stop(self):
        """Stop the queue worker and drain remaining operations."""
        if not self._running:
            return

        self._running = False

        # Process remaining items
        while not self._queue.empty():
            await self._process_one()

        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

        logger.info(
            f"Query queue stopped. "
            f"Processed: {self._processed_count}, "
            f"Failed: {self._failed_count}, "
            f"Retries: {self._retry_count}"
        )

    async def enqueue(
        self,
        func: Callable[[], Coroutine],
        name: str = "",
        priority: Priority = Priority.NORMAL,
        max_retries: int = None,
    ) -> Any:
        """
        Enqueue an operation and wait for its result.

        Args:
            func: Async function to execute (no arguments, use closure)
            name: Human-readable name for logging
            priority: Operation priority
            max_retries: Override default max retries

        Returns:
            Result of the function

        Raises:
            Exception from the function after all retries exhausted
        """
        operation = QueuedOperation(
            priority=priority,
            timestamp=datetime.now(),
            name=name,
            func=func,
            max_retries=max_retries if max_retries is not None else self._max_retries,
        )

        await self._queue.put(operation)
        logger.debug(
            f"Enqueued: {name} (priority={priority}, queue_size={self._queue.qsize()})"
        )

        # Wait for result
        return await operation.result_future

    def enqueue_nowait(
        self,
        func: Callable[[], Coroutine],
        name: str = "",
        priority: Priority = Priority.NORMAL,
    ) -> asyncio.Future:
        """
        Enqueue an operation without waiting.

        Returns a Future that can be awaited later.
        """
        operation = QueuedOperation(
            priority=priority,
            timestamp=datetime.now(),
            name=name,
            func=func,
            max_retries=self._max_retries,
        )

        self._queue.put_nowait(operation)
        logger.debug(f"Enqueued (nowait): {name} (priority={priority})")

        return operation.result_future

    async def _worker(self):
        """Main worker loop - processes one operation at a time."""
        while self._running:
            try:
                await self._process_one()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker error: {e}", exc_info=True)
                await asyncio.sleep(1)  # Prevent tight loop on persistent errors

    async def _process_one(self):
        """Process a single operation from the queue."""
        try:
            operation = await asyncio.wait_for(
                self._queue.get(), timeout=1.0  # Check running flag periodically
            )
        except asyncio.TimeoutError:
            return

        try:
            result = await operation.func()
            operation.result_future.set_result(result)
            self._processed_count += 1
            logger.debug(f"Completed: {operation.name}")

        except Exception as e:
            if operation.retry_count < operation.max_retries:
                # Retry with exponential backoff
                operation.retry_count += 1
                self._retry_count += 1
                delay = self._retry_delay * (2 ** (operation.retry_count - 1))

                logger.warning(
                    f"Retry {operation.retry_count}/{operation.max_retries} for {operation.name}: {e}"
                )

                await asyncio.sleep(delay)
                await self._queue.put(operation)
            else:
                # All retries exhausted
                self._failed_count += 1
                operation.result_future.set_exception(e)
                logger.error(
                    f"Failed after {operation.max_retries} retries: {operation.name}: {e}"
                )

    @property
    def queue_size(self) -> int:
        """Current queue depth."""
        return self._queue.qsize()

    @property
    def is_running(self) -> bool:
        """Whether the queue worker is running."""
        return self._running

    def get_metrics(self) -> dict:
        """Get queue metrics."""
        return {
            "queue_size": self._queue.qsize(),
            "processed_count": self._processed_count,
            "failed_count": self._failed_count,
            "retry_count": self._retry_count,
            "running": self._running,
        }


# Global queue instance
_query_queue: Optional[QueryQueue] = None


def get_query_queue() -> QueryQueue:
    """Get the global query queue instance."""
    global _query_queue
    if _query_queue is None:
        raise RuntimeError(
            "Query queue not initialized. Call init_query_queue() first."
        )
    return _query_queue


async def init_query_queue() -> QueryQueue:
    """Initialize and start the global query queue."""
    global _query_queue
    _query_queue = QueryQueue()
    await _query_queue.start()
    return _query_queue


async def shutdown_query_queue():
    """Stop the global query queue."""
    global _query_queue
    if _query_queue is not None:
        await _query_queue.stop()
        _query_queue = None


async def enqueue(
    func: Callable[[], Coroutine],
    name: str = "",
    priority: Priority = Priority.NORMAL,
) -> Any:
    """
    Convenience function to enqueue an operation.

    Usage:
        from app.infrastructure.database.queue import enqueue, Priority

        result = await enqueue(
            func=lambda: db.execute("INSERT INTO trades ..."),
            name="insert_trade",
            priority=Priority.CRITICAL
        )
    """
    queue = get_query_queue()
    return await queue.enqueue(func, name, priority)
