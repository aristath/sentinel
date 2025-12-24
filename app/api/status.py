"""System status API endpoints."""

import shutil
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter
from app.config import settings
from app.repositories import (
    PortfolioRepository,
    StockRepository,
    PositionRepository,
    AllocationRepository,
    TradeRepository,
    SettingsRepository,
)

router = APIRouter()


@router.get("")
async def get_status():
    """Get system health and status."""
    portfolio_repo = PortfolioRepository()
    stock_repo = StockRepository()
    position_repo = PositionRepository()

    # Get cash balance from latest portfolio snapshot
    latest_snapshot = await portfolio_repo.get_latest()
    cash_balance = latest_snapshot.cash_balance if latest_snapshot else 0

    # Get last sync time from positions (most recent last_updated)
    positions = await position_repo.get_all()
    last_sync = None
    if positions:
        # Find most recent last_updated, format as "YYYY-MM-DD HH:MM"
        latest = max(
            (p.last_updated for p in positions if p.last_updated),
            default=None
        )
        if latest:
            # Parse ISO format and reformat to "YYYY-MM-DD HH:MM"
            try:
                dt = datetime.fromisoformat(latest)
                last_sync = dt.strftime("%Y-%m-%d %H:%M")
            except (ValueError, TypeError):
                last_sync = latest[:16] if len(latest) >= 16 else latest

    # Get stock count
    active_stocks = await stock_repo.get_all_active()
    stock_count = len(active_stocks)

    # Get position count
    positions = await position_repo.get_all()
    position_count = len(positions)

    return {
        "status": "healthy",
        "last_sync": last_sync,
        "stock_universe_count": stock_count,
        "active_positions": position_count,
        "cash_balance": cash_balance,
        "check_interval_minutes": settings.cash_check_interval_minutes,
    }


@router.get("/led")
async def get_led_status():
    """Get current LED display state."""
    from app.infrastructure.hardware.led_display import get_display_state

    state = get_display_state()

    return {
        "connected": True,  # Always "connected" - we just manage state now
        "mode": state["mode"],
        "error_message": state.get("error_message"),
    }


async def _build_ticker_text() -> str:
    """Build ticker text from portfolio data and recommendations.

    Format: EUR12,345 | CASH EUR675 | SELL ABC EUR200 | BUY XIAO EUR855
    Respects user settings for what to show.
    """
    from app.infrastructure.cache import cache
    from app.application.services.portfolio_service import PortfolioService

    parts = []

    try:
        # Get display settings
        settings_repo = SettingsRepository()
        show_value = await settings_repo.get_float("ticker_show_value", 1.0) == 1.0
        show_cash = await settings_repo.get_float("ticker_show_cash", 1.0) == 1.0
        show_actions = await settings_repo.get_float("ticker_show_actions", 1.0) == 1.0
        show_amounts = await settings_repo.get_float("ticker_show_amounts", 1.0) == 1.0
        max_actions = int(await settings_repo.get_float("ticker_max_actions", 3))

        # Get portfolio summary
        portfolio_repo = PortfolioRepository()
        position_repo = PositionRepository()
        allocation_repo = AllocationRepository()

        portfolio_service = PortfolioService(
            portfolio_repo,
            position_repo,
            allocation_repo,
        )
        summary = await portfolio_service.get_portfolio_summary()

        # Portfolio value
        if show_value and summary.total_value:
            parts.append(f"EUR{int(summary.total_value):,}")

        # Cash balance
        if show_cash and summary.cash_balance:
            parts.append(f"CASH EUR{int(summary.cash_balance):,}")

        # Add recommendations if enabled (cache-only, populated by Rebalance Check job)
        if show_actions:
            # Check for multi-step recommendations first (if depth > 1)
            multi_step = cache.get("multi_step_recommendations:default")
            if not multi_step:
                # Try with explicit depth from settings (reuse settings_repo from above)
                depth = await settings_repo.get_int("recommendation_depth", 1)
                if depth > 1:
                    multi_step = cache.get(f"multi_step_recommendations:{depth}")
            
            if multi_step and multi_step.get("steps"):
                # Show multi-step recommendations - format: [step/total]
                total_steps = multi_step.get("depth", len(multi_step["steps"]))
                for step in multi_step["steps"][:max_actions]:
                    symbol = step["symbol"].split(".")[0]  # Remove .US/.EU suffix
                    value = int(step.get("estimated_value", 0))
                    side = step.get("side", "BUY")
                    step_num = step.get("step", 1)
                    step_label = f"[{step_num}/{total_steps}]"
                    if show_amounts and value > 0:
                        parts.append(f"{side} {symbol} EUR{value:,} {step_label}")
                    else:
                        parts.append(f"{side} {symbol} {step_label}")
            else:
                # Fall back to single recommendations
                sell_recs = cache.get("sell_recommendations:3")
                buy_recs = cache.get("recommendations:3")

                # Add sell recommendations (priority - shown first)
                if sell_recs and sell_recs.get("recommendations"):
                    for rec in sell_recs["recommendations"][:max_actions]:
                        symbol = rec["symbol"].split(".")[0]  # Remove .US/.EU suffix
                        value = int(rec.get("estimated_value", 0))
                        if show_amounts and value > 0:
                            parts.append(f"SELL {symbol} EUR{value:,}")
                        else:
                            parts.append(f"SELL {symbol}")

                # Add buy recommendations
                if buy_recs and buy_recs.get("recommendations"):
                    for rec in buy_recs["recommendations"][:max_actions]:
                        symbol = rec["symbol"].split(".")[0]  # Remove .US/.EU suffix
                        value = int(rec.get("amount", 0))
                        if show_amounts and value > 0:
                            parts.append(f"BUY {symbol} EUR{value:,}")
                        else:
                            parts.append(f"BUY {symbol}")

    except Exception:
        # On error, just return empty (no ticker)
        return ""

    return " | ".join(parts) if parts else ""


