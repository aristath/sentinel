"""Securities and prices API routes."""

import inspect
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from typing_extensions import Annotated

from sentinel.api.dependencies import CommonDependencies, get_common_deps
from sentinel.security import Security
from sentinel.strategy import classify_lot_size, compute_contrarian_signal

router = APIRouter(prefix="/securities", tags=["securities"])
prices_router = APIRouter(prefix="/prices", tags=["prices"])


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
    if not symbol:
        raise HTTPException(status_code=400, detail="Symbol is required")

    # Check if already exists
    existing = await deps.db.get_security(symbol)
    if existing:
        raise HTTPException(status_code=400, detail="Security already exists")

    # Get info from broker
    info = await deps.broker.get_security_info(symbol)
    if not info:
        raise HTTPException(status_code=404, detail="Security not found in broker")

    # Extract relevant data
    name = info.get("short_name", info.get("name", symbol))
    currency = info.get("currency", info.get("curr", "EUR"))
    market_id = str(info.get("mrkt", {}).get("mkt_id", ""))
    min_lot = int(float(info.get("lot", 1)))

    # Save to database
    await deps.db.upsert_security(
        symbol,
        name=name,
        currency=currency,
        market_id=market_id,
        min_lot=min_lot,
        active=True,
        geography=data.get("geography", ""),
        industry=data.get("industry", ""),
    )

    # Save full metadata
    await deps.db.update_security_metadata(symbol, info, market_id)

    # Fetch and save 20 years of historical prices (TraderNet getHloc has no documented max range)
    prices_data = await deps.broker.get_historical_prices_bulk([symbol], years=20)
    prices = prices_data.get(symbol, [])
    if prices:
        await deps.db.save_prices(symbol, prices)

    return {"status": "ok", "symbol": symbol, "name": name, "prices_count": len(prices)}


@router.delete("/{symbol}")
async def delete_security(
    symbol: str,
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
    sell_position: bool = True,
) -> dict[str, Any]:
    """Remove a security from the active universe. Optionally sells any existing position first.

    Soft-deletes: marks the security as inactive (active=0, allow_buy=0, allow_sell=0).
    Deletes current-state data (positions) but preserves historical prices and trades.
    """
    # Check if exists
    existing = await deps.db.get_security(symbol)
    if not existing:
        raise HTTPException(status_code=404, detail="Security not found")

    # Check for position
    position = await deps.db.get_position(symbol)
    quantity = position.get("quantity", 0) if position else 0

    # Sell position if requested and exists
    if sell_position and quantity > 0:
        security = Security(symbol)
        await security.load()
        order_id = await security.sell(quantity)
        if not order_id:
            raise HTTPException(status_code=400, detail="Failed to sell position")

    # Soft-delete: mark inactive and disable trading, but preserve historical data
    await deps.db.conn.execute(
        "UPDATE securities SET active = 0, allow_buy = 0, allow_sell = 0 WHERE symbol = ?",
        (symbol,),
    )
    # Delete current-state data (not historical)
    await deps.db.conn.execute("DELETE FROM positions WHERE symbol = ?", (symbol,))
    await deps.db.conn.commit()

    return {"status": "ok", "sold_quantity": quantity if sell_position else 0}


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


@router.get("/{symbol}")
async def get_security(symbol: str) -> dict[str, Any]:
    """Get a specific security."""
    security = Security(symbol)
    if not await security.exists():
        raise HTTPException(status_code=404, detail="Security not found")
    await security.load()
    return {
        "symbol": security.symbol,
        "name": security.name,
        "currency": security.currency,
        "geography": security.geography,
        "industry": security.industry,
        "aliases": security.aliases,
        "quantity": security.quantity,
        "current_price": security.current_price,
    }


