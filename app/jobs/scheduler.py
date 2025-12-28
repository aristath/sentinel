"""APScheduler setup for background jobs.

Simplified scheduler with 4 consolidated jobs:
1. sync_cycle - Every 15 minutes, handles trading operations
2. daily_pipeline - Hourly, processes per-symbol data
3. daily_maintenance - Daily at 3am, backup and cleanup
4. weekly_maintenance - Weekly on Sunday, integrity checks
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler: AsyncIOScheduler = None

# Job failure tracking (job_id -> list of failure timestamps)
_job_failures: dict[str, list[datetime]] = defaultdict(list)


async def _get_job_settings() -> dict[str, int]:
    """Get job interval settings from database."""
    from app.repositories import SettingsRepository

    settings_repo = SettingsRepository()

    return {
        "sync_cycle_minutes": int(
            await settings_repo.get_float("job_sync_cycle_minutes", 15.0)
        ),
        "maintenance_hour": int(
            await settings_repo.get_float("job_maintenance_hour", 3.0)
        ),
    }


def job_listener(event):
    """Listen to job execution events and track failures."""
    from app.config import settings

    if event.exception:
        job_id = event.job_id
        failure_time = datetime.now()

        _job_failures[job_id].append(failure_time)

        failure_window = timedelta(hours=settings.job_failure_window_hours)
        cutoff = failure_time - failure_window
        _job_failures[job_id] = [ft for ft in _job_failures[job_id] if ft > cutoff]

        recent_failures = len(_job_failures[job_id])
        if recent_failures >= settings.job_failure_threshold:
            logger.error(
                f"Job '{job_id}' has failed {recent_failures} times in the last "
                f"{settings.job_failure_window_hours} hour(s). Last error: {event.exception}"
            )
        else:
            logger.warning(
                f"Job '{job_id}' failed (failure {recent_failures}/"
                f"{settings.job_failure_threshold}): {event.exception}"
            )
    else:
        if event.job_id in _job_failures:
            _job_failures[event.job_id].clear()


async def init_scheduler() -> AsyncIOScheduler:
    """Initialize the APScheduler with consolidated jobs."""
    global scheduler

    scheduler = AsyncIOScheduler()
    scheduler.add_listener(job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

    # Import job functions
    from app.jobs.daily_pipeline import run_daily_pipeline
    from app.jobs.dividend_reinvestment import auto_reinvest_dividends
    from app.jobs.maintenance import run_daily_maintenance, run_weekly_maintenance
    from app.jobs.stock_discovery import discover_new_stocks
    from app.jobs.sync_cycle import run_sync_cycle
    from app.jobs.universe_pruning import prune_universe

    # Get settings
    job_settings = await _get_job_settings()
    sync_cycle_minutes = job_settings["sync_cycle_minutes"]
    maintenance_hour = job_settings["maintenance_hour"]

    # Job 1: Sync Cycle - every 15 minutes (configurable)
    # Handles: trades, cash flows, portfolio, prices (market-aware),
    #          recommendations (holistic), trade execution (market-aware), display
    scheduler.add_job(
        run_sync_cycle,
        IntervalTrigger(minutes=sync_cycle_minutes),
        id="sync_cycle",
        name="Sync Cycle",
        replace_existing=True,
    )

    # Job 2: Daily Pipeline - hourly
    # Handles: historical data sync, metrics calculation, score refresh
    # Processes stocks sequentially, only those not synced in 24 hours
    scheduler.add_job(
        run_daily_pipeline,
        IntervalTrigger(hours=1),
        id="daily_pipeline",
        name="Daily Pipeline",
        replace_existing=True,
    )

    # Job 3: Daily Maintenance - daily at configured hour
    # Handles: backup, cleanup, WAL checkpoint
    scheduler.add_job(
        run_daily_maintenance,
        CronTrigger(hour=maintenance_hour, minute=0),
        id="daily_maintenance",
        name="Daily Maintenance",
        replace_existing=True,
    )

    # Job 4: Weekly Maintenance - Sunday, 1 hour after daily maintenance
    # Handles: integrity checks, old backup cleanup
    scheduler.add_job(
        run_weekly_maintenance,
        CronTrigger(day_of_week=6, hour=(maintenance_hour + 1) % 24, minute=0),
        id="weekly_maintenance",
        name="Weekly Maintenance",
        replace_existing=True,
    )

    # Job 5: Dividend Reinvestment - daily, 30 minutes after daily maintenance
    # Handles: automatic reinvestment of dividends
    scheduler.add_job(
        auto_reinvest_dividends,
        CronTrigger(hour=maintenance_hour, minute=30),
        id="dividend_reinvestment",
        name="Dividend Reinvestment",
        replace_existing=True,
    )

    # Job 6: Universe Pruning - monthly on first day of month
    # Handles: automatic removal of low-quality stocks
    scheduler.add_job(
        prune_universe,
        CronTrigger(day=1, hour=maintenance_hour, minute=0),
        id="universe_pruning",
        name="Universe Pruning",
        replace_existing=True,
    )

    # Job 7: Stock Discovery - monthly on 15th of month at 2am
    # Handles: automatic discovery and addition of high-quality stocks
    # Note: discover_new_stocks checks stock_discovery_enabled internally
    scheduler.add_job(
        discover_new_stocks,
        CronTrigger(day=15, hour=2, minute=0),
        id="stock_discovery",
        name="Stock Discovery",
        replace_existing=True,
    )

    logger.info(
        f"Scheduler initialized with 7 jobs - "
        f"sync_cycle:{sync_cycle_minutes}m, daily_pipeline:1h, "
        f"maintenance:{maintenance_hour}:00, dividend_reinvestment:{maintenance_hour}:30, "
        f"universe_pruning:1st of month {maintenance_hour}:00, "
        f"stock_discovery:15th of month 02:00"
    )
    return scheduler


async def reschedule_all_jobs():
    """Reschedule jobs with current settings from database."""
    if not scheduler:
        logger.warning("Scheduler not initialized, cannot reschedule")
        return

    job_settings = await _get_job_settings()
    sync_cycle_minutes = job_settings["sync_cycle_minutes"]
    maintenance_hour = job_settings["maintenance_hour"]

    # Reschedule sync cycle
    scheduler.reschedule_job(
        "sync_cycle", trigger=IntervalTrigger(minutes=sync_cycle_minutes)
    )

    # Daily pipeline is fixed at hourly, no reschedule needed

    # Reschedule maintenance jobs
    scheduler.reschedule_job(
        "daily_maintenance", trigger=CronTrigger(hour=maintenance_hour, minute=0)
    )
    scheduler.reschedule_job(
        "weekly_maintenance",
        trigger=CronTrigger(day_of_week=6, hour=(maintenance_hour + 1) % 24, minute=0),
    )
    scheduler.reschedule_job(
        "dividend_reinvestment",
        trigger=CronTrigger(hour=maintenance_hour, minute=30),
    )
    scheduler.reschedule_job(
        "universe_pruning",
        trigger=CronTrigger(day=1, hour=maintenance_hour, minute=0),
    )

    logger.info(
        f"Jobs rescheduled - sync_cycle:{sync_cycle_minutes}m, "
        f"maintenance:{maintenance_hour}:00, dividend_reinvestment:{maintenance_hour}:30, "
        f"universe_pruning:1st of month {maintenance_hour}:00"
    )


def start_scheduler():
    """Start the scheduler."""
    if scheduler and not scheduler.running:
        scheduler.start()
        logger.info("Scheduler started")


def stop_scheduler():
    """Stop the scheduler."""
    if scheduler and scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped")


def get_scheduler() -> AsyncIOScheduler:
    """Get the scheduler instance."""
    return scheduler


def get_job_health_status() -> dict:
    """Get health status of all scheduled jobs."""
    if not scheduler:
        return {}

    status = {}
    jobs = scheduler.get_jobs()

    for job in jobs:
        job_id = job.id
        recent_failures = len(_job_failures.get(job_id, []))

        from app.config import settings

        status[job_id] = {
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "recent_failures": recent_failures,
            "healthy": recent_failures < settings.job_failure_threshold,
        }

    return status
