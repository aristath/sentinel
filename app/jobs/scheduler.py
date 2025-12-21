"""APScheduler setup for background jobs."""

import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler: AsyncIOScheduler = None


def heartbeat_job():
    """Send heartbeat pulse to LED display every 60 seconds."""
    from app.led.display import get_led_display

    display = get_led_display()
    if display.is_connected:
        display.show_heartbeat()
        logger.debug("Heartbeat pulse sent to LED")


def wifi_check_job():
    """Check wifi connectivity and update LED display."""
    from app.led.display import get_led_display, LEDDisplay

    display = get_led_display()
    if not display.is_connected:
        return

    if LEDDisplay.check_wifi():
        # Wifi is OK - ensure we're not showing "NO WIFI"
        state = display.get_state()
        if state and state.system_status == "no_wifi":
            display.set_system_status("ok")
    else:
        # No wifi - show scrolling text
        display.show_no_wifi()
        logger.warning("WiFi disconnected - showing NO WIFI on LED")


def init_scheduler() -> AsyncIOScheduler:
    """Initialize the APScheduler."""
    global scheduler

    scheduler = AsyncIOScheduler()

    # Import jobs here to avoid circular imports
    from app.jobs.daily_sync import sync_portfolio, sync_prices
    from app.jobs.cash_rebalance import check_and_rebalance

    # Daily portfolio sync (at configured hour)
    scheduler.add_job(
        sync_portfolio,
        CronTrigger(hour=settings.daily_sync_hour, minute=0),
        id="daily_portfolio_sync",
        name="Daily Portfolio Sync",
        replace_existing=True,
    )

    # Daily price sync (every 4 hours during market hours)
    scheduler.add_job(
        sync_prices,
        CronTrigger(hour="9,13,17,21", minute=0),
        id="price_sync",
        name="Price Sync",
        replace_existing=True,
    )

    # Cash-based rebalance check (every N minutes)
    scheduler.add_job(
        check_and_rebalance,
        IntervalTrigger(minutes=settings.cash_check_interval_minutes),
        id="cash_rebalance_check",
        name="Cash Rebalance Check",
        replace_existing=True,
    )

    # LED heartbeat pulse (every 60 seconds)
    scheduler.add_job(
        heartbeat_job,
        IntervalTrigger(seconds=60),
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
