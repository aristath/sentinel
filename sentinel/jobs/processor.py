"""Job processor - executes jobs from the queue one at a time."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from sentinel.jobs.types import Job, MarketTiming
from sentinel.jobs.queue import Queue
from sentinel.jobs.registry import Registry
from sentinel.jobs.market import MarketChecker, BrokerMarketChecker

logger = logging.getLogger(__name__)

# Job execution timeout (15 minutes)
JOB_TIMEOUT = timedelta(minutes=15)


class Processor:
    """Processes jobs from the queue one at a time."""

    # Maximum time to wait for current job to complete during shutdown
    SHUTDOWN_TIMEOUT = 30.0

    def __init__(
        self,
        db,
        queue: Queue,
        registry: Registry,
        market_checker: MarketChecker,
    ):
        self._db = db
        self._queue = queue
        self._registry = registry
        self._market = market_checker
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._current_job: Optional[str] = None

    async def start(self) -> None:
        """Start the processor loop."""
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("Job processor started")

    async def stop(self) -> None:
        """
        Stop the processor loop gracefully.

        Waits for current job to complete (up to SHUTDOWN_TIMEOUT).
        """
        logger.info("Job processor stopping...")
        self._running = False

        if self._current_job:
            logger.info(f"Waiting for job {self._current_job} to complete...")

        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=self.SHUTDOWN_TIMEOUT)
            except asyncio.TimeoutError:
                logger.warning(f"Shutdown timeout: cancelling job {self._current_job}")
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
            except asyncio.CancelledError:
                pass

        logger.info("Job processor stopped")

    async def _loop(self) -> None:
        """Main processing loop."""
        while self._running:
            job = self._queue.peek()
            if job is None:
                await asyncio.sleep(1)
                continue

            await self._process_job(job)

    async def _process_job(self, job: Job) -> None:
        """Process a single job."""
        job_id = job.id()
        job_type = job.type()
        self._current_job = job_id

        try:
            # 1. Check dependencies
            try:
                deps_satisfied = await self._check_dependencies(job)
            except Exception as e:
                logger.error(f"Failed to check dependencies for {job_id}: {e}")
                # Remove from queue, will be re-added by heartbeat
                await self._queue.remove(job_id)
                return

            if not deps_satisfied:
                # Dependencies not satisfied - remove from queue
                # Heartbeat will re-add when deps are satisfied
                await self._queue.remove(job_id)
                logger.debug(f"Job {job_id} waiting for dependencies, removed from queue")
                return

            # 2. Check market timing
            if not self._can_execute_now(job):
                # Can't run yet - remove from queue
                # Heartbeat will re-add when timing allows
                await self._queue.remove(job_id)
                logger.debug(f"Job {job_id} waiting for market timing, removed from queue")
                return

            # 3. Remove from queue and execute
            await self._queue.remove(job_id)

            start = datetime.now()
            try:
                await asyncio.wait_for(
                    job.execute(),
                    timeout=JOB_TIMEOUT.total_seconds(),
                )

                duration_ms = int((datetime.now() - start).total_seconds() * 1000)

                # Update last_run timestamp (for non-parameterized jobs)
                if ':' not in job_id or job_id.count(':') == 1:
                    # Simple job like "sync:portfolio" - update last_run
                    try:
                        await self._db.mark_job_completed(job_type)
                    except Exception as e:
                        logger.warning(f"Failed to mark job {job_type} completed: {e}")

                # Log to history (don't crash if logging fails)
                try:
                    await self._db.log_job_execution(
                        job_id, job_type, 'completed', None, duration_ms, 0
                    )
                except Exception as log_err:
                    logger.warning(f"Failed to log job execution: {log_err}")
                logger.info(f"Job {job_id} completed in {duration_ms}ms")

            except asyncio.TimeoutError:
                duration_ms = int(JOB_TIMEOUT.total_seconds() * 1000)

                # Mark job as failed for backoff (simple jobs only)
                if ':' not in job_id or job_id.count(':') == 1:
                    try:
                        await self._db.mark_job_failed(job_type)
                    except Exception as e:
                        logger.warning(f"Failed to mark job {job_type} as failed: {e}")

                try:
                    await self._db.log_job_execution(
                        job_id, job_type, 'failed', 'Job timed out after 15 minutes', duration_ms, 0
                    )
                except Exception as log_err:
                    logger.warning(f"Failed to log job execution: {log_err}")
                logger.error(f"Job {job_id} timed out after 15 minutes")

            except Exception as e:
                duration_ms = int((datetime.now() - start).total_seconds() * 1000)

                # Mark job as failed for backoff (simple jobs only)
                if ':' not in job_id or job_id.count(':') == 1:
                    try:
                        await self._db.mark_job_failed(job_type)
                    except Exception as mark_err:
                        logger.warning(f"Failed to mark job {job_type} as failed: {mark_err}")

                try:
                    await self._db.log_job_execution(
                        job_id, job_type, 'failed', str(e), duration_ms, 0
                    )
                except Exception as log_err:
                    logger.warning(f"Failed to log job execution: {log_err}")
                logger.error(f"Job {job_id} failed: {e}")

        finally:
            self._current_job = None

    async def _check_dependencies(self, job: Job) -> bool:
        """
        Check if all dependencies are satisfied.
        If any dependency is expired, mark it for immediate run.
        Returns False if any dependency is not satisfied.

        For parameterized dependencies, ALL instances must be fresh.
        """
        # Use market-aware interval for dependency freshness check
        market_open = self._market.is_any_market_open() if self._market else False

        all_deps_satisfied = True

        for dep_type in job.dependencies():
            # Check if this dependency is a parameterized job type
            schedule = await self._db.get_job_schedule(dep_type)

            if schedule and schedule.get('is_parameterized'):
                # Parameterized dependency - check ALL instances
                dep_satisfied = await self._check_parameterized_dependency(
                    schedule, market_open
                )
                if not dep_satisfied:
                    all_deps_satisfied = False
            else:
                # Simple dependency - check single job type
                is_expired = await self._db.is_job_expired(dep_type, market_open=market_open)
                is_in_queue = self._queue.contains(dep_type)

                if is_expired or is_in_queue:
                    if is_expired and not is_in_queue:
                        # Force dependency to run by setting last_run to 0
                        await self._db.set_job_last_run(dep_type, 0)
                        logger.debug(f"Marked dependency {dep_type} for immediate run")
                    all_deps_satisfied = False

        return all_deps_satisfied

    async def _check_parameterized_dependency(self, schedule: dict, market_open: bool) -> bool:
        """
        Check if ALL instances of a parameterized job are fresh.
        Returns True only if every instance is not expired and not in queue.
        """
        from datetime import datetime, timedelta

        job_type = schedule['job_type']
        param_source = schedule.get('parameter_source')
        param_field = schedule.get('parameter_field')

        if not param_source or not param_field:
            logger.warning(f"Parameterized dep {job_type} missing parameter config")
            return True  # Can't check, assume satisfied

        # Get entities
        source_method = getattr(self._db, f'get_{param_source}', None)
        if not source_method:
            logger.warning(f"Unknown parameter source for dep: {param_source}")
            return True  # Can't check, assume satisfied

        try:
            entities = await source_method()
        except Exception as e:
            logger.warning(f"Failed to get entities for dep {job_type}: {e}")
            return True  # Can't check, assume satisfied

        if not entities:
            return True  # No instances to check

        # Calculate interval
        interval_minutes = schedule['interval_minutes']
        if market_open and schedule.get('interval_market_open_minutes'):
            interval_minutes = schedule['interval_market_open_minutes']
        interval = timedelta(minutes=interval_minutes)

        # Check each instance
        for entity in entities:
            param_value = entity.get(param_field)
            if not param_value:
                continue

            job_id = f'{job_type}:{param_value}'

            # Check if in queue (pending execution)
            if self._queue.contains(job_id):
                return False  # Instance pending, dep not satisfied

            # Check if expired (needs to run)
            last = await self._db.get_last_job_completion_by_id(job_id)
            if last is None or datetime.now() - last >= interval:
                # Instance is expired, force it to run
                # For parameterized jobs, we can't set last_run directly
                # The scheduler will pick it up on next heartbeat
                logger.debug(f"Parameterized dep instance {job_id} is expired")
                return False

        return True  # All instances are fresh

    def _can_execute_now(self, job: Job) -> bool:
        """Check if job can execute based on market timing."""
        timing = job.market_timing()

        if timing == MarketTiming.ANY_TIME:
            return True
        elif timing == MarketTiming.DURING_MARKET_OPEN:
            return self._market.is_any_market_open()
        elif timing == MarketTiming.AFTER_MARKET_CLOSE:
            return not self._market.is_any_market_open()
        elif timing == MarketTiming.ALL_MARKETS_CLOSED:
            return self._market.are_all_markets_closed()

        return True
