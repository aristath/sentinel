"""Job task functions - plain async functions for APScheduler."""

from __future__ import annotations

import asyncio
import inspect
import logging
import os
import tarfile
import tempfile
import time
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sentinel.markets import get_open_market_symbols
from sentinel.planner.models import TradeRecommendation
from sentinel.planner.rebalance_rules import buy_rank_key

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data"
SUBMITTED_TRADE_STATE_KEY = "submitted_trade"


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

    prices = await broker.get_historical_prices_bulk(symbols, years=20)
    synced = 0

    for symbol, data in prices.items():
        if data:
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


ETF_INSTR_KIND_C = 7  # Tradernet instr_kind_c for ETF/fund units.
# `getAllSecurities` rate-limits at roughly 30 calls/min as a burst budget,
# but in practice sustained calls hit 429 above ~12/min. Live testing at
# 4s/iter still produced ~6 back-offs per 63-symbol run; 6s/iter (10 calls/min)
# stays cleanly under the threshold and produces zero rate-limit hits in
# steady state. Total run time is ~6–8 min for ~60 active symbols, well
# within the daily sync window.
SYNC_METADATA_PACING_S = 6.0


async def sync_metadata(db, broker) -> None:
    """Refresh every active security's broker metadata, including country-of-risk
    and TRBC industry.

    Two broker calls per symbol: `get_security_info` (thin payload — market, lot,
    currency, used by the existing UPDATE) and the new `get_security_metadata`
    (parses `attributes.CntryOfRisk` and `sector_code` from `getAllSecurities`).

    ETFs (`instr_kind_c == 7`) are intentionally blanked — Tradernet stamps them
    with their domicile country (typically IE) and `"Equity ETFs"`, neither of
    which reflects the actual underlying exposure. Clara's macro-bucket task
    filters rows with empty geo+industry, so blanking keeps ETFs out of the
    macro-analysis loop.

    Resilience: for non-ETFs, empty values from the broker are treated as
    "I don't know" and the existing DB value is left untouched. This means a
    Tradernet shape change (e.g. renamed `CntryOfRisk`) silently degrades to
    "no updates" rather than wiping every classification. ETF blanking is the
    one exception — `instr_kind_c == 7` is a positive signal we trust.
    """
    securities = await db.get_all_securities(active_only=True)
    synced = 0

    for sec in securities:
        symbol = sec["symbol"]
        try:
            info = await broker.get_security_info(symbol)
            if not info:
                continue

            market_id = str(info.get("mrkt", {}).get("mkt_id", ""))
            update_kwargs: dict = {}

            meta = await broker.get_security_metadata(symbol)
            if meta is not None:
                # Always persist `instr_kind_c` — broker is the source of truth
                # for asset-class grouping (stock vs ETF vs depositary receipt).
                if meta.get("instr_kind_c") is not None:
                    update_kwargs["instr_kind_c"] = meta["instr_kind_c"]

                if meta.get("instr_kind_c") == ETF_INSTR_KIND_C:
                    update_kwargs["geography"] = ""
                    update_kwargs["industry"] = ""
                else:
                    geo = meta.get("geography") or ""
                    ind = meta.get("industry") or ""
                    if geo:
                        update_kwargs["geography"] = geo
                    if ind:
                        update_kwargs["industry"] = ind

            await db.update_security_metadata(symbol, info, market_id, **update_kwargs)
            synced += 1
        except Exception as e:
            logger.warning(f"sync_metadata: skipping {symbol} due to error: {e}")
        finally:
            await asyncio.sleep(SYNC_METADATA_PACING_S)

    logger.info(f"Metadata sync complete: {synced} securities")


async def sync_benchmarks(db, broker) -> None:
    """Refresh the benchmark-indices roster from Tradernet and sync their prices.

    Pulls the full set of indices via `broker.get_all_indices()` (paginated
    `getAllSecurities` filtered to `instr_type_c == 5`), upserts each one into
    the `benchmarks` table, then fetches recent daily closes for every known
    benchmark via the existing bulk-prices helper.

    Broker offline / 429-on-roster degrades gracefully: we still try to sync
    prices for whatever's already in the table. Better stale than dark.
    """
    indices = await broker.get_all_indices()
    if indices:
        for idx in indices:
            await db.upsert_benchmark(
                idx["symbol"],
                name=idx.get("name") or idx["symbol"],
                mkt_short_code=idx.get("mkt_short_code"),
                instr_kind_c=idx.get("instr_kind_c"),
                currency=idx.get("currency"),
            )
        logger.info(f"Benchmark roster refreshed: {len(indices)} indices")
    else:
        logger.warning("Benchmark roster fetch failed; price sync continues for existing rows")

    known = await db.get_benchmarks()
    if not known:
        logger.info("No benchmarks to price-sync")
        return

    symbols = [b["symbol"] for b in known]
    prices_by_symbol = await broker.get_historical_prices_bulk(symbols, years=5)
    saved = 0
    for symbol in symbols:
        prices = prices_by_symbol.get(symbol) or []
        if not prices:
            continue
        await db.save_benchmark_prices(symbol, prices)
        saved += 1
    logger.info(f"Benchmark prices synced: {saved}/{len(symbols)}")


