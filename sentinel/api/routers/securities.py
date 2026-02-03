"""Securities and prices API routes."""

from typing import Any

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

    # Fetch and save 10 years of historical prices
    prices_data = await deps.broker.get_historical_prices_bulk([symbol], years=10)
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
    """Delete a security from the universe. Optionally sells any existing position first."""
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

    # Delete all data for this security from database
    await deps.db.conn.execute("DELETE FROM securities WHERE symbol = ?", (symbol,))
    await deps.db.conn.execute("DELETE FROM positions WHERE symbol = ?", (symbol,))
    await deps.db.conn.execute("DELETE FROM prices WHERE symbol = ?", (symbol,))
    await deps.db.conn.execute("DELETE FROM trades WHERE symbol = ?", (symbol,))
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


@unified_router.get("")
async def get_unified_view(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
    period: str = "1Y",
) -> list[dict]:
    """
    Get aggregated data for unified security cards view.

    Args:
        period: Price history period - 1M, 1Y, 5Y, 10Y

    Returns all securities with their positions, prices, scores, and recommendations.
    """
    import json

    from sentinel.planner import Planner

    # Get planner recommendations
    planner = Planner()
    recommendations = await planner.get_recommendations(min_trade_value=0)
    rec_map = {r.symbol: r for r in recommendations}

    # Get all securities
    securities = await deps.db.get_all_securities(active_only=True)

    # Short-circuit if no securities exist
    if not securities:
        return []

    # Get portfolio for position info
    from sentinel.portfolio import Portfolio

    portfolio = Portfolio()
    positions = await portfolio.positions()
    pos_map = {p["symbol"]: p for p in positions}

    # Get scores for all securities
    query = "SELECT symbol, score, components FROM scores WHERE symbol IN ({})".format(",".join("?" * len(securities)))  # noqa: S608
    cursor = await deps.db.conn.execute(query, tuple(s["symbol"] for s in securities))
    score_rows = await cursor.fetchall()
    score_map = {row["symbol"]: dict(row) for row in score_rows}

    # Build unified view
    result = []
    for sec in securities:
        symbol = sec["symbol"]
        position = pos_map.get(symbol, {})
        score_data = score_map.get(symbol, {})
        rec = rec_map.get(symbol)

        # Get prices
        security = Security(symbol)
        prices = await security.get_historical_prices({"1M": 30, "1Y": 365, "5Y": 1825, "10Y": 3650}.get(period, 365))

        # Get recommendation info
        rec_info = None
        if rec:
            rec_info = {
                "action": rec.action,
                "priority": rec.priority,
                "value_delta_eur": rec.value_delta_eur,
                "reason": rec.reason,
            }

        # Parse components
        components = {}
        if score_data.get("components"):
            try:
                components = json.loads(score_data["components"])
            except json.JSONDecodeError:
                pass

        result.append(
            {
                "symbol": symbol,
                "name": sec.get("name", symbol),
                "currency": sec.get("currency", "EUR"),
                "geography": sec.get("geography", ""),
                "industry": sec.get("industry", ""),
                "score": score_data.get("score"),
                "components": components,
                "position": {
                    "quantity": position.get("quantity", 0),
                    "avg_cost": position.get("avg_cost", 0),
                    "current_price": position.get("current_price"),
                }
                if position
                else None,
                "prices": prices,
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
    """Get all security scores."""
    cursor = await deps.db.conn.execute(
        "SELECT symbol, score, components, calculated_at FROM scores ORDER BY score DESC"
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]
