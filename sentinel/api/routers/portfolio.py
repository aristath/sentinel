"""Portfolio and allocation API routes."""

import bisect
import logging
from datetime import date as date_type
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends
from typing_extensions import Annotated

from sentinel.api.dependencies import CommonDependencies, get_common_deps
from sentinel.portfolio import Portfolio
from sentinel.services.portfolio import PortfolioService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/portfolio", tags=["portfolio"])
allocation_router = APIRouter(prefix="/allocation", tags=["allocation"])
targets_router = APIRouter(prefix="/allocation-targets", tags=["allocation"])


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


@router.post("/sync")
async def sync_portfolio() -> dict[str, str]:
    """Sync portfolio from broker."""
    service = PortfolioService()
    return await service.sync_portfolio()


@router.get("/allocations")
async def get_portfolio_allocations() -> dict[str, Any]:
    """Get current vs target allocations."""
    service = PortfolioService()
    return await service.get_allocation_comparison()


async def _backfill_portfolio_snapshots(db, currency) -> None:
    """Reconstruct historical portfolio snapshots."""
    from sentinel.snapshot_service import SnapshotService

    service = SnapshotService(db, currency)
    await service.backfill()


def _ts_to_iso(ts: int) -> str:
    """Convert unix timestamp to YYYY-MM-DD string."""
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def _midnight_utc_ts(iso_date: str) -> int:
    """Convert YYYY-MM-DD to midnight UTC unix timestamp."""
    return int(datetime.strptime(iso_date, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())


@router.get("/pnl-history")
async def get_portfolio_pnl_history(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict[str, Any]:
    """
    Get portfolio P&L history for charting (hardcoded 1Y).

    Snapshots store only positions + cash. All derived metrics
    (total_value, net_deposits, returns) are computed at query time.
    """
    days = 365

    # Get daily snapshots (need extra 365 days for 1-year rolling window)
    snapshots = await deps.db.get_portfolio_snapshots(days + 365)

    # Check if we need to backfill
    latest_ts = await deps.db.get_latest_snapshot_date()
    today_ts = _midnight_utc_ts(date_type.today().isoformat())
    if not latest_ts or latest_ts < today_ts:
        await _backfill_portfolio_snapshots(deps.db, deps.currency)
        snapshots = await deps.db.get_portfolio_snapshots(days + 365)

    if not snapshots:
        return {"snapshots": [], "summary": None}

    # --- Compute net deposits from cash_flows ---
    cash_flows = await deps.db.get_cash_flows()
    cf_sorted = sorted(
        [cf for cf in cash_flows if cf["type_id"] in ("card", "card_payout")],
        key=lambda cf: cf["date"],
    )

    cumulative_deposits: dict[str, float] = {}
    running_nd = 0.0
    for cf in cf_sorted:
        amount_eur = await deps.currency.to_eur_for_date(cf["amount"], cf["currency"], cf["date"])
        running_nd += amount_eur
        cumulative_deposits[cf["date"]] = running_nd

    nd_dates = sorted(cumulative_deposits.keys())
    nd_values = [cumulative_deposits[d] for d in nd_dates]

    def _get_net_deposits_as_of(iso_date: str) -> float:
        idx = bisect.bisect_right(nd_dates, iso_date) - 1
        return nd_values[idx] if idx >= 0 else 0.0

    # --- Build daily data from snapshots ---
    daily = []
    for snap in snapshots:
        date_ts = snap["date"]
        data = snap["data"]
        iso_date = _ts_to_iso(date_ts)

        positions = data.get("positions", {})
        cash_eur = data.get("cash_eur", 0.0) or 0.0
        positions_value = sum(p.get("value_eur", 0) for p in positions.values())
        total_value = positions_value + cash_eur

        net_deposits = _get_net_deposits_as_of(iso_date)
        pnl_eur = total_value - net_deposits
        pnl_pct = (pnl_eur / net_deposits * 100) if net_deposits > 0 else 0.0

        daily.append(
            {
                "date": iso_date,
                "total_value_eur": round(total_value, 2),
                "net_deposits_eur": round(net_deposits, 2),
                "pnl_eur": round(pnl_eur, 2),
                "pnl_pct": round(pnl_pct, 2),
            }
        )

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


# Allocation Targets Routes
@targets_router.get("")
async def get_allocation_targets(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict[str, list]:
    """Get all allocation targets."""
    targets = await deps.db.get_allocation_targets()
    return {
        "geography": [t for t in targets if t["type"] == "geography"],
        "industry": [t for t in targets if t["type"] == "industry"],
    }


@targets_router.put("/{target_type}/{name}")
async def set_allocation_target(
    target_type: str,
    name: str,
    data: dict,
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict[str, str]:
    """Set an allocation target weight."""
    from fastapi import HTTPException

    if target_type not in ("geography", "industry"):
        raise HTTPException(status_code=400, detail="Invalid target type")
    await deps.db.set_allocation_target(target_type, name, data.get("weight", 1.0))
    return {"status": "ok"}


# Allocation Routes
@allocation_router.get("/current")
async def get_allocation_current() -> dict[str, Any]:
    """Get current allocation data formatted for radar charts."""
    portfolio = Portfolio()
    current = await portfolio.get_allocations()
    targets = await portfolio.get_target_allocations()

    # Format geography allocations
    geography = []
    all_geos = set(current.get("by_geography", {}).keys()) | set(targets.get("geography", {}).keys())
    for geo in sorted(all_geos):
        current_pct = current.get("by_geography", {}).get(geo, 0) * 100
        target_pct = targets.get("geography", {}).get(geo, 0) * 100
        geography.append(
            {
                "name": geo,
                "current_pct": current_pct,
                "target_pct": target_pct,
            }
        )

    # Format industry allocations
    industry = []
    all_inds = set(current.get("by_industry", {}).keys()) | set(targets.get("industry", {}).keys())
    for ind in sorted(all_inds):
        current_pct = current.get("by_industry", {}).get(ind, 0) * 100
        target_pct = targets.get("industry", {}).get(ind, 0) * 100
        industry.append(
            {
                "name": ind,
                "current_pct": current_pct,
                "target_pct": target_pct,
            }
        )

    return {
        "geography": geography,
        "industry": industry,
        "alerts": [],
    }


@allocation_router.get("/targets")
async def get_allocation_targets_formatted(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict[str, dict[str, float]]:
    """
    Get allocation targets as:
    {geography: {name: weight}, industry: {name: weight}}.
    """
    targets = await deps.db.get_allocation_targets()

    geography = {}
    industry = {}
    for t in targets:
        if t["type"] == "geography":
            geography[t["name"]] = t["weight"]
        elif t["type"] == "industry":
            industry[t["name"]] = t["weight"]

    return {"geography": geography, "industry": industry}


@allocation_router.get("/available-geographies")
async def get_available_geographies(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict[str, list]:
    """Get available geographies from securities and allocation_targets."""
    # Only from securities + allocation_targets, NOT defaults
    existing = await deps.db.get_categories()
    targets = await deps.db.get_allocation_targets()
    target_geos = {t["name"] for t in targets if t["type"] == "geography"}
    geographies = sorted(set(existing["geographies"]) | target_geos)
    return {"geographies": geographies}


@allocation_router.get("/available-industries")
async def get_available_industries(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict[str, list]:
    """Get available industries from securities and allocation_targets."""
    # Only from securities + allocation_targets, NOT defaults
    existing = await deps.db.get_categories()
    targets = await deps.db.get_allocation_targets()
    target_inds = {t["name"] for t in targets if t["type"] == "industry"}
    industries = sorted(set(existing["industries"]) | target_inds)
    return {"industries": industries}


@allocation_router.put("/targets/geography")
async def save_geography_targets(
    data: dict,
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict[str, str]:
    """Save all geography targets at once."""
    targets = data.get("targets", {})
    for name, weight in targets.items():
        await deps.db.set_allocation_target("geography", name, weight)
    return {"status": "ok"}


@allocation_router.put("/targets/industry")
async def save_industry_targets(
    data: dict,
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict[str, str]:
    """Save all industry targets at once."""
    targets = data.get("targets", {})
    for name, weight in targets.items():
        await deps.db.set_allocation_target("industry", name, weight)
    return {"status": "ok"}


@allocation_router.delete("/targets/geography/{name}")
async def delete_geography_target(
    name: str,
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict[str, str]:
    """
    Delete a geography target.
    Category disappears from UI if not used by any security.
    """
    await deps.db.delete_allocation_target("geography", name)
    return {"status": "ok"}


@allocation_router.delete("/targets/industry/{name}")
async def delete_industry_target(
    name: str,
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict[str, str]:
    """
    Delete an industry target.
    Category disappears from UI if not used by any security.
    """
    await deps.db.delete_allocation_target("industry", name)
    return {"status": "ok"}