@router.put("/{symbol}")
async def update_security(
    symbol: str,
    data: dict,
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict[str, str]:
    """Update security metadata and execution controls."""
    existing = await deps.db.get_security(symbol)
    if not existing:
        raise HTTPException(status_code=404, detail="Security not found")

    # Only allow updating specific fields
    allowed_fields = [
        "geography",
        "industry",
        "aliases",
        "allow_buy",
        "allow_sell",
        "user_multiplier",
        "active",
    ]
    updates = {k: v for k, v in data.items() if k in allowed_fields}

    if updates:
        await deps.db.upsert_security(symbol, **updates)

    return {"status": "ok"}


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
    from sentinel.portfolio import Portfolio
    from sentinel.price_validator import PriceValidator, get_price_anomaly_warning
    from sentinel.utils.scoring import adjust_score_for_conviction

    # Get all active securities
    securities = await deps.db.get_all_securities(active_only=True)
    if not securities:
        return []

    all_symbols = [sec["symbol"] for sec in securities]

    planner = Planner(db=deps.db, broker=deps.broker)

    # Fetch all data sources
    portfolio = Portfolio(db=deps.db, broker=deps.broker)
    analyzer = PortfolioAnalyzer(db=deps.db, portfolio=portfolio, currency=deps.currency)
    if as_of is None:
        positions = await deps.db.get_all_positions()
    else:
        positions = await analyzer.get_positions_as_of(as_of)
    positions_map = {p["symbol"]: p for p in positions}

    # Recommendations using settings default for min_trade_value
    recommendations = await planner.get_recommendations(as_of_date=as_of)
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

    # Total portfolio value in EUR
    total_value = 0.0
    for pos in positions:
        price = latest_prices_map.get(pos["symbol"], pos.get("current_price", 0))
        qty = pos.get("quantity", 0)
        pos_currency = pos.get("currency", "EUR")
        total_value += await deps.currency.to_eur(price * qty, pos_currency)

    # Post-plan total value (current + net effect of all recommendations)
    post_plan_total_value = total_value
    for rec in recommendations:
        post_plan_total_value += rec.value_delta_eur

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
    core_floor_raw = await deps.settings.get("strategy_core_floor_pct", 0.05)
    min_opp_raw = await deps.settings.get("strategy_min_opp_score", 0.55)
    fee_fixed = float(2.0 if fee_fixed_raw is None else fee_fixed_raw)
    fee_pct = float(0.2 if fee_pct_raw is None else fee_pct_raw) / 100.0
    lot_standard_max_pct = float(0.08 if lot_standard_raw is None else lot_standard_raw)
    lot_coarse_max_pct = float(0.30 if lot_coarse_raw is None else lot_coarse_raw)
    core_floor_pct = float(0.05 if core_floor_raw is None else core_floor_raw)
    min_opp_score = float(0.55 if min_opp_raw is None else min_opp_raw)
    cache_getter = getattr(deps.db, "cache_get", None)
    sleeves_map = {}
    if callable(cache_getter):
        maybe_cache = cache_getter("planner:contrarian_sleeves")
        if inspect.isawaitable(maybe_cache):
            maybe_cache = await maybe_cache
        if isinstance(maybe_cache, (str, bytes, bytearray)):
            sleeves_map = json.loads(maybe_cache) if maybe_cache else {}

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
        current_price = quote.get("price", 0) if quote else 0
        if as_of is not None:
            current_price = latest_prices_map.get(symbol, 0)
            if current_price <= 0 and prices:
                current_price = prices[0]["close"]
        else:
            if current_price <= 0 and position:
                current_price = position.get("current_price", 0)
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
            post_plan_value = value_eur + recommendation.value_delta_eur
        else:
            post_plan_value = value_eur
        post_plan_alloc = (post_plan_value / post_plan_total_value * 100) if post_plan_total_value > 0 else 0

        closes = [float(p["close"]) for p in reversed(prices) if p.get("close") is not None]
        signal = compute_contrarian_signal(closes)

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
        user_multiplier = sec.get("user_multiplier", 0.5) or 0.5
        sleeve = sleeves_map.get(symbol)
        if sleeve is None:
            sleeve = "opportunity" if float(signal.get("opp_score", 0.0) or 0.0) >= min_opp_score else "core"
        core_floor_active = bool(
            sleeve == "core" and has_position and total_value > 0 and ((value_eur / total_value) <= core_floor_pct)
        )

        # Contrarian score with user conviction adjustment
        adjusted_contrarian_score = adjust_score_for_conviction(float(signal.get("opp_score", 0.0)), user_multiplier)

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
                "user_multiplier": sec.get("user_multiplier", 0.5),
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
                # Score data (adjusted by user conviction)
                "contrarian_score": adjusted_contrarian_score,
                # Deterministic strategy diagnostics
                "opp_score": signal.get("opp_score"),
                "dip_score": signal.get("dip_score"),
                "capitulation_score": signal.get("capitulation_score"),
                "cycle_turn": signal.get("cycle_turn"),
                "freefall_block": signal.get("freefall_block"),
                "ticket_pct": lot_profile["ticket_pct"],
                "lot_class": lot_profile["lot_class"],
                "sleeve": sleeve,
                "core_floor_active": core_floor_active,
                # Price history (simplified for charts, oldest first)
                "prices": [{"date": p["date"], "close": p["close"]} for p in reversed(prices)],
                # Recommendation
                "recommendation": rec_info,
            }
        )

    return result
