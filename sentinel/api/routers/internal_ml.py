"""Internal read-only data endpoints for Sentinel ML service."""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from typing_extensions import Annotated

from sentinel.api.dependencies import CommonDependencies, get_common_deps

router = APIRouter(prefix="/internal/ml", tags=["internal-ml"])


@router.get("/securities")
async def get_securities(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
    active_only: bool = True,
    ml_enabled_only: bool = False,
) -> list[dict]:
    rows = await deps.db.get_all_securities(active_only=active_only)
    if ml_enabled_only:
        rows = [row for row in rows if int(row.get("ml_enabled", 0)) == 1]
    return [dict(row) for row in rows]


@router.get("/prices/{symbol}")
async def get_prices(
    symbol: str,
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
    start_date: str | None = None,
    end_date: str | None = None,
    days: int = 3650,
) -> list[dict]:
    if start_date and end_date:
        cursor = await deps.db.conn.execute(
            """
            SELECT date, open, high, low, close, volume
            FROM prices
            WHERE symbol = ? AND date >= ? AND date <= ?
            ORDER BY date DESC
            """,
            (symbol, start_date, end_date),
        )
        return [dict(row) for row in await cursor.fetchall()]

    return await deps.db.get_prices(symbol, days=days, end_date=end_date)


@router.get("/scores")
async def get_scores(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
    symbols: str = Query(default=""),
    as_of_ts: int | None = None,
) -> dict[str, float]:
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    if not symbol_list:
        return {}

    if as_of_ts is None:
        values = await deps.db.get_scores(symbol_list)
        return {k: float(v) for k, v in values.items() if v is not None}

    symbols_json = json.dumps(symbol_list)
    sql = """
        SELECT symbol, score FROM (
            SELECT symbol, score, ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY calculated_at DESC, id DESC) AS rn
            FROM scores
            WHERE calculated_at <= ? AND symbol IN (SELECT value FROM json_each(?))
        )
        WHERE rn = 1
    """
    cursor = await deps.db.conn.execute(sql, (as_of_ts, symbols_json))
    rows = await cursor.fetchall()
    return {row["symbol"]: float(row["score"]) for row in rows if row["score"] is not None}


@router.get("/settings")
async def get_settings(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
    keys: str,
) -> dict:
    key_list = [k.strip() for k in keys.split(",") if k.strip()]
    result: dict[str, object] = {}
    for key in key_list:
        result[key] = await deps.settings.get(key)
    return result


@router.get("/quotes")
async def get_quotes(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
    symbols: str,
) -> dict:
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    if not symbol_list:
        return {}
    return await deps.broker.get_quotes(symbol_list)


@router.get("/portfolio-snapshots")
async def get_portfolio_snapshots(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
    days: int = 365,
) -> list[dict]:
    rows = await deps.db.get_portfolio_snapshots(days)
    return [dict(row) for row in rows]


@router.get("/security/{symbol}")
async def get_security(symbol: str, deps: Annotated[CommonDependencies, Depends(get_common_deps)]) -> dict:
    sec = await deps.db.get_security(symbol)
    if not sec:
        raise HTTPException(status_code=404, detail="Symbol not found")
    return dict(sec)


@router.get("/ml-enabled-securities")
async def get_ml_enabled_securities(deps: Annotated[CommonDependencies, Depends(get_common_deps)]) -> list[dict]:
    rows = await deps.db.get_ml_enabled_securities()
    return [dict(row) for row in rows]


@router.get("/as-of-end-ts")
async def as_of_end_ts(date: str) -> dict[str, int]:
    dt = datetime.strptime(f"{date} 23:59:59", "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    return {"timestamp": int(dt.timestamp())}


@router.post("/aggregates/delete")
async def delete_aggregates(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict[str, int]:
    cursor = await deps.db.conn.execute("DELETE FROM prices WHERE symbol LIKE '_AGG_%'")
    await deps.db.conn.commit()
    return {"deleted": cursor.rowcount}


@router.post("/aggregates/recompute")
async def recompute_aggregates(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict:
    from sentinel.aggregates import AggregateComputer

    computer = AggregateComputer(deps.db)
    return await computer.compute_all_aggregates()
