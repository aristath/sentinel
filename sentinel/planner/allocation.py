"""Allocation calculation component for ideal portfolio computation."""

from __future__ import annotations

import json

from sentinel.currency import Currency
from sentinel.database import Database
from sentinel.portfolio import Portfolio
from sentinel.settings import Settings
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

    async def calculate_ideal_portfolio(self) -> dict[str, float]:
        """Calculate ideal portfolio allocations using classic wavelet-based approach.

        The user_multiplier is applied to each security's score:
        - 1.0 = neutral (default)
        - 2.0 = user is very bullish (doubles the score weight)
        - 0.5 = user is bearish (halves the score weight)
        - 0.0 = user wants to exit entirely

        Diversification adjustment:
        - Securities in underweight categories get a boost
        - Securities in overweight categories get a reduction
        - Max impact is configurable via diversification_impact_pct setting

        Returns:
            dict: symbol -> target allocation percentage (0-1)
        """
        # Check cache first (10 minute TTL)
        cached = await self._db.cache_get("planner:ideal_portfolio")
        if cached is not None:
            return json.loads(cached)

        # Get all securities with scores and user multipliers
        securities = await self._db.get_all_securities(active_only=True)
        securities_by_sym = {sec["symbol"]: sec for sec in securities}
        scores = {}

        # Batch-fetch all scores to avoid N+1 queries
        all_symbols = [sec["symbol"] for sec in securities]
        scores_map = await self._db.get_scores(all_symbols)

        # Get current allocations and targets for diversification
        current_allocs = await self._portfolio.get_allocations()
        target_allocs = await self._portfolio.get_target_allocations()
        div_impact = await self._settings.get("diversification_impact_pct", 10) / 100

        for sec in securities:
            symbol = sec["symbol"]
            user_multiplier = sec.get("user_multiplier", 1.0) or 1.0

            # Skip securities where user wants to exit (multiplier = 0)
            if user_multiplier <= 0:
                continue

            base_score = scores_map.get(symbol, 0)

            # Apply user multiplier as conviction adjustment
            from sentinel.utils.scoring import adjust_score_for_conviction

            adjusted_score = adjust_score_for_conviction(base_score, user_multiplier)

            # Apply diversification multiplier
            if div_impact > 0:
                div_score = self._calculate_diversification_score(sec, current_allocs, target_allocs)
                div_multiplier = 1.0 + (div_score * div_impact)
                adjusted_score = adjusted_score * div_multiplier

            scores[symbol] = adjusted_score

        # Apply dividend reinvestment boost
        max_div_boost = await self._settings.get("max_dividend_reinvestment_boost", 0.15)
        if max_div_boost > 0:
            uninvested = await self._db.get_uninvested_dividends()
            total_pool = sum(uninvested.values())
            if total_pool > 0:
                for symbol, pool in uninvested.items():
                    if symbol in scores:
                        share = pool / total_pool
                        scores[symbol] = scores[symbol] + share * max_div_boost

        # Filter to positive scores or strong user conviction
        scores = {
            sym: sc
            for sym, sc in scores.items()
            if sc > 0 or (securities_by_sym.get(sym, {}).get("user_multiplier", 1.0) or 1.0) > 1.0
        }

        if not scores:
            return {}

        # Get constraints from settings
        max_position = await self._settings.get("max_position_pct", 20)
        min_position = await self._settings.get("min_position_pct", 2)
        cash_target = await self._settings.get("target_cash_pct", 5)

        constraints = {
            "max_position": max_position,
            "min_position": min_position,
            "cash_target": cash_target,
        }

        return await self._classic_allocation(scores, constraints)

    async def _classic_allocation(self, scores: dict, constraints: dict) -> dict[str, float]:
        """Classic wavelet-based allocation algorithm.

        Args:
            scores: symbol -> score mapping
            constraints: dict with max_position, min_position, cash_target (percentages)

        Returns:
            dict: symbol -> target allocation percentage (0-1)
        """
        max_position = constraints.get("max_position", 20) / 100
        min_position = constraints.get("min_position", 2) / 100
        cash_target = constraints.get("cash_target", 5) / 100

        # Filter to positive expected returns only
        positive_scores = {k: v for k, v in scores.items() if v > 0}

        if not positive_scores:
            return {}

        # Calculate allocations proportional to expected returns
        min_score = min(positive_scores.values())
        max_score = max(positive_scores.values())
        score_range = max_score - min_score if max_score != min_score else 1.0

        # Normalize scores to 0-1 range, then square to emphasize differences
        normalized = {}
        for symbol, score in positive_scores.items():
            norm = (score - min_score) / score_range if score_range > 0 else 0.5
            normalized[symbol] = (norm + 0.1) ** 2

        # Allocate proportionally
        total_weight = sum(normalized.values())
        if total_weight <= 0:
            return {}
        allocable = 1.0 - cash_target

        allocations = {}
        for symbol, weight in normalized.items():
            raw_alloc = (weight / total_weight) * allocable
            capped = max(min_position, min(max_position, raw_alloc))
            allocations[symbol] = capped

        # Renormalize to sum to allocable amount
        alloc_sum = sum(allocations.values())
        if alloc_sum > 0:
            scale = allocable / alloc_sum
            allocations = {k: v * scale for k, v in allocations.items()}

        # Cache result (10 minutes = 600 seconds)
        await self._db.cache_set("planner:ideal_portfolio", json.dumps(allocations), ttl_seconds=600)
        return allocations