async def decay_user_multipliers(db, settings=None) -> None:
    """Step the stored `user_multiplier` of every old-enough security one tick
    toward neutral (0.5).

    Reads its knobs from settings (`user_multiplier_decay_factor`,
    `user_multiplier_decay_interval_days`) and applies one decay step to every
    security whose slider value is older than the interval AND not already at
    neutral. Touching the slider via the preference endpoint resets the
    timestamp; this job won't re-touch a fresh row until it ages out again.

    Replaces the historic read-time fade — by physically updating the stored
    value, every downstream consumer (planner, UI, exports) sees the same
    "this is what the user effectively believes today" number without having
    to apply any correction.
    """
    from datetime import datetime, timedelta, timezone

    from sentinel.planner.preferences import (
        DEFAULT_DECAY_FADE_FACTOR,
        NEUTRAL_USER_MULTIPLIER,
        decayed_user_multiplier,
        normalize_user_multiplier,
        parse_utc_datetime,
    )

    if settings is None:
        from sentinel.settings import Settings

        settings = Settings()

    factor_raw = await settings.get("user_multiplier_decay_factor", DEFAULT_DECAY_FADE_FACTOR)
    interval_raw = await settings.get("user_multiplier_decay_interval_days", 7)
    try:
        fade_factor = float(factor_raw if factor_raw is not None else DEFAULT_DECAY_FADE_FACTOR)
    except (TypeError, ValueError):
        fade_factor = DEFAULT_DECAY_FADE_FACTOR
    try:
        interval_days = float(interval_raw if interval_raw is not None else 7)
    except (TypeError, ValueError):
        interval_days = 7.0

    securities = await db.get_all_securities(active_only=False)
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=interval_days)

    decayed = 0
    for sec in securities:
        updated_at = parse_utc_datetime(sec.get("user_multiplier_updated_at"))
        if updated_at is None:
            # No timestamp → no idea how old this is. Safer to leave alone
            # than to randomly decay a freshly-set value.
            continue
        if updated_at > cutoff:
            continue

        current = normalize_user_multiplier(sec.get("user_multiplier", NEUTRAL_USER_MULTIPLIER))
        if abs(current - NEUTRAL_USER_MULTIPLIER) < 1e-9:
            # Already neutral — nothing to fade, no write needed.
            continue

        new_value = decayed_user_multiplier(current, fade_factor)
        await db.set_user_multiplier(sec["symbol"], new_value, source="decay")
        decayed += 1

    logger.info(f"User-multiplier decay: {decayed}/{len(securities)} rows decayed one step")


async def sync_exchange_rates() -> None:
    """Sync exchange rates."""
    from sentinel.currency import Currency

    currency = Currency()
    rates = await currency.sync_rates()
    logger.info(f"Exchange rates synced: {len(rates)} currencies")


def _parse_broker_timestamp(date_str: str) -> int:
    """Parse a broker trade date into a unix timestamp (0 if unparseable).

    Tradernet/Freedom24 has used several date formats over time: ISO 8601 with a
    'T' separator and milliseconds ("2026-06-03T11:46:14.640"), space-separated
    ("2026-06-03 11:46:14"), and date-only ("2026-06-03"). The previous parser
    only handled the space and date-only forms, so the current ISO form silently
    collapsed to midnight and lost the intraday time. ``datetime.fromisoformat``
    handles all of these (including a trailing 'Z'/offset); we fall back to the
    date portion only if the full string can't be parsed.
    """
    if not isinstance(date_str, str) or not date_str.strip():
        return 0
    raw = date_str.strip()
    try:
        return int(datetime.fromisoformat(raw).timestamp())
    except ValueError:
        pass
    try:
        return int(datetime.strptime(raw[:10], "%Y-%m-%d").timestamp())
    except (ValueError, TypeError):
        return 0


