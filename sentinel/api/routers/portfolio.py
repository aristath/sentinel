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
    period: str = "1Y",
) -> dict[str, Any]:
    """
    Get portfolio P&L history for charting.

    Args:
        period: Time period - 1M, 3M, 6M, 1Y, MAX

    Returns:
        snapshots: List of {date, pnl_eur, pnl_pct}
        summary: {start_value, end_value, pnl_absolute, pnl_percent}
    """
    # Map period to days
    period_days = {
        "1M": 30,
        "3M": 90,
        "6M": 180,
        "1Y": 365,
        "MAX": None,
    }
    days = period_days.get(period, 365)

    # Get existing snapshots
    snapshots = await deps.db.get_portfolio_snapshots(days)

    # Check if we need to backfill
    latest_date = await deps.db.get_latest_snapshot_date()
    today = date_type.today().isoformat()

    # If no snapshots or latest is not today, trigger backfill
    if not latest_date or latest_date < today:
        await _backfill_portfolio_snapshots(deps.db, deps.currency)
        # Reload snapshots after backfill
        snapshots = await deps.db.get_portfolio_snapshots(days)

    # Filter by period
    if days:
        start_date = (date_type.today() - timedelta(days=days)).isoformat()
        snapshots = [s for s in snapshots if s["date"] >= start_date]

    if not snapshots:
        return {"snapshots": [], "summary": None}

    # Build response with P&L percentages
    result_snapshots = []
    for snap in snapshots:
        net_deposits = snap.get("net_deposits_eur", 0) or 0
        total_value = snap.get("total_value_eur", 0) or 0

        # P&L relative to net deposits at that point in time
        pnl_eur = total_value - net_deposits
        pnl_pct = (pnl_eur / net_deposits * 100) if net_deposits > 0 else 0

        result_snapshots.append(
            {
                "date": snap["date"],
                "total_value_eur": total_value,
                "net_deposits_eur": net_deposits,
                "pnl_eur": round(pnl_eur, 2),
                "pnl_pct": round(pnl_pct, 2),
            }
        )

    # Calculate summary
    first = result_snapshots[0]
    last = result_snapshots[-1]

    summary = {
        "start_value": first["total_value_eur"],
        "end_value": last["total_value_eur"],
        "start_net_deposits": first["net_deposits_eur"],
        "end_net_deposits": last["net_deposits_eur"],
        "pnl_absolute": last["pnl_eur"],
        "pnl_percent": last["pnl_pct"],
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
) -> dict[str, dict]:
    """Get allocation targets as {geography: {name: weight}, industry: {name: weight}}."""
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
    """Get available geographies from securities and allocation_targets only (no defaults)."""
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
    """Get available industries from securities and allocation_targets only (no defaults)."""
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
    """Delete a geography target. Category disappears from UI if not used by any security."""
    await deps.db.delete_allocation_target("geography", name)
    return {"status": "ok"}


@allocation_router.delete("/targets/industry/{name}")
async def delete_industry_target(
    name: str,
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict[str, str]:
    """Delete an industry target. Category disappears from UI if not used by any security."""
    await deps.db.delete_allocation_target("industry", name)
    return {"status": "ok"}
