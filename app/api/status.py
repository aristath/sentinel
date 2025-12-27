"""System status API endpoints."""

import shutil
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter

from app.config import settings
from app.infrastructure.dependencies import (
    DisplayStateManagerDep,
    PortfolioRepositoryDep,
    PositionRepositoryDep,
    SettingsRepositoryDep,
    StockRepositoryDep,
)

router = APIRouter()


@router.get("")
async def get_status(
    portfolio_repo: PortfolioRepositoryDep,
    stock_repo: StockRepositoryDep,
    position_repo: PositionRepositoryDep,
):
    """Get system health and status."""

    # Get cash balance from latest portfolio snapshot
    latest_snapshot = await portfolio_repo.get_latest()
    cash_balance = latest_snapshot.cash_balance if latest_snapshot else 0

    # Get last sync time from positions (most recent last_updated)
    positions = await position_repo.get_all()
    last_sync = None
    if positions:
        # Find most recent last_updated, format as "YYYY-MM-DD HH:MM"
        latest = max(
            (p.last_updated for p in positions if p.last_updated), default=None
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


@router.get("/display/text")
async def get_display_text(settings_repo: SettingsRepositoryDep):
    """Get current text and display settings for Arduino LED matrix.

    Returns the highest priority text (error > processing > next_actions) plus settings.
    Called every 2 seconds by native LED display script.
    """
    from app.infrastructure.hardware.display_service import get_current_text

    speed = await settings_repo.get_float("ticker_speed", 50.0)
    brightness = int(await settings_repo.get_float("led_brightness", 150))
    return {
        "text": get_current_text(),
        "speed": int(speed),
        "brightness": brightness,
    }


@router.get("/led/display")
async def get_led_display_state(
    settings_repo: SettingsRepositoryDep,
    display_manager: DisplayStateManagerDep,
):
    """Get LED display state for Arduino App Framework Docker app.

    Returns display mode, text, and RGB LED states in the format expected
    by the trader-display Arduino app.
    """
    error_text = display_manager.get_error_text()
    processing_text = display_manager.get_processing_text()
    next_actions_text = display_manager.get_next_actions_text()

    # Determine mode based on current state
    if error_text:
        mode = "error"
    elif processing_text:
        mode = "activity"
    else:
        mode = "normal"

    ticker_speed = await settings_repo.get_float("ticker_speed", 50.0)

    return {
        "mode": mode,
        "error_message": error_text if error_text else None,
        "trade_is_buy": True,
        "led3": [0, 0, 0],
        "led4": [0, 0, 0],
        "ticker_text": next_actions_text,
        "activity_message": processing_text if processing_text else None,
        "ticker_speed": int(ticker_speed),
    }


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


@router.post("/sync/daily-pipeline")
async def trigger_daily_pipeline():
    """Manually trigger daily pipeline (historical sync, industry detection, metrics, scores).

    Processes all stocks that haven't been synced in 24 hours.
    This includes:
    - Syncing historical prices from Yahoo Finance
    - Detecting and updating industry from Yahoo Finance
    - Calculating technical metrics (RSI, EMA, CAGR, etc.)
    - Refreshing stock scores
    """
    from app.jobs.daily_pipeline import run_daily_pipeline

    try:
        await run_daily_pipeline()
        return {"status": "success", "message": "Daily pipeline completed"}
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


@router.post("/sync/recommendations")
async def trigger_recommendation_sync():
    """Manually trigger recommendation generation and cache update."""
    from app.infrastructure.cache import cache
    from app.infrastructure.recommendation_cache import get_recommendation_cache
    from app.jobs.sync_cycle import _step_get_recommendation, _step_update_display

    try:
        # Clear recommendation caches first
        cache.invalidate_prefix("recommendations")
        rec_cache = get_recommendation_cache()
        await rec_cache.invalidate_all_recommendations()

        # Generate fresh recommendations
        rec = await _step_get_recommendation()
        await _step_update_display()
        if rec:
            return {
                "status": "success",
                "recommendation": f"{rec.side} {rec.symbol} EUR{int(rec.estimated_value)}",
            }
        return {"status": "success", "message": "No recommendations generated"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/tradernet")
async def get_tradernet_status():
    """Get Tradernet connection status."""
    from app.infrastructure.external.tradernet_connection import (
        ensure_tradernet_connected,
    )

    try:
        client = await ensure_tradernet_connected(raise_on_error=False)
        if client:
            return {
                "connected": True,
                "message": "Connected to Tradernet",
            }
    except Exception:
        pass

    return {
        "connected": False,
        "message": "Not connected",
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


def _calculate_data_dir_size(data_dir: Path) -> int:
    """Calculate total size of data directory."""
    data_size = 0
    if data_dir.exists():
        for f in data_dir.glob("**/*"):
            if f.is_file():
                try:
                    data_size += f.stat().st_size
                except (OSError, FileNotFoundError):
                    pass
    return data_size


def _get_core_db_sizes(data_dir: Path) -> dict[str, float]:
    """Get sizes of core databases."""
    core_dbs = ["config.db", "ledger.db", "state.db", "cache.db"]
    db_sizes = {}
    for db_name in core_dbs:
        db_path = data_dir / db_name
        if db_path.exists():
            db_sizes[db_name] = round(db_path.stat().st_size / (1024 * 1024), 2)
    return db_sizes


def _get_history_db_info(data_dir: Path) -> tuple[int, int]:
    """Get count and total size of history databases."""
    history_dir = data_dir / "history"
    history_count = 0
    history_size = 0
    if history_dir.exists():
        for f in history_dir.glob("*.db"):
            history_count += 1
            history_size += f.stat().st_size
    return history_count, history_size


def _get_backup_info(data_dir: Path) -> tuple[int, int]:
    """Get count and total size of backup files."""
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
    return backup_count, backup_size


@router.get("/markets")
async def get_markets_status():
    """Get current market open/closed status for all geographies.

    Returns status for EU, US, and ASIA markets including:
    - Whether each market is currently open
    - Exchange code (XETR, XNYS, XHKG)
    - Timezone
    - Next open/close time
    """
    from app.infrastructure.market_hours import get_market_status, get_open_markets

    try:
        status = get_market_status()
        open_markets = get_open_markets()

        return {
            "status": "ok",
            "open_markets": open_markets,
            "markets": status,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "open_markets": [],
            "markets": {},
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
        disk = shutil.disk_usage("/")

        data_size = _calculate_data_dir_size(data_dir)
        db_sizes = _get_core_db_sizes(data_dir)
        history_count, history_size = _get_history_db_info(data_dir)
        backup_count, backup_size = _get_backup_info(data_dir)

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
