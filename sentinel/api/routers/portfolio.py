"""Portfolio and allocation API routes."""

from datetime import date as date_type
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends
from typing_extensions import Annotated

from sentinel.api.dependencies import CommonDependencies, get_common_deps
from sentinel.portfolio import Portfolio
from sentinel.services.portfolio import PortfolioService

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


@router.get("/pnl-history")
async def get_portfolio_pnl_history(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict[str, Any]:
    """
    Get portfolio P&L history for charting (hardcoded 1Y).

    All three series use 14-day windows with 7-day steps.
    ML predicts 14-day forward returns, so ML/wavelet are offset by 14 days:
      predictions from [i-27, i-14] cover returns ending between i-13 and i.

    Returns weekly-sampled data points with:
    - actual_ann_return: 14-day rolling TWR as %
    - wavelet_ann_return: 14-day avg of raw wavelet scores, offset 14 days
    - ml_ann_return: 14-day avg of predicted_return as %, offset 14 days
    - target_ann_return in summary
    """
    days = 365

    # Get daily snapshots (need extra 28 days for 14-day window + 14-day offset)
    snapshots = await deps.db.get_portfolio_snapshots(days + 28)

    # Check if we need to backfill
    latest_date = await deps.db.get_latest_snapshot_date()
    today = date_type.today().isoformat()
    if not latest_date or latest_date < today:
        await _backfill_portfolio_snapshots(deps.db, deps.currency)
        snapshots = await deps.db.get_portfolio_snapshots(days + 44)

    if not snapshots:
        return {"snapshots": [], "summary": None}

    # Build daily data arrays from raw snapshots
    daily = []
    for i, snap in enumerate(snapshots):
        net_deposits = snap.get("net_deposits_eur", 0) or 0
        total_value = snap.get("total_value_eur", 0) or 0
        pnl_eur = snap.get("unrealized_pnl_eur", 0) or (total_value - net_deposits)

        denominator = net_deposits
        if i > 0:
            prev_nd = snapshots[i - 1].get("net_deposits_eur", 0) or 0
            if net_deposits > prev_nd:
                denominator = prev_nd

        pnl_pct = (pnl_eur / denominator * 100) if denominator > 0 else 0

        daily.append(
            {
                "date": snap["date"],
                "total_value_eur": total_value,
                "net_deposits_eur": net_deposits,
                "pnl_eur": round(pnl_eur, 2),
                "pnl_pct": round(pnl_pct, 2),
                "wavelet_score": snap.get("avg_wavelet_score"),
                "ml_predicted_return": snap.get("avg_ml_score"),
            }
        )

    # Determine the 1Y output range (indices into daily array)
    start_date = (date_type.today() - timedelta(days=days)).isoformat()
    output_start = 0
    for idx, d in enumerate(daily):
        if d["date"] >= start_date:
            output_start = idx
            break

    # Sample at 7-day steps within the 1Y range
    window = 14  # 14-day rolling window (matches ML prediction horizon)
    offset = 14  # ML predictions are 14-day forward-looking

    result_snapshots = []
    i = output_start
    while i < len(daily):
        d = daily[i]
        point = {
            "date": d["date"],
            "total_value_eur": d["total_value_eur"],
            "net_deposits_eur": d["net_deposits_eur"],
            "pnl_eur": d["pnl_eur"],
            "pnl_pct": d["pnl_pct"],
        }

        # Actual: 14-day rolling TWR as %
        if i >= window:
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

        # Prediction window: [i-27, i-14] — offset by 14 days
        p_start = max(0, i - offset - window + 1)
        p_end = max(0, i - offset + 1)

        # Wavelet: 14-day avg of raw scores, offset 14 days
        w_vals = [daily[j]["wavelet_score"] for j in range(p_start, p_end) if daily[j]["wavelet_score"] is not None]
        if w_vals:
            point["wavelet_ann_return"] = round(sum(w_vals) / len(w_vals), 4)
        else:
            point["wavelet_ann_return"] = None

        # ML: 14-day avg of predicted_return (14-day forward), offset 14 days, as %
        m_vals = [
            daily[j]["ml_predicted_return"]
            for j in range(p_start, p_end)
            if daily[j]["ml_predicted_return"] is not None
        ]
        if m_vals:
            point["ml_ann_return"] = round(sum(m_vals) / len(m_vals) * 100.0, 2)
        else:
            point["ml_ann_return"] = None

        result_snapshots.append(point)
        i += 7  # 1-week step

    if not result_snapshots:
        return {"snapshots": [], "summary": None}

    first = result_snapshots[0]
    last = result_snapshots[-1]

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