async def sync_trades(db, broker) -> None:
    """
    Sync trade history from broker.

    Fetches all trades from Tradernet since 2020-01-01 and upserts them.
    Existing trades (by broker_trade_id) are skipped.
    """
    if not broker.connected:
        logger.warning("Broker not connected, skipping trades sync")
        return

    start_date = "2020-01-01"
    get_trades = getattr(db, "get_trades", None)
    if callable(get_trades):
        latest_rows = get_trades(limit=1)
        if inspect.isawaitable(latest_rows):
            latest_rows = await latest_rows
        if isinstance(latest_rows, list) and latest_rows:
            first_row = latest_rows[0]
            if not isinstance(first_row, dict):
                first_row = {}
            latest_ts_raw = first_row.get("executed_at")
            if isinstance(latest_ts_raw, str | int | float):
                try:
                    latest_ts = int(latest_ts_raw)
                except ValueError:
                    latest_ts = 0
            else:
                latest_ts = 0
            if latest_ts > 0:
                # Re-fetch a small overlap window to avoid missing delayed broker entries.
                overlap_start = datetime.fromtimestamp(latest_ts, tz=timezone.utc) - timedelta(days=2)
                start_date = overlap_start.strftime("%Y-%m-%d")

    # Fetch trades from broker
    trades = await broker.get_trades_history(start_date=start_date)

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

        # Parse broker date to unix timestamp. Handles ISO 8601 ("...T..."),
        # space-separated, and date-only forms (see _parse_broker_timestamp).
        executed_at_ts = _parse_broker_timestamp(date_str)

        row_id = await db.upsert_trade(
            broker_trade_id=trade_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            executed_at=executed_at_ts,
            raw_data=trade,
            commission=commission,
            commission_currency=commission_currency,
        )

        if row_id and row_id > 0:
            new_count += 1
        else:
            skipped_count += 1

    logger.info(f"Trades sync complete ({start_date}): {new_count} new, {skipped_count} existing")


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


async def sync_dividends(db, broker) -> None:
    """
    Sync dividend history from broker corporate actions report.

    Fetches all corporate actions, filters to dividends, computes net EUR value,
    and upserts into the dividends table. Deduplicates by corporate_action_id.
    """
    from sentinel.currency import Currency

    if not broker.connected:
        logger.warning("Broker not connected, skipping dividends sync")
        return

    actions = await broker.get_corporate_actions(start_date="2020-01-01")

    if not actions:
        logger.info("No corporate actions returned from broker")
        return

    currency_svc = Currency()
    new_count = 0
    skipped_count = 0

    for action in actions:
        try:
            if action.get("type_id") != "dividend":
                continue

            ca_id = action.get("corporate_action_id", "")
            symbol = action.get("ticker", "")
            date = action.get("date", "")
            amount = float(action.get("amount", 0) or 0)
            cur = action.get("currency", "EUR")

            if not ca_id or not symbol or not date:
                continue

            # The `amount` field from the API is already net of all taxes
            # (both tax_amount and external_tax are already deducted from gross).
            # Convert the net credited amount to EUR.
            if cur != "EUR":
                value_eur = await currency_svc.to_eur_for_date(amount, cur, date)
            else:
                value_eur = amount

            row_id = await db.upsert_dividend(
                id=ca_id,
                symbol=symbol,
                date=date,
                amount=amount,
                currency=cur,
                value=value_eur,
                data=action,
            )

            if row_id and row_id > 0:
                new_count += 1
            else:
                skipped_count += 1

        except (ValueError, TypeError) as e:
            logger.warning(f"Skipping invalid dividend entry: {e}")
            continue

    logger.info(f"Dividends sync complete: {new_count} new, {skipped_count} existing")


async def snapshot_backfill(db, currency) -> None:
    """Maintain portfolio snapshots by filling only missing dates."""
    from sentinel.snapshot_service import SnapshotService

    service = SnapshotService(db, currency)
    await service.backfill()


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
    open_securities = await get_open_market_symbols(broker, db)

    if not open_securities:
        logger.info("No securities with open markets")
        return

    logger.info(f"Securities with open markets: {', '.join(open_securities)}")

    # Check for pending trades
    recommendations = await planner.get_recommendations(eligible_symbols=open_securities)
    actionable = [r for r in recommendations if r.symbol in open_securities]

    if not actionable:
        logger.info("No actionable trades for open markets")
        return

    # Log recommendations (actual execution requires live mode)
    for rec in actionable:
        logger.info(f"Ready to {rec.action.upper()}: {rec.quantity} x {rec.symbol} @ {rec.price:.2f} {rec.currency}")


