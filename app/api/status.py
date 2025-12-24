"""System status API endpoints."""

import shutil
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends
from app.config import settings
from app.infrastructure.dependencies import (
    get_portfolio_repository,
    get_stock_repository,
    get_position_repository,
    get_allocation_repository,
    get_trade_repository,
)
from app.domain.repositories import (
    PortfolioRepository,
    StockRepository,
    PositionRepository,
    AllocationRepository,
    TradeRepository,
)

router = APIRouter()


@router.get("")
async def get_status(
    portfolio_repo: PortfolioRepository = Depends(get_portfolio_repository),
    stock_repo: StockRepository = Depends(get_stock_repository),
    position_repo: PositionRepository = Depends(get_position_repository),
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


async def _build_ticker_text(
    portfolio_repo: PortfolioRepository,
    position_repo: PositionRepository,
    allocation_repo: AllocationRepository,
    stock_repo: StockRepository,
    trade_repo: TradeRepository,
) -> str:
    """Build ticker text from portfolio data and recommendations.

    Format: EUR12,345 | CASH EUR675 | SELL ABC EUR200 | BUY XIAO EUR855
    Respects user settings for what to show.
    """
    from app.infrastructure.cache import cache
    from app.application.services.portfolio_service import PortfolioService
    from app.application.services.rebalancing_service import RebalancingService
    from app.api.settings import get_setting_value

    parts = []

    try:
        # Get display settings
        show_value = await get_setting_value("ticker_show_value") == 1.0
        show_cash = await get_setting_value("ticker_show_cash") == 1.0
        show_actions = await get_setting_value("ticker_show_actions") == 1.0
        show_amounts = await get_setting_value("ticker_show_amounts") == 1.0
        max_actions = int(await get_setting_value("ticker_max_actions"))

        # Get portfolio summary
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

        # Add recommendations if enabled
        if show_actions:
            # Try cache first, calculate if empty
            sell_recs = cache.get("sell_recommendations:3")
            buy_recs = cache.get("recommendations:3")

            # Calculate recommendations if not cached
            if buy_recs is None or sell_recs is None:
                rebalancing_service = RebalancingService(
                    stock_repo,
                    position_repo,
                    allocation_repo,
                    portfolio_repo,
                    trade_repo,
                )

                if buy_recs is None:
                    recommendations = await rebalancing_service.get_recommendations(
                        limit=3
                    )
                    buy_recs = {
                        "recommendations": [
                            {
                                "symbol": r.symbol,
                                "amount": r.amount,
                            }
                            for r in recommendations
                        ]
                    }
                    cache.set("recommendations:3", buy_recs, ttl_seconds=300)

                if sell_recs is None:
                    sell_recommendations = (
                        await rebalancing_service.get_sell_recommendations(limit=3)
                    )
                    sell_recs = {
                        "recommendations": [
                            {
                                "symbol": r.symbol,
                                "estimated_value": r.estimated_value,
                            }
                            for r in sell_recommendations
                        ]
                    }
                    cache.set("sell_recommendations:3", sell_recs, ttl_seconds=300)

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
    from app.infrastructure.hardware.led_display import get_display_state
    from app.infrastructure.cache import cache

    # Get live display state (in-memory, no DB)
    state = get_display_state()

    # Check if we have cached ticker data
    cached = cache.get("led_display:ticker_data")

    # Use cached ticker/settings if available, otherwise fetch fresh
    if cached is not None:
        state["ticker_text"] = state.get("ticker_text") or cached.get("ticker_text", "")
        state["ticker_speed"] = cached.get("ticker_speed", 50.0)
        state["led_brightness"] = cached.get("led_brightness", 150)
    else:
        # Fetch fresh data and cache it
        await _refresh_led_display_cache()
        cached = cache.get("led_display:ticker_data") or {}
        state["ticker_text"] = state.get("ticker_text") or cached.get("ticker_text", "")
        state["ticker_speed"] = cached.get("ticker_speed", 50.0)
        state["led_brightness"] = cached.get("led_brightness", 150)

    return state


async def _refresh_led_display_cache():
    """Refresh cached LED display data (ticker text + settings)."""
    from app.infrastructure.cache import cache
    from app.api.settings import get_setting_value
    from app.database import get_db_connection
    from app.infrastructure.database.repositories import (
        SQLitePortfolioRepository,
        SQLitePositionRepository,
        SQLiteAllocationRepository,
        SQLiteStockRepository,
        SQLiteTradeRepository,
    )

    try:
        async with get_db_connection() as db:
            # Create all repos with single connection
            portfolio_repo = SQLitePortfolioRepository(db)
            position_repo = SQLitePositionRepository(db)
            allocation_repo = SQLiteAllocationRepository(db)
            stock_repo = SQLiteStockRepository(db)
            trade_repo = SQLiteTradeRepository(db)

            # Build ticker text
            ticker = await _build_ticker_text(
                portfolio_repo, position_repo, allocation_repo, stock_repo, trade_repo
            )

        # Get settings (uses cached batch query)
        ticker_speed = await get_setting_value("ticker_speed")
        led_brightness = int(await get_setting_value("led_brightness"))

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
    import aiosqlite

    try:
        async with aiosqlite.connect(settings.database_path) as db:
            db.row_factory = aiosqlite.Row

            # Count daily stock price history records
            cursor = await db.execute("SELECT COUNT(*) as count FROM stock_price_history")
            price_history_count = (await cursor.fetchone())["count"]

            # Count unique symbols in price history
            cursor = await db.execute("SELECT COUNT(DISTINCT symbol) as count FROM stock_price_history")
            price_history_symbols = (await cursor.fetchone())["count"]

            # Get date range of daily price history
            cursor = await db.execute("""
                SELECT MIN(date) as min_date, MAX(date) as max_date
                FROM stock_price_history
            """)
            price_range = await cursor.fetchone()

            # Count monthly price records
            cursor = await db.execute("SELECT COUNT(*) as count FROM stock_price_monthly")
            monthly_count = (await cursor.fetchone())["count"]

            # Count unique symbols in monthly prices
            cursor = await db.execute("SELECT COUNT(DISTINCT symbol) as count FROM stock_price_monthly")
            monthly_symbols = (await cursor.fetchone())["count"]

            # Get date range of monthly prices
            cursor = await db.execute("""
                SELECT MIN(year_month) as min_date, MAX(year_month) as max_date
                FROM stock_price_monthly
            """)
            monthly_range = await cursor.fetchone()

            # Count portfolio snapshots
            cursor = await db.execute("SELECT COUNT(*) as count FROM portfolio_snapshots")
            snapshot_count = (await cursor.fetchone())["count"]

            # Get date range of snapshots
            cursor = await db.execute("""
                SELECT MIN(date) as min_date, MAX(date) as max_date
                FROM portfolio_snapshots
            """)
            snapshot_range = await cursor.fetchone()

            # Count active stocks
            cursor = await db.execute("SELECT COUNT(*) as count FROM stocks WHERE active = 1")
            active_stocks = (await cursor.fetchone())["count"]

            # Count trades
            cursor = await db.execute("SELECT COUNT(*) as count FROM trades")
            trades_count = (await cursor.fetchone())["count"]

            # Calculate data freshness
            today = datetime.now().date()

            # Daily price freshness
            daily_latest = price_range["max_date"] if price_range["max_date"] else None
            daily_days_old = None
            daily_stale = False
            if daily_latest:
                try:
                    latest_date = datetime.strptime(daily_latest, "%Y-%m-%d").date()
                    daily_days_old = (today - latest_date).days
                    daily_stale = daily_days_old > 3  # Stale if > 3 days old (weekend buffer)
                except ValueError:
                    pass

            # Monthly price freshness
            monthly_latest = monthly_range["max_date"] if monthly_range["max_date"] else None
            monthly_days_old = None
            monthly_stale = False
            if monthly_latest:
                try:
                    # Parse YYYY-MM format
                    latest_month = datetime.strptime(monthly_latest + "-01", "%Y-%m-%d").date()
                    monthly_days_old = (today - latest_month).days
                    monthly_stale = monthly_days_old > 45  # Stale if > 45 days (1.5 months)
                except ValueError:
                    pass

            return {
                "status": "ok",
                "stock_price_history_daily": {
                    "total_records": price_history_count,
                    "unique_symbols": price_history_symbols,
                    "date_range": {
                        "min": price_range["min_date"] if price_range["min_date"] else None,
                        "max": daily_latest,
                    },
                    "freshness": {
                        "days_old": daily_days_old,
                        "stale": daily_stale,
                    }
                },
                "stock_price_monthly": {
                    "total_records": monthly_count,
                    "unique_symbols": monthly_symbols,
                    "date_range": {
                        "min": monthly_range["min_date"] if monthly_range["min_date"] else None,
                        "max": monthly_latest,
                    },
                    "freshness": {
                        "days_old": monthly_days_old,
                        "stale": monthly_stale,
                    }
                },
                "portfolio_snapshots": {
                    "total_records": snapshot_count,
                    "date_range": {
                        "min": snapshot_range["min_date"] if snapshot_range["min_date"] else None,
                        "max": snapshot_range["max_date"] if snapshot_range["max_date"] else None,
                    }
                },
                "active_stocks": active_stocks,
                "trades": trades_count,
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
        - db_size_mb: Database file size
        - wal_size_mb: WAL file size
        - log_size_mb: Log directory size
        - backup_size_mb: Backup directory size
    """
    try:
        db_path = Path(settings.database_path)
        data_dir = db_path.parent

        # System disk usage
        disk = shutil.disk_usage("/")

        # Database file sizes
        db_size = db_path.stat().st_size if db_path.exists() else 0
        wal_path = Path(f"{db_path}-wal")
        wal_size = wal_path.stat().st_size if wal_path.exists() else 0
        shm_path = Path(f"{db_path}-shm")
        shm_size = shm_path.stat().st_size if shm_path.exists() else 0

        # Log directory size
        log_dir = data_dir / "logs"
        log_size = 0
        if log_dir.exists():
            for f in log_dir.glob("**/*"):
                if f.is_file():
                    log_size += f.stat().st_size

        # Backup directory size
        backup_dir = data_dir / "backups"
        backup_size = 0
        backup_count = 0
        if backup_dir.exists():
            for f in backup_dir.glob("trader_*.db"):
                backup_size += f.stat().st_size
                backup_count += 1

        return {
            "status": "ok",
            "disk": {
                "total_mb": round(disk.total / (1024 * 1024), 1),
                "free_mb": round(disk.free / (1024 * 1024), 1),
                "used_percent": round((disk.used / disk.total) * 100, 1),
            },
            "database": {
                "db_size_mb": round(db_size / (1024 * 1024), 2),
                "wal_size_mb": round(wal_size / (1024 * 1024), 2),
                "shm_size_mb": round(shm_size / (1024 * 1024), 2),
                "total_mb": round((db_size + wal_size + shm_size) / (1024 * 1024), 2),
            },
            "logs": {
                "size_mb": round(log_size / (1024 * 1024), 2),
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
