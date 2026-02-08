"""
Snapshot Service - Handles portfolio snapshot reconstruction and backfill.

Usage:
    service = SnapshotService(db, currency)
    await service.backfill()
"""

import asyncio
import logging
import time
from datetime import date as date_type
from datetime import datetime, timedelta, timezone

from sentinel.database import Database
from sentinel.price_validator import PriceValidator

logger = logging.getLogger(__name__)
_BACKFILL_LOCK = asyncio.Lock()


def _format_progress(start_ts: float, current_idx: int, total: int, date_str: str, now_ts: float | None = None) -> str:
    now = time.monotonic() if now_ts is None else now_ts
    elapsed = max(0.0, now - start_ts)
    pct = (current_idx / total * 100.0) if total else 0.0
    if elapsed > 0 and current_idx > 0:
        rate = current_idx / elapsed
        remaining = (total - current_idx) / rate if rate > 0 else 0.0
    else:
        rate = 0.0
        remaining = 0.0
    return (
        f"Progress {current_idx}/{total} ({pct:.1f}%) date={date_str} "
        f"elapsed={elapsed:.1f}s eta={remaining:.1f}s rate={rate:.2f}/s"
    )


def _midnight_utc_ts(iso_date: str) -> int:
    """Convert YYYY-MM-DD string to unix timestamp at midnight UTC."""
    dt = datetime.strptime(iso_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


class SnapshotService:
    """Reconstructs historical portfolio snapshots from trades, prices, and cash flows."""

    def __init__(self, db: Database, currency):
        self._db = db
        self._currency = currency
        self._validator = PriceValidator()

    async def backfill(self) -> None:
        """
        Reconstruct historical portfolio snapshots from trades, prices, and cash flows.

        For each day from the first activity to today, builds a JSON snapshot:
        {"positions": {symbol: {quantity, value_eur}}, "cash_eur": float}
        """
        from sentinel.broker import Broker

        if _BACKFILL_LOCK.locked():
            logger.info("Snapshot backfill already running, waiting for lock")

        async with _BACKFILL_LOCK:
            start_ts = time.monotonic()
            logger.info("Backfilling portfolio snapshots...")

            trades = await self._db.get_trades(limit=10000)
            cash_flows = await self._db.get_cash_flows()
            if not trades and not cash_flows:
                logger.info("No trades or cash flows found, skipping backfill")
                return
            logger.info(
                "Loaded %s trades and %s cash flows in %.2fs",
                len(trades),
                len(cash_flows),
                time.monotonic() - start_ts,
            )

            # Deduplicate trades by broker_trade_id
            seen_ids = set()
            unique_trades = []
            for trade in trades:
                trade_id = trade.get("broker_trade_id")
                if trade_id and trade_id not in seen_ids:
                    seen_ids.add(trade_id)
                    unique_trades.append(trade)
            trades = unique_trades
            logger.info("Deduplicated trades: %s", len(trades))

            # Sort trades and cash flows by date
            trades_sorted = sorted(trades, key=lambda t: t["executed_at"])
            cash_flows_sorted = sorted(cash_flows, key=lambda cf: cf["date"])

            # First activity date
            first_trade_date = (
                datetime.fromtimestamp(trades_sorted[0]["executed_at"]).date().isoformat() if trades_sorted else None
            )
            first_cf_date = cash_flows_sorted[0]["date"] if cash_flows_sorted else None

            if not first_trade_date and not first_cf_date:
                logger.info("No activity found, skipping backfill")
                return

            first_activity_date = min(d for d in [first_trade_date, first_cf_date] if d)
            logger.info("First activity date: %s", first_activity_date)

            # Generate all dates from first activity to today.
            start_date = date_type.fromisoformat(first_activity_date)
            end_date = date_type.today()
            all_dates = []
            all_date_timestamps = []
            current = start_date
            while current <= end_date:
                iso = current.isoformat()
                all_dates.append(iso)
                all_date_timestamps.append(_midnight_utc_ts(iso))
                current += timedelta(days=1)
            logger.info("Date range: %s → %s (%s days)", start_date.isoformat(), end_date.isoformat(), len(all_dates))

            # Only process missing snapshot days.
            existing_snapshot_dates = set(
                await self._db.get_portfolio_snapshot_dates(
                    start_ts=all_date_timestamps[0],
                    end_ts=all_date_timestamps[-1],
                )
            )
            missing_date_pairs = [
                (iso, ts)
                for iso, ts in zip(all_dates, all_date_timestamps, strict=False)
                if ts not in existing_snapshot_dates
            ]
            if not missing_date_pairs:
                logger.info("Portfolio snapshots already complete for full activity range; skipping backfill")
                return
            missing_dates = [iso for iso, _ in missing_date_pairs]
            missing_timestamps = {ts for _, ts in missing_date_pairs}
            logger.info(
                "Backfilling only missing dates: %s missing of %s total",
                len(missing_date_pairs),
                len(all_dates),
            )

            # Filter out FX pairs and options — only keep actual stock positions
            def is_stock_symbol(symbol: str) -> bool:
                if "/" in symbol:
                    return False
                if symbol.startswith("+"):
                    return False
                if symbol.startswith("DGT"):
                    return False
                return True

            stock_trades = [t for t in trades if is_stock_symbol(t["symbol"])]
            excluded = len(trades) - len(stock_trades)
            logger.info(f"Processing {len(stock_trades)} stock trades (excluded {excluded} FX/options)")

            # Get all unique stock symbols from trades
            symbols = list(set(t["symbol"] for t in stock_trades))
            logger.info(f"Symbols to process: {len(symbols)}")

            all_prices_raw = await self._db.get_prices_bulk(symbols)
            missing_symbols = [s for s in symbols if not all_prices_raw.get(s)]
            if missing_symbols:
                logger.info("Missing price history for %s symbols", len(missing_symbols))
                logger.info(f"Fetching historical prices for {len(missing_symbols)} symbols: {missing_symbols}")
                broker = Broker()
                fetched_prices = await broker.get_historical_prices_bulk(missing_symbols, years=3)
                for symbol, prices in fetched_prices.items():
                    if prices:
                        await self._db.save_prices(symbol, prices)
                        all_prices_raw[symbol] = prices
                        logger.info(f"  Fetched {len(prices)} prices for {symbol}")
            else:
                logger.info("All price histories found locally (%s symbols)", len(symbols))

            # Validate prices using PriceValidator
            price_lookup: dict[str, dict[str, float]] = {}
            for symbol, raw_prices in all_prices_raw.items():
                if not raw_prices:
                    price_lookup[symbol] = {}
                    continue
                validated = self._validator.validate_and_interpolate(list(reversed(raw_prices)))
                price_lookup[symbol] = {p["date"]: p["close"] for p in validated}

            logger.info(
                "Validated price history for %s symbols in %.2fs",
                len(price_lookup),
                time.monotonic() - start_ts,
            )

            # Get securities for currency info
            securities = await self._db.get_all_securities(active_only=False)
            sec_currency_map = {s["symbol"]: s.get("currency", "EUR") for s in securities}

            for symbol in symbols:
                if symbol not in sec_currency_map:
                    if symbol.endswith(".US"):
                        sec_currency_map[symbol] = "USD"
                    elif symbol.endswith((".EU", ".GR")):
                        sec_currency_map[symbol] = "EUR"
                    elif symbol.endswith(".AS"):
                        sec_currency_map[symbol] = "HKD"
                    else:
                        sec_currency_map[symbol] = "EUR"

            # Prefetch historical FX rates only for missing dates.
            currencies_needed = list(set(sec_currency_map.values()))
            cf_currencies = list(set(cf["currency"] for cf in cash_flows))
            currencies_needed = list(set(currencies_needed + cf_currencies))
            logger.info(f"Prefetching FX rates for {len(missing_dates)} dates, currencies: {currencies_needed}")
            fx_start = time.monotonic()
            await self._currency.prefetch_rates_for_dates(currencies_needed, missing_dates)
            logger.info("FX prefetch complete in %.2fs", time.monotonic() - fx_start)

            # Running state
            positions: dict[str, float] = {}  # symbol -> quantity
            running_cash_eur = 0.0

            last_trade_idx = 0
            last_cf_idx = 0

            total_dates = len(all_dates)
            progress_every = max(1, total_dates // 50)
            if total_dates > 10 and progress_every < 5:
                progress_every = 5
            logger.info("Starting daily backfill scan for %s days (%s missing)", total_dates, len(missing_timestamps))

            for i, date_str in enumerate(all_dates):
                if i == 0 or (i + 1) % progress_every == 0 or i + 1 == total_dates:
                    logger.info(_format_progress(start_ts, i + 1, total_dates, date_str))

                # 1. Update cash flows up to this date
                while last_cf_idx < len(cash_flows_sorted):
                    cf = cash_flows_sorted[last_cf_idx]
                    if cf["date"] > date_str:
                        break

                    amount_local = cf["amount"]
                    curr = cf["currency"]
                    type_id = cf["type_id"]

                    amount_eur = await self._currency.to_eur_for_date(amount_local, curr, cf["date"])

                    if type_id not in ("block", "unblock"):
                        running_cash_eur += amount_eur

                    last_cf_idx += 1

                # 2. Update trades up to this date
                while last_trade_idx < len(trades_sorted):
                    trade = trades_sorted[last_trade_idx]
                    trade_date = datetime.fromtimestamp(trade["executed_at"]).date().isoformat()
                    if trade_date > date_str:
                        break

                    symbol = trade["symbol"]
                    qty = trade["quantity"]
                    price_local = trade["price"]
                    trade_value_local = qty * price_local
                    sec_curr = sec_currency_map.get(symbol, "EUR")

                    comm_local = trade.get("commission", 0) or 0
                    comm_curr = trade.get("commission_currency", "EUR")
                    comm_eur = await self._currency.to_eur_for_date(comm_local, comm_curr, trade_date)

                    trade_value_eur = await self._currency.to_eur_for_date(trade_value_local, sec_curr, trade_date)

                    if trade["side"] == "BUY":
                        if is_stock_symbol(symbol):
                            running_cash_eur -= trade_value_eur + comm_eur
                            positions[symbol] = positions.get(symbol, 0) + qty
                    else:  # SELL
                        if is_stock_symbol(symbol):
                            running_cash_eur += trade_value_eur - comm_eur
                            positions[symbol] = max(0, positions.get(symbol, 0) - qty)

                    last_trade_idx += 1

                date_ts = all_date_timestamps[i]
                if date_ts not in missing_timestamps:
                    continue

                # 3. Build positions snapshot with EUR values for missing dates only.
                positions_data = {}
                for symbol, qty in positions.items():
                    if qty <= 0:
                        continue

                    symbol_prices = price_lookup.get(symbol, {})
                    price = symbol_prices.get(date_str)
                    if price is None:
                        available_dates = sorted(d for d in symbol_prices.keys() if d <= date_str)
                        if available_dates:
                            price = symbol_prices[available_dates[-1]]

                    if price:
                        value_local = qty * price
                        sec_curr = sec_currency_map.get(symbol, "EUR")
                        value_eur = await self._currency.to_eur_for_date(value_local, sec_curr, date_str)
                        positions_data[symbol] = {
                            "quantity": qty,
                            "value_eur": round(value_eur, 2),
                        }

                # 4. Save snapshot (only missing date)
                snapshot_data = {
                    "positions": positions_data,
                    "cash_eur": round(running_cash_eur, 2),
                }
                await self._db.upsert_portfolio_snapshot(date_ts, snapshot_data)

            logger.info(
                "Portfolio snapshots backfill complete in %.2fs (%s snapshots written)",
                time.monotonic() - start_ts,
                len(missing_timestamps),
            )
