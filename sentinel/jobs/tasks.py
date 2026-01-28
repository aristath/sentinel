"""Job task functions - plain async functions for APScheduler."""

from __future__ import annotations

import json
import logging
import os
import tarfile
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data"


# -----------------------------------------------------------------------------
# Sync Tasks
# -----------------------------------------------------------------------------


async def sync_portfolio(portfolio) -> None:
    """Sync portfolio positions from broker."""
    await portfolio.sync()
    logger.info("Portfolio sync complete")


async def sync_prices(db, broker, cache) -> None:
    """Sync historical prices for all securities."""
    # Clear analysis cache since prices are changing
    cleared = cache.clear()
    logger.info(f"Cleared {cleared} cached analyses before price sync")

    securities = await db.get_all_securities(active_only=True)
    symbols = [s["symbol"] for s in securities]

    prices = await broker.get_historical_prices_bulk(symbols, years=10)
    synced = 0

    for symbol, data in prices.items():
        if data and len(data) > 0:
            await db.replace_prices(symbol, data)
            synced += 1

    logger.info(f"Price sync complete: {synced}/{len(symbols)} securities updated")


async def sync_quotes(db, broker) -> None:
    """Sync quote data for all securities."""
    securities = await db.get_all_securities(active_only=True)
    symbols = [s["symbol"] for s in securities]

    if not symbols:
        logger.info("No securities to sync quotes for")
        return

    quotes = await broker.get_quotes(symbols)
    if quotes:
        await db.update_quotes_bulk(quotes)
        logger.info(f"Quote sync complete: {len(quotes)} securities")
    else:
        logger.warning("No quotes returned from broker")


async def sync_metadata(db, broker) -> None:
    """Sync security metadata from broker."""
    securities = await db.get_all_securities(active_only=True)
    synced = 0

    for sec in securities:
        symbol = sec["symbol"]
        info = await broker.get_security_info(symbol)
        if info:
            market_id = str(info.get("mrkt", {}).get("mkt_id", ""))
            await db.update_security_metadata(symbol, info, market_id)
            synced += 1

    logger.info(f"Metadata sync complete: {synced} securities")


async def sync_exchange_rates() -> None:
    """Sync exchange rates."""
    from sentinel.currency import Currency

    currency = Currency()
    rates = await currency.sync_rates()
    logger.info(f"Exchange rates synced: {len(rates)} currencies")


# -----------------------------------------------------------------------------
# Scoring Tasks
# -----------------------------------------------------------------------------


async def scoring_calculate(analyzer) -> None:
    """Calculate scores for all securities."""
    count = await analyzer.update_scores()
    logger.info(f"Calculated scores for {count} securities")


# -----------------------------------------------------------------------------
# Analytics Tasks
# -----------------------------------------------------------------------------


async def analytics_regime(db, detector) -> None:
    """Train HMM regime detection model."""
    securities = await db.get_all_securities(active_only=True)
    symbols = [s["symbol"] for s in securities]

    if len(symbols) < 3:
        logger.warning("Not enough securities for regime detection")
        return

    model = await detector.train_model(symbols)
    if model:
        logger.info(f"Regime model trained on {len(symbols)} securities")


# -----------------------------------------------------------------------------
# Trading Tasks
# -----------------------------------------------------------------------------


async def trading_check_markets(broker, db, planner) -> None:
    """Check which markets are open and log pending trades."""
    if not broker.connected:
        logger.warning("Broker not connected, skipping market check")
        return

    # Get market status
    market_data = await broker.get_market_status("*")
    if not market_data:
        logger.warning("Could not get market status")
        return

    markets = market_data.get("m", [])
    open_markets = {m.get("n2"): m for m in markets if m.get("s") == "OPEN"}

    if not open_markets:
        logger.info("No markets currently open")
        return

    logger.info(f"Open markets: {', '.join(open_markets.keys())}")

    # Get securities whose market is open
    open_securities = await _get_open_market_symbols(broker, db)

    if not open_securities:
        logger.info("No securities with open markets")
        return

    logger.info(f"Securities with open markets: {', '.join(open_securities)}")

    # Check for pending trades
    recommendations = await planner.get_recommendations()
    actionable = [r for r in recommendations if r.symbol in open_securities]

    if not actionable:
        logger.info("No actionable trades for open markets")
        return

    # Log recommendations (actual execution requires live mode)
    for rec in actionable:
        logger.info(f"Ready to {rec.action.upper()}: {rec.quantity} x {rec.symbol} @ {rec.price:.2f} {rec.currency}")


