"""Allocation calculation component for ideal portfolio computation."""

from __future__ import annotations

import asyncio
import inspect
import json
from datetime import datetime, timezone

from sentinel.currency import Currency
from sentinel.database import Database
from sentinel.planner.analyzer import PortfolioAnalyzer
from sentinel.portfolio import Portfolio
from sentinel.settings import Settings
from sentinel.strategy import (
    compute_contrarian_signal,
    compute_symbol_targets,
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

    @staticmethod
    def _normalize_conviction(value: object) -> float:
        """Normalize conviction into [0.0, 1.0]."""
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return 0.5
        return max(0.0, min(1.0, parsed))

    async def _load_strategy_settings(self) -> dict[str, float]:
        keys_defaults: dict[str, float] = {
            "diversification_impact_pct": 10,
            "strategy_entry_t1_dd": -0.10,
            "strategy_entry_t3_dd": -0.22,
            "strategy_entry_memory_days": 42,
            "strategy_memory_max_boost": 0.18,
            "max_dividend_reinvestment_boost": 0.15,
            "strategy_core_target_pct": 70,
            "strategy_opportunity_target_pct": 30,
            "strategy_opportunity_target_max_pct": 45,
            "strategy_min_opp_score": 0.55,
            "max_position_pct": 35,
            "min_position_pct": 1,
        }
        keys = list(keys_defaults.keys())
        values = await asyncio.gather(*[self._settings.get(k, keys_defaults[k]) for k in keys])
        return {k: float(v if v is not None else keys_defaults[k]) for k, v in zip(keys, values, strict=False)}

    async def calculate_ideal_portfolio(self, as_of_date: str | None = None) -> dict[str, float]:
        """Calculate ideal portfolio allocations using deterministic contrarian strategy.

        Per-security conviction (0..1) is used as a core preference weight:
        - 0.5 = neutral
        - 1.0 = strongest "keep/add" preference
        - 0.0 = weakest preference (eligible to be deprioritized)

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

        # Get all securities with user conviction values
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

        symbol_signals: dict[str, dict[str, float | int]] = {}
        user_multipliers: dict[str, float] = {}
        symbols = [sec["symbol"] for sec in securities]
        all_prices = await asyncio.gather(
            *[self._db.get_prices(symbol, days=300, end_date=as_of_date) for symbol in symbols]
        )
        prices_by_symbol = {symbol: prices for symbol, prices in zip(symbols, all_prices, strict=False)}
        for sec in securities:
            symbol = sec["symbol"]
            conviction = self._normalize_conviction(sec.get("user_multiplier", 0.5))
            # Continuous preference multiplier (no binary cutoff).
            user_multipliers[symbol] = 0.2 + (1.8 * conviction)

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
            # Conviction influences tactical opportunity intensity continuously.
            signal["opp_score"] = max(0.0, min(1.0, float(signal["opp_score"]) * (0.2 + (0.8 * conviction))))

            # Apply diversification multiplier
            if div_impact > 0:
                div_score = self._calculate_diversification_score(sec, current_allocs, target_allocs)
                div_multiplier = 1.0 + (div_score * div_impact)
                signal["core_rank"] = float(signal.get("core_rank", 0.0)) * div_multiplier
                signal["opp_score"] = max(0.0, min(1.0, float(signal.get("opp_score", 0.0)) * div_multiplier))

            symbol_signals[symbol] = signal

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
        max_opportunity_target = config["strategy_opportunity_target_max_pct"] / 100.0
        min_opp_score = config["strategy_min_opp_score"]

        allocations, sleeves = compute_symbol_targets(
            symbol_signals,
            user_multipliers,
            core_target=core_target,
            opportunity_target=opportunity_target,
            min_opp_score=min_opp_score,
            max_opportunity_target=max_opportunity_target,
        )

        # Enforce position bounds and renormalize to 100% invested
        max_position = config["max_position_pct"] / 100.0
        min_position = config["min_position_pct"] / 100.0
        bounded = {s: max(min_position, min(max_position, w)) for s, w in allocations.items() if w > 0}
        total = sum(bounded.values())
        if total > 0:
            bounded = {s: w / total for s, w in bounded.items()}

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
                maybe_set = cache_setter("planner:contrarian_sleeves", json.dumps(sleeves), ttl_seconds=600)
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
