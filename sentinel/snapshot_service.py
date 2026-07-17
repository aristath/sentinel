"""
Snapshot Service - Handles portfolio snapshot reconstruction and backfill.

Usage:
    service = SnapshotService(db, currency)
    await service.backfill()
"""

import asyncio
import json
import logging
import time
from collections.abc import Mapping
from datetime import date as date_type
from datetime import datetime, timedelta, timezone
from typing import Any

from sentinel.database import Database
from sentinel.price_validator import PriceValidator

logger = logging.getLogger(__name__)
_BACKFILL_LOCK = asyncio.Lock()
SNAPSHOT_MUTABLE_TAIL_DAYS = 30
POSITION_EPSILON = 1e-9


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


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _raw_data(row: Mapping[str, Any]) -> dict[str, Any]:
    raw = row.get("raw_data")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _snapshot_write_plan(
    all_dates: list[str],
    all_date_timestamps: list[int],
    existing_snapshot_dates: set[int],
    *,
    today: date_type | None = None,
    tail_days: int = SNAPSHOT_MUTABLE_TAIL_DAYS,
) -> list[tuple[str, int]]:
    if not all_dates:
        return []
    today = today or date_type.today()
    refresh_start = max(date_type.fromisoformat(all_dates[0]), today - timedelta(days=tail_days))
    return [
        (iso, ts)
        for iso, ts in zip(all_dates, all_date_timestamps, strict=False)
        if ts not in existing_snapshot_dates or date_type.fromisoformat(iso) >= refresh_start
    ]


def _apply_stock_position_trade(positions: dict[str, float], symbol: str, side: str, quantity: float) -> None:
    current_quantity = positions.get(symbol, 0.0)
    next_quantity = current_quantity + quantity if side == "BUY" else current_quantity - quantity

    if abs(next_quantity) < POSITION_EPSILON:
        positions.pop(symbol, None)
    else:
        positions[symbol] = next_quantity


def _apply_cash_balance(cash_balances: dict[str, float], currency: str, amount: float) -> None:
    if not currency or abs(amount) < POSITION_EPSILON:
        return
    next_amount = cash_balances.get(currency, 0.0) + amount
    if abs(next_amount) < POSITION_EPSILON:
        cash_balances.pop(currency, None)
    else:
        cash_balances[currency] = next_amount


def _cashflow_affects_trading_cash(cash_flow: Mapping[str, Any]) -> bool:
    type_id = cash_flow.get("type_id")
    if type_id not in {"block", "unblock", "block_commission", "unblock_commission"}:
        return True
    return _raw_data(cash_flow).get("account") == "trading"


def _apply_cash_flow(cash_balances: dict[str, float], cash_flow: Mapping[str, Any]) -> None:
    if not _cashflow_affects_trading_cash(cash_flow):
        return
    _apply_cash_balance(
        cash_balances,
        str(cash_flow.get("currency") or "EUR"),
        _as_float(cash_flow.get("amount")),
    )


def _trade_cash_amount(trade: Mapping[str, Any]) -> float:
    raw = _raw_data(trade)
    amount = _as_float(raw.get("summ"), default=float("nan"))
    if amount == amount:
        return amount
    amount = _as_float(raw.get("v"), default=float("nan"))
    if amount == amount:
        return amount
    return _as_float(trade.get("quantity")) * _as_float(trade.get("price"))


