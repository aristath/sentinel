"""APScheduler setup for background jobs."""

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

from app.config import settings

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler: AsyncIOScheduler = None

# Job failure tracking (job_id -> list of failure timestamps)
_job_failures: dict[str, list[datetime]] = defaultdict(list)


def job_listener(event):
    """Listen to job execution events and track failures."""
    from app.config import settings

    if event.exception:
        job_id = event.job_id
        failure_time = datetime.now()

        _job_failures[job_id].append(failure_time)

        failure_window = timedelta(hours=settings.job_failure_window_hours)
        cutoff = failure_time - failure_window
        _job_failures[job_id] = [
            ft for ft in _job_failures[job_id] if ft > cutoff
        ]

        recent_failures = len(_job_failures[job_id])
        if recent_failures >= settings.job_failure_threshold:
            logger.error(
                f"Job '{job_id}' has failed {recent_failures} times in the last {settings.job_failure_window_hours} hour(s). "
                f"Last error: {event.exception}"
            )
        else:
            logger.warning(
                f"Job '{job_id}' failed (failure {recent_failures}/{settings.job_failure_threshold}): {event.exception}"
            )
    else:
        if event.job_id in _job_failures:
            _job_failures[event.job_id].clear()


def init_scheduler() -> AsyncIOScheduler:
    """Initialize the APScheduler with error tracking."""
    global scheduler

    scheduler = AsyncIOScheduler()

    scheduler.add_listener(job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

    from app.jobs.daily_sync import sync_portfolio, sync_prices
    from app.jobs.cash_rebalance import check_and_rebalance
    from app.jobs.score_refresh import refresh_all_scores
    from app.jobs.cash_flow_sync import sync_cash_flows
    from app.jobs.historical_data_sync import sync_historical_data
    from app.jobs.maintenance import run_daily_maintenance, run_weekly_maintenance
    from app.jobs.sync_trades import sync_trades

    # Tradernet portfolio sync (every 2 minutes)
    scheduler.add_job(
        sync_portfolio,
        IntervalTrigger(minutes=2),
        id="portfolio_sync",
        name="Portfolio Sync",
        replace_existing=True,
    )

    # Tradernet trade sync (every 4 minutes)
    scheduler.add_job(
        sync_trades,
        IntervalTrigger(minutes=4),
        id="trade_sync",
        name="Trade Sync",
        replace_existing=True,
    )

    # Yahoo price sync (every 7 minutes)
    scheduler.add_job(
        sync_prices,
        IntervalTrigger(minutes=7),
        id="price_sync",
        name="Price Sync",
        replace_existing=True,
    )

    # Cash-based rebalance check (every 15 minutes)
    scheduler.add_job(
        check_and_rebalance,
        IntervalTrigger(minutes=15),
        id="cash_rebalance_check",
        name="Cash Rebalance Check",
        replace_existing=True,
    )

    # Stock score refresh (every 10 minutes)
    scheduler.add_job(
        refresh_all_scores,
        IntervalTrigger(minutes=10),
        id="score_refresh",
        name="Score Refresh",
        replace_existing=True,
    )

    # Cash flow sync (daily at 1 AM)
    scheduler.add_job(
        sync_cash_flows,
        CronTrigger(hour=1, minute=0),
        id="cash_flow_sync",
        name="Cash Flow Sync",
        replace_existing=True,
    )

    # Historical data sync (daily at 8 PM, after market close)
    scheduler.add_job(
        sync_historical_data,
        CronTrigger(hour=20, minute=0),
        id="historical_data_sync",
        name="Historical Data Sync",
        replace_existing=True,
    )

    # Daily maintenance (at 3 AM - backup, cleanup, WAL checkpoint)
    scheduler.add_job(
        run_daily_maintenance,
        CronTrigger(hour=3, minute=0),
        id="daily_maintenance",
        name="Daily Maintenance",
        replace_existing=True,
    )

    # Weekly maintenance (Sunday at 4 AM - integrity check)
    scheduler.add_job(
        run_weekly_maintenance,
        CronTrigger(day_of_week=6, hour=4, minute=0),
        id="weekly_maintenance",
        name="Weekly Maintenance",
        replace_existing=True,
    )

    logger.info("Scheduler initialized with jobs")
    return scheduler


def start_scheduler():
    """Start the scheduler."""
    global scheduler
    if scheduler and not scheduler.running:
        scheduler.start()
        logger.info("Scheduler started")


def stop_scheduler():
    """Stop the scheduler."""
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped")


def get_scheduler() -> AsyncIOScheduler:
    """Get the scheduler instance."""
    global scheduler
    if scheduler is None:
        scheduler = init_scheduler()
    return scheduler


def get_job_health_status() -> dict:
    """Get health status of all scheduled jobs."""
    global scheduler, _job_failures

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
