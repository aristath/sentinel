"""Rebalance engine for generating trade recommendations."""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
from dataclasses import asdict
from datetime import datetime, timezone

from sentinel.broker import Broker
from sentinel.currency import Currency
from sentinel.database import Database
from sentinel.portfolio import Portfolio
from sentinel.price_validator import PriceValidator, check_trade_blocking
from sentinel.settings import Settings
from sentinel.strategy import (
    classify_lot_size,
    compute_contrarian_signal,
    effective_opportunity_score,
    recent_dd252_min,
)
from sentinel.utils.scoring import adjust_score_for_conviction

from .models import TradeRecommendation
from .rebalance_cash import apply_cash_constraint, generate_deficit_sells, get_deficit_sells
from .rebalance_rules import (
    calculate_priority,
    desired_tranche_stage,
    generate_buy_reason,
    generate_sell_reason,
    get_forced_opportunity_exit,
)

logger = logging.getLogger(__name__)


class RebalanceEngine:
    """Generates trade recommendations to move portfolio toward ideal allocations."""

    # Buffer to maintain above zero when calculating deficit (avoid oscillating)
    BALANCE_BUFFER_EUR = 10.0

    @staticmethod
    def _recommendation_cache_key(min_trade_value: float) -> str:
        """Build stable cache key for recommendation payloads."""
        return f"planner:recommendations:{float(min_trade_value):.2f}"

    @staticmethod
    def _normalize_conviction(value: object) -> float:
        """Normalize conviction into [0.0, 1.0]."""
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return 0.5
        return max(0.0, min(1.0, parsed))

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

    async def _load_runtime_settings(self) -> dict[str, float]:
        defaults: dict[str, float] = {
            "transaction_fee_fixed": 2.0,
            "transaction_fee_percent": 0.2,
            "strategy_lot_standard_max_pct": 0.08,
            "strategy_lot_coarse_max_pct": 0.30,
            "strategy_min_opp_score": 0.55,
            "strategy_entry_t1_dd": -0.10,
            "strategy_entry_t2_dd": -0.16,
            "strategy_entry_t3_dd": -0.22,
            "strategy_entry_memory_days": 42,
            "strategy_memory_max_boost": 0.18,
            "max_position_pct": 25,
            "strategy_opportunity_addon_threshold": 0.75,
            "strategy_rotation_time_stop_days": 90,
            "strategy_opportunity_cooloff_days": 7,
            "strategy_core_cooloff_days": 21,
            "strategy_same_side_cooloff_days": 15,
            "strategy_core_new_min_score": 0.30,
            "strategy_core_new_min_dip_score": 0.20,
            "strategy_coarse_max_new_lots_per_cycle": 1,
            "strategy_core_floor_pct": 0.05,
            "strategy_max_opportunity_buys_per_cycle": 4,
            "strategy_max_new_opportunity_buys_per_cycle": 2,
        }
        keys = list(defaults.keys())
        values = await asyncio.gather(*[self._settings.get(k, defaults[k]) for k in keys])
        return {k: float(v if v is not None else defaults[k]) for k, v in zip(keys, values, strict=False)}

    async def get_recommendations(
        self,
        ideal: dict[str, float],
        current: dict[str, float],
        total_value: float,
        min_trade_value: float | None = None,
        as_of_date: str | None = None,
        precomputed_rebalance_signals: dict[str, dict[str, float | int | str]] | None = None,
        precomputed_sleeves: dict[str, str] | None = None,
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
            cache_key = self._recommendation_cache_key(min_trade_value)
            cache_getter = getattr(self._db, "cache_get", None)
            if callable(cache_getter):
                maybe_cached = cache_getter(cache_key)
                if inspect.isawaitable(maybe_cached):
                    cached = await maybe_cached
                    if cached is not None:
                        return [TradeRecommendation(**r) for r in json.loads(cached)]

        if total_value == 0:
            return []
        settings_ctx = await self._load_runtime_settings()

        # Build per-symbol signal scores and market context for recommendation rules.
        contrarian_scores = {}
        security_data = {}

        all_symbols = list(set(list(ideal.keys()) + list(current.keys())))

        # Fetch all data in parallel for performance
        if as_of_date is not None:
            current_quotes = {}
        else:
            current_quotes = await self._broker.get_quotes(all_symbols)

        # Batch-fetch securities and positions
        all_securities = await self._db.get_all_securities(active_only=False)
        securities_map = {s["symbol"]: s for s in all_securities}

        all_positions = await self._get_positions_for_context(as_of_date=as_of_date, securities_map=securities_map)
        positions_map = {p["symbol"]: p for p in all_positions}

        fee_fixed = settings_ctx["transaction_fee_fixed"]
        fee_pct = settings_ctx["transaction_fee_percent"] / 100.0
        lot_standard_max_pct = settings_ctx["strategy_lot_standard_max_pct"]
        lot_coarse_max_pct = settings_ctx["strategy_lot_coarse_max_pct"]
        min_opp_score = settings_ctx["strategy_min_opp_score"]
        entry_t1_dd = settings_ctx["strategy_entry_t1_dd"]
        entry_t3_dd = settings_ctx["strategy_entry_t3_dd"]
        entry_memory_days = int(settings_ctx["strategy_entry_memory_days"])
        memory_max_boost = settings_ctx["strategy_memory_max_boost"]

        # Fetch historical prices: single path via get_prices(end_date=as_of_date).
        # When as_of_date is None we get latest 250; when set we get only data on or before that date.
        # As-of/backtest mode uses trusted DB snapshots, so skip expensive validator passes.
        use_price_validation = as_of_date is None
        price_validator = PriceValidator()

        get_prices_multi = getattr(self._db, "get_prices_for_symbols", None)
        raw_hist_map: dict[str, list[dict]] | None = None
        if callable(get_prices_multi):
            maybe_hist = get_prices_multi(all_symbols, days=250, end_date=as_of_date)
            if inspect.isawaitable(maybe_hist):
                resolved = await maybe_hist
                if isinstance(resolved, dict):
                    raw_hist_map = resolved
            elif isinstance(maybe_hist, dict):
                raw_hist_map = maybe_hist
        if raw_hist_map is None:

            async def get_historical_rows(symbol: str) -> list[dict]:
                return await self._db.get_prices(symbol, days=250, end_date=as_of_date)

            hist_prices_list = await asyncio.gather(*[get_historical_rows(s) for s in all_symbols])
            raw_hist_map = {all_symbols[i]: hist_prices_list[i] for i in range(len(all_symbols))}

        hist_prices_map: dict[str, list[dict]] = {}
        for symbol in all_symbols:
            raw = raw_hist_map.get(symbol, [])
            if not raw:
                hist_prices_map[symbol] = []
                continue
            for price in raw:
                if price.get("close") is not None:
                    try:
                        price["close"] = float(price["close"])
                    except (ValueError, TypeError):
                        price["close"] = 0.0
            if use_price_validation:
                hist_prices_map[symbol] = price_validator.validate_price_series_desc(raw)
            else:
                hist_prices_map[symbol] = raw

        symbol_signals: dict[str, dict[str, float | int | str]] = {}
        sleeves_map = dict(precomputed_sleeves or {})
        rebalance_signals_map: dict[str, dict[str, float | int | str]] = dict(precomputed_rebalance_signals or {})
        cache_getter = getattr(self._db, "cache_get", None)
        if callable(cache_getter) and as_of_date is None:
            maybe_sleeves = cache_getter("planner:contrarian_sleeves")
            if inspect.isawaitable(maybe_sleeves):
                sleeves_cache = await maybe_sleeves
                if not sleeves_map:
                    sleeves_map = json.loads(sleeves_cache) if sleeves_cache else {}
            maybe_rebalance_signals = cache_getter("planner:rebalance_signals")
            if inspect.isawaitable(maybe_rebalance_signals):
                rebalance_signals_cache = await maybe_rebalance_signals
                if not rebalance_signals_map:
                    rebalance_signals_map = json.loads(rebalance_signals_cache) if rebalance_signals_cache else {}
        strategy_states_getter = getattr(self._db, "get_strategy_states", None)
        strategy_states = {}
        if callable(strategy_states_getter):
            maybe_states = strategy_states_getter(all_symbols)
            if inspect.isawaitable(maybe_states):
                strategy_states = await maybe_states
        latest_trades_map: dict[str, dict] = {}
        latest_trades_getter = getattr(self._db, "get_latest_trades_for_symbols", None)
        if callable(latest_trades_getter):
            maybe_latest = latest_trades_getter(all_symbols)
            if inspect.isawaitable(maybe_latest):
                resolved_latest = await maybe_latest
                if isinstance(resolved_latest, dict):
                    latest_trades_map = resolved_latest
            elif isinstance(maybe_latest, dict):
                latest_trades_map = maybe_latest

        currencies = {(securities_map.get(symbol) or {}).get("currency", "EUR") for symbol in all_symbols}
        fx_values = await asyncio.gather(*[self._currency.get_rate(currency) for currency in currencies])
        fx_rates = {currency: rate for currency, rate in zip(currencies, fx_values, strict=False)}
        # Process each symbol
        for symbol in all_symbols:
            sec = securities_map.get(symbol)
            pos = positions_map.get(symbol)
            conviction = self._normalize_conviction(sec.get("user_multiplier", 0.5) if sec else 0.5)

            hist_rows = hist_prices_map.get(symbol, [])
            closes = [float(r["close"]) for r in reversed(hist_rows) if r.get("close") is not None]
            cached_signal = rebalance_signals_map.get(symbol)
            if isinstance(cached_signal, dict):
                signal = dict(cached_signal)
                raw_score = float(signal.get("opp_score_raw", signal.get("opp_score", 0.0)) or 0.0)
                effective_score = float(signal.get("opp_score", 0.0) or 0.0)
                if "dd252_recent_min" not in signal:
                    signal["dd252_recent_min"] = recent_dd252_min(closes, window_days=entry_memory_days)
                signal["memory_boosted"] = int(signal.get("memory_boosted", 0) or 0)
            else:
                signal = dict(compute_contrarian_signal(closes))
                signal["dd252_recent_min"] = recent_dd252_min(closes, window_days=entry_memory_days)
                raw_score = float(signal.get("opp_score", 0.0) or 0.0)
                effective_score = effective_opportunity_score(
                    raw_opp_score=raw_score,
                    cycle_turn=int(signal.get("cycle_turn", 0) or 0),
                    freefall_block=int(signal.get("freefall_block", 0) or 0),
                    recent_dd252_min_value=float(signal.get("dd252_recent_min", 0.0) or 0.0),
                    entry_t1_dd=entry_t1_dd,
                    entry_t3_dd=entry_t3_dd,
                    max_boost=memory_max_boost,
                )
                signal["opp_score_raw"] = raw_score
                signal["opp_score"] = effective_score
                signal["memory_boosted"] = 1 if effective_score > raw_score else 0
            contrarian_scores[symbol] = adjust_score_for_conviction(effective_score, conviction)

            # Get price
            price = self._get_price(symbol, current_quotes, pos, hist_rows)

            # Check for price anomaly using already prepared close series.
            trade_blocked, block_reason = self._check_price_anomaly_closes(price, closes, symbol)

            symbol_currency = sec.get("currency", "EUR") if sec else "EUR"
            fx_rate = fx_rates.get(symbol_currency, 1.0)
            lot_profile = classify_lot_size(
                price=price,
                lot_size=sec.get("min_lot", 1) if sec else 1,
                fx_rate_to_eur=fx_rate,
                portfolio_value_eur=total_value,
                fee_fixed_eur=fee_fixed,
                fee_pct=fee_pct,
                standard_max_pct=lot_standard_max_pct,
                coarse_max_pct=lot_coarse_max_pct,
            )
            signal["ticket_pct"] = float(lot_profile["ticket_pct"])
            signal["lot_class"] = str(lot_profile["lot_class"])
            signal["lot_size"] = int(sec.get("min_lot", 1) if sec else 1)
            cached_sleeve = sleeves_map.get(symbol)
            if cached_sleeve is None:
                cached_sleeve = "opportunity" if effective_score >= min_opp_score else "core"
            signal["sleeve"] = str(cached_sleeve)
            signal["state_tranche_stage"] = int((strategy_states.get(symbol) or {}).get("tranche_stage", 0) or 0)
            signal["state_scaleout_stage"] = int((strategy_states.get(symbol) or {}).get("scaleout_stage", 0) or 0)
            symbol_signals[symbol] = signal

            security_data[symbol] = {
                "price": price,
                "currency": sec.get("currency", "EUR") if sec else "EUR",
                "fx_rate": fx_rate,
                "lot_size": sec.get("min_lot", 1) if sec else 1,
                "current_qty": pos.get("quantity", 0) if pos else 0,
                "avg_cost": pos.get("avg_cost", 0) if pos else 0,
                "allow_buy": sec.get("allow_buy", 1) if sec else 1,
                "allow_sell": sec.get("allow_sell", 1) if sec else 1,
                "trade_blocked": trade_blocked,
                "block_reason": block_reason,
                "lot_class": lot_profile["lot_class"],
                "ticket_pct": lot_profile["ticket_pct"],
                "min_ticket_eur": lot_profile["min_ticket_eur"],
                "state": strategy_states.get(symbol) or {},
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
                contrarian_scores,
                symbol_signals,
                min_trade_value,
                settings_ctx=settings_ctx,
                latest_trade=latest_trades_map.get(symbol),
                as_of_date=as_of_date,
            )
            if rec:
                recommendations.append(rec)

        # Sort: SELL first, then by priority
        recommendations.sort(key=lambda x: (0 if x.action == "sell" else 1, -x.priority))

        # Add deficit-fix sells at the front
        deficit_sells = await self._get_deficit_sells(
            as_of_date=as_of_date,
            ideal=ideal,
            current=current,
            total_value=total_value,
        )
        if deficit_sells:
            deficit_symbols = {s.symbol for s in deficit_sells}
            recommendations = [r for r in recommendations if r.symbol not in deficit_symbols or r.action != "sell"]
            recommendations = deficit_sells + recommendations

        # Throttle aggressive opportunity buy count per cycle.
        recommendations = await self._apply_opportunity_buy_throttle(
            recommendations,
            max_opp_buys=int(settings_ctx["strategy_max_opportunity_buys_per_cycle"]),
            max_new_opp_buys=int(settings_ctx["strategy_max_new_opportunity_buys_per_cycle"]),
        )

        # Apply cash constraint (including optional funding sells)
        recommendations = await self._apply_cash_constraint(
            recommendations,
            min_trade_value,
            as_of_date=as_of_date,
            ideal=ideal,
            current=current,
            total_value=total_value,
            symbol_convictions={
                symbol: self._normalize_conviction(sec.get("user_multiplier", 0.5))
                for symbol, sec in securities_map.items()
            },
            preloaded_positions=all_positions,
            preloaded_securities_map=securities_map,
            preloaded_symbol_scores={
                symbol: float(signal.get("opp_score_raw", signal.get("opp_score", 0.0)) or 0.0)
                for symbol, signal in symbol_signals.items()
            },
            preloaded_symbol_prices={
                symbol: float(sec.get("price", 0.0) or 0.0) for symbol, sec in security_data.items()
            },
        )

        # Cache result only when live (not as_of_date)
        if as_of_date is None:
            cache_key = self._recommendation_cache_key(min_trade_value)
            cache_setter = getattr(self._db, "cache_set", None)
            if callable(cache_setter):
                maybe_set = cache_setter(
                    cache_key,
                    json.dumps([asdict(r) for r in recommendations]),
                    ttl_seconds=300,
                )
                if inspect.isawaitable(maybe_set):
                    await maybe_set
        return recommendations

    async def _apply_opportunity_buy_throttle(
        self,
        recommendations: list[TradeRecommendation],
        max_opp_buys: int | None = None,
        max_new_opp_buys: int | None = None,
    ) -> list[TradeRecommendation]:
        """Limit opportunity buys per cycle to reduce churn and concentrated risk."""
        if max_opp_buys is None:
            max_opp_buys = int(await self._settings.get("strategy_max_opportunity_buys_per_cycle", 4))
        if max_new_opp_buys is None:
            max_new_opp_buys = int(await self._settings.get("strategy_max_new_opportunity_buys_per_cycle", 2))
        if max_opp_buys < 0:
            max_opp_buys = 0
        if max_new_opp_buys < 0:
            max_new_opp_buys = 0

        sells = [r for r in recommendations if r.action == "sell"]
        non_opp_buys = [r for r in recommendations if r.action == "buy" and r.sleeve != "opportunity"]
        opp_buys = [r for r in recommendations if r.action == "buy" and r.sleeve == "opportunity"]
        if not opp_buys:
            return recommendations

        def rank_key(rec: TradeRecommendation) -> tuple[float, float, float]:
            return (float(rec.priority), float(rec.contrarian_score), float(rec.value_delta_eur))

        new_opp = [r for r in opp_buys if float(r.current_allocation) <= 1e-6]
        add_opp = [r for r in opp_buys if float(r.current_allocation) > 1e-6]
        new_opp.sort(key=rank_key, reverse=True)
        add_opp.sort(key=rank_key, reverse=True)

        kept_new = new_opp[:max_new_opp_buys]
        remaining = max(0, max_opp_buys - len(kept_new))
        kept_add = add_opp[:remaining]

        buys = non_opp_buys + kept_new + kept_add
        buys.sort(key=lambda r: float(r.priority), reverse=True)
        return sells + buys

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

    def _check_price_anomaly_closes(
        self, price: float, closes_oldest_first: list[float], symbol: str
    ) -> tuple[bool, str]:
        """Check if current price indicates an anomaly using precomputed closes."""
        if price <= 0:
            return False, ""
        if closes_oldest_first:
            allow_trade, reason = check_trade_blocking(price, closes_oldest_first, symbol)
            return not allow_trade, reason
        return False, ""

    async def _build_recommendation(
        self,
        symbol: str,
        ideal: dict[str, float],
        current: dict[str, float],
        total_value: float,
        security_data: dict,
        contrarian_scores: dict[str, float],
        signal_data: dict[str, dict[str, float | int | str]],
        min_trade_value: float,
        settings_ctx: dict[str, float],
        latest_trade: dict | None = None,
        as_of_date: str | None = None,
    ) -> TradeRecommendation | None:
        """Build a single trade recommendation for a symbol."""
        current_alloc = current.get(symbol, 0)
        target_alloc = ideal.get(symbol, 0)
        delta = target_alloc - current_alloc

        raw_value_delta = delta * total_value
        sec_data = security_data.get(symbol)

        if not sec_data:
            return None

        price = sec_data["price"]
        currency = sec_data["currency"]
        fx_rate = float(sec_data.get("fx_rate", 1.0) or 1.0)
        lot_size = sec_data["lot_size"]
        current_qty = sec_data["current_qty"]
        avg_cost = sec_data.get("avg_cost", 0)
        allow_buy = sec_data.get("allow_buy", 1)
        allow_sell = sec_data.get("allow_sell", 1)
        lot_class = sec_data.get("lot_class", "standard")
        ticket_pct = float(sec_data.get("ticket_pct", 0.0) or 0.0)
        signal = signal_data.get(symbol, {})
        sleeve = str(signal.get("sleeve", "core"))
        state = sec_data.get("state", {}) or {}
        opp_score = float(signal.get("opp_score", 0.0) or 0.0)
        raw_opp_score = float(signal.get("opp_score_raw", opp_score) or 0.0)
        memory_boosted = bool(int(signal.get("memory_boosted", 0) or 0) == 1)
        min_opp_score = settings_ctx["strategy_min_opp_score"]
        max_position_pct = settings_ctx["max_position_pct"] / 100.0
        addon_threshold = settings_ctx["strategy_opportunity_addon_threshold"]
        entry_t1_dd = settings_ctx["strategy_entry_t1_dd"]
        entry_t2_dd = settings_ctx["strategy_entry_t2_dd"]
        entry_t3_dd = settings_ctx["strategy_entry_t3_dd"]

        if price <= 0:
            return None

        if sec_data.get("trade_blocked"):
            return None

        # Opportunity sleeve forced exits/rotation can trigger sells even without allocation drift.
        forced_exit = get_forced_opportunity_exit(
            signal=signal,
            state=state,
            current_qty=current_qty,
            price=price,
            avg_cost=avg_cost,
            as_of_date=as_of_date,
            time_stop_days=int(settings_ctx["strategy_rotation_time_stop_days"]),
        )
        forced_sell_qty = 0
        forced_reason = ""
        forced_reason_code = None
        if forced_exit and sleeve == "opportunity":
            forced_sell_qty = forced_exit["quantity"]
            forced_reason = forced_exit["reason"]
            forced_reason_code = forced_exit["reason_code"]

        if abs(delta) < 0.0001 and forced_sell_qty <= 0:  # No significant change needed
            return None

        # Check cool-off period
        if sleeve == "opportunity":
            cooloff_days = int(settings_ctx["strategy_opportunity_cooloff_days"])
        else:
            cooloff_days = int(settings_ctx["strategy_core_cooloff_days"])
        same_side_cooloff_days = int(settings_ctx["strategy_same_side_cooloff_days"])
        action_for_cooloff = "sell" if forced_sell_qty > 0 else ("buy" if delta > 0 else "sell")
        is_blocked, _ = await self._check_cooloff_violation(
            symbol,
            action_for_cooloff,
            cooloff_days,
            same_side_cooloff_days=same_side_cooloff_days,
            latest_trade=latest_trade,
            as_of_date=as_of_date,
        )
        if is_blocked:
            return None

        if delta > 0 and forced_sell_qty <= 0 and not allow_buy:
            return None
        if (delta < 0 or forced_sell_qty > 0) and not allow_sell:
            return None

        # Convert to local currency
        if currency != "EUR":
            local_value_delta = raw_value_delta / fx_rate if fx_rate > 0 else raw_value_delta
        else:
            local_value_delta = raw_value_delta

        # Calculate quantity
        if forced_sell_qty > 0:
            rounded_qty = forced_sell_qty
        else:
            raw_qty = abs(local_value_delta) / price
            rounded_qty = (int(raw_qty) // lot_size) * lot_size

        if rounded_qty < lot_size:
            return None

        if delta < 0 or forced_sell_qty > 0:
            rounded_qty = min(rounded_qty, current_qty)
            if rounded_qty < lot_size:
                return None

        if delta > 0 and forced_sell_qty <= 0:
            # For new core names, require minimum contrarian quality to avoid pure drift-driven churn.
            if sleeve == "core" and current_alloc <= 1e-6 and lot_class == "standard":
                core_new_min_score = settings_ctx["strategy_core_new_min_score"]
                core_new_min_dip = settings_ctx["strategy_core_new_min_dip_score"]
                dip_score = float(signal.get("dip_score", 0.0) or 0.0)
                cycle_turn = int(signal.get("cycle_turn", 0) or 0)
                if opp_score < core_new_min_score:
                    return None
                if dip_score < core_new_min_dip and cycle_turn == 0:
                    return None

            # Tranche entry control for opportunity sleeve.
            desired_stage = 0
            if sleeve == "opportunity":
                desired_stage = desired_tranche_stage(
                    float(signal.get("dd252", 0.0) or 0.0),
                    entry_t1_dd,
                    entry_t2_dd,
                    entry_t3_dd,
                )
                recent_stage = desired_tranche_stage(
                    float(signal.get("dd252_recent_min", signal.get("dd252", 0.0)) or 0.0),
                    entry_t1_dd,
                    entry_t2_dd,
                    entry_t3_dd,
                )
                # Event memory: allow entry after rebound if a qualifying dip happened recently.
                if desired_stage <= 0 and int(signal.get("cycle_turn", 0) or 0) == 1 and recent_stage > 0:
                    desired_stage = max(1, recent_stage - 1)
                current_stage = int(state.get("tranche_stage", 0) or 0)
                if desired_stage <= 0:
                    return None
                if desired_stage <= current_stage and current_qty > 0:
                    # Allow additional accumulation on very strong opportunities if under hard cap.
                    if not (opp_score >= addon_threshold and current_alloc < max_position_pct):
                        return None
            if lot_class == "jumbo" and current_qty <= 0:
                return None
            if lot_class == "coarse":
                # Allow stacking for very strong opportunities.
                if opp_score < 0.8:
                    max_new_lots = int(settings_ctx["strategy_coarse_max_new_lots_per_cycle"])
                    rounded_qty = min(rounded_qty, max_new_lots * lot_size)
                    if rounded_qty < lot_size:
                        return None

        core_floor_active = False
        if delta < 0 or forced_sell_qty > 0:
            # Protect core holdings from over-trimming.
            floor_pct = settings_ctx["strategy_core_floor_pct"]
            if sleeve == "core":
                current_value = current_alloc * total_value
                max_sell_value_eur = max(0.0, current_value - (floor_pct * total_value))
                core_floor_active = current_value <= (floor_pct * total_value)
                if max_sell_value_eur <= 0:
                    return None
                if currency != "EUR":
                    max_sell_local = max_sell_value_eur / fx_rate if fx_rate > 0 else max_sell_value_eur
                else:
                    max_sell_local = max_sell_value_eur
                max_sell_qty = (int(max_sell_local / price) // lot_size) * lot_size
                # Keep at least one lot for held core positions.
                if current_qty >= lot_size:
                    max_sell_qty = min(max_sell_qty, max(0, current_qty - lot_size))
                rounded_qty = min(rounded_qty, max_sell_qty)
                if rounded_qty < lot_size:
                    return None

        # Recalculate EUR value
        local_value = rounded_qty * price
        if currency != "EUR":
            if fx_rate > 0:
                actual_value_eur = local_value * fx_rate
            else:
                actual_value_eur = await self._currency.to_eur(local_value, currency)
        else:
            actual_value_eur = local_value

        # Enforce hard per-symbol cap for buys.
        if delta > 0 and forced_sell_qty <= 0:
            current_value_eur = current_alloc * total_value
            max_target_value_eur = max_position_pct * total_value
            max_buy_eur = max(0.0, max_target_value_eur - current_value_eur)
            if max_buy_eur <= 0:
                return None
            if actual_value_eur > max_buy_eur:
                if currency != "EUR":
                    max_buy_local = max_buy_eur / fx_rate if fx_rate > 0 else max_buy_eur
                else:
                    max_buy_local = max_buy_eur
                capped_qty = (int(max_buy_local / price) // lot_size) * lot_size
                if capped_qty < lot_size:
                    return None
                rounded_qty = capped_qty
                local_value = rounded_qty * price
                if currency != "EUR":
                    actual_value_eur = (
                        local_value * fx_rate if fx_rate > 0 else await self._currency.to_eur(local_value, currency)
                    )
                else:
                    actual_value_eur = local_value

        if actual_value_eur < min_trade_value:
            return None

        contrarian_score = contrarian_scores.get(symbol, 0)
        reason_code = None
        memory_entry = False

        if forced_sell_qty > 0:
            action = "sell"
            reason = forced_reason
            reason_code = forced_reason_code
        elif delta > 0:
            action = "buy"
            reason_code = "rebalance_buy"
            if sleeve == "opportunity":
                reason_stage = desired_stage if desired_stage > 0 else 1
                reason_code = f"entry_t{reason_stage}"
                memory_entry = memory_boosted and raw_opp_score < min_opp_score <= opp_score
            reason = generate_buy_reason(
                symbol=symbol,
                contrarian_score=contrarian_score,
                current_alloc=current_alloc,
                target_alloc=target_alloc,
                signal=signal,
                lot_class=lot_class,
            )
        else:
            action = "sell"
            reason_code = "rebalance_sell"
            reason = generate_sell_reason(
                symbol=symbol,
                contrarian_score=contrarian_score,
                current_alloc=current_alloc,
                target_alloc=target_alloc,
                signal=signal,
            )

        priority = calculate_priority(
            action=action,
            allocation_delta=delta,
            contrarian_score=contrarian_score,
        )

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
            contrarian_score=contrarian_score,
            priority=priority,
            reason=reason,
            reason_code=reason_code,
            sleeve=sleeve,
            lot_class=lot_class,
            ticket_pct=ticket_pct,
            core_floor_active=core_floor_active,
            memory_entry=memory_entry,
        )

    async def _check_cooloff_violation(
        self,
        symbol: str,
        action: str,
        cooloff_days: int,
        same_side_cooloff_days: int = 0,
        latest_trade: dict | None = None,
        as_of_date: str | None = None,
    ) -> tuple[bool, str]:
        """Check if trade would violate cool-off period.

        Returns:
            Tuple of (is_blocked, reason)
        """

        if cooloff_days <= 0 and same_side_cooloff_days <= 0:
            return False, ""

        last_trade = latest_trade
        if not last_trade:
            # Fallback: fetch latest trade if caller did not preload it.
            trades_fn = getattr(self._db, "get_trades", None)
            if not callable(trades_fn):
                return False, ""
            maybe_trades = trades_fn(symbol=symbol, limit=1)
            if not inspect.isawaitable(maybe_trades):
                return False, ""
            trades = await maybe_trades
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

        # Check opposite-side cool-off
        if action == "buy" and last_action == "SELL" and cooloff_days > 0:
            if days_since < cooloff_days:
                days_remaining = cooloff_days - days_since
                return True, f"Cool-off period: {days_remaining} days remaining after last sell"
        elif action == "sell" and last_action == "BUY" and cooloff_days > 0:
            if days_since < cooloff_days:
                days_remaining = cooloff_days - days_since
                return True, f"Cool-off period: {days_remaining} days remaining after last buy"

        # Check same-side cool-off
        if action == "buy" and last_action == "BUY" and same_side_cooloff_days > 0:
            if days_since < same_side_cooloff_days:
                days_remaining = same_side_cooloff_days - days_since
                return True, f"Same-side cool-off: {days_remaining} days remaining after last buy"
        elif action == "sell" and last_action == "SELL" and same_side_cooloff_days > 0:
            if days_since < same_side_cooloff_days:
                days_remaining = same_side_cooloff_days - days_since
                return True, f"Same-side cool-off: {days_remaining} days remaining after last sell"

        # Same direction as last trade, or enough time has passed
        return False, ""

    async def _apply_cash_constraint(
        self,
        recommendations: list[TradeRecommendation],
        min_trade_value: float,
        as_of_date: str | None = None,
        ideal: dict[str, float] | None = None,
        current: dict[str, float] | None = None,
        total_value: float | None = None,
        symbol_convictions: dict[str, float] | None = None,
        preloaded_positions: list[dict] | None = None,
        preloaded_securities_map: dict[str, dict] | None = None,
        preloaded_symbol_scores: dict[str, float] | None = None,
        preloaded_symbol_prices: dict[str, float] | None = None,
    ) -> list[TradeRecommendation]:
        """Scale down buy recommendations to fit within available cash."""
        return await apply_cash_constraint(
            engine=self,
            recommendations=recommendations,
            min_trade_value=min_trade_value,
            as_of_date=as_of_date,
            ideal=ideal,
            current=current,
            total_value=total_value,
            symbol_convictions=symbol_convictions,
            preloaded_positions=preloaded_positions,
            preloaded_securities_map=preloaded_securities_map,
            preloaded_symbol_scores=preloaded_symbol_scores,
            preloaded_symbol_prices=preloaded_symbol_prices,
        )

    async def _get_deficit_sells(
        self,
        as_of_date: str | None = None,
        ideal: dict[str, float] | None = None,
        current: dict[str, float] | None = None,
        total_value: float | None = None,
    ) -> list[TradeRecommendation]:
        """Generate sell recommendations if negative balances can't be covered."""
        return await get_deficit_sells(
            engine=self,
            as_of_date=as_of_date,
            ideal=ideal,
            current=current,
            total_value=total_value,
        )

    async def _generate_deficit_sells(
        self,
        deficit_eur: float,
        as_of_date: str | None = None,
        ideal: dict[str, float] | None = None,
        current: dict[str, float] | None = None,
        total_value: float | None = None,
        reason_kind: str = "cash_deficit",
        max_sell_conviction: float | None = None,
        preloaded_positions: list[dict] | None = None,
        preloaded_securities_map: dict[str, dict] | None = None,
        preloaded_symbol_scores: dict[str, float] | None = None,
        preloaded_symbol_prices: dict[str, float] | None = None,
    ) -> list[TradeRecommendation]:
        """Generate sell recommendations to cover remaining deficit."""
        return await generate_deficit_sells(
            engine=self,
            deficit_eur=deficit_eur,
            as_of_date=as_of_date,
            ideal=ideal,
            current=current,
            total_value=total_value,
            reason_kind=reason_kind,
            max_sell_conviction=max_sell_conviction,
            preloaded_positions=preloaded_positions,
            preloaded_securities_map=preloaded_securities_map,
            preloaded_symbol_scores=preloaded_symbol_scores,
            preloaded_symbol_prices=preloaded_symbol_prices,
        )

    async def _get_positions_for_context(
        self,
        *,
        as_of_date: str | None,
        securities_map: dict[str, dict],
    ) -> list[dict]:
        """Get positions either from live DB state or as-of snapshot state."""
        if as_of_date is None:
            return await self._db.get_all_positions()

        get_snapshot = getattr(self._db, "get_portfolio_snapshot_as_of", None)
        if get_snapshot is None:
            return await self._db.get_all_positions()
        as_of_ts = int(datetime.strptime(as_of_date, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
        maybe_snapshot = get_snapshot(as_of_ts)
        if not inspect.isawaitable(maybe_snapshot):
            return await self._db.get_all_positions()
        snapshot = await maybe_snapshot
        if not snapshot and self._db.__class__.__name__ == "SimulationDatabase":
            return await self._db.get_all_positions()
        if not snapshot:
            return []

        positions_blob = snapshot.get("data", {}).get("positions", {}) or {}
        result: list[dict] = []
        for symbol, payload in positions_blob.items():
            quantity = float((payload or {}).get("quantity", 0) or 0)
            if quantity <= 0:
                continue
            sec = securities_map.get(symbol) or {}
            result.append(
                {
                    "symbol": symbol,
                    "quantity": quantity,
                    "currency": sec.get("currency", "EUR"),
                    "current_price": 0.0,
                }
            )
        return result

    async def _get_cash_balances_for_context(self, as_of_date: str | None = None) -> dict[str, float]:
        """Get cash balances from live portfolio or as-of snapshot."""
        if as_of_date is None:
            return await self._portfolio.get_cash_balances()

        get_snapshot = getattr(self._db, "get_portfolio_snapshot_as_of", None)
        if get_snapshot is None:
            return await self._portfolio.get_cash_balances()
        as_of_ts = int(datetime.strptime(as_of_date, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
        maybe_snapshot = get_snapshot(as_of_ts)
        if not inspect.isawaitable(maybe_snapshot):
            return await self._portfolio.get_cash_balances()
        snapshot = await maybe_snapshot
        if not snapshot and self._db.__class__.__name__ == "SimulationDatabase":
            return await self._portfolio.get_cash_balances()
        if not snapshot:
            return {"EUR": 0.0}
        return {"EUR": float(snapshot.get("data", {}).get("cash_eur", 0.0) or 0.0)}