def _apply_trade_cash(
    cash_balances: dict[str, float],
    trade: Mapping[str, Any],
    *,
    security_currency: str,
) -> None:
    symbol = str(trade.get("symbol") or "")
    side = str(trade.get("side") or "").upper()
    quantity = _as_float(trade.get("quantity"))
    amount = _trade_cash_amount(trade)

    if "/" in symbol:
        base, quote = symbol.split("/", 1)
        if side == "BUY":
            _apply_cash_balance(cash_balances, base, quantity)
            _apply_cash_balance(cash_balances, quote, -amount)
        elif side == "SELL":
            _apply_cash_balance(cash_balances, base, -quantity)
            _apply_cash_balance(cash_balances, quote, amount)
    else:
        raw = _raw_data(trade)
        currency = str(raw.get("curr_c") or security_currency or "EUR")
        _apply_cash_balance(cash_balances, currency, -amount if side == "BUY" else amount)

    commission = _as_float(trade.get("commission"))
    if commission:
        _apply_cash_balance(cash_balances, str(trade.get("commission_currency") or "EUR"), -commission)


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

            # Historical snapshots are deterministic, but the recent tail is
            # mutable in practice: trades, cashflows, and broker settlement can
            # arrive after a date already has a row.
            existing_snapshot_dates = set(
                await self._db.get_portfolio_snapshot_dates(
                    start_ts=all_date_timestamps[0],
                    end_ts=all_date_timestamps[-1],
                )
            )
            write_date_pairs = _snapshot_write_plan(all_dates, all_date_timestamps, existing_snapshot_dates)
            if not write_date_pairs:
                logger.info("Portfolio snapshots already complete and recent tail is fresh; skipping backfill")
                return
            write_dates = [iso for iso, _ in write_date_pairs]
            write_timestamps = {ts for _, ts in write_date_pairs}
            missing_count = sum(1 for _, ts in write_date_pairs if ts not in existing_snapshot_dates)
            refresh_count = len(write_date_pairs) - missing_count
            logger.info(
                "Backfilling/refreshing snapshots: %s missing, %s recent refreshes of %s total",
                missing_count,
                refresh_count,
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

            live_cash_balances = await self._current_broker_cash()

            # Prefetch historical FX rates only for dates we will write.
            currencies_needed = list(set(sec_currency_map.values()))
            cf_currencies = list(set(cf["currency"] for cf in cash_flows))
            trade_currencies = []
            for trade in trades:
                symbol = trade.get("symbol") or ""
                if "/" in symbol:
                    base, quote = symbol.split("/", 1)
                    trade_currencies.extend([base, quote])
                else:
                    raw = _raw_data(trade)
                    trade_currencies.append(raw.get("curr_c") or sec_currency_map.get(symbol, "EUR"))
                if trade.get("commission_currency"):
                    trade_currencies.append(trade["commission_currency"])
            live_cash_currencies = list((live_cash_balances or {}).keys())
            currencies_needed = [
                str(currency)
                for currency in set(currencies_needed + cf_currencies + trade_currencies + live_cash_currencies)
                if currency
            ]
            logger.info(f"Prefetching FX rates for {len(write_dates)} dates, currencies: {currencies_needed}")
            fx_start = time.monotonic()
            await self._currency.prefetch_rates_for_dates(currencies_needed, write_dates)
            logger.info("FX prefetch complete in %.2fs", time.monotonic() - fx_start)

            # Running state
            positions: dict[str, float] = {}  # symbol -> quantity
            cash_balances: dict[str, float] = {}

            last_trade_idx = 0
            last_cf_idx = 0

            total_dates = len(all_dates)
            progress_every = max(1, total_dates // 50)
            if total_dates > 10 and progress_every < 5:
                progress_every = 5
            logger.info("Starting daily backfill scan for %s days (%s writes)", total_dates, len(write_timestamps))

            for i, date_str in enumerate(all_dates):
                if i == 0 or (i + 1) % progress_every == 0 or i + 1 == total_dates:
                    logger.info(_format_progress(start_ts, i + 1, total_dates, date_str))

                # 1. Update cash flows up to this date
                while last_cf_idx < len(cash_flows_sorted):
                    cf = cash_flows_sorted[last_cf_idx]
                    if cf["date"] > date_str:
                        break

                    _apply_cash_flow(cash_balances, cf)

                    last_cf_idx += 1

                # 2. Update trades up to this date
                while last_trade_idx < len(trades_sorted):
                    trade = trades_sorted[last_trade_idx]
                    trade_date = datetime.fromtimestamp(trade["executed_at"]).date().isoformat()
                    if trade_date > date_str:
                        break

                    symbol = trade["symbol"]
                    qty = trade["quantity"]
                    sec_curr = sec_currency_map.get(symbol, "EUR")

                    _apply_trade_cash(cash_balances, trade, security_currency=sec_curr)

                    if trade["side"] == "BUY":
                        if is_stock_symbol(symbol):
                            _apply_stock_position_trade(positions, symbol, trade["side"], qty)
                    else:  # SELL
                        if is_stock_symbol(symbol):
                            _apply_stock_position_trade(positions, symbol, trade["side"], qty)

                    last_trade_idx += 1

                date_ts = all_date_timestamps[i]
                if date_ts not in write_timestamps:
                    continue

                # 3. Build positions snapshot with EUR values for dates we will write.
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

                snapshot_cash_balances = cash_balances
                if live_cash_balances and date_str == date_type.today().isoformat():
                    snapshot_cash_balances = live_cash_balances

                cash_eur = 0.0
                cash_data = {}
                for currency, amount in snapshot_cash_balances.items():
                    if abs(amount) < POSITION_EPSILON:
                        continue
                    cash_data[currency] = round(amount, 2)
                    cash_eur += await self._currency.to_eur_for_date(amount, currency, date_str)

                # 4. Save snapshot (only missing date)
                snapshot_data = {
                    "positions": positions_data,
                    "cash": cash_data,
                    "cash_eur": round(cash_eur, 2),
                }
                await self._db.upsert_portfolio_snapshot(date_ts, snapshot_data)

            logger.info(
                "Portfolio snapshots backfill complete in %.2fs (%s snapshots written)",
                time.monotonic() - start_ts,
                len(write_timestamps),
            )

    async def _current_broker_cash(self) -> dict[str, float] | None:
        from sentinel.broker import Broker

        try:
            broker = Broker()
            if not await broker.connect():
                return None
            portfolio = await broker.get_portfolio()
            cash = portfolio.get("cash") or {}
        except Exception as e:
            logger.info("Live broker cash unavailable for snapshot reconciliation: %s", e)
            return None

        return {str(currency): _as_float(amount) for currency, amount in cash.items()}
