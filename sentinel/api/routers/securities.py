"""Securities and prices API routes."""

from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from typing_extensions import Annotated

from sentinel.api.dependencies import CommonDependencies, get_common_deps
from sentinel.security import Security

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
    Deletes current-state data (positions, scores) but preserves historical prices and trades.
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
    await deps.db.conn.execute("DELETE FROM scores WHERE symbol = ?", (symbol,))
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
        "score": await security.get_score(),
    }


@router.put("/{symbol}")
async def update_security(
    symbol: str,
    data: dict,
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict[str, str]:
    """Update security metadata (geography, industry, allow_buy/sell, user_multiplier, ml settings)."""
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
        "ml_enabled",
        "ml_blend_ratio",
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


def _end_of_day_utc_ts(date_str: str) -> int:
    """Unix timestamp for end of date_str (YYYY-MM-DD) in UTC."""
    dt = datetime.strptime(date_str + " 23:59:59", "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


async def _get_blended_prediction(
    deps: CommonDependencies,
    symbol: str,
    as_of_ts: int | None = None,
) -> dict:
    predictions = await _get_blended_predictions(deps, [symbol], as_of_ts=as_of_ts)
    return predictions.get(symbol, {})


async def _get_blended_predictions(
    deps: CommonDependencies,
    symbols: list[str],
    as_of_ts: int | None = None,
) -> dict[str, dict]:
    """Load blended ML scores for symbols from sentinel-ml service."""
    if not symbols:
        return {}

    base_url = str(await deps.db.get_setting("ml_service_base_url", "http://localhost:8001")).rstrip("/")
    params: dict[str, str | int] = {"symbols": ",".join(symbols)}
    if as_of_ts is not None:
        params["as_of_ts"] = as_of_ts

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(f"{base_url}/ml/latest-scores", params=params)
            resp.raise_for_status()
            payload = resp.json()
            scores = payload.get("scores", {})
            return scores if isinstance(scores, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


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
        as_of: Optional date (YYYY-MM-DD). When set, scores and ML predictions
            are returned as of that date (wavelet score and ML prediction on or before that date).

    Returns all securities with positions, prices, scores, allocations,
    and recommendations.
    """
    import json

    from sentinel.planner import Planner
    from sentinel.price_validator import PriceValidator, get_price_anomaly_warning
    from sentinel.utils.scoring import adjust_score_for_conviction

    # Get all active securities
    securities = await deps.db.get_all_securities(active_only=True)
    if not securities:
        return []

    all_symbols = [sec["symbol"] for sec in securities]

    planner = Planner()

    # Fetch all data sources
    positions = await deps.db.get_all_positions()
    positions_map = {p["symbol"]: p for p in positions}

    if as_of is not None:
        as_of_ts = _end_of_day_utc_ts(as_of)
        # Scores as of date: latest row per symbol with calculated_at <= as_of_ts
        cursor = await deps.db.conn.execute(
            """SELECT * FROM (
                   SELECT *, ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY calculated_at DESC, id DESC) AS rn
                   FROM scores WHERE calculated_at <= ?
               ) WHERE rn = 1""",
            (as_of_ts,),
        )
        scores = await cursor.fetchall()
        scores_map = {}
        for s in scores:
            d = dict(s)
            d.pop("rn", None)
            scores_map[d["symbol"]] = d
        ml_preds_map = await _get_blended_predictions(deps, all_symbols, as_of_ts=as_of_ts)
    else:
        cursor = await deps.db.conn.execute("SELECT * FROM scores")
        scores = await cursor.fetchall()
        scores_map = {s["symbol"]: dict(s) for s in scores}

        ml_preds_map = await _get_blended_predictions(deps, all_symbols)

    # Recommendations using settings default for min_trade_value
    recommendations = await planner.get_recommendations()
    recommendations_map = {r.symbol: r for r in recommendations}

    # Ideal and current allocations
    ideal = await planner.calculate_ideal_portfolio()
    current_allocs = await planner.get_current_allocations()

    # Live quotes
    current_quotes = await deps.broker.get_quotes(all_symbols)

    # Total portfolio value in EUR
    total_value = 0.0
    for pos in positions:
        price = pos.get("current_price", 0)
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
    all_prices_raw = await deps.db.get_prices_bulk(all_symbols, days=days)

    validator = PriceValidator()
    all_prices_validated = {}
    for symbol, raw_prices in all_prices_raw.items():
        all_prices_validated[symbol] = validator.validate_price_series_desc(raw_prices)

    # Build unified response
    result = []
    for sec in securities:
        symbol = sec["symbol"]
        position = positions_map.get(symbol)
        score_data = scores_map.get(symbol, {})
        recommendation = recommendations_map.get(symbol)
        prices = all_prices_validated.get(symbol, [])

        # Position data
        has_position = position is not None and position.get("quantity", 0) > 0
        quantity = position.get("quantity", 0) if position else 0
        avg_cost = position.get("avg_cost", 0) if position else 0

        # Current price: prefer live quote, fallback to position, then historical
        quote = current_quotes.get(symbol)
        current_price = quote.get("price", 0) if quote else 0
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

        # Parse score components
        components = {}
        if score_data.get("components"):
            try:
                components = (
                    json.loads(score_data["components"])
                    if isinstance(score_data["components"], str)
                    else score_data["components"]
                )
            except (json.JSONDecodeError, TypeError, ValueError):
                pass

        # Expected return with user conviction adjustment
        user_multiplier = sec.get("user_multiplier", 1.0) or 1.0
        ml_pred = ml_preds_map.get(symbol, {})
        ml_final_score = ml_pred.get("final_score", ml_pred.get("ml_score"))
        fallback_score = components.get("expected_return", 0) or 0
        base_expected_return = float(ml_final_score if ml_final_score is not None else fallback_score)
        adjusted_expected_return = adjust_score_for_conviction(base_expected_return, user_multiplier)
        conviction_boost = adjusted_expected_return - base_expected_return

        # Recommendation info
        rec_info = None
        if recommendation:
            rec_info = {
                "action": recommendation.action,
                "quantity": recommendation.quantity,
                "value_delta_eur": recommendation.value_delta_eur,
                "reason": recommendation.reason,
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
                "user_multiplier": sec.get("user_multiplier", 1.0),
                "ml_enabled": sec.get("ml_enabled", 0),
                "ml_blend_ratio": sec.get("ml_blend_ratio", 0.5),
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
                "target_allocation": ideal_alloc,
                # Score data (adjusted by user conviction)
                "score": (score_data.get("score") or 0) + conviction_boost,
                "expected_return": adjusted_expected_return,
                "base_expected_return": base_expected_return,
                "score_components": components,
                # ML prediction breakdown
                "wavelet_score": score_data.get("score"),
                "ml_score": ml_pred.get("ml_score"),
                # Price history (simplified for charts, oldest first)
                "prices": [{"date": p["date"], "close": p["close"]} for p in reversed(prices)],
                # Recommendation
                "recommendation": rec_info,
            }
        )

    return result


# Scores router
scores_router = APIRouter(prefix="/scores", tags=["scores"])


@scores_router.post("/calculate")
async def calculate_scores() -> dict[str, int]:
    """Calculate scores for all securities."""
    from sentinel.analyzer import Analyzer

    analyzer = Analyzer()
    count = await analyzer.update_scores()
    return {"calculated": count}


@scores_router.get("")
async def get_scores(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> list[dict]:
    """Get latest score per security (one row per symbol)."""
    cursor = await deps.db.conn.execute(
        """SELECT s.id, s.symbol, s.score, s.components, s.calculated_at FROM scores s
           INNER JOIN (
             SELECT symbol, MAX(calculated_at) AS calculated_at FROM scores GROUP BY symbol
           ) latest ON s.symbol = latest.symbol AND s.calculated_at = latest.calculated_at
           ORDER BY s.score DESC, s.id DESC"""
    )
    rows = await cursor.fetchall()
    # One row per symbol (tie-break same calculated_at by max id)
    by_symbol: dict[str, dict] = {}
    for row in rows:
        r = dict(row)
        sym = r["symbol"]
        if sym not in by_symbol or r["id"] > by_symbol[sym]["id"]:
            by_symbol[sym] = r
    return sorted(by_symbol.values(), key=lambda x: (-(x["score"] or 0), -(x.get("id") or 0)))