async def trading_execute(broker, db, planner) -> None:
    """Execute pending trade recommendations.

    Only executes in LIVE trading mode. In research mode, logs what would happen.
    Checks market status before executing and only trades securities with open markets.
    """
    from sentinel.settings import Settings

    if not broker.connected:
        logger.warning("Broker not connected, skipping trade execution")
        return

    # Check trading mode
    settings = Settings()
    trading_mode = await settings.get("trading_mode", "research")

    if trading_mode != "live":
        logger.info(f"Trading mode is '{trading_mode}', skipping actual execution")
        # Still log what would happen
        await _log_pending_trades(broker, db, planner)
        return

    # Get market status to find open markets
    open_symbols = await _get_open_market_symbols(broker, db)
    if not open_symbols:
        logger.info("No securities with open markets, skipping execution")
        return

    # Get recommendations
    recommendations = await planner.get_recommendations()
    if not recommendations:
        logger.info("No trade recommendations")
        return

    # Filter to actionable (open markets only)
    actionable = [r for r in recommendations if r.symbol in open_symbols]
    if not actionable:
        logger.info("No actionable trades for open markets")
        return

    # Sort by priority (highest first) and execute sells before buys
    sells = sorted([r for r in actionable if r.action == "sell"], key=lambda x: -x.priority)
    buys = sorted([r for r in actionable if r.action == "buy"], key=lambda x: -x.priority)

    executed = []
    failed = []

    # Execute sells first (to free up cash for buys)
    for rec in sells:
        success = await _execute_trade(broker, rec)
        if success:
            executed.append(rec)
        else:
            failed.append(rec)

    # Then execute buys
    for rec in buys:
        success = await _execute_trade(broker, rec)
        if success:
            executed.append(rec)
        else:
            failed.append(rec)

    # Log summary
    if executed:
        logger.info(f"Executed {len(executed)} trades successfully")
    if failed:
        logger.warning(f"Failed to execute {len(failed)} trades")


async def trading_rebalance(planner) -> None:
    """Check if portfolio needs rebalancing and generate recommendations."""
    summary = await planner.get_rebalance_summary()

    if summary["needs_rebalance"]:
        logger.warning(f"Portfolio needs rebalancing! Total deviation: {summary['total_deviation']:.1%}")

        recommendations = await planner.get_recommendations()
        for rec in recommendations:
            logger.warning(f"  {rec.action.upper()} {rec.symbol}: EUR {abs(rec.value_delta_eur):.0f} ({rec.reason})")
    else:
        logger.info("Portfolio is balanced")


async def planning_refresh(db, planner) -> None:
    """Refresh trading plan by clearing caches and regenerating recommendations."""
    # Clear planner-related caches
    cleared = await db.cache_clear("planner:")
    logger.info(f"Cleared {cleared} planner cache entries")

    # Regenerate ideal portfolio (this will cache the result)
    ideal = await planner.calculate_ideal_portfolio()
    logger.info(f"Recalculated ideal portfolio with {len(ideal)} securities")

    # Regenerate recommendations (this will cache the result)
    recommendations = await planner.get_recommendations()
    buys = [r for r in recommendations if r.action == "buy"]
    sells = [r for r in recommendations if r.action == "sell"]
    logger.info(f"Generated {len(recommendations)} recommendations: {len(buys)} buys, {len(sells)} sells")


# -----------------------------------------------------------------------------
# ML Tasks
# -----------------------------------------------------------------------------


async def ml_retrain(db, retrainer) -> None:
    """Retrain ML models for all ML-enabled securities."""
    securities = await db.get_ml_enabled_securities()

    if not securities:
        logger.info("No ML-enabled securities to retrain")
        return

    trained = 0
    skipped = 0

    for sec in securities:
        symbol = sec["symbol"]
        result = await retrainer.retrain_symbol(symbol)

        if result:
            logger.info(
                f"ML retraining complete for {symbol}: "
                f"RMSE={result.get('validation_rmse', 0):.4f}, "
                f"samples={result.get('training_samples', 0)}"
            )
            trained += 1
        else:
            logger.info(f"ML retraining skipped for {symbol}: insufficient data")
            skipped += 1

    logger.info(f"ML retraining complete: {trained} trained, {skipped} skipped")


async def ml_monitor(db, monitor) -> None:
    """Monitor ML model performance for all ML-enabled securities."""
    securities = await db.get_ml_enabled_securities()

    if not securities:
        logger.info("No ML-enabled securities to monitor")
        return

    monitored = 0

    for sec in securities:
        symbol = sec["symbol"]
        result = await monitor.track_symbol_performance(symbol)

        if result and result.get("predictions_evaluated", 0) > 0:
            logger.info(
                f"ML performance for {symbol}: "
                f"MAE={result.get('mean_absolute_error', 0):.4f}, "
                f"RMSE={result.get('root_mean_squared_error', 0):.4f}, "
                f"N={result['predictions_evaluated']}"
            )

            if result.get("drift_detected"):
                logger.warning(f"ML DRIFT DETECTED for {symbol}!")
            monitored += 1
        else:
            logger.info(f"ML monitoring for {symbol}: no predictions to evaluate")

    logger.info(f"ML monitoring complete: {monitored} securities evaluated")


# -----------------------------------------------------------------------------
# Backup Tasks
# -----------------------------------------------------------------------------


