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
            await db.save_prices(symbol, data)
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


async def sync_trades(db, broker) -> None:
    """
    Sync trade history from broker.

    Fetches all trades from Tradernet since 2020-01-01 and upserts them.
    Existing trades (by broker_trade_id) are skipped.
    """
    if not broker.connected:
        logger.warning("Broker not connected, skipping trades sync")
        return

    # Fetch all trades from broker
    trades = await broker.get_trades_history(start_date="2020-01-01")

    if not trades:
        logger.info("No trades returned from broker")
        return

    new_count = 0
    skipped_count = 0

    for trade in trades:
        trade_id = str(trade.get("id", ""))
        symbol = trade.get("symbol", trade.get("instr_nm", ""))
        side = trade.get("side", "BUY")
        quantity = float(trade.get("q", 0))
        price = float(trade.get("p", 0))
        date_str = trade.get("date", "")

        # Extract commission
        commission = float(trade.get("commission", 0) or 0)
        commission_currency = trade.get("commission_currency", "EUR")

        if not trade_id or not symbol:
            continue

        # Convert date format if needed (Tradernet uses "YYYY-MM-DD HH:MM:SS")
        executed_at = date_str.replace(" ", "T") if " " in date_str else date_str

        row_id = await db.upsert_trade(
            broker_trade_id=trade_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            executed_at=executed_at,
            raw_data=trade,
            commission=commission,
            commission_currency=commission_currency,
        )

        if row_id and row_id > 0:
            new_count += 1
        else:
            skipped_count += 1

    logger.info(f"Trades sync complete: {new_count} new, {skipped_count} existing")


async def sync_cashflows(db, broker) -> None:
    """
    Sync cash flow history (deposits, withdrawals, dividends, taxes) from broker.

    Fetches all cash flows from Tradernet since 2020-01-01 and upserts them.
    Existing entries are deduplicated using a content hash of the raw data.
    """
    if not broker.connected:
        logger.warning("Broker not connected, skipping cashflows sync")
        return

    # Fetch all cash flows from broker
    cash_flows = await broker.get_cash_flows(start_date="2020-01-01")

    if not cash_flows:
        logger.info("No cash flows returned from broker")
        return

    new_count = 0
    skipped_count = 0

    for flow in cash_flows:
        try:
            date = flow.get("date", "")
            type_id = flow.get("type_id", "")
            amount = float(flow.get("amount", 0) or 0)
            currency = flow.get("currency", "EUR")
            comment = flow.get("comment", "")

            if not date or not type_id:
                continue

            row_id = await db.upsert_cash_flow(
                date=date,
                type_id=type_id,
                amount=amount,
                currency=currency,
                comment=comment,
                raw_data=flow,
            )

            if row_id and row_id > 0:
                new_count += 1
            else:
                skipped_count += 1
        except (ValueError, TypeError) as e:
            logger.warning(f"Skipping invalid cash flow entry: {e}")
            continue

    logger.info(f"Cash flows sync complete: {new_count} new, {skipped_count} existing")


async def aggregate_compute(db) -> None:
    """Compute aggregate price series for country and industry groups."""
    from sentinel.aggregates import AggregateComputer

    computer = AggregateComputer(db)
    result = await computer.compute_all_aggregates()
    logger.info(f"Aggregate computation complete: {result['country']} country, {result['industry']} industry")


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


async def trading_balance_fix(db, broker) -> None:
    """Fix negative currency balances by converting from positive balances.

    This job runs periodically to ensure no currency has a negative balance,
    which would incur margin fees. It converts from currencies with positive
    balances to those with negative balances.
    """
    from sentinel.currency import Currency
    from sentinel.currency_exchange import CurrencyExchangeService

    if not broker.connected:
        logger.warning("Broker not connected, skipping balance fix")
        return

    # Get current cash balances
    balances = await db.get_cash_balances()
    if not balances:
        logger.info("No cash balances to check")
        return

    # Find negative and positive balances
    negative = {c: amt for c, amt in balances.items() if amt < 0}
    positive = {c: amt for c, amt in balances.items() if amt > 0}

    if not negative:
        logger.info("All currency balances are non-negative")
        return

    logger.warning(f"Found negative balances: {negative}")

    if not positive:
        logger.error("No positive currency balances available for conversion")
        return

    # Initialize services
    currency = Currency()
    fx = CurrencyExchangeService()

    # Buffer: aim to bring balance slightly positive, not just 0
    BUFFER_EUR = 10.0

    # Process each negative currency
    for neg_currency, neg_amount in negative.items():
        # Convert deficit to EUR, then add buffer (buffer is always in EUR terms)
        if neg_currency == "EUR":
            deficit_eur = abs(neg_amount) + BUFFER_EUR
        else:
            deficit_eur = await currency.to_eur(abs(neg_amount), neg_currency) + BUFFER_EUR

        logger.info(f"Covering {neg_currency} deficit: {abs(neg_amount):.2f} ({deficit_eur:.2f} EUR incl. buffer)")

        # Try to convert from positive balances
        for pos_currency, pos_amount in list(positive.items()):
            if deficit_eur <= 0:
                break

            if pos_amount <= 0:
                continue

            # Calculate EUR value of positive balance
            pos_eur_value = await currency.to_eur(pos_amount, pos_currency)

            # Determine how much to convert
            convert_eur = min(pos_eur_value, deficit_eur)

            # Calculate amount in source currency
            rate = await currency.get_rate(pos_currency)
            if rate > 0:
                convert_amount = convert_eur / rate
            else:
                convert_amount = pos_amount

            convert_amount = min(convert_amount, pos_amount)

            if convert_amount <= 0:
                continue

            # Determine target currency
            target_currency = "EUR" if neg_currency == "EUR" else neg_currency

            logger.info(f"Converting {convert_amount:.2f} {pos_currency} to {target_currency}")

            try:
                result = await fx.exchange(pos_currency, target_currency, convert_amount)
                if result:
                    logger.info(f"Successfully converted {convert_amount:.2f} {pos_currency} to {target_currency}")
                    # Update tracking
                    actual_eur = await currency.to_eur(convert_amount, pos_currency)
                    deficit_eur -= actual_eur
                    positive[pos_currency] = pos_amount - convert_amount
                else:
                    logger.error(f"Failed to convert {pos_currency} to {target_currency}")
            except Exception as e:
                logger.error(f"Error converting {pos_currency} to {target_currency}: {e}")

        if deficit_eur > 0:
            logger.warning(f"Could not fully cover {neg_currency} deficit. Remaining: {deficit_eur:.2f} EUR")


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