@router.get("/led/display")
async def get_led_display_state():
    """
    Get display state for Arduino Bridge apps.

    Returns what the LED display should show including:
    - mode: current display mode (normal, syncing, trade, error)
    - error_message: error text for scrolling (only in error mode)
    - trade_is_buy: true for buy, false for sell (only in trade mode)
    - since: timestamp when mode last changed
    - led3: RGB values for LED 3 (sync indicator)
    - led4: RGB values for LED 4 (processing indicator)
    - ticker_text: scrolling ticker with portfolio info
    - activity_message: current activity (higher priority)
    - ticker_speed: scroll speed in ms per frame
    - led_brightness: brightness 0-255

    Note: This endpoint is called ~10 times/second by the LED controller.
    Response is cached for 2 seconds to prevent DB connection exhaustion.
    Mode/activity changes are reflected immediately from in-memory state.
    """
    import asyncio
    from app.infrastructure.hardware.led_display import get_display_state
    from app.infrastructure.cache import cache

    # Get live display state (in-memory, no DB)
    state = get_display_state()

    # Check if we have cached ticker data
    cached = cache.get("led_display:ticker_data")

    # Use cached ticker/settings if available, otherwise fetch fresh with timeout
    if cached is not None:
        state["ticker_text"] = state.get("ticker_text") or cached.get("ticker_text", "")
        state["ticker_speed"] = cached.get("ticker_speed", 50.0)
        state["led_brightness"] = cached.get("led_brightness", 150)
    else:
        # Fetch fresh data with 2 second timeout to prevent hanging
        try:
            await asyncio.wait_for(_refresh_led_display_cache(), timeout=2.0)
            cached = cache.get("led_display:ticker_data") or {}
        except asyncio.TimeoutError:
            # On timeout, use empty ticker and cache it to prevent retries
            cache.set("led_display:ticker_data", {
                "ticker_text": "",
                "ticker_speed": 50.0,
                "led_brightness": 150,
            }, ttl_seconds=5)
            cached = {}
        state["ticker_text"] = state.get("ticker_text") or cached.get("ticker_text", "")
        state["ticker_speed"] = cached.get("ticker_speed", 50.0)
        state["led_brightness"] = cached.get("led_brightness", 150)

    return state


async def _refresh_led_display_cache():
    """Refresh cached LED display data (ticker text + settings)."""
    from app.infrastructure.cache import cache

    try:
        # Build ticker text
        ticker = await _build_ticker_text()

        # Get settings
        settings_repo = SettingsRepository()
        ticker_speed = await settings_repo.get_float("ticker_speed", 50.0)
        led_brightness = int(await settings_repo.get_float("led_brightness", 150))

        # Cache for 2 seconds
        cache.set("led_display:ticker_data", {
            "ticker_text": ticker,
            "ticker_speed": ticker_speed,
            "led_brightness": led_brightness,
        }, ttl_seconds=2)
    except Exception:
        # On error, set minimal cache to prevent rapid retries
        cache.set("led_display:ticker_data", {
            "ticker_text": "",
            "ticker_speed": 50.0,
            "led_brightness": 150,
        }, ttl_seconds=2)


