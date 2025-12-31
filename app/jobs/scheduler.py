"""APScheduler setup for background jobs.

The scheduler manages 7 scheduled jobs plus 1 background task, organized by category:

DATA SYNC JOBS:
1. sync_cycle - Every 5 minutes (configurable)
   - Syncs trades, cash flows, portfolio, prices (market-aware)
   - Updates LED display
   - Calls emergency_rebalance internally when negative balances detected

2. securities_data_sync - Hourly
   - Historical data sync (per symbol, only if not synced in 24h)
   - Metrics calculation
   - Score refresh

TRADING JOBS:
- event_based_trading - Continuous background task (not scheduled)
  - Waits for planning completion, executes trades, monitors portfolio
  - Triggers API-driven planner_batch chains for faster processing

8. planner_batch - Every 30 minutes (fallback only)
   - Processes planner sequences incrementally
   - Only runs if incremental mode enabled
   - Normal processing is API-driven (triggered by event_based_trading)
   - This scheduled job is a fallback mechanism

MAINTENANCE JOBS:
3. daily_maintenance - Daily at configured hour
   - Database backup
   - Data cleanup (expired prices, snapshots, caches)
   - WAL checkpoint

4. weekly_maintenance - Sunday, 1 hour after daily maintenance
   - Integrity checks
   - Expired backup cleanup

PORTFOLIO MANAGEMENT JOBS:
5. dividend_reinvestment - Daily, 30 minutes after daily maintenance
   - Automatic reinvestment of dividend payments

SYSTEM JOBS:
6. display_ticker_update - Every 10 seconds
   - Updates LED matrix display with current ticker text

7. auto_deploy - Every 5 minutes (configurable)
   - Checks GitHub for updates
   - Deploys changes automatically
   - Compiles and uploads sketch if changed
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
            await settings_repo.get_float("job_sync_cycle_minutes", 5.0)
        ),
        "maintenance_hour": int(
            await settings_repo.get_float("job_maintenance_hour", 3.0)
        ),
        "auto_deploy_minutes": int(
            await settings_repo.get_float("job_auto_deploy_minutes", 5.0)
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
    from app.jobs.auto_deploy import run_auto_deploy
    from app.jobs.event_based_trading import run_event_based_trading_loop
    from app.jobs.maintenance import run_daily_maintenance, run_weekly_maintenance
    from app.jobs.securities_data_sync import run_securities_data_sync
    from app.modules.display.services.display_updater_service import (
        update_display_ticker,
    )
    from app.modules.dividends.jobs.dividend_reinvestment import auto_reinvest_dividends
    from app.modules.planning.jobs.planner_batch import process_planner_batch_job
    from app.modules.system.jobs.sync_cycle import run_sync_cycle

    # Get settings
    job_settings = await _get_job_settings()
    sync_cycle_minutes = job_settings["sync_cycle_minutes"]
    maintenance_hour = job_settings["maintenance_hour"]
    auto_deploy_minutes = job_settings["auto_deploy_minutes"]

    # Get planner batch settings from settings
    from app.repositories import SettingsRepository

    settings_repo = SettingsRepository()
    incremental_enabled = (
        await settings_repo.get_float("incremental_planner_enabled", 1.0) == 1.0
    )
    # Scheduled planner batch runs every 30 minutes as fallback only
    # API-driven batches (triggered by event-based trading) handle normal processing
    planner_batch_interval = 30 * 60  # 30 minutes in seconds

    # ============================================================================
    # DATA SYNC JOBS
    # ============================================================================

    # Job 1: Sync Cycle - every 5 minutes (configurable, default 5.0)
    # Handles: trades, cash flows, portfolio, prices (market-aware), display
    #
    # JOB RELATIONSHIPS:
    # - Trade execution is handled by event_based_trading (not sync_cycle)
    # - Calls emergency_rebalance internally when negative balances detected
    # - Updates LED display via display_updater_service
    # - Can dynamically start/stop frequent_portfolio_update job (every 30s) after trades
    scheduler.add_job(
        run_sync_cycle,
        IntervalTrigger(minutes=sync_cycle_minutes),
        id="sync_cycle",
        name="Sync Cycle",
        replace_existing=True,
    )

    # Job 2: Securities Data Sync - hourly
    # Handles: historical data sync, metrics calculation, score refresh
    # Processes securities sequentially, only those not synced in 24 hours
    scheduler.add_job(
        run_securities_data_sync,
        IntervalTrigger(hours=1),
        id="securities_data_sync",
        name="Securities Data Sync",
        replace_existing=True,
    )

    # ============================================================================
    # TRADING JOBS
    # ============================================================================

    # Event-Based Trading - started as background task (see below)
    # Handles: waiting for planning completion, trade execution, portfolio monitoring
    # Not added as a scheduled job because it has a while True loop and runs continuously
    #
    # JOB RELATIONSHIPS:
    # - Triggers API-driven planner_batch chains via HTTP POST to /api/status/jobs/planner-batch
    # - Waits for all sequences to be evaluated before executing trades
    # - Monitors portfolio hash changes and restarts planning cycle when detected
    # - Calls emergency_rebalance after trade execution if negative balances detected

    # Job 8: Planner Batch - every 30 minutes (fallback only)
    # Processes next batch of sequences for holistic planner (only if incremental mode enabled)
    #
    # JOB RELATIONSHIPS:
    # - Has TWO modes:
    #   1. API-driven mode: Triggered by event_based_trading via HTTP POST
    #      - Uses small batches (5 sequences) for faster processing
    #      - Self-triggers next batch via API until all sequences evaluated
    #   2. Scheduled fallback mode: Runs every 30 minutes (this job)
    #      - Uses larger batches (50 sequences)
    #      - Skips if API-driven batches are active (sequences exist but not all evaluated)
    # - Normal processing is API-driven; scheduled job is safety net
    if incremental_enabled:
        scheduler.add_job(
            process_planner_batch_job,
            IntervalTrigger(seconds=planner_batch_interval),
            id="planner_batch",
            name="Planner Batch (Fallback)",
            replace_existing=True,
        )
    else:
        # Remove job if it exists and incremental mode is disabled
        try:
            scheduler.remove_job("planner_batch")
        except Exception:
            pass  # Job doesn't exist, that's fine

    # ============================================================================
    # MAINTENANCE JOBS
    # ============================================================================

    # Job 3: Daily Maintenance - daily at configured hour
    # Handles: backup, cleanup, WAL checkpoint
    #
    # JOB RELATIONSHIPS:
    # - Runs in sequence: backup -> cleanup -> WAL checkpoint
    # - Cleanup includes: expired prices, snapshots, caches
    scheduler.add_job(
        run_daily_maintenance,
        CronTrigger(hour=maintenance_hour, minute=0),
        id="daily_maintenance",
        name="Daily Maintenance",
        replace_existing=True,
    )

    # Job 4: Weekly Maintenance - Sunday, 1 hour after daily maintenance
    # Handles: integrity checks, old backup cleanup
    #
    # JOB RELATIONSHIPS:
    # - Runs after daily_maintenance (1 hour later on Sunday)
    # - Checks all database files for corruption
    scheduler.add_job(
        run_weekly_maintenance,
        CronTrigger(day_of_week=6, hour=(maintenance_hour + 1) % 24, minute=0),
        id="weekly_maintenance",
        name="Weekly Maintenance",
        replace_existing=True,
    )

    # ============================================================================
    # PORTFOLIO MANAGEMENT JOBS
    # ============================================================================

    # Job 5: Dividend Reinvestment - daily, 30 minutes after daily maintenance
    # Handles: automatic reinvestment of dividends
    #
    # JOB RELATIONSHIPS:
    # - Runs after daily_maintenance (30 minutes later)
    # - Uses holistic planner to find best opportunities for low-yield dividends
    # - High-yield dividends (>=3%) are reinvested in same security
    scheduler.add_job(
        auto_reinvest_dividends,
        CronTrigger(hour=maintenance_hour, minute=30),
        id="dividend_reinvestment",
        name="Dividend Reinvestment",
        replace_existing=True,
    )

    # ============================================================================
    # SYSTEM JOBS
    # ============================================================================

    # Job 6: Display Ticker Update - every 10 seconds
    # Handles: updating LED matrix display with current ticker text
    # Lightweight job that only updates display, not full sync
    scheduler.add_job(
        update_display_ticker,
        IntervalTrigger(seconds=10),
        id="display_ticker_update",
        name="Display Ticker Update",
        replace_existing=True,
    )

    # Job 7: Auto-Deploy - every N minutes (configurable)
    # Handles: checking for updates from GitHub and deploying changes
    scheduler.add_job(
        run_auto_deploy,
        IntervalTrigger(minutes=auto_deploy_minutes),
        id="auto_deploy",
        name="Auto-Deploy",
        replace_existing=True,
    )

    # ============================================================================
    # BACKGROUND TASKS
    # ============================================================================

    # Start event-based trading loop as background task (not a scheduled job)
    # since it has a while True loop and runs continuously
    # Wrap in a function that restarts it if it crashes
    import asyncio

    async def _run_with_restart():
        """Run event-based trading loop with automatic restart on crash."""
        while True:
            try:
                await run_event_based_trading_loop()
            except Exception as e:
                logger.error(f"Event-based trading loop crashed: {e}", exc_info=True)
                # Wait 10 seconds before restarting
                await asyncio.sleep(10)

    asyncio.create_task(_run_with_restart())
    logger.info("Started event-based trading loop as background task")

    logger.info(
        f"Scheduler initialized with 7 scheduled jobs + 1 background task - "
        f"sync_cycle:{sync_cycle_minutes}m, securities_data_sync:1h, "
        f"maintenance:{maintenance_hour}:00, dividend_reinvestment:{maintenance_hour}:30, "
        f"planner_batch:{planner_batch_interval//60}m (fallback), "
        f"display_ticker_update:10s, auto_deploy:{auto_deploy_minutes}m, "
        f"event_based_trading:background"
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
    auto_deploy_minutes = job_settings["auto_deploy_minutes"]

    # Reschedule sync cycle
    scheduler.reschedule_job(
        "sync_cycle", trigger=IntervalTrigger(minutes=sync_cycle_minutes)
    )

    # Securities data sync is fixed at hourly, no reschedule needed

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

    # Reschedule auto-deploy
    scheduler.reschedule_job(
        "auto_deploy", trigger=IntervalTrigger(minutes=auto_deploy_minutes)
    )

    logger.info(
        f"Jobs rescheduled - sync_cycle:{sync_cycle_minutes}m, "
        f"maintenance:{maintenance_hour}:00, dividend_reinvestment:{maintenance_hour}:30, "
        f"auto_deploy:{auto_deploy_minutes}m"
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