async def trading_execute(broker, db, planner, portfolio) -> None:
    """Replan from fresh broker state and submit at most one transaction.

    Only executes in LIVE trading mode. In research mode, logs what would happen.
    Each invocation is independent: the previous plan is discarded and the next
    order is selected from current broker state and currently open markets.
    """
    from sentinel.settings import Settings

    if not broker.connected:
        logger.warning("Broker not connected, skipping trade execution")
        return

    # Check trading mode
    settings = Settings()
    trading_mode = await settings.get("trading_mode", "research")

    is_live = trading_mode == "live"

    # Plans are disposable. Refresh the account and discard every cached input
    # before deciding what the next configured execution window should do.
    await sync_portfolio(portfolio)
    await sync_trades(db, broker)
    if not await _reconcile_submitted_trade(db):
        logger.info("Previous submitted trade is awaiting broker confirmation")
        return

    if is_live and await broker.has_pending_orders():
        logger.info("Broker has pending orders, skipping trade execution")
        return

    await db.cache_clear("quotes:")
    await db.invalidate_planner_cache()

    open_symbols = await get_open_market_symbols(broker, db)
    if not open_symbols:
        logger.info("No securities with open markets, skipping execution")
        return

    recommendations = await planner.get_recommendations(
        eligible_symbols=open_symbols,
        track_fallback_state=is_live,
    )
    if not recommendations:
        logger.info("No trade recommendations")
        return

    # Filter to actionable (open markets only)
    actionable = [r for r in recommendations if r.symbol in open_symbols]
    if not actionable:
        logger.info("No actionable trades for open markets")
        return

    next_trade = min(actionable, key=_execution_order_key)
    if not is_live:
        logger.info(
            f"Trading mode is '{trading_mode}', would {next_trade.action.upper()}: "
            f"{next_trade.quantity} x {next_trade.symbol} @ {next_trade.price:.2f} {next_trade.currency}"
        )
        return

    order_id = await _execute_trade(broker, next_trade)
    if not order_id:
        return

    await db.set_planner_state(
        SUBMITTED_TRADE_STATE_KEY,
        {
            "order_id": str(order_id),
            "submitted_at": int(time.time()),
            "recommendation": asdict(next_trade),
        },
    )
    await db.invalidate_planner_cache()


async def trading_rebalance(planner) -> None:
    """Check if portfolio needs rebalancing and generate recommendations."""
    summary = await planner.get_rebalance_summary()
    if "needs_rebalance" in summary:
        needs_rebalance = bool(summary["needs_rebalance"])
    else:
        needs_rebalance = summary.get("status") in {"minor_drift", "needs_rebalance"}

    if needs_rebalance:
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


async def planning_refresh(db, planner, broker) -> None:
    """Refresh trading plan by clearing caches and regenerating recommendations."""
    from sentinel.universe import reconcile_universe_from_freedom24_default_list

    # Ensure planner sees manual broker trades before refreshing recommendations.
    await sync_trades(db, broker)

    universe_result = await reconcile_universe_from_freedom24_default_list(db, broker)
    if universe_result.changed:
        logger.info("Freedom24 universe reconciliation changed state: %s", universe_result.as_dict())

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


def _execution_order_key(rec) -> tuple:
    """Use the planner's explicit rank, with deterministic legacy fallbacks."""
    rank = getattr(rec, "execution_rank", None)
    if isinstance(rank, int | float):
        return (0, float(rank), str(rec.symbol))
    if rec.action == "sell":
        return (1, 0, -float(rec.priority), str(rec.symbol))
    return (1, 1, *buy_rank_key(rec))


async def _execute_trade(broker, rec) -> str | None:
    """Submit one trade recommendation and return its broker order ID."""
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
                f"Submitted {action_str}: {rec.quantity} x {rec.symbol} "
                f"@ {rec.price:.2f} {rec.currency} (order: {order_id})"
            )
            return str(order_id)
        else:
            logger.error(f"Failed to {action_str} {rec.symbol}: no order ID returned")
            return None

    except Exception as e:
        logger.error(f"Failed to execute {rec.action} {rec.symbol}: {e}")
        return None


