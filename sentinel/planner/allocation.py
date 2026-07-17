"""Allocation calculation component for ideal portfolio computation."""

from __future__ import annotations

import asyncio
import inspect
import json
from datetime import datetime, timezone

from sentinel.currency import Currency
from sentinel.database import Database
from sentinel.forecasting.scoring import adjusted_opportunity_score
from sentinel.planner.preferences import (
    apply_max_cap,
    normalize_user_multiplier,
    normalize_weights,
    preference_tilt,
)
from sentinel.portfolio import Portfolio
from sentinel.settings import DEFAULTS, Settings
from sentinel.strategy import (
    compute_contrarian_signal,
    effective_opportunity_score,
    recent_dd252_min,
)

# A security only participates in the ideal allocation if the user has actively
# endorsed it above the configured threshold and it is buyable. The rebalance
# engine still sees non-qualifying securities so it can plan sells / maintenance
# on legacy holdings; these gates only affect what the *ideal* portfolio holds.


class AllocationCalculator:
    """Calculates ideal portfolio allocations based on scores and constraints."""

    def __init__(
        self,
        db: Database | None = None,
        portfolio: Portfolio | None = None,
        currency: Currency | None = None,
        settings: Settings | None = None,
    ):
        """Initialize calculator with optional dependencies.

        Args:
            db: Database instance (uses singleton if None)
            portfolio: Portfolio instance (uses singleton if None)
            currency: Currency instance (uses singleton if None)
            settings: Settings instance (uses singleton if None)
        """
        self._db = db or Database()
        self._portfolio = portfolio or Portfolio()
        self._currency = currency or Currency()
        self._settings = settings or Settings()
        self._last_signal_bundle: dict | None = None

    def get_last_signal_bundle(self, as_of_date: str | None = None) -> dict | None:
        """Return most recent signal bundle for the given as-of context."""
        bundle = self._last_signal_bundle
        if not isinstance(bundle, dict):
            return None
        if bundle.get("as_of_date") != as_of_date:
            return None
        return bundle

    async def _load_strategy_settings(self) -> dict[str, float]:
        keys_defaults: dict[str, float] = {
            "strategy_entry_t1_dd": DEFAULTS["strategy_entry_t1_dd"],
            "strategy_entry_t3_dd": DEFAULTS["strategy_entry_t3_dd"],
            "strategy_entry_memory_days": DEFAULTS["strategy_entry_memory_days"],
            "strategy_memory_max_boost": DEFAULTS["strategy_memory_max_boost"],
            "max_dividend_reinvestment_boost": DEFAULTS["max_dividend_reinvestment_boost"],
            "strategy_min_opp_score": DEFAULTS["strategy_min_opp_score"],
            "strategy_ideal_qualifying_threshold": DEFAULTS["strategy_ideal_qualifying_threshold"],
            "max_position_pct": DEFAULTS["max_position_pct"],
            "target_cash_pct": DEFAULTS["target_cash_pct"],
            "clara_preference_strength": DEFAULTS["clara_preference_strength"],
            "user_multiplier_decay_factor": DEFAULTS["user_multiplier_decay_factor"],
            "user_multiplier_decay_interval_days": DEFAULTS["user_multiplier_decay_interval_days"],
            "forecasting_enabled": DEFAULTS["forecasting_enabled"],
            "forecasting_score_max_age_days": DEFAULTS["forecasting_score_max_age_days"],
            "forecasting_timing_weight": DEFAULTS["forecasting_timing_weight"],
        }
        keys = list(keys_defaults.keys())
        values = await asyncio.gather(*[self._settings.get(k, keys_defaults[k]) for k in keys])
        return {k: float(v if v is not None else keys_defaults[k]) for k, v in zip(keys, values, strict=False)}

    async def calculate_ideal_portfolio(self, as_of_date: str | None = None) -> dict[str, float]:
        """Calculate ideal portfolio allocations using the deterministic contrarian strategy.

        Per-security `user_multiplier` (0..1) is Clara's strategic preference:
        0.5 neutral, 1.0 strongest overweight, 0.0 strongest avoid.

        Returns:
            dict: symbol -> target allocation percentage (0-1)
        """
        # Cache only live calculations; as-of runs must be point-in-time deterministic.
        if as_of_date is None:
            cache_getter = getattr(self._db, "cache_get", None)
            if callable(cache_getter):
                maybe_snapshot = cache_getter("planner:allocation_snapshot")
                if inspect.isawaitable(maybe_snapshot):
                    maybe_snapshot = await maybe_snapshot
                if isinstance(maybe_snapshot, (str, bytes, bytearray)):
                    snapshot = json.loads(maybe_snapshot)
                    if isinstance(snapshot, dict) and isinstance(snapshot.get("ideal"), dict):
                        bundle = snapshot.get("signal_bundle")
                        if isinstance(bundle, dict):
                            self._last_signal_bundle = bundle
                            return snapshot["ideal"]

        # Get all securities with Clara strategic preference values
        securities = await self._db.get_all_securities(active_only=True)
        if not securities:
            return {}

        config = await self._load_strategy_settings()
        entry_t1_dd = config["strategy_entry_t1_dd"]
        entry_t3_dd = config["strategy_entry_t3_dd"]
        entry_memory_days = int(config["strategy_entry_memory_days"])
        memory_max_boost = config["strategy_memory_max_boost"]
        preference_strength = config["clara_preference_strength"]
        ideal_qualifying_threshold = config["strategy_ideal_qualifying_threshold"]
        forecasting_enabled = bool(config["forecasting_enabled"])
        forecast_timing_weight = config["forecasting_timing_weight"]

        symbol_signals: dict[str, dict[str, float | int | str]] = {}
        rebalance_signals: dict[str, dict[str, float | int | str]] = {}
        clara_raw_weights: dict[str, float] = {}
        preference_details: dict[str, dict[str, float]] = {}
        symbols = [sec["symbol"] for sec in securities]
        forecast_scores: dict[str, dict] = {}
        if as_of_date is None and forecasting_enabled:
            forecast_getter = getattr(self._db, "get_latest_forecast_scores", None)
            if callable(forecast_getter):
                max_age_seconds = int(config["forecasting_score_max_age_days"] * 86400)
                maybe_scores = forecast_getter(symbols, scope="combined", max_age_seconds=max_age_seconds)
                if inspect.isawaitable(maybe_scores):
                    maybe_scores = await maybe_scores
                if isinstance(maybe_scores, dict):
                    forecast_scores = maybe_scores
        prices_by_symbol: dict[str, list[dict]] | None = None
        get_prices_multi = getattr(self._db, "get_prices_for_symbols", None)
        if callable(get_prices_multi):
            maybe_prices = get_prices_multi(symbols, days=300, end_date=as_of_date)
            if inspect.isawaitable(maybe_prices):
                resolved = await maybe_prices
                if isinstance(resolved, dict):
                    prices_by_symbol = resolved
            elif isinstance(maybe_prices, dict):
                prices_by_symbol = maybe_prices
        if prices_by_symbol is None:
            all_prices = await asyncio.gather(
                *[self._db.get_prices(symbol, days=300, end_date=as_of_date) for symbol in symbols]
            )
            prices_by_symbol = {symbol: prices for symbol, prices in zip(symbols, all_prices, strict=False)}
        for sec in securities:
            symbol = sec["symbol"]
            # Stored slider value is the truth — the weekly decay job has
            # already faded historical ratings; no read-time correction here.
            stored_preference = normalize_user_multiplier(sec.get("user_multiplier", 0.5))
            preference_details[symbol] = {
                "user_multiplier": stored_preference,
            }

            raw = prices_by_symbol.get(symbol, [])
            closes = [float(p["close"]) for p in reversed(raw) if p.get("close") is not None]
            signal: dict[str, float | int | str] = dict(compute_contrarian_signal(closes))
            raw_opp = float(signal.get("opp_score", 0.0) or 0.0)
            recent_min = recent_dd252_min(closes, window_days=entry_memory_days)
            effective_opp = effective_opportunity_score(
                raw_opp_score=raw_opp,
                cycle_turn=int(signal.get("cycle_turn", 0) or 0),
                freefall_block=int(signal.get("freefall_block", 0) or 0),
                recent_dd252_min_value=recent_min,
                entry_t1_dd=entry_t1_dd,
                entry_t3_dd=entry_t3_dd,
                max_boost=memory_max_boost,
            )
            signal["opp_score_raw"] = raw_opp
            signal["dd252_recent_min"] = recent_min
            signal["opp_score_pre_forecast"] = effective_opp
            forecast = forecast_scores.get(symbol) or {}
            forecast_score = forecast.get("score")
            adjusted_opp = effective_opp
            if int(signal.get("freefall_block", 0) or 0) != 1:
                adjusted_opp = adjusted_opportunity_score(
                    current_opp_score=effective_opp,
                    forecast_score=float(forecast_score) if forecast_score is not None else None,
                    weight=forecast_timing_weight,
                )
            signal["opp_score"] = adjusted_opp
            if forecast:
                signal["forecast_score"] = float(forecast.get("score") or 0.5)
                signal["forecast_return_4w"] = float(forecast.get("forecast_return_4w") or 0.0)
                signal["forecast_updated_at"] = int(forecast.get("updated_at") or 0)
            signal["memory_boosted"] = 1 if effective_opp > raw_opp else 0

            symbol_signals[symbol] = signal
            rebalance_signals[symbol] = dict(signal)

            # Securities below the configured Clara threshold are excluded from
            # the ideal entirely — both the Clara half AND the algo half. Capital
            # flows to the securities the user actually wants.
            # Signals stay populated above so the rebalance engine can still
            # plan sells / maintenance on legacy holdings.
            if stored_preference < ideal_qualifying_threshold:
                continue
            if not int(sec.get("allow_buy", 1) or 0):
                continue

            # Clara defines the destination. Price signals are retained for
            # today's timing decision, but never alter long-term target weights.
            clara_raw_weights[symbol] = preference_tilt(stored_preference, preference_strength)

        # Apply dividend reinvestment boost
        max_div_boost = config["max_dividend_reinvestment_boost"]
        if max_div_boost > 0:
            uninvested = await self._db.get_uninvested_dividends()
            total_pool = sum(uninvested.values())
            if total_pool > 0:
                for symbol, pool in uninvested.items():
                    if symbol in symbol_signals:
                        share = pool / total_pool
                        boosted = float(symbol_signals[symbol].get("opp_score", 0.0)) + share * max_div_boost
                        boosted = max(0.0, min(1.0, boosted))
                        symbol_signals[symbol]["opp_score"] = boosted
                        rebalance_signals[symbol]["opp_score"] = boosted

        min_opp_score = config["strategy_min_opp_score"]
        clara_weights = normalize_weights(clara_raw_weights)

        allocations: dict[str, float] = {}
        decomposition: dict[str, dict[str, float | str]] = {}
        sleeves: dict[str, str] = {}
        for symbol in symbols:
            final_weight = clara_weights.get(symbol, 0.0)
            if final_weight <= 0:
                continue
            allocations[symbol] = final_weight
            opportunity_score = float(symbol_signals.get(symbol, {}).get("opp_score", 0.0) or 0.0)
            sleeve = "opportunity" if opportunity_score >= min_opp_score else "core"
            sleeves[symbol] = sleeve
            detail = preference_details.get(symbol, {})
            decomposition[symbol] = {
                "baseline_target_pct": 0.0,
                "clara_target_pct": final_weight,
                "opportunity_target_pct": 0.0,
                "final_target_pct": final_weight,
                "allocation_sleeve": sleeve,
                "user_multiplier": detail.get("user_multiplier", 0.5),
            }

        allocations = normalize_weights(allocations)
        for symbol, detail in decomposition.items():
            signal_update = {
                "sleeve": str(detail["allocation_sleeve"]),
                "user_multiplier": float(detail["user_multiplier"]),
                "baseline_target_pct": float(detail["baseline_target_pct"]),
                "clara_target_pct": float(detail["clara_target_pct"]),
                "opportunity_target_pct": float(detail["opportunity_target_pct"]),
                "final_target_pct": float(detail["final_target_pct"]),
            }
            rebalance_signals.setdefault(symbol, {}).update(signal_update)
            symbol_signals.setdefault(symbol, {}).update(signal_update)
        # Enforce hard max position bounds. Minimum position is a trade-practicality
        # constraint now, not an allocation floor.
        max_position = config["max_position_pct"] / 100.0
        target_cash = max(0.0, min(1.0, config["target_cash_pct"] / 100.0))
        target_security_total = 1.0 - target_cash
        if target_security_total <= 0:
            bounded = {}
        else:
            unit_cap = max_position / target_security_total
            bounded = {
                symbol: weight * target_security_total
                for symbol, weight in apply_max_cap(allocations, unit_cap).items()
            }
        for symbol, final_weight in bounded.items():
            if symbol in decomposition:
                original_weight = float(decomposition[symbol].get("final_target_pct", 0.0) or 0.0)
                scale = final_weight / original_weight if original_weight > 0 else 1.0
                decomposition[symbol]["baseline_target_pct"] = (
                    float(decomposition[symbol].get("baseline_target_pct", 0.0) or 0.0) * scale
                )
                decomposition[symbol]["clara_target_pct"] = (
                    float(decomposition[symbol].get("clara_target_pct", 0.0) or 0.0) * scale
                )
                decomposition[symbol]["opportunity_target_pct"] = (
                    float(decomposition[symbol].get("opportunity_target_pct", 0.0) or 0.0) * scale
                )
                decomposition[symbol]["final_target_pct"] = final_weight
                signal_update = {
                    "baseline_target_pct": float(decomposition[symbol]["baseline_target_pct"]),
                    "clara_target_pct": float(decomposition[symbol]["clara_target_pct"]),
                    "opportunity_target_pct": float(decomposition[symbol]["opportunity_target_pct"]),
                    "final_target_pct": float(decomposition[symbol]["final_target_pct"]),
                }
                rebalance_signals.setdefault(symbol, {}).update(signal_update)
                symbol_signals.setdefault(symbol, {}).update(signal_update)
        for symbol in set(decomposition) - set(bounded):
            decomposition[symbol].update(
                {
                    "baseline_target_pct": 0.0,
                    "clara_target_pct": 0.0,
                    "opportunity_target_pct": 0.0,
                    "final_target_pct": 0.0,
                }
            )
            rebalance_signals.setdefault(symbol, {}).update(decomposition[symbol])
            symbol_signals.setdefault(symbol, {}).update(decomposition[symbol])

        allocation_decomposition = {
            "global": {
                "target_model": "clara_risk",
                "clara_target_pct": 1.0,
                "algo_blend_pct": 0.0,
                "requested_cash_target_pct": target_cash,
                "effective_cash_target_pct": max(0.0, 1.0 - sum(bounded.values())),
            },
            "symbols": decomposition,
        }
        signal_bundle = {
            "as_of_date": as_of_date,
            "rebalance_signals": rebalance_signals,
            "sleeves": sleeves,
            "allocation_decomposition": allocation_decomposition,
        }
        self._last_signal_bundle = signal_bundle

        # Cache live allocations/diagnostics for downstream APIs/rebalance.
        # Do not cache as-of signals to avoid polluting live state.
        if as_of_date is None:
            cache_setter = getattr(self._db, "cache_set", None)
            if callable(cache_setter):
                maybe_set = cache_setter(
                    "planner:allocation_snapshot",
                    json.dumps({"ideal": bounded, "signal_bundle": signal_bundle}),
                    ttl_seconds=600,
                )
                if inspect.isawaitable(maybe_set):
                    await maybe_set
                maybe_set = cache_setter("planner:ideal_portfolio", json.dumps(bounded), ttl_seconds=600)
                if inspect.isawaitable(maybe_set):
                    await maybe_set
                maybe_set = cache_setter("planner:contrarian_signals", json.dumps(symbol_signals), ttl_seconds=600)
                if inspect.isawaitable(maybe_set):
                    await maybe_set
                maybe_set = cache_setter("planner:rebalance_signals", json.dumps(rebalance_signals), ttl_seconds=600)
                if inspect.isawaitable(maybe_set):
                    await maybe_set
                maybe_set = cache_setter("planner:contrarian_sleeves", json.dumps(sleeves), ttl_seconds=600)
                if inspect.isawaitable(maybe_set):
                    await maybe_set
                maybe_set = cache_setter(
                    "planner:allocation_decomposition",
                    json.dumps(allocation_decomposition),
                    ttl_seconds=600,
                )
                if inspect.isawaitable(maybe_set):
                    await maybe_set
                maybe_set = cache_setter(
                    "planner:contrarian_signals_ts",
                    str(int(datetime.now(timezone.utc).timestamp())),
                    ttl_seconds=600,
                )
                if inspect.isawaitable(maybe_set):
                    await maybe_set
        return bounded