@router.post("/led/test")
async def test_led():
    """Test LED display with trade animation."""
    from app.infrastructure.events import emit, SystemEvent

    emit(SystemEvent.TRADE_EXECUTED, is_buy=True)
    return {"status": "success", "message": "Test animation triggered"}


@router.post("/sync/portfolio")
async def trigger_portfolio_sync():
    """Manually trigger portfolio sync."""
    from app.jobs.daily_sync import sync_portfolio

    try:
        await sync_portfolio()
        return {"status": "success", "message": "Portfolio sync completed"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/sync/prices")
async def trigger_price_sync():
    """Manually trigger price sync."""
    from app.jobs.daily_sync import sync_prices

    try:
        await sync_prices()
        return {"status": "success", "message": "Price sync completed"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/sync/historical")
async def trigger_historical_sync():
    """Manually trigger historical data sync (stock prices + monthly aggregation)."""
    from app.jobs.historical_data_sync import sync_historical_data

    try:
        await sync_historical_data()
        return {"status": "success", "message": "Historical data sync completed"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/maintenance/daily")
async def trigger_daily_maintenance():
    """Manually trigger daily maintenance (backup, cleanup, WAL checkpoint)."""
    from app.jobs.maintenance import run_daily_maintenance

    try:
        await run_daily_maintenance()
        return {"status": "success", "message": "Daily maintenance completed"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/tradernet")
async def get_tradernet_status():
    """Get Tradernet connection status."""
    from app.services.tradernet import get_tradernet_client

    client = get_tradernet_client()
    return {
        "connected": client.is_connected,
        "message": "Connected to Tradernet" if client.is_connected else "Not connected",
    }


@router.get("/jobs")
async def get_job_status():
    """Get status of all scheduled jobs."""
    from app.jobs.scheduler import get_job_health_status

    try:
        job_status = get_job_health_status()
        return {
            "status": "ok",
            "jobs": job_status,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "jobs": {},
        }


@router.get("/database/stats")
async def get_database_stats():
    """Get database statistics including historical data counts and freshness."""
    from app.jobs.health_check import get_database_stats as get_db_stats

    try:
        stats = await get_db_stats()
        return {
            "status": "ok",
            **stats,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
        }


@router.get("/disk")
async def get_disk_usage():
    """
    Get disk usage information for monitoring.

    Returns:
        - disk_total_mb: Total disk space
        - disk_free_mb: Free disk space
        - disk_used_percent: Percentage of disk used
        - data_dir_size_mb: Data directory size
    """
    try:
        data_dir = settings.data_dir

        # System disk usage
        disk = shutil.disk_usage("/")

        # Data directory size
        data_size = 0
        if data_dir.exists():
            for f in data_dir.glob("**/*"):
                if f.is_file():
                    try:
                        data_size += f.stat().st_size
                    except (OSError, FileNotFoundError):
                        pass

        # Count databases
        core_dbs = ["config.db", "ledger.db", "state.db", "cache.db"]
        db_sizes = {}
        for db_name in core_dbs:
            db_path = data_dir / db_name
            if db_path.exists():
                db_sizes[db_name] = round(db_path.stat().st_size / (1024 * 1024), 2)

        # Count history databases
        history_dir = data_dir / "history"
        history_count = 0
        history_size = 0
        if history_dir.exists():
            for f in history_dir.glob("*.db"):
                history_count += 1
                history_size += f.stat().st_size

        # Backup directory size
        backup_dir = data_dir / "backups"
        backup_size = 0
        backup_count = 0
        if backup_dir.exists():
            for f in backup_dir.glob("*.db"):
                backup_size += f.stat().st_size
                backup_count += 1
            for d in backup_dir.glob("history_*"):
                if d.is_dir():
                    for f in d.glob("*.db"):
                        backup_size += f.stat().st_size
                    backup_count += 1

        return {
            "status": "ok",
            "disk": {
                "total_mb": round(disk.total / (1024 * 1024), 1),
                "free_mb": round(disk.free / (1024 * 1024), 1),
                "used_percent": round((disk.used / disk.total) * 100, 1),
            },
            "databases": {
                **db_sizes,
                "history_count": history_count,
                "history_size_mb": round(history_size / (1024 * 1024), 2),
            },
            "data_directory": {
                "total_size_mb": round(data_size / (1024 * 1024), 2),
            },
            "backups": {
                "count": backup_count,
                "size_mb": round(backup_size / (1024 * 1024), 2),
            },
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
        }