async def _reconcile_submitted_trade(db) -> bool:
    """Advance strategy state only after a submitted order appears in broker trades."""
    payload = await db.get_planner_state(SUBMITTED_TRADE_STATE_KEY)
    if payload is None:
        return True
    if not isinstance(payload, dict):
        logger.error("Discarding malformed submitted trade state")
        await db.delete_planner_state(SUBMITTED_TRADE_STATE_KEY)
        return True

    order_id = str(payload.get("order_id", ""))
    rec_data = payload.get("recommendation")
    submitted_at = int(payload.get("submitted_at", 0) or 0)
    if not order_id or not isinstance(rec_data, dict):
        logger.error("Discarding incomplete submitted trade state")
        await db.delete_planner_state(SUBMITTED_TRADE_STATE_KEY)
        return True

    trades = await db.get_trades(symbol=rec_data.get("symbol"), limit=100)
    matching = [trade for trade in trades if str((trade.get("raw_data") or {}).get("order_id", "")) == order_id]
    if matching:
        rec = TradeRecommendation(**rec_data)
        executed_at = max(int(trade.get("executed_at", 0) or 0) for trade in matching)
        filled_quantity = sum(float(trade.get("quantity", 0) or 0) for trade in matching)
        weighted_price = (
            sum(float(trade.get("price", 0) or 0) * float(trade.get("quantity", 0) or 0) for trade in matching)
            / filled_quantity
            if filled_quantity > 0
            else rec.price
        )
        await _update_strategy_state_after_execution(
            db,
            rec,
            executed_at=executed_at or None,
            executed_price=weighted_price,
        )
        await db.delete_planner_state(SUBMITTED_TRADE_STATE_KEY)
        logger.info("Confirmed broker fill for order %s", order_id)
        return True

    schedule = await db.get_job_schedule("trading:execute")
    interval_minutes = 60
    if isinstance(schedule, dict):
        interval_minutes = int(
            schedule.get("interval_market_open_minutes") or schedule.get("interval_minutes") or interval_minutes
        )
    grace_seconds = max(60, interval_minutes * 2 * 60)
    if submitted_at > 0 and int(time.time()) - submitted_at < grace_seconds:
        return False

    logger.warning("Order %s was not found in broker trade history; releasing stale submission state", order_id)
    await db.delete_planner_state(SUBMITTED_TRADE_STATE_KEY)
    return True


async def _update_strategy_state_after_execution(
    db,
    rec,
    *,
    executed_at: int | None = None,
    executed_price: float | None = None,
) -> None:
    """Persist deterministic strategy lifecycle state after a successful trade."""
    getter = getattr(db, "get_strategy_state", None)
    upserter = getattr(db, "upsert_strategy_state", None)
    if not callable(getter) or not callable(upserter):
        return

    current_value = getter(rec.symbol)
    if inspect.isawaitable(current_value):
        current_value = await current_value
    current = current_value if isinstance(current_value, dict) else {}
    now = int(executed_at if executed_at is not None else time.time())
    updates = {
        "updated_at": now,
        "sleeve": rec.sleeve or current.get("sleeve", "core"),
    }

    if rec.action == "buy":
        tranche_stage = int(current.get("tranche_stage", 0) or 0)
        if rec.reason_code and rec.reason_code.startswith("entry_t"):
            try:
                tranche_stage = max(tranche_stage, int(rec.reason_code[-1]))
            except ValueError:
                pass
        updates.update(
            {
                "tranche_stage": tranche_stage,
                "last_entry_price": executed_price if executed_price is not None else rec.price,
                "last_entry_ts": now,
            }
        )
        delete_planner_state = getattr(db, "delete_planner_state", None)
        if callable(delete_planner_state):
            result = delete_planner_state("fallback_wait_started_at")
            if inspect.isawaitable(result):
                await result
    else:
        scaleout_stage = int(current.get("scaleout_stage", 0) or 0)
        if rec.reason_code == "scaleout_10":
            scaleout_stage = max(scaleout_stage, 1)
        elif rec.reason_code == "scaleout_18":
            scaleout_stage = max(scaleout_stage, 2)

        updates["scaleout_stage"] = scaleout_stage
        if rec.reason_code in {"exit_momentum", "time_stop_rotation"}:
            updates["last_rotation_ts"] = now
            updates["tranche_stage"] = 0
            updates["scaleout_stage"] = 0

    upsert_result = upserter(rec.symbol, **updates)
    if inspect.isawaitable(upsert_result):
        await upsert_result


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
