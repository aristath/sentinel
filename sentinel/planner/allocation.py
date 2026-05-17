"""Allocation calculation component for ideal portfolio computation."""

from __future__ import annotations

import asyncio
import inspect
import json
from datetime import datetime, timezone

from sentinel.currency import Currency
from sentinel.database import Database
from sentinel.planner.analyzer import PortfolioAnalyzer
from sentinel.planner.preferences import (
    apply_max_cap,
    effective_user_multiplier,
    freshness_from_timestamp,
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
from sentinel.utils.strings import parse_csv_field


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

    def _calculate_diversification_score(
        self,
        security: dict,
        current_allocs: dict,
        target_allocs: dict,
    ) -> float:
        """Calculate diversification score for a security.

        Returns a value from -1 (heavily overweight categories) to +1 (heavily underweight).
        Securities with multiple categories get averaged scores.

        Args:
            security: Security dict with geography/industry fields
            current_allocs: Current allocations from portfolio.get_allocations()
            target_allocs: Target allocations from portfolio.get_target_allocations()

        Returns:
            float: Diversification score clamped to [-1, +1]
        """
        deviations = []

        # Parse comma-separated geographies
        geos = parse_csv_field(security.get("geography"))

        # Parse comma-separated industries
        inds = parse_csv_field(security.get("industry"))

        # Calculate deviation for each geography
        for geo in geos:
            target = target_allocs.get("geography", {}).get(geo, 0)
            current = current_allocs.get("by_geography", {}).get(geo, 0)
            # Positive deviation = underweight = good
            deviation = target - current
            deviations.append(deviation)

        # Calculate deviation for each industry
        for ind in inds:
            target = target_allocs.get("industry", {}).get(ind, 0)
            current = current_allocs.get("by_industry", {}).get(ind, 0)
            deviation = target - current
            deviations.append(deviation)

        # Average all deviations
        if not deviations:
            return 0.0

        avg_deviation = sum(deviations) / len(deviations)

        # Clamp to [-1, +1]
        return max(-1.0, min(1.0, avg_deviation))

    async def _load_strategy_settings(self) -> dict[str, float]:
        keys_defaults: dict[str, float] = {
            "diversification_impact_pct": DEFAULTS["diversification_impact_pct"],
            "strategy_entry_t1_dd": DEFAULTS["strategy_entry_t1_dd"],
            "strategy_entry_t3_dd": DEFAULTS["strategy_entry_t3_dd"],
            "strategy_entry_memory_days": DEFAULTS["strategy_entry_memory_days"],
            "strategy_memory_max_boost": DEFAULTS["strategy_memory_max_boost"],
            "max_dividend_reinvestment_boost": DEFAULTS["max_dividend_reinvestment_boost"],
            "strategy_core_target_pct": DEFAULTS["strategy_core_target_pct"],
            "strategy_opportunity_target_pct": DEFAULTS["strategy_opportunity_target_pct"],
            "strategy_min_opp_score": DEFAULTS["strategy_min_opp_score"],
            "max_position_pct": DEFAULTS["max_position_pct"],
            "clara_preference_weekly_fade": DEFAULTS["clara_preference_weekly_fade"],
            "clara_preference_strength": DEFAULTS["clara_preference_strength"],
        }
        keys = list(keys_defaults.keys())
        values = await asyncio.gather(*[self._settings.get(k, keys_defaults[k]) for k in keys])
        return {k: float(v if v is not None else keys_defaults[k]) for k, v in zip(keys, values, strict=False)}

    async def calculate_ideal_portfolio(self, as_of_date: str | None = None) -> dict[str, float]:
        """Calculate ideal portfolio allocations using deterministic contrarian strategy.

        Per-security `user_multiplier` (0..1) is used as Clara's strategic preference:
        - 0.5 = neutral
        - 1.0 = strongest strategic overweight preference
        - 0.0 = strongest avoid/near-zero preference

        Diversification adjustment:
        - Securities in underweight categories get a boost
        - Securities in overweight categories get a reduction
        - Max impact is configurable via diversification_impact_pct setting

        Returns:
            dict: symbol -> target allocation percentage (0-1)
        """
        # Cache only live calculations; as-of runs must be point-in-time deterministic.
        if as_of_date is None:
            cache_getter = getattr(self._db, "cache_get", None)
            if callable(cache_getter):
                maybe_cached = cache_getter("planner:ideal_portfolio")
                if inspect.isawaitable(maybe_cached):
                    maybe_cached = await maybe_cached
                if isinstance(maybe_cached, (str, bytes, bytearray)):
                    return json.loads(maybe_cached)

        # Get all securities with Clara strategic preference values
        securities = await self._db.get_all_securities(active_only=True)
        if not securities:
            return {}

        # Get current allocations and targets for diversification
        if as_of_date is None:
            current_allocs = await self._portfolio.get_allocations()
        else:
            analyzer = PortfolioAnalyzer(db=self._db, portfolio=self._portfolio, currency=self._currency)
            by_security = await analyzer.get_current_allocations(as_of_date=as_of_date)
            current_allocs = {
                "by_security": by_security,
                "by_geography": {},
                "by_industry": {},
            }
        target_allocs = await self._portfolio.get_target_allocations()
        config = await self._load_strategy_settings()
        div_impact = config["diversification_impact_pct"] / 100.0
        entry_t1_dd = config["strategy_entry_t1_dd"]
        entry_t3_dd = config["strategy_entry_t3_dd"]
        entry_memory_days = int(config["strategy_entry_memory_days"])
        memory_max_boost = config["strategy_memory_max_boost"]
        weekly_fade = config["clara_preference_weekly_fade"]
        preference_strength = config["clara_preference_strength"]

        symbol_signals: dict[str, dict[str, float | int]] = {}
        rebalance_signals: dict[str, dict[str, float | int]] = {}
        baseline_raw_weights: dict[str, float] = {}
        clara_raw_weights: dict[str, float] = {}
        opportunity_raw_weights: dict[str, float] = {}
        preference_details: dict[str, dict[str, float]] = {}
        symbols = [sec["symbol"] for sec in securities]
        as_of_now: datetime | None = None
        if as_of_date is not None:
            as_of_now = datetime.strptime(as_of_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
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
            stored_preference = normalize_user_multiplier(sec.get("user_multiplier", 0.5))
            effective_preference = effective_user_multiplier(
                stored_preference,
                sec.get("user_multiplier_updated_at"),
                weekly_fade,
                now=as_of_now,
            )
            preference_details[symbol] = {
                "user_multiplier": stored_preference,
                "effective_user_multiplier": effective_preference,
            }

            raw = prices_by_symbol.get(symbol, [])
            closes = [float(p["close"]) for p in reversed(raw) if p.get("close") is not None]
            signal = compute_contrarian_signal(closes)
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
            signal["opp_score"] = effective_opp
            signal["memory_boosted"] = 1 if effective_opp > raw_opp else 0

            # Apply diversification multiplier
            if div_impact > 0:
                div_score = self._calculate_diversification_score(sec, current_allocs, target_allocs)
                div_multiplier = 1.0 + (div_score * div_impact)
                signal["core_rank"] = float(signal.get("core_rank", 0.0)) * div_multiplier
                signal["opp_score"] = max(0.0, min(1.0, float(signal.get("opp_score", 0.0)) * div_multiplier))

            symbol_signals[symbol] = signal
            rebalance_signals[symbol] = dict(signal)

            baseline_weight = max(0.001, float(signal.get("core_rank", 0.0) or 0.0) + 1.0)
            baseline_raw_weights[symbol] = baseline_weight
            clara_raw_weights[symbol] = baseline_weight * preference_tilt(effective_preference, preference_strength)

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
                        symbol_signals[symbol]["opp_score"] = max(0.0, min(1.0, boosted))

        core_target = config["strategy_core_target_pct"] / 100.0
        opportunity_target = config["strategy_opportunity_target_pct"] / 100.0
        min_opp_score = config["strategy_min_opp_score"]
        core_target = max(0.0, min(1.0, core_target))
        opportunity_target = max(0.0, min(1.0, opportunity_target))
        if core_target + opportunity_target <= 0:
            core_target = 0.8
            opportunity_target = 0.2
        total_sleeves = core_target + opportunity_target
        core_target /= total_sleeves
        opportunity_target /= total_sleeves

        for symbol, signal in symbol_signals.items():
            opp_score = float(signal.get("opp_score", 0.0) or 0.0)
            if opp_score < min_opp_score:
                continue
            vol20 = max(float(signal.get("vol20", 0.0) or 0.0), 1e-6)
            opportunity_raw_weights[symbol] = opp_score / vol20

        baseline_weights = normalize_weights(baseline_raw_weights)
        clara_weights = normalize_weights(clara_raw_weights)
        opportunity_weights = normalize_weights(opportunity_raw_weights)

        global_updated_at = await self._settings.get("clara_preferences_updated_at")
        if global_updated_at is None:
            preference_updates = [
                str(sec["user_multiplier_updated_at"]) for sec in securities if sec.get("user_multiplier_updated_at")
            ]
            global_updated_at = max(preference_updates, default=None)
        clara_freshness = freshness_from_timestamp(global_updated_at, weekly_fade, now=as_of_now)
        clara_sleeve = core_target * clara_freshness
        baseline_sleeve = core_target * (1.0 - clara_freshness)
        tactical_sleeve = opportunity_target if opportunity_weights else 0.0

        allocations: dict[str, float] = {}
        decomposition: dict[str, dict[str, float | str]] = {}
        sleeves: dict[str, str] = {}
        for symbol in symbols:
            clara_component = clara_sleeve * clara_weights.get(symbol, 0.0)
            baseline_component = baseline_sleeve * baseline_weights.get(symbol, 0.0)
            opportunity_component = tactical_sleeve * opportunity_weights.get(symbol, 0.0)
            final_weight = clara_component + baseline_component + opportunity_component
            if final_weight <= 0:
                continue
            allocations[symbol] = final_weight
            sleeve = "opportunity" if opportunity_component > 0 else "core"
            sleeves[symbol] = sleeve
            detail = preference_details.get(symbol, {})
            decomposition[symbol] = {
                "baseline_target_pct": baseline_component,
                "clara_target_pct": clara_component,
                "opportunity_target_pct": opportunity_component,
                "final_target_pct": final_weight,
                "allocation_sleeve": sleeve,
                "clara_freshness": clara_freshness,
                "effective_user_multiplier": detail.get("effective_user_multiplier", 0.5),
                "user_multiplier": detail.get("user_multiplier", 0.5),
            }

        allocations = normalize_weights(allocations)
        for symbol, detail in decomposition.items():
            signal_update = {
                "sleeve": str(detail["allocation_sleeve"]),
                "effective_user_multiplier": float(detail["effective_user_multiplier"]),
                "user_multiplier": float(detail["user_multiplier"]),
                "baseline_target_pct": float(detail["baseline_target_pct"]),
                "clara_target_pct": float(detail["clara_target_pct"]),
                "opportunity_target_pct": float(detail["opportunity_target_pct"]),
                "final_target_pct": float(detail["final_target_pct"]),
                "clara_freshness": float(detail["clara_freshness"]),
            }
            rebalance_signals.setdefault(symbol, {}).update(signal_update)
            symbol_signals.setdefault(symbol, {}).update(signal_update)
        # Enforce hard max position bounds. Minimum position is a trade-practicality
        # constraint now, not an allocation floor.
        max_position = config["max_position_pct"] / 100.0
        bounded = apply_max_cap(allocations, max_position)
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

        allocation_decomposition = {
            "global": {
                "clara_freshness": clara_freshness,
                "clara_strategic_sleeve": clara_sleeve,
                "sentinel_baseline_sleeve": baseline_sleeve,
                "tactical_opportunity_sleeve": tactical_sleeve,
            },
            "symbols": decomposition,
        }
        self._last_signal_bundle = {
            "as_of_date": as_of_date,
            "rebalance_signals": rebalance_signals,
            "sleeves": sleeves,
            "allocation_decomposition": allocation_decomposition,
        }

        # Cache live allocations/diagnostics for downstream APIs/rebalance.
        # Do not cache as-of signals to avoid polluting live state.
        if as_of_date is None:
            cache_setter = getattr(self._db, "cache_set", None)
            if callable(cache_setter):
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
