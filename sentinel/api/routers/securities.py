"""Securities and prices API routes."""

import inspect
import math
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from typing_extensions import Annotated

from sentinel.api.dependencies import CommonDependencies, get_common_deps
from sentinel.markets import get_open_market_symbols
from sentinel.planner.preferences import preference_snapshot, utc_now_iso
from sentinel.security import Security
from sentinel.strategy import classify_lot_size, compute_contrarian_signal
from sentinel.universe import apply_removed_from_favorites_rule, import_security_from_broker

router = APIRouter(prefix="/securities", tags=["securities"])
prices_router = APIRouter(prefix="/prices", tags=["prices"])
MAX_ANALYSIS_LENGTH = 20_000


async def _invalidate_planner_cache(deps: CommonDependencies) -> None:
    invalidator = getattr(deps.db, "invalidate_planner_cache", None)
    if callable(invalidator):
        maybe = invalidator()
        if inspect.isawaitable(maybe):
            await maybe
        return
    cache_clear = getattr(deps.db, "cache_clear", None)
    if callable(cache_clear):
        maybe = cache_clear(prefix="planner:")
        if inspect.isawaitable(maybe):
            await maybe


def _validate_user_multiplier(value: Any) -> float:
    if isinstance(value, bool):
        raise HTTPException(status_code=400, detail="'user_multiplier' must be a number between 0.0 and 1.0")
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="'user_multiplier' must be a number between 0.0 and 1.0") from None
    if not math.isfinite(parsed) or parsed < 0.0 or parsed > 1.0:
        raise HTTPException(status_code=400, detail="'user_multiplier' must be between 0.0 and 1.0")
    return parsed


def _validate_analysis(value: object) -> str:
    if not isinstance(value, str):
        raise HTTPException(status_code=400, detail="'analysis' must be a non-empty string")
    analysis = value.strip()
    if not analysis:
        raise HTTPException(status_code=400, detail="'analysis' must be a non-empty string")
    if len(analysis) > MAX_ANALYSIS_LENGTH:
        raise HTTPException(status_code=400, detail=f"'analysis' must be at most {MAX_ANALYSIS_LENGTH} characters")
    return analysis


async def _security_payload(symbol: str, deps: CommonDependencies) -> dict[str, Any]:
    sec = await deps.db.get_security(symbol)
    if not sec:
        raise HTTPException(status_code=404, detail="Security not found")
    position = await deps.db.get_position(symbol)
    pref = preference_snapshot(sec)
    return {
        "symbol": sec.get("symbol"),
        "name": sec.get("name"),
        "currency": sec.get("currency", "EUR"),
        "geography": sec.get("geography"),
        "industry": sec.get("industry"),
        "aliases": sec.get("aliases"),
        "min_lot": sec.get("min_lot", 1),
        "active": sec.get("active", 1),
        "allow_buy": sec.get("allow_buy", 1),
        "allow_sell": sec.get("allow_sell", 1),
        "user_multiplier": pref["user_multiplier"],
        "user_multiplier_age_weeks": pref["user_multiplier_age_weeks"],
        "user_multiplier_updated_at": sec.get("user_multiplier_updated_at"),
        "user_multiplier_source": sec.get("user_multiplier_source"),
        "user_multiplier_analysis": sec.get("user_multiplier_analysis"),
        "universe_source": sec.get("universe_source"),
        "universe_last_seen_at": sec.get("universe_last_seen_at"),
        "quantity": position.get("quantity", 0) if position else 0,
        "current_price": position.get("current_price") if position else None,
    }


