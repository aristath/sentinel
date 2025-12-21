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
    # Trigger heartbeat for API-based display
    display.trigger_heartbeat()
    # Also try serial if connected
    if display.is_connected:
        display.show_heartbeat()
    logger.debug("Heartbeat pulse triggered")


def wifi_check_job():
    """Check wifi connectivity and update LED display."""
    from app.led.display import get_led_display, LEDDisplay, DisplayMode

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


def init_scheduler() -> AsyncIOScheduler:
    """Initialize the APScheduler."""
    global scheduler

    scheduler = AsyncIOScheduler()

    # Import jobs here to avoid circular imports
    from app.jobs.daily_sync import sync_portfolio, sync_prices
    from app.jobs.cash_rebalance import check_and_rebalance

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
