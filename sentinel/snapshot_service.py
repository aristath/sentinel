"""
Snapshot Service - Handles portfolio snapshot reconstruction and backfill.

Usage:
    service = SnapshotService(db, currency)
    await service.backfill()
"""

import logging
from datetime import date as date_type
from datetime import datetime, timedelta

from sentinel.database import Database
from sentinel.price_validator import PriceValidator

logger = logging.getLogger(__name__)


class SnapshotService:
    """Reconstructs historical portfolio snapshots from trades, prices, and cash flows."""

    def __init__(self, db: Database, currency):
        self._db = db
        self._currency = currency
        self._validator = PriceValidator()

    async def backfill(self) -> None:
        """
        Reconstruct historical portfolio snapshots from trades, prices, and cash flows.

        For each trading day from the first trade to today:
        1. Reconstruct positions from cumulative trades up to that date
        2. Get closing prices for that date (using historical FX rates)
        3. Get cumulative deposits/withdrawals from cash_flows
        4. Calculate: P&L = positions_value - net_deposits
        """
        from sentinel.broker import Broker

        logger.info("Backfilling portfolio snapshots...")

        # Get all trades ordered by date
        trades = await self._db.get_trades(limit=10000)
        cash_flows = await self._db.get_cash_flows()
        if not trades and not cash_flows:
            logger.info("No trades or cash flows found, skipping backfill")
            return

        # Deduplicate trades by broker_trade_id
        seen_ids = set()
        unique_trades = []
        for trade in trades:
            trade_id = trade.get("broker_trade_id")
            if trade_id and trade_id not in seen_ids:
                seen_ids.add(trade_id)
                unique_trades.append(trade)
        trades = unique_trades

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

        # Filter out FX pairs and options for position tracking - only keep actual stock positions
        def is_stock_symbol(symbol: str) -> bool:
            if "/" in symbol:  # FX pairs like EUR/USD
                return False
            if symbol.startswith("+"):  # Options like +VXX.17MAY2024.C12.5
                return False
            if symbol.startswith("DGT"):  # Derivatives
                return False
            return True

        stock_trades = [t for t in trades if is_stock_symbol(t["symbol"])]
        excluded = len(trades) - len(stock_trades)
        logger.info(f"Processing {len(stock_trades)} stock trades (excluded {excluded} FX/options)")

        # Get all unique stock symbols from trades
        symbols = list(set(t["symbol"] for t in stock_trades))
        logger.info(f"Symbols to process: {len(symbols)}")

        # Check which symbols are missing price data
        all_prices_raw = await self._db.get_prices_bulk(symbols)
        missing_symbols = [s for s in symbols if not all_prices_raw.get(s)]

        # Fetch missing historical prices from broker
        if missing_symbols:
            logger.info(f"Fetching historical prices for {len(missing_symbols)} symbols: {missing_symbols}")
            broker = Broker()
            fetched_prices = await broker.get_historical_prices_bulk(missing_symbols, years=3)
            for symbol, prices in fetched_prices.items():
                if prices:
                    await self._db.save_prices(symbol, prices)
                    all_prices_raw[symbol] = prices
                    logger.info(f"  Fetched {len(prices)} prices for {symbol}")

        # Validate prices using PriceValidator
        price_lookup: dict[str, dict[str, float]] = {}
        for symbol, raw_prices in all_prices_raw.items():
            if not raw_prices:
                price_lookup[symbol] = {}
                continue
            # Prices come from DB newest-first, validator expects oldest-first
            validated = self._validator.validate_and_interpolate(list(reversed(raw_prices)))
            price_lookup[symbol] = {p["date"]: p["close"] for p in validated}

        # Get securities for currency info
        securities = await self._db.get_all_securities(active_only=False)
        sec_currency_map = {s["symbol"]: s.get("currency", "EUR") for s in securities}

        # For symbols not in securities table, try to infer currency from symbol suffix
        for symbol in symbols:
            if symbol not in sec_currency_map:
                if symbol.endswith(".US"):
                    sec_currency_map[symbol] = "USD"
                elif symbol.endswith(".EU"):
                    sec_currency_map[symbol] = "EUR"
                elif symbol.endswith(".GR"):
                    sec_currency_map[symbol] = "EUR"
                elif symbol.endswith(".AS"):
                    sec_currency_map[symbol] = "HKD"
                else:
                    sec_currency_map[symbol] = "EUR"

        # Generate all dates from first activity to today
        start_date = date_type.fromisoformat(first_activity_date)
        end_date = date_type.today()
        all_dates = []
        current = start_date
        while current <= end_date:
            all_dates.append(current.isoformat())
            current += timedelta(days=1)

        # Prefetch historical FX rates for all dates and currencies
        currencies_needed = list(set(sec_currency_map.values()))
        # Also include currencies from cash flows
        cf_currencies = list(set(cf["currency"] for cf in cash_flows))
        currencies_needed = list(set(currencies_needed + cf_currencies))

        logger.info(f"Prefetching FX rates for {len(all_dates)} dates, currencies: {currencies_needed}")
        await self._currency.prefetch_rates_for_dates(currencies_needed, all_dates)

        # Running state
        positions: dict[str, float] = {}  # symbol -> quantity
        cost_basis: dict[str, float] = {}  # symbol -> total cost in EUR
        running_cash_eur = 0.0
        cumulative_net_deposits_eur = 0.0

        # Keep track of processed items to avoid re-processing
        last_trade_idx = 0
        last_cf_idx = 0

        # Process each date
        total_dates = len(all_dates)
        for i, date_str in enumerate(all_dates):
            if i % 100 == 0:
                logger.info(f"Processing date {i + 1}/{total_dates}: {date_str}")

            # 1. Update cash flows up to this date
            while last_cf_idx < len(cash_flows_sorted):
                cf = cash_flows_sorted[last_cf_idx]
                if cf["date"] > date_str:
                    break

                amount_local = cf["amount"]
                curr = cf["currency"]
                type_id = cf["type_id"]

                # Convert to EUR using historical rate on the flow date
                amount_eur = await self._currency.to_eur_for_date(amount_local, curr, cf["date"])

                # Update cash balance
                running_cash_eur += amount_eur

                # Update net deposits (only for card deposits/payouts)
                if type_id in ("card", "card_payout"):
                    cumulative_net_deposits_eur += amount_eur

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

                # Commission
                comm_local = trade.get("commission", 0) or 0
                comm_curr = trade.get("commission_currency", "EUR")
                comm_eur = await self._currency.to_eur_for_date(comm_local, comm_curr, trade_date)

                # Convert trade value to EUR
                trade_value_eur = await self._currency.to_eur_for_date(trade_value_local, sec_curr, trade_date)

                if trade["side"] == "BUY":
                    # Buy: Cash goes down by value + commission
                    running_cash_eur -= trade_value_eur + comm_eur

                    if is_stock_symbol(symbol):
                        positions[symbol] = positions.get(symbol, 0) + qty
                        cost_basis[symbol] = cost_basis.get(symbol, 0) + trade_value_eur
                else:  # SELL
                    # Sell: Cash goes up by value - commission
                    running_cash_eur += trade_value_eur - comm_eur

                    if is_stock_symbol(symbol):
                        prev_qty = positions.get(symbol, 0)
                        if prev_qty > 0:
                            # Reduce cost basis proportionally
                            avg_cost_per_unit = cost_basis.get(symbol, 0) / prev_qty
                            cost_basis[symbol] = cost_basis.get(symbol, 0) - (min(qty, prev_qty) * avg_cost_per_unit)
                        positions[symbol] = max(0, positions.get(symbol, 0) - qty)

                last_trade_idx += 1

            # 3. Calculate positions value using closing prices
            positions_value_eur = 0.0
            for symbol, qty in positions.items():
                if qty <= 0:
                    continue

                # Get price for this date, or most recent before
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
                    positions_value_eur += value_eur

            # 4. Final calculation for this date
            total_value_eur = positions_value_eur + running_cash_eur
            unrealized_pnl_eur = total_value_eur - cumulative_net_deposits_eur

            await self._db.upsert_portfolio_snapshot(
                date=date_str,
                total_value_eur=round(total_value_eur, 2),
                positions_value_eur=round(positions_value_eur, 2),
                cash_eur=round(running_cash_eur, 2),
                net_deposits_eur=round(cumulative_net_deposits_eur, 2),
                unrealized_pnl_eur=round(unrealized_pnl_eur, 2),
            )

        logger.info("Portfolio snapshots backfill complete")