@router.get("")
async def get_securities(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> list[dict]:
    """Get all securities in universe."""
    return await deps.db.get_all_securities(active_only=False)


@router.post("")
async def add_security(
    data: dict,
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict[str, Any]:
    """Add a new security to the universe."""
    symbol = data.get("symbol")
    if not isinstance(symbol, str) or not symbol.strip():
        raise HTTPException(status_code=400, detail="Symbol is required")
    symbol = symbol.strip()

    # Check if already exists
    existing = await deps.db.get_security(symbol)
    if existing:
        # If security exists but is inactive, treat this as a re-enable.
        # This matches the UX expectation that "adding" an inactive symbol brings it back into the universe.
        if int(existing.get("active", 0) or 0) == 1:
            raise HTTPException(status_code=400, detail="Security already exists")

    # Get info from broker
    info = await deps.broker.get_security_info(symbol)
    if not info:
        raise HTTPException(status_code=404, detail="Security not found in broker")

    if not await deps.broker.add_stock_list_ticker(symbol):
        raise HTTPException(status_code=502, detail="Failed to add security to Freedom24 Favorites")

    # geography/industry are broker-sourced now; any client-supplied values are
    # silently dropped here so that only the sync job decides those fields.
    imported = await import_security_from_broker(
        deps.db,
        deps.broker,
        symbol,
        info=info,
    )
    await _invalidate_planner_cache(deps)

    return {
        "status": "ok",
        "symbol": symbol,
        "name": imported.name,
        "prices_count": imported.prices_count,
        "re_enabled": imported.re_enabled,
    }


@router.delete("/{symbol}")
async def delete_security(
    symbol: str,
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
    sell_position: bool = False,
) -> dict[str, Any]:
    """Remove a security from Favorites and apply safe local universe rules.

    If a position exists, the security remains active with buys disabled and sells allowed.
    If no position exists, it is soft-deleted from the active universe.
    """
    _ = sell_position  # Kept for old clients; universe removal no longer triggers selling.

    # Check if exists
    existing = await deps.db.get_security(symbol)
    if not existing:
        raise HTTPException(status_code=404, detail="Security not found")

    if not await deps.broker.delete_stock_list_ticker(symbol):
        raise HTTPException(status_code=502, detail="Failed to remove security from Freedom24 Favorites")

    result = await apply_removed_from_favorites_rule(deps.db, symbol)
    await _invalidate_planner_cache(deps)

    return {"status": "ok", "sold_quantity": 0, **result}


@router.get("/aliases")
async def get_all_aliases(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> list[dict]:
    """Get aliases for all securities (for companion news/sentiment app)."""
    securities = await deps.db.get_all_securities(active_only=True)
    return [
        {
            "symbol": sec["symbol"],
            "name": sec.get("name"),
            "aliases": sec.get("aliases"),
        }
        for sec in securities
    ]


@router.post("/preference")
async def update_security_preference(
    data: dict,
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict[str, Any]:
    """Update one security's Clara strategic preference and analysis."""
    symbol = data.get("symbol")
    if not isinstance(symbol, str) or not symbol.strip():
        raise HTTPException(status_code=400, detail="'symbol' is required")
    symbol = symbol.strip()

    existing = await deps.db.get_security(symbol)
    if not existing:
        raise HTTPException(status_code=404, detail="Security not found")

    if "user_multiplier" not in data:
        raise HTTPException(status_code=400, detail="'user_multiplier' is required")
    user_multiplier = _validate_user_multiplier(data.get("user_multiplier"))
    analysis = _validate_analysis(data.get("analysis"))
    now = utc_now_iso()

    updater = getattr(deps.db, "update_user_multiplier_preference", None)
    if callable(updater):
        maybe = updater(
            symbol,
            user_multiplier=user_multiplier,
            analysis=analysis,
            source="clara",
            updated_at=now,
        )
        if inspect.isawaitable(maybe):
            await maybe
    else:
        await deps.db.upsert_security(
            symbol,
            user_multiplier=user_multiplier,
            user_multiplier_updated_at=now,
            user_multiplier_source="clara",
            user_multiplier_analysis=analysis,
        )

    await _invalidate_planner_cache(deps)
    return await _security_payload(symbol, deps)


@router.get("/{symbol}")
async def get_security(
    symbol: str,
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict[str, Any]:
    """Get a specific security."""
    return await _security_payload(symbol, deps)


@router.put("/{symbol}")
async def update_security(
    symbol: str,
    data: dict,
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict[str, Any]:
    """Update security metadata and execution controls."""
    existing = await deps.db.get_security(symbol)
    if not existing:
        raise HTTPException(status_code=404, detail="Security not found")

    # `geography` and `industry` are broker-sourced at sync time — not editable
    # via the API. See `Broker.get_security_metadata` and `sync_metadata`.
    allowed_fields = [
        "aliases",
        "allow_buy",
        "allow_sell",
    ]
    updates = {k: v for k, v in data.items() if k in allowed_fields}

    if updates:
        await deps.db.upsert_security(symbol, **updates)
        await _invalidate_planner_cache(deps)

    if "user_multiplier" in data:
        user_multiplier = _validate_user_multiplier(data.get("user_multiplier"))
        analysis = data.get("user_multiplier_analysis")
        if analysis is None:
            analysis = "Manual preference override from Sentinel UI."
        analysis = _validate_analysis(analysis)
        now = utc_now_iso()
        updater = getattr(deps.db, "update_user_multiplier_preference", None)
        if callable(updater):
            maybe = updater(
                symbol,
                user_multiplier=user_multiplier,
                analysis=analysis,
                source="manual",
                updated_at=now,
            )
            if inspect.isawaitable(maybe):
                await maybe
        else:
            await deps.db.upsert_security(
                symbol,
                user_multiplier=user_multiplier,
                user_multiplier_updated_at=now,
                user_multiplier_source="manual",
                user_multiplier_analysis=analysis,
            )
        await _invalidate_planner_cache(deps)

    return await _security_payload(symbol, deps)


@router.get("/{symbol}/prices")
async def get_prices(
    symbol: str,
    days: int = 365,
) -> list[dict]:
    """Get historical prices for a security (validated)."""
    from sentinel.price_validator import PriceValidator

    security = Security(symbol)
    raw_prices = await security.get_historical_prices(days)
    validator = PriceValidator()
    return validator.validate_price_series_desc(raw_prices)


@router.post("/{symbol}/sync-prices")
async def sync_prices(
    symbol: str,
    days: int = 365,
) -> dict[str, int]:
    """Sync historical prices from broker."""
    security = Security(symbol)
    count = await security.sync_prices(days)
    return {"synced": count}


# Prices router (separate prefix)
@prices_router.post("/sync-all")
async def sync_all_prices(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict[str, str]:
    """Sync historical prices for all securities with positions."""
    from sentinel.app import _sync_missing_prices

    await _sync_missing_prices(deps.db, deps.broker)
    return {"status": "ok"}


# Unified view router (under /api/unified)
unified_router = APIRouter(prefix="/unified", tags=["unified"])


@unified_router.get("")
async def get_unified_view(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
    period: str = "1Y",
    as_of: str | None = None,
) -> list[dict]:
    """
    Get aggregated data for unified security cards view.

    Args:
        period: Price history period - 1M, 1Y, 5Y, 10Y
        as_of: Optional date (YYYY-MM-DD). When set, historical prices are scoped on or before that date.

    Returns all securities with positions, prices, allocations, and recommendations.
    """
    from sentinel.planner import Planner
    from sentinel.planner.analyzer import PortfolioAnalyzer
    from sentinel.planner.preferences import preference_snapshot
    from sentinel.portfolio import Portfolio
    from sentinel.price_validator import PriceValidator, get_price_anomaly_warning

    # Get all active securities
    securities = await deps.db.get_all_securities(active_only=True)
    if not securities:
        return []

    all_symbols = [sec["symbol"] for sec in securities]

    # Fetch all data sources
    portfolio = Portfolio(
        db=deps.db,
        broker=deps.broker,
        settings=deps.settings,
        currency=deps.currency,
    )
    planner = Planner(db=deps.db, broker=deps.broker, portfolio=portfolio)
    analyzer = PortfolioAnalyzer(db=deps.db, portfolio=portfolio, currency=deps.currency)
    if as_of is None:
        positions = await deps.db.get_all_positions()
    else:
        positions = await analyzer.get_positions_as_of(as_of)
    positions_map = {p["symbol"]: p for p in positions}

    # Recommendations using settings default for min_trade_value
    eligible_symbols = await get_open_market_symbols(deps.broker, deps.db) if as_of is None else None
    recommendations = await planner.get_recommendations(as_of_date=as_of, eligible_symbols=eligible_symbols)
    recommendations_map = {r.symbol: r for r in recommendations}

    # Ideal and current allocations
    ideal = await planner.calculate_ideal_portfolio(as_of_date=as_of)
    current_allocs = await planner.get_current_allocations(as_of_date=as_of)

    # Live quotes only for live view. As-of views are valued from historical prices.
    current_quotes = await deps.broker.get_quotes(all_symbols) if as_of is None else {}

    latest_prices_map: dict[str, float] = {}
    if as_of is not None:
        latest_prices_raw = await deps.db.get_prices_bulk(all_symbols, days=1, end_date=as_of)
        for symbol, rows in latest_prices_raw.items():
            if rows:
                latest_prices_map[symbol] = rows[0].get("close", 0)

    # Use the whole portfolio, including cash, for every allocation denominator.
    if as_of is not None:
        total_value = await analyzer.get_total_value(as_of_date=as_of)
    else:
        total_value = await portfolio.total_value()

    # Bulk-fetch and validate prices
    days_map = {"1M": 30, "1Y": 365, "5Y": 1825, "10Y": 3650}
    days = days_map.get(period, 365)
    all_prices_raw = await deps.db.get_prices_bulk(all_symbols, days=days, end_date=as_of)

    validator = PriceValidator()
    all_prices_validated = {}
    for symbol, raw_prices in all_prices_raw.items():
        all_prices_validated[symbol] = validator.validate_price_series_desc(raw_prices)

    fee_fixed_raw = await deps.settings.get("transaction_fee_fixed", 2.0)
    fee_pct_raw = await deps.settings.get("transaction_fee_percent", 0.2)
    lot_standard_raw = await deps.settings.get("strategy_lot_standard_max_pct", 0.08)
    lot_coarse_raw = await deps.settings.get("strategy_lot_coarse_max_pct", 0.30)
    min_opp_raw = await deps.settings.get("strategy_min_opp_score", 0.55)
    fee_fixed = float(2.0 if fee_fixed_raw is None else fee_fixed_raw)
    fee_pct = float(0.2 if fee_pct_raw is None else fee_pct_raw) / 100.0
    lot_standard_max_pct = float(0.08 if lot_standard_raw is None else lot_standard_raw)
    lot_coarse_max_pct = float(0.30 if lot_coarse_raw is None else lot_coarse_raw)
    min_opp_score = float(0.55 if min_opp_raw is None else min_opp_raw)
    total_plan_fees = sum(
        fee_fixed + abs(float(rec.value_delta_eur)) * fee_pct
        for rec in recommendations
        if abs(float(rec.value_delta_eur)) > 0
    )
    post_plan_total_value = max(0.0, total_value - total_plan_fees)
    sleeves_map = {}
    allocation_decomposition = {}
    global_decomposition = {}
    diagnostics_getter = getattr(planner, "get_last_allocation_diagnostics", None)
    diagnostics = diagnostics_getter(as_of_date=as_of) if callable(diagnostics_getter) else {}
    effective_signals = {}
    if isinstance(diagnostics, dict):
        sleeves_map = diagnostics.get("sleeves", {}) or {}
        effective_signals = diagnostics.get("rebalance_signals", {}) or {}
        parsed_decomposition = diagnostics.get("allocation_decomposition", {}) or {}
        if isinstance(parsed_decomposition, dict):
            allocation_decomposition = parsed_decomposition.get("symbols", {}) or {}
            global_decomposition = parsed_decomposition.get("global", {}) or {}

    # Build unified response
    result = []
    for sec in securities:
        symbol = sec["symbol"]
        position = positions_map.get(symbol)
        recommendation = recommendations_map.get(symbol)
        prices = all_prices_validated.get(symbol, [])

        # Position data
        has_position = position is not None and position.get("quantity", 0) > 0
        quantity = position.get("quantity", 0) if position else 0
        avg_cost = position.get("avg_cost", 0) if position else 0

        # Current price: prefer live quote, fallback to position, then historical
        quote = current_quotes.get(symbol)
        current_price = (quote.get("price") or 0) if quote else 0
        if as_of is not None:
            current_price = latest_prices_map.get(symbol, 0)
            if current_price <= 0 and prices:
                current_price = prices[0]["close"]
        else:
            if current_price <= 0 and position:
                current_price = position.get("current_price") or 0
            if current_price <= 0 and prices:
                current_price = prices[0]["close"]

        # Price anomaly warning
        price_warning = None
        if current_price > 0 and prices:
            sorted_prices = sorted(prices, key=lambda p: p["date"])
            historical_closes = [p["close"] for p in sorted_prices if p.get("close") and p["close"] > 0]
            price_warning = get_price_anomaly_warning(current_price, historical_closes, symbol)

        # Profit / loss
        sec_currency = sec.get("currency", "EUR")
        min_lot = sec.get("min_lot", 1)
        if has_position and avg_cost > 0:
            profit_pct = ((current_price - avg_cost) / avg_cost) * 100
            profit_value = (current_price - avg_cost) * quantity
            profit_value_eur = await deps.currency.to_eur(profit_value, sec_currency)
        else:
            profit_pct = 0
            profit_value = 0
            profit_value_eur = 0

        # EUR value
        value_local = current_price * quantity
        value_eur = await deps.currency.to_eur(value_local, sec_currency) if has_position else 0

        # Allocations (as percentages)
        current_alloc = current_allocs.get(symbol, 0) * 100
        ideal_alloc = ideal.get(symbol, 0) * 100

        if recommendation:
            post_plan_value = max(0.0, value_eur + recommendation.value_delta_eur)
        else:
            post_plan_value = value_eur
        post_plan_alloc = (post_plan_value / post_plan_total_value * 100) if post_plan_total_value > 0 else 0

        closes = [float(p["close"]) for p in reversed(prices) if p.get("close") is not None]
        raw_signal = compute_contrarian_signal(closes)
        signal = {**raw_signal, **(effective_signals.get(symbol) or {})}

        maybe_fx_rate = deps.currency.get_rate(sec_currency)
        if inspect.isawaitable(maybe_fx_rate):
            maybe_fx_rate = await maybe_fx_rate
        try:
            fx_rate = float(maybe_fx_rate)
        except (TypeError, ValueError):
            fx_rate = 1.0
        lot_profile = classify_lot_size(
            price=current_price,
            lot_size=min_lot,
            fx_rate_to_eur=fx_rate,
            portfolio_value_eur=total_value if total_value > 0 else 1.0,
            fee_fixed_eur=fee_fixed,
            fee_pct=fee_pct,
            standard_max_pct=lot_standard_max_pct,
            coarse_max_pct=lot_coarse_max_pct,
        )
        preference = preference_snapshot(sec)
        decomposition = allocation_decomposition.get(symbol, {})
        sleeve = sleeves_map.get(symbol)
        if sleeve is None:
            sleeve = decomposition.get("allocation_sleeve")
        if sleeve is None:
            sleeve = "opportunity" if float(signal.get("opp_score", 0.0) or 0.0) >= min_opp_score else "core"
        contrarian_score = float(signal.get("opp_score", 0.0) or 0.0)

        # Recommendation info
        rec_info = None
        if recommendation:
            rec_info = {
                "action": recommendation.action,
                "quantity": recommendation.quantity,
                "value_delta_eur": recommendation.value_delta_eur,
                "reason": recommendation.reason,
                "reason_code": recommendation.reason_code,
                "priority": recommendation.priority,
                "execution_rank": recommendation.execution_rank,
                "contrarian_score": recommendation.contrarian_score,
                "target_gap_ratio": recommendation.target_gap_ratio,
                "timing_eligible": recommendation.timing_eligible,
                "is_fallback": recommendation.is_fallback,
            }

        result.append(
            {
                "symbol": symbol,
                "name": sec.get("name", symbol),
                "currency": sec_currency,
                "geography": sec.get("geography"),
                "industry": sec.get("industry"),
                "min_lot": sec.get("min_lot", 1),
                "active": sec.get("active", 1),
                "allow_buy": sec.get("allow_buy", 1),
                "allow_sell": sec.get("allow_sell", 1),
                "user_multiplier": preference["user_multiplier"],
                "user_multiplier_age_weeks": preference["user_multiplier_age_weeks"],
                "user_multiplier_updated_at": sec.get("user_multiplier_updated_at"),
                "user_multiplier_source": sec.get("user_multiplier_source"),
                "user_multiplier_analysis": sec.get("user_multiplier_analysis"),
                "aliases": sec.get("aliases"),
                # Position data
                "has_position": has_position,
                "quantity": quantity,
                "avg_cost": avg_cost,
                "current_price": current_price,
                "value_local": value_local,
                "value_eur": value_eur,
                "profit_pct": profit_pct,
                "profit_value": profit_value,
                "profit_value_eur": profit_value_eur,
                # Price anomaly warning
                "price_warning": price_warning,
                # Allocations
                "current_allocation": current_alloc,
                "post_plan_allocation": post_plan_alloc,
                "ideal_allocation": ideal_alloc,
                # Score data
                "contrarian_score": contrarian_score,
                # Deterministic strategy diagnostics
                "opp_score": signal.get("opp_score"),
                "opp_score_raw": signal.get("opp_score_raw", raw_signal.get("opp_score")),
                "dip_score": signal.get("dip_score"),
                "capitulation_score": signal.get("capitulation_score"),
                "cycle_turn": signal.get("cycle_turn"),
                "freefall_block": signal.get("freefall_block"),
                "ticket_pct": lot_profile["ticket_pct"],
                "lot_class": lot_profile["lot_class"],
                "sleeve": sleeve,
                "allocation_sleeves": global_decomposition or None,
                "baseline_target_pct": float(decomposition.get("baseline_target_pct", 0.0) or 0.0) * 100,
                "clara_target_pct": float(decomposition.get("clara_target_pct", 0.0) or 0.0) * 100,
                "opportunity_target_pct": float(decomposition.get("opportunity_target_pct", 0.0) or 0.0) * 100,
                "final_target_pct": float(decomposition.get("final_target_pct", ideal.get(symbol, 0)) or 0.0) * 100,
                # Price history (simplified for charts, oldest first)
                "prices": [{"date": p["date"], "close": p["close"]} for p in reversed(prices)],
                # Recommendation
                "recommendation": rec_info,
            }
        )

    return result
