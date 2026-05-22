"""Portfolio API routes."""

import logging
from datetime import date as date_type
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from typing_extensions import Annotated

from sentinel.api.dependencies import CommonDependencies, get_common_deps
from sentinel.freedom24_web import Freedom24WebClient
from sentinel.services.portfolio import PortfolioService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("")
async def get_portfolio(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict[str, Any]:
    """Get current portfolio state."""
    service = PortfolioService(
        db=deps.db,
        portfolio=None,  # Uses singleton
        currency=deps.currency,
    )
    return await service.get_portfolio_state()


@router.get("/structure")
async def get_portfolio_structure(force: bool = False) -> dict[str, Any]:
    """PRAAMS portfolio analysis from freedom24.com (rating, risk/return radar,
    sector/region/currency breakdowns, replacement recommendations).

    Requires `freedom24_login` and `freedom24_password` to be set. Result is
    cached in memory for 5 minutes; pass ?force=true to bypass.
    """
    data = await Freedom24WebClient().get_portfolio_structure(force_refresh=force)
    if data is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Could not fetch portfolio structure. Check freedom24_login / "
                "freedom24_password settings and try again."
            ),
        )
    return data


@router.post("/sync")
async def sync_portfolio() -> dict[str, str]:
    """Sync portfolio from broker."""
    service = PortfolioService()
    return await service.sync_portfolio()


@router.get("/composition")
async def get_portfolio_composition(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict[str, Any]:
    """Portfolio composition + risk/return metrics for the sidebar widgets.

    Surfaces: composition breakdowns (% of EUR value by country, continent,
    industry, currency, asset class), portfolio-level metrics (1Y/5Y return,
    volatility, max drawdown, Sharpe, beta vs VWCE.EU, HHI concentration),
    and the six radar axes derived from those metrics. See
    `sentinel.portfolio_composition` for the math.
    """
    from sentinel.portfolio_composition import build_composition

    return await build_composition(deps.db, deps.currency, deps.settings)


@router.get("/cagr")
async def get_portfolio_cagr(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict[str, Any]:
    """Lightweight CAGR from inception for ambient display."""
    snapshots = await deps.db.get_portfolio_snapshots()
    if not snapshots:
        return {"cagr": 0.0, "years": 0.0, "target": 11.0}

    # Latest snapshot → final value
    latest = snapshots[-1]
    data = latest["data"]
    positions_value = sum(p.get("value_eur", 0) for p in data.get("positions", {}).values())
    final_value = positions_value + (data.get("cash_eur", 0.0) or 0.0)

    # Net deposits from card cash flows
    cash_flows = await deps.db.get_cash_flows()
    total_deposits = 0.0
    for cf in cash_flows:
        if cf["type_id"] in ("card", "card_payout"):
            amount_eur = await deps.currency.to_eur_for_date(cf["amount"], cf["currency"], cf["date"])
            total_deposits += amount_eur

    # Years from first snapshot to now
    first_ts = snapshots[0]["date"]
    last_ts = snapshots[-1]["date"]
    years = (last_ts - first_ts) / (365.25 * 86400)

    if years > 0 and total_deposits > 0 and final_value > 0:
        cagr = ((final_value / total_deposits) ** (1 / years) - 1) * 100
    else:
        cagr = 0.0

    return {
        "cagr": round(cagr, 2),
        "years": round(years, 2),
        "target": 11.0,
    }


@router.get("/pnl-history")
async def get_portfolio_pnl_history(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict[str, Any]:
    """
    Get portfolio P&L history for charting (hardcoded 1Y).

    Snapshots store only positions + cash. All derived metrics
    (total_value, net_deposits, returns) are computed at query time via
    the shared helpers in `sentinel.portfolio_composition`.
    """
    from sentinel.portfolio_composition import build_daily_pnl

    days = 365

    # Get daily snapshots (need extra 365 days for 1-year rolling window).
    # Snapshot maintenance is handled by scheduled jobs; avoid backfill work on request path.
    snapshots = await deps.db.get_portfolio_snapshots(days + 365)

    if not snapshots:
        return {"snapshots": [], "summary": None}

    # Cumulative net-deposits lookup keyed by ISO date. Card deposits +
    # withdrawals (card_payout) only — that's what funds the account.
    cash_flows = await deps.db.get_cash_flows()
    cf_sorted = sorted(
        [cf for cf in cash_flows if cf["type_id"] in ("card", "card_payout")],
        key=lambda cf: cf["date"],
    )
    deposits_by_date: dict[str, float] = {}
    running = 0.0
    for cf in cf_sorted:
        amount_eur = await deps.currency.to_eur_for_date(cf["amount"], cf["currency"], cf["date"])
        running += amount_eur
        deposits_by_date[cf["date"]] = running

    daily = build_daily_pnl(snapshots, deposits_by_date)

    # --- Build output with rolling TWR ---
    start_date = (date_type.today() - timedelta(days=days)).isoformat()
    output_start = 0
    for idx, d in enumerate(daily):
        if d["date"] >= start_date:
            output_start = idx
            break
    window = 365
    output_start = max(output_start, window)

    last_daily_idx = len(daily) - 1

    result_snapshots = []
    i = output_start
    while i < last_daily_idx + 1:
        in_future = i > last_daily_idx

        if in_future:
            last_date = datetime.strptime(daily[last_daily_idx]["date"], "%Y-%m-%d")
            future_date = last_date + timedelta(days=i - last_daily_idx)
            point = {
                "date": future_date.strftime("%Y-%m-%d"),
                "total_value_eur": None,
                "net_deposits_eur": None,
                "pnl_eur": None,
                "pnl_pct": None,
            }
        else:
            d = daily[i]
            point = {
                "date": d["date"],
                "total_value_eur": d["total_value_eur"],
                "net_deposits_eur": d["net_deposits_eur"],
                "pnl_eur": d["pnl_eur"],
                "pnl_pct": d["pnl_pct"],
            }

        # Actual: 365-day rolling TWR
        if not in_future and i >= window:
            cumulative = 1.0
            valid = True
            for j in range(i - window + 1, i + 1):
                prev_val = daily[j - 1]["total_value_eur"]
                curr_val = daily[j]["total_value_eur"]
                cash_flow = daily[j]["net_deposits_eur"] - daily[j - 1]["net_deposits_eur"]
                if prev_val and prev_val > 0:
                    hpr = (curr_val - prev_val - cash_flow) / prev_val
                    cumulative *= 1.0 + hpr
                else:
                    valid = False
                    break
            if valid:
                point["actual_ann_return"] = round((cumulative - 1.0) * 100.0, 2)
            else:
                point["actual_ann_return"] = None
        else:
            point["actual_ann_return"] = None

        result_snapshots.append(point)
        i += 1

    if not result_snapshots:
        return {"snapshots": [], "summary": None}

    first = result_snapshots[0]
    last = first
    for s in result_snapshots:
        if s["total_value_eur"] is not None:
            last = s

    summary = {
        "start_value": first["total_value_eur"],
        "end_value": last["total_value_eur"],
        "start_net_deposits": first["net_deposits_eur"],
        "end_net_deposits": last["net_deposits_eur"],
        "pnl_absolute": last["pnl_eur"],
        "pnl_percent": last["pnl_pct"],
        "target_ann_return": 11.0,
    }

    return {"snapshots": result_snapshots, "summary": summary}
