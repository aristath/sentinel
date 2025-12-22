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


def heartbeat_job():
    """Send heartbeat pulse to LED display every 60 seconds."""
    from app.infrastructure.hardware.led_display import get_led_display

    display = get_led_display()
    # Trigger heartbeat for API-based display
    display.trigger_heartbeat()
    # Also try serial if connected
    if display.is_connected:
        display.show_heartbeat()
    logger.debug("Heartbeat pulse triggered")


def wifi_check_job():
    """Check wifi connectivity and update LED display."""
    from app.infrastructure.hardware.led_display import get_led_display, LEDDisplay, DisplayMode

    display = get_led_display()

    if LEDDisplay.check_wifi():
        # Wifi is OK - ensure we're in balance mode
        if display._display_mode == DisplayMode.NO_WIFI:
            display.set_display_mode(DisplayMode.BALANCE)
        # Also try serial if connected
        if display.is_connected:
            state = display.get_state()
            if state and state.system_status == "no_wifi":
                display.set_system_status("ok")
    else:
        # No wifi - show NO WIFI mode
        display.set_display_mode(DisplayMode.NO_WIFI)
        if display.is_connected:
            display.show_no_wifi()
        logger.warning("WiFi disconnected - showing NO WIFI on LED")


def job_listener(event):
    """Listen to job execution events and track failures."""
    from app.config import settings
    
    if event.exception:
        job_id = event.job_id
        failure_time = datetime.now()
        
        # Add failure to tracking
        _job_failures[job_id].append(failure_time)
        
        # Clean up old failures outside the window
        failure_window = timedelta(hours=settings.job_failure_window_hours)
        cutoff = failure_time - failure_window
        _job_failures[job_id] = [
            ft for ft in _job_failures[job_id] if ft > cutoff
        ]
        
        # Check if we've exceeded the threshold
        recent_failures = len(_job_failures[job_id])
        if recent_failures >= settings.job_failure_threshold:
            logger.error(
                f"Job '{job_id}' has failed {recent_failures} times in the last {settings.job_failure_window_hours} hour(s). "
                f"Last error: {event.exception}"
            )
            # Could add alerting here (email, webhook, etc.)
        else:
            logger.warning(
                f"Job '{job_id}' failed (failure {recent_failures}/{settings.job_failure_threshold}): {event.exception}"
            )
    else:
        # Job succeeded - clear failure history
        if event.job_id in _job_failures:
            _job_failures[event.job_id].clear()


def init_scheduler() -> AsyncIOScheduler:
    """Initialize the APScheduler with error tracking."""
    global scheduler

    scheduler = AsyncIOScheduler()
    
    # Add event listeners for job execution tracking
    scheduler.add_listener(job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

    # Import jobs here to avoid circular imports
    from app.jobs.daily_sync import sync_portfolio, sync_prices
    from app.jobs.cash_rebalance import check_and_rebalance
    from app.jobs.score_refresh import refresh_all_scores
    from app.jobs.cash_flow_sync import sync_cash_flows

    # Tradernet portfolio sync (every 2 minutes)
    scheduler.add_job(
        sync_portfolio,
        IntervalTrigger(minutes=2),
        id="portfolio_sync",
        name="Portfolio Sync",
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

    # LED heartbeat pulse (every 20 seconds)
    scheduler.add_job(
        heartbeat_job,
        IntervalTrigger(seconds=20),
        id="led_heartbeat",
        name="LED Heartbeat",
        replace_existing=True,
    )

    # WiFi connectivity check (every 30 seconds)
    scheduler.add_job(
        wifi_check_job,
        IntervalTrigger(seconds=30),
        id="wifi_check",
        name="WiFi Check",
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
    """
    Get health status of all scheduled jobs.
    
    Returns:
        Dict with job_id -> status info (failures, last_run, etc.)
    """
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
