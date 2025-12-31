"""System status API endpoints."""

import logging
import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.api.models import (
    DatabaseStatsResponse,
    DiskUsageResponse,
    MarketsStatusResponse,
    StatusResponse,
)
from app.config import settings
from app.infrastructure.dependencies import (
    DisplayStateManagerDep,
    PortfolioRepositoryDep,
    PositionRepositoryDep,
    SettingsRepositoryDep,
    StockRepositoryDep,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class PlannerBatchRequest(BaseModel):
    """Request model for planner batch processing."""

    portfolio_hash: Optional[str] = None
    depth: int = 0


@router.get("", response_model=StatusResponse)
async def get_status(
    portfolio_repo: PortfolioRepositoryDep,
    stock_repo: StockRepositoryDep,
    position_repo: PositionRepositoryDep,
):
    """Get system health and status."""

    # Get cash balance from actual cash balances (more accurate than snapshot)
    # Fallback to snapshot if Tradernet is not connected
    cash_balance = 0.0
    try:
        from app.infrastructure.external.tradernet_connection import (
            ensure_tradernet_connected,
        )

        client = await ensure_tradernet_connected(raise_on_error=False)
        if client:
            from app.core.database.manager import get_db_manager
            from app.infrastructure.dependencies import get_exchange_rate_service

            db_manager = get_db_manager()
            exchange_rate_service = get_exchange_rate_service(db_manager)
            cash_balances = client.get_cash_balances()
            amounts_by_currency = {b.currency: b.amount for b in cash_balances}
            amounts_in_eur = await exchange_rate_service.batch_convert_to_eur(
                amounts_by_currency
            )
            cash_balance = sum(amounts_in_eur.values())
        else:
            # Fallback to snapshot if Tradernet not connected
            latest_snapshot = await portfolio_repo.get_latest()
            cash_balance = latest_snapshot.cash_balance if latest_snapshot else 0
    except Exception as e:
        logger.warning(
            f"Failed to get cash balance from Tradernet: {e}, using snapshot"
        )
        # Fallback to snapshot on error
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
            from app.shared.utils import safe_parse_datetime_string

            dt = safe_parse_datetime_string(latest)
            if dt:
                last_sync = dt.strftime("%Y-%m-%d %H:%M")
            else:
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


@router.get("/led/display")
async def get_led_display_state(
    settings_repo: SettingsRepositoryDep,
    display_manager: DisplayStateManagerDep,
):
    """Get LED display state for Arduino App Framework Docker app.

    Returns display text and RGB LED states in the format expected
    by the trader-display Arduino app.
    """
    display_text = display_manager.get_current_text()
    ticker_speed = int(await settings_repo.get_float("ticker_speed", 50.0))
    led3 = display_manager.get_led3()
    led4 = display_manager.get_led4()

    logger.debug(
        f"LED display state requested: text='{display_text}', speed={ticker_speed}, "
        f"led3={led3}, led4={led4}"
    )

    return {
        "display_text": display_text,
        "ticker_speed": ticker_speed,
        "led3": led3,
        "led4": led4,
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


@router.post("/sync/rebuild-universe")
async def rebuild_universe_from_portfolio():
    """Rebuild universe from portfolio and populate all databases.

    This endpoint performs a complete rebuild:
    1. Gets all stocks from current portfolio positions
    2. Checks if they exist in the universe
    3. Adds missing stocks with full data (ISIN, Yahoo symbols, etc.)
    4. Syncs historical data for all stocks in universe
    5. Refreshes scores and metrics for all stocks

    Returns:
        Status with detailed counts of operations performed
    """
    from app.infrastructure.dependencies import get_stock_repository
    from app.infrastructure.external.tradernet import get_tradernet_client
    from app.jobs.daily_sync import _ensure_portfolio_stocks_in_universe
    from app.jobs.historical_data_sync import sync_historical_data
    from app.jobs.securities_data_sync import run_stocks_data_sync

    result = {
        "status": "success",
        "message": "",
        "portfolio_positions": 0,
        "stocks_in_universe_before": 0,
        "stocks_in_universe_after": 0,
        "stocks_added": 0,
        "historical_synced": False,
        "scores_refreshed": False,
        "errors": [],
    }

    try:
        logger.info("Starting universe rebuild from portfolio...")

        # Step 1: Connect to Tradernet
        client = get_tradernet_client()
        if not client.is_connected:
            if not client.connect():
                result["status"] = "error"
                result["message"] = "Failed to connect to Tradernet"
                result["errors"].append("Tradernet connection failed")
                return result

        # Step 2: Get portfolio positions
        logger.info("Fetching portfolio positions from Tradernet...")
        positions = client.get_portfolio()
        if not positions:
            result["message"] = "No positions in portfolio"
            return result

        result["portfolio_positions"] = len(positions)
        logger.info(f"Found {len(positions)} portfolio positions")

        # Step 3: Get stock counts before adding
        stock_repo = get_stock_repository()
        stocks_before = await stock_repo.get_all_active()
        result["stocks_in_universe_before"] = len(stocks_before)
        logger.info(f"Universe has {len(stocks_before)} stocks before rebuild")

        # Step 4: Ensure all portfolio stocks are in universe
        logger.info("Adding missing portfolio stocks to universe...")
        try:
            await _ensure_portfolio_stocks_in_universe(positions, client, stock_repo)
        except Exception as e:
            error_msg = f"Failed to add portfolio stocks: {e}"
            logger.error(error_msg, exc_info=True)
            result["errors"].append(error_msg)
            # Continue - some stocks might have been added

        # Step 5: Get stock counts after adding
        stocks_after = await stock_repo.get_all_active()
        result["stocks_in_universe_after"] = len(stocks_after)
        result["stocks_added"] = len(stocks_after) - len(stocks_before)
        logger.info(
            f"Universe now has {len(stocks_after)} stocks "
            f"({result['stocks_added']} added)"
        )

        # Step 6: Sync historical data for all stocks
        logger.info("Syncing historical data for all stocks in universe...")
        try:
            await sync_historical_data()
            result["historical_synced"] = True
            logger.info("Historical data sync completed")
        except Exception as e:
            error_msg = f"Historical data sync failed: {e}"
            logger.error(error_msg, exc_info=True)
            result["errors"].append(error_msg)
            # Continue - historical sync failure shouldn't block the process

        # Step 7: Refresh scores and metrics for all stocks
        logger.info("Refreshing scores and metrics for all stocks...")
        try:
            await run_stocks_data_sync()
            result["scores_refreshed"] = True
            logger.info("Scores and metrics refresh completed")
        except Exception as e:
            error_msg = f"Scores/metrics refresh failed: {e}"
            logger.error(error_msg, exc_info=True)
            result["errors"].append(error_msg)
            # Continue - score refresh failure shouldn't block the process

        # Build success message
        if result["errors"]:
            result["message"] = (
                f"Universe rebuild completed with {len(result['errors'])} error(s). "
                f"Added {result['stocks_added']} stocks, "
                f"synced historical data: {result['historical_synced']}, "
                f"refreshed scores: {result['scores_refreshed']}"
            )
            result["status"] = "partial_success"
        else:
            result["message"] = (
                f"Universe rebuild completed successfully. "
                f"Added {result['stocks_added']} stocks, "
                f"synced historical data for all stocks, "
                f"refreshed scores and metrics for all stocks."
            )

        logger.info(f"Universe rebuild completed: {result['message']}")
        return result

    except Exception as e:
        error_msg = f"Failed to rebuild universe from portfolio: {e}"
        logger.error(error_msg, exc_info=True)
        result["status"] = "error"
        result["message"] = error_msg
        result["errors"].append(error_msg)
        return result


@router.post("/sync/stocks-data")
async def trigger_stocks_data_sync():
    """Manually trigger stocks data sync (historical sync, industry detection, metrics, scores).

    Processes all stocks that haven't been synced in 24 hours.
    This includes:
    - Syncing historical prices from Yahoo Finance
    - Detecting and updating industry from Yahoo Finance
    - Calculating technical metrics (RSI, EMA, CAGR, etc.)
    - Refreshing stock scores
    """
    from app.jobs.securities_data_sync import run_stocks_data_sync

    try:
        await run_stocks_data_sync()
        return {"status": "success", "message": "Stocks data sync completed"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/sync/daily-pipeline")
async def trigger_daily_pipeline():
    """Manually trigger daily pipeline (stocks data sync).

    This is an alias for /sync/stocks-data for backwards compatibility.
    Processes all stocks that haven't been synced in 24 hours.
    This includes:
    - Syncing historical prices from Yahoo Finance
    - Detecting and updating industry from Yahoo Finance
    - Calculating technical metrics (RSI, EMA, CAGR, etc.)
    - Refreshing stock scores
    """
    from app.jobs.securities_data_sync import run_stocks_data_sync

    try:
        await run_stocks_data_sync()
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
    from app.core.cache.cache import cache
    from app.infrastructure.recommendation_cache import get_recommendation_cache
    from app.modules.system.jobs.sync_cycle import (
        _step_get_recommendation,
        _step_update_display,
    )

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


@router.post("/jobs/sync-cycle")
async def trigger_sync_cycle():
    """Manually trigger sync cycle (trades, cash flows, portfolio, prices, recommendations, trade execution)."""
    from app.modules.system.jobs.sync_cycle import run_sync_cycle

    try:
        await run_sync_cycle()
        return {"status": "success", "message": "Sync cycle completed"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/jobs/weekly-maintenance")
async def trigger_weekly_maintenance():
    """Manually trigger weekly maintenance (integrity checks, old backup cleanup)."""
    from app.jobs.maintenance import run_weekly_maintenance

    try:
        await run_weekly_maintenance()
        return {"status": "success", "message": "Weekly maintenance completed"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/jobs/dividend-reinvestment")
async def trigger_dividend_reinvestment():
    """Manually trigger dividend reinvestment."""
    from app.jobs.dividend_reinvestment import auto_reinvest_dividends

    try:
        await auto_reinvest_dividends()
        return {"status": "success", "message": "Dividend reinvestment completed"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/jobs/universe-pruning")
async def trigger_universe_pruning():
    """Manually trigger universe pruning (removal of low-quality stocks)."""
    from app.jobs.universe_pruning import prune_universe

    try:
        await prune_universe()
        return {"status": "success", "message": "Universe pruning completed"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/jobs/planner-batch")
async def trigger_planner_batch(request: PlannerBatchRequest):
    """
    Manually trigger planner batch processing.

    Accepts JSON body with portfolio_hash and depth parameters.
    This endpoint is used by the event-based trading loop to trigger
    API-driven batch processing (depth > 0) which self-triggers subsequent batches.
    """
    from app.modules.planning.jobs.planner_batch import process_planner_batch_job

    try:
        await process_planner_batch_job(
            max_depth=request.depth, portfolio_hash=request.portfolio_hash
        )
        return {"status": "success", "message": "Planner batch processed"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/jobs/stock-discovery")
async def trigger_stock_discovery():
    """Manually trigger stock discovery (addition of high-quality stocks)."""
    from app.modules.universe.jobs.stock_discovery import discover_new_stocks

    try:
        await discover_new_stocks()
        return {"status": "success", "message": "Stock discovery completed"}
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
    except Exception as e:
        logger.debug(f"Failed to check Tradernet connection: {e}")

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


@router.get("/database/stats", response_model=DatabaseStatsResponse)
async def get_database_stats():
    """Get database statistics including historical data counts and freshness."""
    from app.api.errors import error_response, success_response
    from app.modules.system.jobs.health_check import get_database_stats as get_db_stats

    try:
        stats = await get_db_stats()
        return success_response(**stats)
    except Exception as e:
        return error_response(str(e))


def _calculate_data_dir_size(data_dir: Path) -> int:
    """Calculate total size of data directory.

    Args:
        data_dir: Path to data directory

    Returns:
        Total size in bytes
    """
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
    """Get sizes of core databases.

    Args:
        data_dir: Path to data directory

    Returns:
        Dictionary mapping database name to size in MB
    """
    core_dbs = ["config.db", "ledger.db", "state.db", "cache.db"]
    db_sizes = {}
    for db_name in core_dbs:
        db_path = data_dir / db_name
        if db_path.exists():
            db_sizes[db_name] = round(db_path.stat().st_size / (1024 * 1024), 2)
    return db_sizes


def _get_history_db_info(data_dir: Path) -> tuple[int, int]:
    """Get count and total size of history databases.

    Args:
        data_dir: Path to data directory

    Returns:
        Tuple of (count, total_size_bytes)
    """
    history_dir = data_dir / "history"
    history_count = 0
    history_size = 0
    if history_dir.exists():
        for f in history_dir.glob("*.db"):
            history_count += 1
            history_size += f.stat().st_size
    return history_count, history_size


def _get_backup_info(data_dir: Path) -> tuple[int, int]:
    """Get count and total size of backup files.

    Args:
        data_dir: Path to data directory

    Returns:
        Tuple of (count, total_size_bytes)
    """
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


@router.get("/markets", response_model=MarketsStatusResponse)
async def get_markets_status():
    """Get current market open/closed status for markets where we have stocks.

    Returns status for all markets where stocks exist in our universe including:
    - Whether each market is currently open
    - Exchange code (e.g., XNYS, XAMS, ASEX)
    - Timezone
    - Next open/close time
    """
    from app.infrastructure.market_hours import get_market_status, get_open_markets

    try:
        status = await get_market_status()
        open_markets = await get_open_markets()

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


@router.get("/disk", response_model=DiskUsageResponse)
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


def _get_log_file_path(log_file: str) -> Path:
    """Get the full path to a log file.

    Args:
        log_file: Log file name (e.g., "arduino-trader.log", "auto-deploy.log")

    Returns:
        Path to the log file
    """
    # Main app log is in data_dir/logs
    if log_file == "arduino-trader.log":
        return settings.data_dir / "logs" / log_file

    # Other logs are in /home/arduino/logs
    return Path(f"/home/arduino/logs/{log_file}")


def _get_available_log_files() -> list[dict[str, str]]:
    """Get list of available log files with their paths.

    Returns:
        List of dicts with 'name' and 'path' keys
    """
    log_files = []

    # Main app log
    app_log = settings.data_dir / "logs" / "arduino-trader.log"
    if app_log.exists():
        log_files.append({"name": "arduino-trader.log", "path": str(app_log)})

    # System logs in /home/arduino/logs
    system_log_dir = Path("/home/arduino/logs")
    if system_log_dir.exists():
        for log_file in system_log_dir.glob("*.log"):
            log_files.append({"name": log_file.name, "path": str(log_file)})

    return log_files


@router.get("/logs/list")
async def list_log_files():
    """Get list of available log files."""
    try:
        log_files = _get_available_log_files()
        return {
            "status": "ok",
            "log_files": log_files,
        }
    except Exception as e:
        logger.error(f"Failed to list log files: {e}")
        return {
            "status": "error",
            "message": str(e),
            "log_files": [],
        }


@router.get("/logs")
async def get_logs(
    log_file: str = Query("arduino-trader.log", description="Log file name"),
    lines: int = Query(100, ge=1, le=1000, description="Number of lines to return"),
    level: Optional[str] = Query(
        None, description="Filter by log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    ),
    search: Optional[str] = Query(None, description="Search for text in logs"),
):
    """Get recent application logs.

    Returns logs from the specified log file with optional filtering.
    """
    try:
        log_path = _get_log_file_path(log_file)

        if not log_path.exists():
            return {
                "status": "error",
                "message": f"Log file not found: {log_file}",
                "logs": [],
            }

        # Read log file
        with open(log_path, "r", encoding="utf-8") as f:
            all_lines = f.readlines()

        # Filter by level if specified
        if level:
            level_upper = level.upper()
            all_lines = [line for line in all_lines if f" - {level_upper} - " in line]

        # Filter by search term if specified
        if search:
            search_lower = search.lower()
            all_lines = [line for line in all_lines if search_lower in line.lower()]

        # Get last N lines
        recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines

        return {
            "status": "ok",
            "total_lines": len(all_lines),
            "returned_lines": len(recent_lines),
            "log_file": log_file,
            "log_path": str(log_path),
            "logs": [line.rstrip("\n") for line in recent_lines],
        }
    except Exception as e:
        logger.error(f"Failed to read logs: {e}")
        return {
            "status": "error",
            "message": str(e),
            "logs": [],
        }


@router.get("/logs/errors")
async def get_error_logs(
    log_file: str = Query("arduino-trader.log", description="Log file name"),
    lines: int = Query(50, ge=1, le=500, description="Number of lines to return"),
):
    """Get recent error logs only (ERROR and CRITICAL levels)."""
    try:
        log_path = _get_log_file_path(log_file)

        if not log_path.exists():
            return {
                "status": "error",
                "message": f"Log file not found: {log_file}",
                "logs": [],
            }

        # Read log file
        with open(log_path, "r", encoding="utf-8") as f:
            all_lines = f.readlines()

        # Filter for ERROR and CRITICAL only
        error_lines = [
            line
            for line in all_lines
            if " - ERROR - " in line or " - CRITICAL - " in line
        ]

        # Get last N lines
        recent_lines = error_lines[-lines:] if len(error_lines) > lines else error_lines

        return {
            "status": "ok",
            "total_error_lines": len(error_lines),
            "returned_lines": len(recent_lines),
            "log_file": log_file,
            "log_path": str(log_path),
            "logs": [line.rstrip("\n") for line in recent_lines],
        }
    except Exception as e:
        logger.error(f"Failed to read error logs: {e}")
        return {
            "status": "error",
            "message": str(e),
            "logs": [],
        }


@router.post("/locks/clear")
async def clear_stuck_locks(lock_name: Optional[str] = Query(None)):
    """Clear stuck lock files.

    Args:
        lock_name: Optional specific lock name to clear (e.g., "portfolio_sync").
                   If not provided, clears all lock files.

    Returns:
        Dict with status and cleared locks
    """
    from app.config import settings

    lock_dir = settings.data_dir / "locks"
    cleared = []

    try:
        if not lock_dir.exists():
            return {
                "status": "ok",
                "message": "No lock directory found",
                "cleared": [],
            }

        if lock_name:
            # Clear specific lock
            lock_file = lock_dir / f"{lock_name}.lock"
            if lock_file.exists():
                try:
                    lock_file.unlink()
                    cleared.append(lock_name)
                    logger.info(f"Cleared lock: {lock_name}")
                except Exception as e:
                    logger.error(f"Failed to clear lock {lock_name}: {e}")
                    return {
                        "status": "error",
                        "message": f"Failed to clear lock {lock_name}: {e}",
                        "cleared": [],
                    }
        else:
            # Clear all locks
            for lock_file in lock_dir.glob("*.lock"):
                try:
                    lock_name_only = lock_file.stem
                    lock_file.unlink()
                    cleared.append(lock_name_only)
                    logger.info(f"Cleared lock: {lock_name_only}")
                except Exception as e:
                    logger.warning(f"Failed to clear lock {lock_file.name}: {e}")

        return {
            "status": "ok",
            "message": f"Cleared {len(cleared)} lock(s)",
            "cleared": cleared,
        }
    except Exception as e:
        logger.error(f"Failed to clear locks: {e}")
        return {
            "status": "error",
            "message": str(e),
            "cleared": cleared,
        }


@router.get("/deploy/status")
async def get_deployment_status():
    """Get deployment status information.

    Returns:
        - repo_dir: Repository directory path
        - deploy_dir: Deployment directory path
        - has_changes: Whether there are changes between local and remote
        - local_commit: Current local commit (short hash)
        - remote_commit: Remote commit (short hash)
        - service_status: Systemd service status
        - staging_exists: Whether staging directory exists
    """
    try:
        from pathlib import Path

        from app.infrastructure.deployment.deployment_manager import DeploymentManager

        REPO_DIR = Path("/home/arduino/repos/autoTrader")
        DEPLOY_DIR = Path("/home/arduino/arduino-trader")
        STAGING_DIR = Path("/home/arduino/arduino-trader-staging")
        VENV_DIR = DEPLOY_DIR / "venv"

        if not REPO_DIR.exists():
            return {
                "status": "error",
                "message": f"Repository directory not found: {REPO_DIR}",
            }

        manager = DeploymentManager(
            repo_dir=REPO_DIR,
            deploy_dir=DEPLOY_DIR,
            staging_dir=STAGING_DIR,
            venv_dir=VENV_DIR,
        )

        status = manager.get_deployment_status()
        return {
            "status": "ok",
            **status,
        }
    except Exception as e:
        logger.error(f"Error getting deployment status: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e),
        }


@router.post("/deploy/trigger")
async def trigger_deployment():
    """Manually trigger deployment check.

    This will check for updates and deploy if changes are detected.
    Note: Deployment uses file-based locking, so if a deployment is already
    in progress, this will wait or fail depending on lock timeout.

    Returns:
        - status: "ok" or "error"
        - message: Status message
        - deployed: Whether deployment actually happened (if completed)
        - commit_before: Commit before deployment (if deployed)
        - commit_after: Commit after deployment (if deployed)
        - error: Error message (if failed)
    """
    try:
        # Run deployment in background to avoid blocking the API
        import asyncio

        from app.jobs.auto_deploy import run_auto_deploy

        asyncio.create_task(run_auto_deploy())

        return {
            "status": "ok",
            "message": "Deployment check triggered (running in background)",
        }
    except Exception as e:
        logger.error(f"Error triggering deployment: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e),
        }
