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


async def _get_all_job_settings() -> dict[str, float]:
    """Get all job interval settings from database in one query."""
    from app.api.settings import get_job_settings

    return await get_job_settings()


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


async def init_scheduler() -> AsyncIOScheduler:
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
    from app.jobs.health_check import run_health_check
    from app.jobs.metrics_calculation import calculate_metrics_for_all_stocks

    # Get all job intervals from database in one query
    job_settings = await _get_all_job_settings()
    portfolio_minutes = int(job_settings["job_portfolio_sync_minutes"])
    trade_minutes = int(job_settings["job_trade_sync_minutes"])
    price_minutes = int(job_settings["job_price_sync_minutes"])
    score_minutes = int(job_settings["job_score_refresh_minutes"])
    rebalance_minutes = int(job_settings["job_rebalance_check_minutes"])
    cash_flow_hour = int(job_settings["job_cash_flow_sync_hour"])
    historical_hour = int(job_settings["job_historical_sync_hour"])
    maintenance_hour = int(job_settings["job_maintenance_hour"])

    # Tradernet portfolio sync
    scheduler.add_job(
        sync_portfolio,
        IntervalTrigger(minutes=portfolio_minutes),
        id="portfolio_sync",
        name="Portfolio Sync",
        replace_existing=True,
    )

    # Tradernet trade sync
    scheduler.add_job(
        sync_trades,
        IntervalTrigger(minutes=trade_minutes),
        id="trade_sync",
        name="Trade Sync",
        replace_existing=True,
    )

    # Yahoo price sync
    scheduler.add_job(
        sync_prices,
        IntervalTrigger(minutes=price_minutes),
        id="price_sync",
        name="Price Sync",
        replace_existing=True,
    )

    # Cash-based rebalance check
    scheduler.add_job(
        check_and_rebalance,
        IntervalTrigger(minutes=rebalance_minutes),
        id="cash_rebalance_check",
        name="Cash Rebalance Check",
        replace_existing=True,
    )

    # Stock score refresh
    scheduler.add_job(
        refresh_all_scores,
        IntervalTrigger(minutes=score_minutes),
        id="score_refresh",
        name="Score Refresh",
        replace_existing=True,
    )

    # Cash flow sync (daily)
    scheduler.add_job(
        sync_cash_flows,
        CronTrigger(hour=cash_flow_hour, minute=0),
        id="cash_flow_sync",
        name="Cash Flow Sync",
        replace_existing=True,
    )

    # Historical data sync (daily, after market close)
    scheduler.add_job(
        sync_historical_data,
        CronTrigger(hour=historical_hour, minute=0),
        id="historical_data_sync",
        name="Historical Data Sync",
        replace_existing=True,
    )

    # Metrics calculation (daily, after historical data sync)
    scheduler.add_job(
        calculate_metrics_for_all_stocks,
        CronTrigger(hour=historical_hour, minute=30),  # 30 minutes after historical sync
        id="metrics_calculation",
        name="Metrics Calculation",
        replace_existing=True,
    )

    # Daily maintenance (backup, cleanup, WAL checkpoint)
    scheduler.add_job(
        run_daily_maintenance,
        CronTrigger(hour=maintenance_hour, minute=0),
        id="daily_maintenance",
        name="Daily Maintenance",
        replace_existing=True,
    )

    # Weekly maintenance (Sunday, 1 hour after daily maintenance)
    scheduler.add_job(
        run_weekly_maintenance,
        CronTrigger(day_of_week=6, hour=(maintenance_hour + 1) % 24, minute=0),
        id="weekly_maintenance",
        name="Weekly Maintenance",
        replace_existing=True,
    )

    # Database health check (hourly)
    scheduler.add_job(
        run_health_check,
        IntervalTrigger(hours=1),
        id="health_check",
        name="Database Health Check",
        replace_existing=True,
    )

    logger.info(
        f"Scheduler initialized - portfolio:{portfolio_minutes}m, trade:{trade_minutes}m, "
        f"price:{price_minutes}m, score:{score_minutes}m, rebalance:{rebalance_minutes}m"
    )
    return scheduler


async def reschedule_all_jobs():
    """Reschedule all jobs with current settings from database."""
    global scheduler

    if not scheduler:
        logger.warning("Scheduler not initialized, cannot reschedule")
        return

    # Get all job intervals from database in one query
    job_settings = await _get_all_job_settings()
    portfolio_minutes = int(job_settings["job_portfolio_sync_minutes"])
    trade_minutes = int(job_settings["job_trade_sync_minutes"])
    price_minutes = int(job_settings["job_price_sync_minutes"])
    score_minutes = int(job_settings["job_score_refresh_minutes"])
    rebalance_minutes = int(job_settings["job_rebalance_check_minutes"])
    cash_flow_hour = int(job_settings["job_cash_flow_sync_hour"])
    historical_hour = int(job_settings["job_historical_sync_hour"])
    maintenance_hour = int(job_settings["job_maintenance_hour"])

    # Reschedule interval jobs
    scheduler.reschedule_job(
        "portfolio_sync", trigger=IntervalTrigger(minutes=portfolio_minutes)
    )
    scheduler.reschedule_job(
        "trade_sync", trigger=IntervalTrigger(minutes=trade_minutes)
    )
    scheduler.reschedule_job(
        "price_sync", trigger=IntervalTrigger(minutes=price_minutes)
    )
    scheduler.reschedule_job(
        "score_refresh", trigger=IntervalTrigger(minutes=score_minutes)
    )
    scheduler.reschedule_job(
        "cash_rebalance_check", trigger=IntervalTrigger(minutes=rebalance_minutes)
    )

    # Reschedule cron jobs
    scheduler.reschedule_job(
        "cash_flow_sync", trigger=CronTrigger(hour=cash_flow_hour, minute=0)
    )
    scheduler.reschedule_job(
        "historical_data_sync", trigger=CronTrigger(hour=historical_hour, minute=0)
    )
    scheduler.reschedule_job(
        "metrics_calculation", trigger=CronTrigger(hour=historical_hour, minute=30)
    )
    scheduler.reschedule_job(
        "daily_maintenance", trigger=CronTrigger(hour=maintenance_hour, minute=0)
    )
    scheduler.reschedule_job(
        "weekly_maintenance",
        trigger=CronTrigger(day_of_week=6, hour=(maintenance_hour + 1) % 24, minute=0),
    )

    # Health check is fixed at hourly, no reschedule needed

    logger.info(
        f"Jobs rescheduled - portfolio:{portfolio_minutes}m, trade:{trade_minutes}m, "
        f"price:{price_minutes}m, score:{score_minutes}m, rebalance:{rebalance_minutes}m"
    )


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
