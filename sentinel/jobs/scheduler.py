"""Heartbeat-based job scheduler."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from sentinel.jobs.market import BrokerMarketChecker
from sentinel.jobs.queue import Queue
from sentinel.jobs.registry import Registry
from sentinel.jobs.types import MarketTiming

logger = logging.getLogger(__name__)

# Heartbeat interval in seconds
HEARTBEAT_INTERVAL = 2.0


class Scheduler:
    """Heartbeat-based job scheduler that enqueues expired jobs."""

    def __init__(
        self,
        db,
        queue: Queue,
        registry: Registry,
        market_checker=None,
    ):
        self._db = db
        self._queue = queue
        self._registry = registry
        self._market = market_checker
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the scheduler heartbeat loop."""
        self._running = True
        # Initial check on startup
        await self._check_expired_jobs()
        self._task = asyncio.create_task(self._heartbeat_loop())
        logger.info("Scheduler started (heartbeat every 2s)")

    async def stop(self) -> None:
        """Stop the scheduler loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Scheduler stopped")

    async def _heartbeat_loop(self) -> None:
        """Main heartbeat loop - runs every 2 seconds."""
        while self._running:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            if not self._running:
                return
            await self._check_expired_jobs()

    async def _check_expired_jobs(self) -> None:
        """Check all jobs for expiration and enqueue if needed."""
        try:
            # Refresh market data if available
            if self._market and isinstance(self._market, BrokerMarketChecker):
                await self._market.ensure_fresh()

            # Check if any market is open (for interval calculation)
            market_open = self._market.is_any_market_open() if self._market else False

            # Read schedules from database
            schedules = await self._db.get_job_schedules()
        except Exception as e:
            logger.error(f"Failed to check expired jobs: {e}")
            return

        for schedule in schedules:
            if not schedule["enabled"]:
                continue

            job_type = schedule["job_type"]

            # Skip unregistered job types
            if not self._registry.is_registered(job_type):
                continue

            if schedule.get("is_parameterized"):
                await self._check_parameterized_job(schedule, market_open)
            else:
                await self._check_simple_job(schedule, market_open)

    async def _check_simple_job(self, schedule: dict, market_open: bool) -> None:
        """Check and enqueue a simple (non-parameterized) job if expired."""
        job_type = schedule["job_type"]

        # Skip if already in queue
        if self._queue.contains(job_type):
            return

        # Check if expired using database method (with market-aware interval)
        if await self._db.is_job_expired(job_type, market_open=market_open):
            try:
                job = await self._registry.create(job_type, {"_schedule": schedule})
                self._apply_schedule_to_job(job, schedule)
                if await self._queue.enqueue(job):
                    logger.debug(f"Enqueued expired job: {job_type}")
            except Exception as e:
                logger.warning(f"Failed to create/enqueue job {job_type}: {e}")

    async def _check_parameterized_job(self, schedule: dict, market_open: bool) -> None:
        """Check and enqueue parameterized jobs (one per entity) if expired."""
        job_type = schedule["job_type"]
        param_source = schedule.get("parameter_source")
        param_field = schedule.get("parameter_field")

        if not param_source or not param_field:
            logger.warning(f"Parameterized job {job_type} missing parameter_source or parameter_field")
            return

        # Get parameter values from database
        source_method = getattr(self._db, f"get_{param_source}", None)
        if not source_method:
            logger.warning(f"Unknown parameter source: {param_source}")
            return

        try:
            entities = await source_method()
        except Exception as e:
            logger.warning(f"Failed to get parameter source {param_source}: {e}")
            return

        # Use shorter interval when markets are open (if configured)
        from datetime import datetime, timedelta

        interval_minutes = schedule["interval_minutes"]
        if market_open and schedule.get("interval_market_open_minutes"):
            interval_minutes = schedule["interval_market_open_minutes"]
        interval = timedelta(minutes=interval_minutes)

        for entity in entities:
            param_value = entity.get(param_field)
            if not param_value:
                continue

            job_id = f"{job_type}:{param_value}"

            # Skip if already in queue
            if self._queue.contains(job_id):
                continue

            # For parameterized jobs, check expiration based on job_history
            # (they don't have individual last_run in job_schedules)
            last = await self._db.get_last_job_completion_by_id(job_id)

            if last is None or datetime.now() - last >= interval:
                try:
                    job = await self._registry.create(
                        job_type,
                        {
                            param_field: param_value,
                            "_schedule": schedule,
                        },
                    )
                    self._apply_schedule_to_job(job, schedule)
                    if await self._queue.enqueue(job):
                        logger.debug(f"Enqueued parameterized job: {job_id}")
                except Exception as e:
                    logger.warning(f"Failed to create parameterized job {job_id}: {e}")

    def _apply_schedule_to_job(self, job, schedule: dict) -> None:
        """Apply schedule configuration to job instance."""
        # Override market_timing from database if set
        market_timing = schedule.get("market_timing")
        if market_timing is not None and hasattr(job, "_market_timing"):
            job._market_timing = MarketTiming(market_timing)

        # Override dependencies from database if set
        deps_str = schedule.get("dependencies")
        if deps_str and hasattr(job, "_dependencies"):
            try:
                deps = json.loads(deps_str)
                if isinstance(deps, list):
                    job._dependencies = deps
            except (json.JSONDecodeError, TypeError):
                pass


# Keep SyncScheduler as alias for backward compatibility
SyncScheduler = Scheduler
