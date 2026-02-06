"""Rebalance engine for generating trade recommendations."""

from __future__ import annotations

import asyncio
import json
import logging
import math
from dataclasses import asdict
from datetime import datetime, timezone

import httpx

from sentinel.analyzer import Analyzer
from sentinel.broker import Broker
from sentinel.currency import Currency
from sentinel.database import Database
from sentinel.portfolio import Portfolio
from sentinel.price_validator import PriceValidator, check_trade_blocking
from sentinel.settings import Settings
from sentinel.utils.scoring import adjust_score_for_conviction

from .models import TradeRecommendation

logger = logging.getLogger(__name__)


class RebalanceEngine:
    """Generates trade recommendations to move portfolio toward ideal allocations."""

    # Buffer to maintain above zero when calculating deficit (avoid oscillating)
    BALANCE_BUFFER_EUR = 10.0

    def __init__(
        self,
        db: Database | None = None,
        broker: Broker | None = None,
        portfolio: Portfolio | None = None,
        settings: Settings | None = None,
        currency: Currency | None = None,
    ):
        """Initialize engine with optional dependencies.

        Args:
            db: Database instance (uses singleton if None)
            broker: Broker instance (uses singleton if None)
            portfolio: Portfolio instance (uses singleton if None)
            settings: Settings instance (uses singleton if None)
            currency: Currency instance (uses singleton if None)
        """
        self._db = db or Database()
        self._broker = broker or Broker()
        self._portfolio = portfolio or Portfolio()
        self._settings = settings or Settings()
        self._currency = currency or Currency()
        self._analyzer = Analyzer(db=self._db)

    async def get_recommendations(
        self,
        ideal: dict[str, float],
        current: dict[str, float],
        total_value: float,
        min_trade_value: float | None = None,
        as_of_date: str | None = None,
    ) -> list[TradeRecommendation]:
        """Generate trade recommendations to move toward ideal portfolio.

        Args:
            ideal: symbol -> target allocation percentage
            current: symbol -> current allocation percentage
            total_value: total portfolio value in EUR
            min_trade_value: minimum trade value in EUR (uses setting if None)
            as_of_date: optional date (YYYY-MM-DD). When set (e.g. backtest),
                prices and "today" are scoped to this date; cache is skipped.

        Returns:
            List of TradeRecommendation, sorted by priority
        """
        # Get min_trade_value from settings if not provided
        if min_trade_value is None:
            setting_value = await self._settings.get("min_trade_value", default=100.0)
            min_trade_value = float(setting_value) if setting_value is not None else 100.0

        # Skip cache when as_of_date is set (e.g. backtest)
        if as_of_date is None:
            cache_key = f"planner:recommendations:{min_trade_value}"
            cached = await self._db.cache_get(cache_key)
            if cached is not None:
                return [TradeRecommendation(**r) for r in json.loads(cached)]

        if total_value == 0:
            return []

        # Get all expected returns and security data
        expected_returns = {}
        security_data = {}

        all_symbols = list(set(list(ideal.keys()) + list(current.keys())))

        # Fetch all data in parallel for performance
        if as_of_date is not None:
            current_quotes = {}
        else:
            current_quotes = await self._broker.get_quotes(all_symbols)

        # Batch-fetch securities, positions, and scores
        all_securities = await self._db.get_all_securities(active_only=False)
        securities_map = {s["symbol"]: s for s in all_securities}

        all_positions = await self._db.get_all_positions()
        positions_map = {p["symbol"]: p for p in all_positions}

        end_of_day_ts: int | None = None
        # Scores: when as_of_date is set (e.g. backtest), request scores as of that date explicitly.
        if as_of_date is not None:
            end_of_day_ts = int(
                datetime.strptime(as_of_date + " 23:59:59", "%Y-%m-%d %H:%M:%S")
                .replace(tzinfo=timezone.utc)
                .timestamp()
            )
            scores_map = await self._db.get_scores(all_symbols, as_of_date=end_of_day_ts)
        else:
            scores_map = await self._db.get_scores(all_symbols)
        ml_scores_map = await self._get_ml_weighted_scores(all_symbols, as_of_ts=end_of_day_ts)

        # Fetch historical prices: single path via get_prices(end_date=as_of_date).
        # When as_of_date is None we get latest 250; when set we get only data on or before that date.
        price_validator = PriceValidator()

        async def get_historical_ohlcv(symbol):
            raw = await self._db.get_prices(symbol, days=250, end_date=as_of_date)
            if not raw:
                return []
            for price in raw:
                for col in ["open", "high", "low", "close", "volume"]:
                    if col in price and price[col] is not None:
                        try:
                            price[col] = float(price[col])
                        except (ValueError, TypeError):
                            price[col] = 0.0
            return price_validator.validate_price_series_desc(raw)

        hist_prices_list = await asyncio.gather(*[get_historical_ohlcv(s) for s in all_symbols])
        hist_prices_map = {all_symbols[i]: hist_prices_list[i] for i in range(len(all_symbols))}

        # Process each symbol
        for symbol in all_symbols:
            sec = securities_map.get(symbol)
            pos = positions_map.get(symbol)
            user_multiplier = sec.get("user_multiplier", 1.0) if sec else 1.0

            wavelet_score = scores_map.get(symbol, 0)
            hist_rows = hist_prices_map.get(symbol, [])
            base_score = ml_scores_map.get(symbol, wavelet_score)
            expected_returns[symbol] = adjust_score_for_conviction(base_score, user_multiplier or 1.0)

            # Get price
            price = self._get_price(symbol, current_quotes, pos, hist_rows)

            # Check for price anomaly
            trade_blocked, block_reason = self._check_price_anomaly(price, hist_rows, symbol)

            security_data[symbol] = {
                "price": price,
                "currency": sec.get("currency", "EUR") if sec else "EUR",
                "lot_size": sec.get("min_lot", 1) if sec else 1,
                "current_qty": pos.get("quantity", 0) if pos else 0,
                "allow_buy": sec.get("allow_buy", 1) if sec else 1,
                "allow_sell": sec.get("allow_sell", 1) if sec else 1,
                "trade_blocked": trade_blocked,
                "block_reason": block_reason,
            }

        # Generate recommendations
        recommendations = []

        for symbol in all_symbols:
            rec = await self._build_recommendation(
                symbol,
                ideal,
                current,
                total_value,
                security_data,
                expected_returns,
                min_trade_value,
                as_of_date=as_of_date,
            )
            if rec:
                recommendations.append(rec)

        # Sort: SELL first, then by priority
        recommendations.sort(key=lambda x: (0 if x.action == "sell" else 1, -x.priority))

        # Add deficit-fix sells at the front
        deficit_sells = await self._get_deficit_sells(as_of_date=as_of_date)
        if deficit_sells:
            deficit_symbols = {s.symbol for s in deficit_sells}
            recommendations = [r for r in recommendations if r.symbol not in deficit_symbols or r.action != "sell"]
            recommendations = deficit_sells + recommendations

        # Apply cash constraint
        recommendations = await self._apply_cash_constraint(recommendations, min_trade_value)

        # Cache result only when live (not as_of_date)
        if as_of_date is None:
            cache_key = f"planner:recommendations:{min_trade_value}"
            await self._db.cache_set(
                cache_key,
                json.dumps([asdict(r) for r in recommendations]),
                ttl_seconds=300,
            )
        return recommendations

    def _get_price(
        self,
        symbol: str,
        current_quotes: dict,
        pos: dict | None,
        hist_rows: list,
    ) -> float:
        """Get current price from available sources."""
        quote = current_quotes.get(symbol)
        price = quote.get("price", 0) if quote else 0

        if price <= 0 and pos:
            price = pos.get("current_price", 0)

        if price <= 0 and hist_rows:
            price = hist_rows[0]["close"] if hist_rows[0]["close"] else 0

        return price

    def _check_price_anomaly(self, price: float, hist_rows: list, symbol: str) -> tuple[bool, str]:
        """Check if current price indicates an anomaly."""
        if price <= 0:
            return False, ""

        sorted_hist = sorted(hist_rows, key=lambda p: p["date"])
        historical_prices = [r["close"] for r in sorted_hist if r["close"] and r["close"] > 0]

        if historical_prices:
            allow_trade, reason = check_trade_blocking(price, historical_prices, symbol)
            return not allow_trade, reason

        return False, ""

    async def _build_recommendation(
        self,
        symbol: str,
        ideal: dict[str, float],
        current: dict[str, float],
        total_value: float,
        security_data: dict,
        expected_returns: dict[str, float],
        min_trade_value: float,
        as_of_date: str | None = None,
    ) -> TradeRecommendation | None:
        """Build a single trade recommendation for a symbol."""
        current_alloc = current.get(symbol, 0)
        target_alloc = ideal.get(symbol, 0)
        delta = target_alloc - current_alloc

        if abs(delta) < 0.0001:  # No significant change needed
            return None

        raw_value_delta = delta * total_value
        sec_data = security_data.get(symbol)

        if not sec_data:
            return None

        price = sec_data["price"]
        currency = sec_data["currency"]
        lot_size = sec_data["lot_size"]
        current_qty = sec_data["current_qty"]
        allow_buy = sec_data.get("allow_buy", 1)
        allow_sell = sec_data.get("allow_sell", 1)

        if price <= 0:
            return None

        if sec_data.get("trade_blocked"):
            return None

        # Check cool-off period
        cooloff_days = await self._settings.get("trade_cooloff_days", 30)
        is_blocked, _ = await self._check_cooloff_violation(
            symbol,
            "buy" if delta > 0 else "sell",
            cooloff_days,
            as_of_date=as_of_date,
        )
        if is_blocked:
            return None

        if delta > 0 and not allow_buy:
            return None
        if delta < 0 and not allow_sell:
            return None

        # Convert to local currency
        if currency != "EUR":
            rate = await self._currency.get_rate(currency)
            local_value_delta = raw_value_delta / rate if rate > 0 else raw_value_delta
        else:
            local_value_delta = raw_value_delta

        # Calculate quantity
        raw_qty = abs(local_value_delta) / price
        rounded_qty = (int(raw_qty) // lot_size) * lot_size

        if rounded_qty < lot_size:
            return None

        if delta < 0:
            rounded_qty = min(rounded_qty, current_qty)
            if rounded_qty < lot_size:
                return None

        # Recalculate EUR value
        local_value = rounded_qty * price
        if currency != "EUR":
            actual_value_eur = await self._currency.to_eur(local_value, currency)
        else:
            actual_value_eur = local_value

        if actual_value_eur < min_trade_value:
            return None

        expected_return = expected_returns.get(symbol, 0)

        if delta > 0:
            action = "buy"
            reason = self._generate_buy_reason(symbol, expected_return, current_alloc, target_alloc)
        else:
            action = "sell"
            reason = self._generate_sell_reason(symbol, expected_return, current_alloc, target_alloc)

        priority = self._calculate_priority(action, delta, expected_return)

        return TradeRecommendation(
            symbol=symbol,
            action=action,
            current_allocation=current_alloc,
            target_allocation=target_alloc,
            allocation_delta=delta,
            current_value_eur=current_alloc * total_value,
            target_value_eur=target_alloc * total_value,
            value_delta_eur=actual_value_eur if delta > 0 else -actual_value_eur,
            quantity=rounded_qty,
            price=price,
            currency=currency,
            lot_size=lot_size,
            expected_return=expected_return,
            priority=priority,
            reason=reason,
        )

    async def _check_cooloff_violation(
        self,
        symbol: str,
        action: str,
        cooloff_days: int,
        as_of_date: str | None = None,
    ) -> tuple[bool, str]:
        """Check if trade would violate cool-off period.

        Returns:
            Tuple of (is_blocked, reason)
        """
        from datetime import datetime

        if cooloff_days <= 0:
            return False, ""

        # Get last trade for this symbol
        trades = await self._db.get_trades(symbol=symbol, limit=1)

        if not trades:
            return False, ""  # No trade history, allow trade

        last_trade = trades[0]
        last_action = last_trade["side"]  # 'BUY' or 'SELL'
        last_date = datetime.fromtimestamp(last_trade["executed_at"])

        if as_of_date is not None:
            current_date = datetime.strptime(as_of_date, "%Y-%m-%d")
        else:
            current_date = datetime.now()

        days_since = (current_date - last_date).days

        # Check if action is opposite of last trade
        if action == "buy" and last_action == "SELL":
            if days_since < cooloff_days:
                days_remaining = cooloff_days - days_since
                return True, f"Cool-off period: {days_remaining} days remaining after last sell"
        elif action == "sell" and last_action == "BUY":
            if days_since < cooloff_days:
                days_remaining = cooloff_days - days_since
                return True, f"Cool-off period: {days_remaining} days remaining after last buy"

        # Same direction as last trade, or enough time has passed
        return False, ""

    def _calculate_priority(self, action: str, allocation_delta: float, expected_return: float) -> float:
        """Calculate priority score for a recommendation."""
        base = abs(allocation_delta) * 10

        if action == "buy":
            return base + expected_return
        else:
            return base - expected_return

    def _generate_buy_reason(
        self, symbol: str, expected_return: float, current_alloc: float, target_alloc: float
    ) -> str:
        """Generate human-readable reason for buy recommendation."""
        underweight = (target_alloc - current_alloc) * 100

        if current_alloc == 0:
            return f"New position: {symbol} has expected return of {expected_return:.2f}"

        if expected_return > 0.3:
            return f"Underweight by {underweight:.1f}%. High expected return ({expected_return:.2f})"
        elif expected_return > 0:
            return f"Underweight by {underweight:.1f}%. Positive expected return ({expected_return:.2f})"
        else:
            return f"Underweight by {underweight:.1f}% despite neutral outlook"

    def _generate_sell_reason(
        self, symbol: str, expected_return: float, current_alloc: float, target_alloc: float
    ) -> str:
        """Generate human-readable reason for sell recommendation."""
        overweight = (current_alloc - target_alloc) * 100

        if target_alloc == 0:
            if expected_return < 0:
                return f"Exit position: {symbol} has negative expected return ({expected_return:.2f})"
            else:
                return f"Exit position: {symbol} not in ideal portfolio"

        if expected_return < 0:
            return f"Overweight by {overweight:.1f}%. Negative expected return ({expected_return:.2f})"
        else:
            return f"Overweight by {overweight:.1f}%. Reduce to target allocation"

    async def _apply_cash_constraint(
        self,
        recommendations: list[TradeRecommendation],
        min_trade_value: float,
    ) -> list[TradeRecommendation]:
        """Scale down buy recommendations to fit within available cash."""
        fixed_fee = await self._settings.get("transaction_fee_fixed", 2.0)
        pct_fee = await self._settings.get("transaction_fee_percent", 0.2) / 100

        sells = [r for r in recommendations if r.action == "sell"]
        buys = [r for r in recommendations if r.action == "buy"]

        if not buys:
            return recommendations

        # Calculate available budget
        current_cash = await self._portfolio.total_cash_eur()
        net_sell_proceeds = sum(
            abs(r.value_delta_eur) - self._calculate_transaction_cost(abs(r.value_delta_eur), fixed_fee, pct_fee)
            for r in sells
        )
        available_budget = current_cash + net_sell_proceeds

        # Calculate total buy costs
        total_buy_costs = sum(
            r.value_delta_eur + self._calculate_transaction_cost(r.value_delta_eur, fixed_fee, pct_fee) for r in buys
        )

        if total_buy_costs <= available_budget:
            return recommendations

        # Scale down buys
        buys_by_priority = sorted(buys, key=lambda x: -x.priority)
        remaining_budget = available_budget

        buy_minimums = []
        for buy in buys_by_priority:
            one_lot_local = buy.lot_size * buy.price
            if buy.currency != "EUR":
                one_lot_eur = await self._currency.to_eur(one_lot_local, buy.currency)
            else:
                one_lot_eur = one_lot_local

            if one_lot_eur >= min_trade_value:
                min_qty = buy.lot_size
                min_eur = one_lot_eur
            elif one_lot_eur <= 0:
                continue
            else:
                lots_needed = int(min_trade_value / one_lot_eur) + 1
                min_qty = lots_needed * buy.lot_size
                min_eur = lots_needed * one_lot_eur

            if min_qty > buy.quantity:
                min_qty = buy.quantity
                min_local_value = min_qty * buy.price
                if buy.currency != "EUR":
                    min_eur = await self._currency.to_eur(min_local_value, buy.currency)
                else:
                    min_eur = min_local_value

            min_cost_with_tx = min_eur + self._calculate_transaction_cost(min_eur, fixed_fee, pct_fee)
            ideal_cost_with_tx = buy.value_delta_eur + self._calculate_transaction_cost(
                buy.value_delta_eur, fixed_fee, pct_fee
            )
            buy_minimums.append(
                {
                    "buy": buy,
                    "min_qty": min_qty,
                    "min_eur": min_eur,
                    "min_cost": min_cost_with_tx,
                    "ideal_eur": buy.value_delta_eur,
                    "ideal_cost": ideal_cost_with_tx,
                }
            )

        included_buys = []
        for item in buy_minimums:
            if item["min_cost"] <= remaining_budget:
                included_buys.append(item)
                remaining_budget -= item["min_cost"]

        if not included_buys:
            return sells

        # Distribute remaining budget proportionally
        total_extra_needed = sum(max(0, item["ideal_cost"] - item["min_cost"]) for item in included_buys)

        final_buys = []
        for item in included_buys:
            buy = item["buy"]
            min_eur = item["min_eur"]
            ideal_cost = item["ideal_cost"]
            allocated_eur = min_eur

            if total_extra_needed > 0 and remaining_budget > 0:
                extra_needed = max(0, ideal_cost - item["min_cost"])
                proportion = extra_needed / total_extra_needed
                extra_budget = proportion * remaining_budget
                extra_trade_value = extra_budget / (1 + pct_fee)
                allocated_eur += extra_trade_value

            # Convert back to quantity
            if buy.currency != "EUR":
                rate = await self._currency.get_rate(buy.currency)
                local_value = allocated_eur / rate if rate > 0 else allocated_eur
            else:
                local_value = allocated_eur

            raw_qty = local_value / buy.price
            rounded_qty = (int(raw_qty) // buy.lot_size) * buy.lot_size

            if rounded_qty < buy.lot_size:
                continue

            actual_local = rounded_qty * buy.price
            if buy.currency != "EUR":
                actual_eur = await self._currency.to_eur(actual_local, buy.currency)
            else:
                actual_eur = actual_local

            if actual_eur < min_trade_value:
                continue

            final_buys.append(
                TradeRecommendation(
                    symbol=buy.symbol,
                    action="buy",
                    current_allocation=buy.current_allocation,
                    target_allocation=buy.target_allocation,
                    allocation_delta=buy.allocation_delta,
                    current_value_eur=buy.current_value_eur,
                    target_value_eur=buy.target_value_eur,
                    value_delta_eur=actual_eur,
                    quantity=rounded_qty,
                    price=buy.price,
                    currency=buy.currency,
                    lot_size=buy.lot_size,
                    expected_return=buy.expected_return,
                    priority=buy.priority,
                    reason=buy.reason,
                )
            )

        final_buys.sort(key=lambda x: -x.priority)

        # Top-up with leftover budget
        total_buy_cost = sum(
            b.value_delta_eur + self._calculate_transaction_cost(b.value_delta_eur, fixed_fee, pct_fee)
            for b in final_buys
        )
        leftover = available_budget - total_buy_cost

        iterations = 0
        while leftover > 0 and iterations < 1000:
            iterations += 1
            added_any = False
            for i, buy in enumerate(final_buys):
                one_lot_local = buy.lot_size * buy.price
                if buy.currency != "EUR":
                    one_lot_eur = await self._currency.to_eur(one_lot_local, buy.currency)
                else:
                    one_lot_eur = one_lot_local
                one_lot_cost = one_lot_eur + self._calculate_transaction_cost(one_lot_eur, fixed_fee, pct_fee)

                if one_lot_cost <= leftover:
                    new_qty = buy.quantity + buy.lot_size
                    new_local_value = new_qty * buy.price
                    if buy.currency != "EUR":
                        new_eur = await self._currency.to_eur(new_local_value, buy.currency)
                    else:
                        new_eur = new_local_value

                    final_buys[i] = TradeRecommendation(
                        symbol=buy.symbol,
                        action="buy",
                        current_allocation=buy.current_allocation,
                        target_allocation=buy.target_allocation,
                        allocation_delta=buy.allocation_delta,
                        current_value_eur=buy.current_value_eur,
                        target_value_eur=buy.target_value_eur,
                        value_delta_eur=new_eur,
                        quantity=new_qty,
                        price=buy.price,
                        currency=buy.currency,
                        lot_size=buy.lot_size,
                        expected_return=buy.expected_return,
                        priority=buy.priority,
                        reason=buy.reason,
                    )
                    leftover -= one_lot_cost
                    added_any = True

            if not added_any:
                break

        return sells + final_buys

    def _calculate_transaction_cost(self, value: float, fixed_fee: float, pct_fee: float) -> float:
        """Calculate transaction cost for a trade."""
        return fixed_fee + (value * pct_fee)

    async def _get_deficit_sells(self, as_of_date: str | None = None) -> list[TradeRecommendation]:
        """Generate sell recommendations if negative balances can't be covered."""
        balances = await self._portfolio.get_cash_balances()

        total_deficit_eur = 0.0
        for currency, amount in balances.items():
            if amount < 0:
                if currency == "EUR":
                    total_deficit_eur += abs(amount) + self.BALANCE_BUFFER_EUR
                else:
                    total_deficit_eur += await self._currency.to_eur(abs(amount), currency) + self.BALANCE_BUFFER_EUR

        if total_deficit_eur == 0:
            return []

        total_positive_eur = 0.0
        for currency, amount in balances.items():
            if amount > 0:
                total_positive_eur += await self._currency.to_eur(amount, currency)

        uncovered_deficit = total_deficit_eur - total_positive_eur
        if uncovered_deficit <= 0:
            return []

        return await self._generate_deficit_sells(uncovered_deficit, as_of_date=as_of_date)

    async def _generate_deficit_sells(
        self,
        deficit_eur: float,
        as_of_date: str | None = None,
    ) -> list[TradeRecommendation]:
        """Generate sell recommendations to cover remaining deficit."""
        sells: list[TradeRecommendation] = []
        remaining_deficit = deficit_eur

        positions = await self._db.get_all_positions()
        if not positions:
            return sells

        all_securities = await self._db.get_all_securities(active_only=False)
        securities_map = {s["symbol"]: s for s in all_securities}

        all_symbols = [pos["symbol"] for pos in positions]
        end_of_day_ts: int | None = None
        if as_of_date is not None:
            end_of_day_ts = int(
                datetime.strptime(as_of_date + " 23:59:59", "%Y-%m-%d %H:%M:%S")
                .replace(tzinfo=timezone.utc)
                .timestamp()
            )
            scores_map = await self._db.get_scores(all_symbols, as_of_date=end_of_day_ts)
        else:
            scores_map = await self._db.get_scores(all_symbols)
        ml_scores_map = await self._get_ml_weighted_scores(all_symbols, as_of_ts=end_of_day_ts)

        position_data = []
        for pos in positions:
            symbol = pos["symbol"]
            qty = pos.get("quantity", 0)
            if qty <= 0:
                continue

            price = pos.get("current_price", 0)
            if as_of_date is not None:
                hist = await self._db.get_prices(symbol, days=1, end_date=as_of_date)
                if hist:
                    close = hist[0].get("close")
                    if close is not None:
                        try:
                            price = float(close)
                        except (TypeError, ValueError):
                            price = 0

            if price <= 0:
                continue

            sec = securities_map.get(symbol)
            if not sec:
                continue

            if not sec.get("allow_sell", 1):
                continue

            currency = sec.get("currency", "EUR")
            lot_size = sec.get("min_lot", 1)
            score = ml_scores_map.get(symbol, scores_map.get(symbol, 0))

            local_value = qty * price
            eur_value = await self._currency.to_eur(local_value, currency)

            position_data.append(
                {
                    "symbol": symbol,
                    "quantity": qty,
                    "price": price,
                    "currency": currency,
                    "lot_size": lot_size,
                    "score": score,
                    "eur_value": eur_value,
                }
            )

        position_data.sort(key=lambda x: (x["score"], x["eur_value"]))
        total_value = await self._portfolio.total_value()

        for pos in position_data:
            if remaining_deficit <= 0:
                break

            symbol = pos["symbol"]
            qty = pos["quantity"]
            price = pos["price"]
            currency = pos["currency"]
            lot_size = pos["lot_size"]
            eur_value = pos["eur_value"]
            score = pos["score"]

            if eur_value <= remaining_deficit:
                sell_qty = (qty // lot_size) * lot_size
            else:
                rate = await self._currency.get_rate(currency)
                if rate > 0:
                    local_needed = remaining_deficit / rate
                else:
                    local_needed = remaining_deficit
                shares_needed = local_needed / price
                sell_qty = math.ceil(shares_needed / lot_size) * lot_size
                sell_qty = min(sell_qty, qty)

            if sell_qty < lot_size:
                continue

            current_alloc = eur_value / total_value if total_value > 0 else 0
            sell_value_local = sell_qty * price
            sell_value_eur = await self._currency.to_eur(sell_value_local, currency)

            sells.append(
                TradeRecommendation(
                    symbol=symbol,
                    action="sell",
                    current_allocation=current_alloc,
                    target_allocation=0,
                    allocation_delta=-current_alloc,
                    current_value_eur=eur_value,
                    target_value_eur=eur_value - sell_value_eur,
                    value_delta_eur=-sell_value_eur,
                    quantity=sell_qty,
                    price=price,
                    currency=currency,
                    lot_size=lot_size,
                    expected_return=score,
                    priority=1000,
                    reason=f"Sell to cover negative balance deficit ({remaining_deficit:.0f} EUR remaining)",
                )
            )

            remaining_deficit -= sell_value_eur

        return sells

    async def _get_ml_weighted_scores(self, symbols: list[str], as_of_ts: int | None = None) -> dict[str, float]:
        """Fetch blended ML scores from sentinel-ml for planner prioritization.

        Falls back to empty map on connectivity issues so planner still works with
        wavelet-only scoring.
        """
        if not symbols:
            return {}

        try:
            base_url_setting = self._settings.get("ml_service_base_url", "http://localhost:8001")
            if asyncio.iscoroutine(base_url_setting):
                base_url_setting = await base_url_setting
            base_url = str(base_url_setting or "http://localhost:8001").rstrip("/")

            params: dict[str, str | int] = {"symbols": ",".join(symbols)}
            if as_of_ts is not None:
                params["as_of_ts"] = as_of_ts

            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(f"{base_url}/ml/latest-scores", params=params)
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Planner ML score fetch failed: %s", exc)
            return {}

        scores = payload.get("scores", {})
        if not isinstance(scores, dict):
            return {}

        result: dict[str, float] = {}
        for symbol, score_payload in scores.items():
            if not isinstance(score_payload, dict):
                continue
            value = score_payload.get("final_score", score_payload.get("ml_score"))
            if isinstance(value, int | float):
                result[symbol] = float(value)
        return result