async def backup_r2(db) -> None:
    """Backup data folder to Cloudflare R2."""
    from sentinel.settings import Settings

    settings = Settings()
    account_id = await settings.get("r2_account_id", "")
    access_key = await settings.get("r2_access_key", "")
    secret_key = await settings.get("r2_secret_key", "")
    bucket_name = await settings.get("r2_bucket_name", "")
    retention_days = await settings.get("r2_backup_retention_days", 30)

    if not all([account_id, access_key, secret_key, bucket_name]):
        logger.warning("R2 backup skipped: credentials not configured")
        return

    # Create tar.gz archive
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%S")
    archive_key = f"backups/sentinel-{timestamp}.tar.gz"

    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        _create_archive(tmp_path)
        client = _get_r2_client(account_id, access_key, secret_key)
        _upload_archive(client, bucket_name, archive_key, tmp_path)
        logger.info(f"Backup uploaded: {archive_key}")

        if retention_days > 0:
            _prune_old_backups(client, bucket_name, retention_days)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


# -----------------------------------------------------------------------------
# Helper Functions (for trading)
# -----------------------------------------------------------------------------


async def _execute_trade(broker, rec) -> bool:
    """Execute a single trade recommendation. Returns True if successful."""
    from sentinel.security import Security

    try:
        security = Security(rec.symbol)
        await security.load()

        if rec.action == "sell":
            order_id = await security.sell(rec.quantity)
            action_str = "SELL"
        else:
            order_id = await security.buy(rec.quantity)
            action_str = "BUY"

        if order_id:
            logger.info(
                f"Executed {action_str}: {rec.quantity} x {rec.symbol} "
                f"@ {rec.price:.2f} {rec.currency} (order: {order_id})"
            )
            return True
        else:
            logger.error(f"Failed to {action_str} {rec.symbol}: no order ID returned")
            return False

    except Exception as e:
        logger.error(f"Failed to execute {rec.action} {rec.symbol}: {e}")
        return False


async def _get_open_market_symbols(broker, db) -> set[str]:
    """Get symbols whose markets are currently open."""
    market_data = await broker.get_market_status("*")
    if not market_data:
        return set()

    markets = market_data.get("m", [])
    open_market_ids = {str(m.get("i")) for m in markets if m.get("s") == "OPEN"}

    if not open_market_ids:
        return set()

    securities = await db.get_all_securities(active_only=True)
    open_symbols = set()

    for sec in securities:
        data = sec.get("data")
        if data:
            try:
                sec_data = json.loads(data) if isinstance(data, str) else data
                market_id = str(sec_data.get("mrkt", {}).get("mkt_id"))
                if market_id in open_market_ids:
                    open_symbols.add(sec["symbol"])
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                pass

    return open_symbols


async def _log_pending_trades(broker, db, planner) -> None:
    """Log what trades would be executed (for research mode)."""
    recommendations = await planner.get_recommendations()
    if not recommendations:
        logger.info("No pending trade recommendations")
        return

    open_symbols = await _get_open_market_symbols(broker, db)

    for rec in recommendations:
        market_status = "OPEN" if rec.symbol in open_symbols else "CLOSED"
        logger.info(
            f"[RESEARCH] Would {rec.action.upper()}: {rec.quantity} x {rec.symbol} "
            f"@ {rec.price:.2f} {rec.currency} (market: {market_status})"
        )


# -----------------------------------------------------------------------------
# Helper Functions (for backup)
# -----------------------------------------------------------------------------


def _get_r2_client(account_id: str, access_key: str, secret_key: str):
    """Create a boto3 S3 client pointed at Cloudflare R2."""
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="auto",
    )


def _create_archive(dest_path: str) -> None:
    """Create a tar.gz archive of the data directory."""
    if not DATA_DIR.exists():
        raise FileNotFoundError(f"Data directory not found: {DATA_DIR}")

    with tarfile.open(dest_path, "w:gz") as tar:
        tar.add(str(DATA_DIR), arcname="data")

    size_mb = os.path.getsize(dest_path) / (1024 * 1024)
    logger.info(f"Archive created: {size_mb:.1f} MB")


def _upload_archive(client, bucket: str, key: str, file_path: str) -> None:
    """Upload archive to R2 bucket."""
    client.upload_file(file_path, bucket, key)


def _prune_old_backups(client, bucket: str, retention_days: int) -> None:
    """Delete backups older than retention period."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)

    try:
        response = client.list_objects_v2(Bucket=bucket, Prefix="backups/")
        contents = response.get("Contents", [])

        to_delete = [obj["Key"] for obj in contents if obj.get("LastModified") and obj["LastModified"] < cutoff]

        if to_delete:
            client.delete_objects(
                Bucket=bucket,
                Delete={"Objects": [{"Key": k} for k in to_delete]},
            )
            logger.info(f"Pruned {len(to_delete)} old backups")
    except Exception as e:
        logger.warning(f"Failed to prune old backups: {e}")
