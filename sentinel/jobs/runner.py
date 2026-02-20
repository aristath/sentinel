"""APScheduler-based job runner."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Callable

from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from sentinel.jobs import tasks

logger = logging.getLogger(__name__)

# Module-level state
_scheduler: AsyncIOScheduler | None = None
_deps: dict[str, Any] = {}
_current_job: str | None = None
_market_check_task: asyncio.Task | None = None
_startup_catchup_task: asyncio.Task | None = None

# Job timeout in seconds (15 minutes)
JOB_TIMEOUT = 15 * 60

# How often to check market status and adjust intervals (5 minutes)
MARKET_CHECK_INTERVAL = 5 * 60

# Task registry: job_type -> (task_function, list of dependency keys)
TASK_REGISTRY: dict[str, tuple[Callable, list[str]]] = {
    "sync:portfolio": (tasks.sync_portfolio, ["portfolio"]),
    "sync:prices": (tasks.sync_prices, ["db", "broker", "cache"]),
    "sync:quotes": (tasks.sync_quotes, ["db", "broker"]),
    "sync:metadata": (tasks.sync_metadata, ["db", "broker"]),
    "sync:exchange_rates": (tasks.sync_exchange_rates, []),
    "sync:trades": (tasks.sync_trades, ["db", "broker"]),
    "sync:cashflows": (tasks.sync_cashflows, ["db", "broker"]),
    "sync:dividends": (tasks.sync_dividends, ["db", "broker"]),
    "snapshot:backfill": (tasks.snapshot_backfill, ["db", "currency"]),
    "aggregate:compute": (tasks.aggregate_compute, ["db"]),
    "trading:check_markets": (tasks.trading_check_markets, ["broker", "db", "planner"]),
    "trading:execute": (tasks.trading_execute, ["broker", "db", "planner"]),
    "trading:rebalance": (tasks.trading_rebalance, ["planner"]),
    "trading:balance_fix": (tasks.trading_balance_fix, ["db", "broker"]),
    "planning:refresh": (tasks.planning_refresh, ["db", "planner", "broker"]),
    "backup:r2": (tasks.backup_r2, ["db"]),
}

# Market timing constants (matching database values)
MARKET_TIMING_ANY_TIME = 0
MARKET_TIMING_AFTER_MARKET_CLOSE = 1
MARKET_TIMING_DURING_MARKET_OPEN = 2
MARKET_TIMING_ALL_MARKETS_CLOSED = 3


async def init(
    db,
    broker,
    portfolio,
    planner,
    cache,
    market_checker,
    currency,
) -> AsyncIOScheduler:
    """Create scheduler, load schedules from DB, add all jobs, start.

    Args:
        db: Database instance
        broker: Broker instance
        portfolio: Portfolio instance
        planner: Planner instance
        cache: Cache instance
        market_checker: MarketChecker instance

    Returns:
        The running AsyncIOScheduler instance
    """
    global _scheduler, _deps, _current_job, _market_check_task

    # Store dependencies for task execution
    _deps = {
        "db": db,
        "broker": broker,
        "portfolio": portfolio,
        "planner": planner,
        "cache": cache,
        "market_checker": market_checker,
        "currency": currency,
    }
    _current_job = None

    # Configure APScheduler with proper settings
    jobstores = {"default": MemoryJobStore()}
    executors = {"default": AsyncIOExecutor()}
    job_defaults = {
        "coalesce": True,  # If multiple runs are missed, only run once
        "max_instances": 1,  # Prevent concurrent runs of the same job
        "misfire_grace_time": 60,  # Allow 60 seconds grace for missed runs
    }

    _scheduler = AsyncIOScheduler(
        jobstores=jobstores,
        executors=executors,
        job_defaults=job_defaults,
    )

    # Load schedules from database
    schedules = await db.get_job_schedules()
    schedule_map = {s["job_type"]: s for s in schedules}

    # Check if any market is open (for interval selection)
    market_open = market_checker.is_any_market_open()

    # Add each job
    for job_type in TASK_REGISTRY:
        schedule = schedule_map.get(job_type)
        if schedule:
            _add_job(job_type, schedule, market_open)
        else:
            # Use default 60 minute interval if no schedule found
            logger.warning(f"No schedule found for {job_type}, using 60 minute default")
            _add_job(job_type, {"job_type": job_type, "interval_minutes": 60, "market_timing": 0}, market_open)

    # Start scheduler
    _scheduler.start()
    logger.info(f"APScheduler started with {len(TASK_REGISTRY)} jobs")

    # Start background task to periodically check market status and adjust intervals
    _market_check_task = asyncio.create_task(_market_status_loop())

    # Run snapshot backfill shortly after startup to catch up on missed days
    _startup_catchup_task = asyncio.create_task(_startup_catchup())

    return _scheduler


async def stop() -> None:
    """Shutdown the scheduler."""
    global _scheduler, _current_job, _market_check_task, _startup_catchup_task

    # Stop startup catch-up task
    if _startup_catchup_task:
        _startup_catchup_task.cancel()
        try:
            await _startup_catchup_task
        except asyncio.CancelledError:
            pass
        _startup_catchup_task = None

    # Stop market check task
    if _market_check_task:
        _market_check_task.cancel()
        try:
            await _market_check_task
        except asyncio.CancelledError:
            pass
        _market_check_task = None

    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("APScheduler stopped")

    _current_job = None


async def reschedule(job_type: str, db) -> None:
    """Reload schedule from DB and update APScheduler.

    Args:
        job_type: The job type to reschedule
        db: Database instance to load schedule from
    """
    global _scheduler

    if not _scheduler:
        logger.warning("Scheduler not running, cannot reschedule")
        return

    schedule = await db.get_job_schedule(job_type)
    if not schedule:
        logger.warning(f"No schedule found for {job_type}")
        return

    # Get current market status
    market_checker = _deps.get("market_checker")
    market_open = market_checker.is_any_market_open() if market_checker else False

    # Determine interval
    interval = _get_interval(schedule, market_open)

    try:
        _scheduler.reschedule_job(
            job_type,
            trigger=IntervalTrigger(minutes=interval),
        )
        logger.info(f"Rescheduled {job_type} with interval {interval} minutes")
    except Exception as e:
        logger.error(f"Failed to reschedule {job_type}: {e}")


async def run_now(job_type: str) -> dict:
    """Execute a task immediately.

    Args:
        job_type: The job type to execute

    Returns:
        Dict with status, duration_ms, and optional error
    """
    if job_type not in TASK_REGISTRY:
        return {"status": "failed", "error": f"Unknown job type: {job_type}", "duration_ms": 0}

    # Get schedule for this job (for market timing)
    db = _deps.get("db")
    schedule = await db.get_job_schedule(job_type) if db else None

    if not schedule:
        schedule = {"job_type": job_type, "market_timing": 0}

    start = datetime.now()
    try:
        result = await _run_task(job_type, schedule, skip_timing_check=True)
        duration_ms = int((datetime.now() - start).total_seconds() * 1000)

        if result and result.get("skipped"):
            return {"status": "skipped", "reason": result.get("reason", ""), "duration_ms": duration_ms}

        return {"status": "completed", "duration_ms": duration_ms}
    except Exception as e:
        duration_ms = int((datetime.now() - start).total_seconds() * 1000)
        return {"status": "failed", "error": str(e), "duration_ms": duration_ms}


async def get_status() -> dict:
    """Return scheduler status with current job, upcoming jobs, and recent history.

    Returns:
        {
            "current": "job_type" or None,
            "upcoming": [{"job_type": str, "next_run": ISO datetime}, ...],  # 3 soonest
            "recent": [{"job_type": str, "status": str, "executed_at": ISO datetime}, ...]  # 3 most recent
        }
    """
    global _scheduler, _current_job

    result = {
        "current": _current_job,
        "upcoming": [],
        "recent": [],
    }

    # Get upcoming jobs from scheduler
    if _scheduler:
        jobs = _scheduler.get_jobs()
        upcoming = []
        for job in jobs:
            if job.next_run_time:
                upcoming.append(
                    {
                        "job_type": job.id,
                        "next_run": job.next_run_time.isoformat(),
                    }
                )

        # Sort by next_run time and take top 3
        upcoming.sort(key=lambda x: x["next_run"])
        result["upcoming"] = upcoming[:3]

    # Get recent job history from database (deduplicated by job_type)
    db = _deps.get("db")
    if db:
        history = await db.get_job_history(limit=20)

        # Deduplicate by job_type, keeping most recent
        seen_types = set()
        recent = []
        for entry in history:
            job_type = entry["job_type"]
            if job_type not in seen_types:
                seen_types.add(job_type)
                recent.append(
                    {
                        "job_type": job_type,
                        "status": entry["status"],
                        "executed_at": datetime.fromtimestamp(entry["executed_at"]).isoformat(),
                    }
                )
                if len(recent) >= 3:
                    break

        result["recent"] = recent

    return result


def _get_interval(schedule: dict, market_open: bool) -> int:
    """Determine the appropriate interval based on market status.

    Args:
        schedule: Schedule configuration from database
        market_open: Whether any market is currently open

    Returns:
        Interval in minutes
    """
    interval = schedule.get("interval_minutes", 60)
    if market_open and schedule.get("interval_market_open_minutes"):
        interval = schedule["interval_market_open_minutes"]
    return interval


def _add_job(job_type: str, schedule: dict, market_open: bool) -> None:
    """Add a job to the scheduler with IntervalTrigger.

    Args:
        job_type: The job type identifier
        schedule: Schedule configuration from database
        market_open: Whether any market is currently open
    """
    global _scheduler

    if not _scheduler:
        return

    interval = _get_interval(schedule, market_open)

    # Add job with the async wrapper function directly
    # APScheduler's AsyncIOExecutor will handle running it properly
    _scheduler.add_job(
        _job_executor,
        IntervalTrigger(minutes=interval),
        id=job_type,
        name=job_type,
        args=[job_type, schedule],
        replace_existing=True,
    )

    logger.debug(f"Added job {job_type} with interval {interval} minutes")


async def _job_executor(job_type: str, schedule: dict) -> None:
    """Executor function that APScheduler calls. Wraps _run_task for proper async handling."""
    await _run_task(job_type, schedule)


async def _run_task(job_type: str, schedule: dict, skip_timing_check: bool = False) -> dict | None:
    """Wrapper that handles market timing, timeout, error handling, DB logging.

    Args:
        job_type: The job type to execute
        schedule: Schedule configuration
        skip_timing_check: If True, skip market timing check (for manual runs)

    Returns:
        Dict with result info, or None
    """
    global _current_job

    # Refresh market checker before checking timing
    market_checker = _deps.get("market_checker")
    if market_checker:
        await market_checker.ensure_fresh()

    # Check market timing (unless skipped)
    if not skip_timing_check:
        market_timing = schedule.get("market_timing", 0)

        if market_checker and not _check_market_timing(market_timing, market_checker):
            logger.debug(f"Skipping {job_type}: market timing not satisfied")
            return {"skipped": True, "reason": "market_timing"}

    # Get task function and dependencies
    if job_type not in TASK_REGISTRY:
        logger.error(f"Unknown job type: {job_type}")
        return {"skipped": True, "reason": "unknown_job_type"}

    task_func, dep_keys = TASK_REGISTRY[job_type]

    # Build arguments from dependencies
    args = []
    for key in dep_keys:
        dep = _deps.get(key)
        if dep is None:
            logger.error(f"Missing dependency {key} for job {job_type}")
            return {"skipped": True, "reason": f"missing_dependency:{key}"}
        args.append(dep)

    # Set current job
    _current_job = job_type
    start = datetime.now()
    db = _deps.get("db")

    try:
        # Execute with timeout
        await asyncio.wait_for(task_func(*args), timeout=JOB_TIMEOUT)

        duration_ms = int((datetime.now() - start).total_seconds() * 1000)

        # Log success to DB
        if db:
            await db.mark_job_completed(job_type)
            await db.log_job_execution(job_type, job_type, "completed", None, duration_ms, 0)

        logger.info(f"Job {job_type} completed in {duration_ms}ms")
        return {"status": "completed", "duration_ms": duration_ms}

    except asyncio.TimeoutError:
        duration_ms = int((datetime.now() - start).total_seconds() * 1000)
        error_msg = f"Job {job_type} timed out after {JOB_TIMEOUT}s"
        logger.error(error_msg)

        if db:
            await db.mark_job_failed(job_type)
            await db.log_job_execution(job_type, job_type, "failed", error_msg, duration_ms, 0)

        return {"status": "failed", "error": error_msg, "duration_ms": duration_ms}

    except Exception as e:
        duration_ms = int((datetime.now() - start).total_seconds() * 1000)
        error_msg = str(e)
        logger.error(f"Job {job_type} failed: {error_msg}")

        if db:
            await db.mark_job_failed(job_type)
            await db.log_job_execution(job_type, job_type, "failed", error_msg, duration_ms, 0)

        return {"status": "failed", "error": error_msg, "duration_ms": duration_ms}

    finally:
        _current_job = None


async def _startup_catchup() -> None:
    """Run snapshot backfill shortly after startup to catch up on missed days.

    IntervalTrigger with 1440-min intervals won't fire until 24h after startup,
    so if the app restarts frequently, the daily backfill never gets a chance to run.
    This ensures missing snapshots are filled promptly after each restart.
    """
    await asyncio.sleep(30)  # Let other services stabilize
    logger.info("Startup catch-up: running snapshot:backfill")
    try:
        result = await run_now("snapshot:backfill")
        logger.info("Startup snapshot backfill: %s", result.get("status", "unknown"))
    except Exception as e:
        logger.error("Startup snapshot backfill failed: %s", e)


async def _market_status_loop() -> None:
    """Background loop that checks market status and adjusts job intervals.

    This runs every MARKET_CHECK_INTERVAL seconds and:
    1. Refreshes market checker data
    2. Compares current market status with what jobs are configured for
    3. Reschedules jobs if market status changed (open -> closed or vice versa)
    """
    global _scheduler

    last_market_open = None

    while True:
        try:
            await asyncio.sleep(MARKET_CHECK_INTERVAL)

            market_checker = _deps.get("market_checker")
            if not market_checker:
                continue

            # Refresh market data
            await market_checker.refresh()

            market_open = market_checker.is_any_market_open()

            # If market status changed, reschedule all jobs
            if last_market_open is not None and market_open != last_market_open:
                logger.info(f"Market status changed: {'OPEN' if market_open else 'CLOSED'}, adjusting job intervals")
                await _adjust_all_intervals(market_open)

            last_market_open = market_open

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in market status loop: {e}")
            # Continue running, don't crash the loop


async def _adjust_all_intervals(market_open: bool) -> None:
    """Adjust all job intervals based on market status.

    Args:
        market_open: Whether any market is currently open
    """
    global _scheduler

    if not _scheduler:
        return

    db = _deps.get("db")
    if not db:
        return

    schedules = await db.get_job_schedules()

    for schedule in schedules:
        job_type = schedule["job_type"]
        if job_type not in TASK_REGISTRY:
            continue

        # Only reschedule if this job has different intervals for market open/closed
        interval_normal = schedule.get("interval_minutes", 60)
        interval_open = schedule.get("interval_market_open_minutes")

        if interval_open and interval_open != interval_normal:
            new_interval = interval_open if market_open else interval_normal
            try:
                _scheduler.reschedule_job(
                    job_type,
                    trigger=IntervalTrigger(minutes=new_interval),
                )
                logger.debug(f"Adjusted {job_type} interval to {new_interval} minutes")
            except Exception as e:
                logger.error(f"Failed to adjust interval for {job_type}: {e}")


def _check_market_timing(timing: int, market_checker) -> bool:
    """Check if market timing allows execution.

    Args:
        timing: Market timing value from schedule
        market_checker: MarketChecker instance

    Returns:
        True if timing allows execution
    """
    if timing == MARKET_TIMING_ANY_TIME:
        return True
    elif timing == MARKET_TIMING_AFTER_MARKET_CLOSE:
        return not market_checker.is_any_market_open()
    elif timing == MARKET_TIMING_DURING_MARKET_OPEN:
        return market_checker.is_any_market_open()
    elif timing == MARKET_TIMING_ALL_MARKETS_CLOSED:
        return market_checker.are_all_markets_closed()

    return True
