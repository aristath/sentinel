"""Allocation target management API endpoints."""

from typing import Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.infrastructure.dependencies import (
    AllocationRepositoryDep,
    ConcentrationAlertServiceDep,
    GroupingRepositoryDep,
    PortfolioServiceDep,
)
from app.modules.allocation.domain.models import AllocationTarget

router = APIRouter()


class CountryTargets(BaseModel):
    """Dynamic country allocation weights."""

    targets: dict[str, float]


class IndustryTargets(BaseModel):
    """Dynamic industry allocation weights."""

    targets: dict[str, float]


@router.get("/current")
async def get_current_allocation(
    portfolio_service: PortfolioServiceDep,
    alert_service: ConcentrationAlertServiceDep,
):
    """Get current allocation vs targets for both country and industry."""
    summary = await portfolio_service.get_portfolio_summary()
    alerts = await alert_service.detect_alerts(summary)

    return {
        "total_value": summary.total_value,
        "cash_balance": summary.cash_balance,
        "country": [
            {
                "name": a.name,
                "target_pct": a.target_pct,
                "current_pct": a.current_pct,
                "current_value": a.current_value,
                "deviation": a.deviation,
            }
            for a in summary.country_allocations
        ],
        "industry": [
            {
                "name": a.name,
                "target_pct": a.target_pct,
                "current_pct": a.current_pct,
                "current_value": a.current_value,
                "deviation": a.deviation,
            }
            for a in summary.industry_allocations
        ],
        "alerts": [
            {
                "type": alert.type,
                "name": alert.name,
                "current_pct": alert.current_pct,
                "limit_pct": alert.limit_pct,
                "alert_threshold_pct": alert.alert_threshold_pct,
                "severity": alert.severity,
            }
            for alert in alerts
        ],
    }


@router.get("/deviations")
async def get_allocation_deviations(portfolio_service: PortfolioServiceDep):
    """Get allocation deviation scores for rebalancing decisions."""
    summary = await portfolio_service.get_portfolio_summary()

    country_deviations = {
        a.name: {
            "deviation": a.deviation,
            "need": max(0, -a.deviation),
            "status": (
                "underweight"
                if a.deviation < -0.02
                else ("overweight" if a.deviation > 0.02 else "balanced")
            ),
        }
        for a in summary.country_allocations
    }

    industry_deviations = {
        a.name: {
            "deviation": a.deviation,
            "need": max(0, -a.deviation),
            "status": (
                "underweight"
                if a.deviation < -0.02
                else ("overweight" if a.deviation > 0.02 else "balanced")
            ),
        }
        for a in summary.industry_allocations
    }

    return {
        "country": country_deviations,
        "industry": industry_deviations,
    }


@router.get("/targets")
async def get_allocation_targets(
    allocation_repo: AllocationRepositoryDep,
):
    """Get allocation targets for country and industry groups."""
    country_targets = await allocation_repo.get_country_group_targets()
    industry_targets = await allocation_repo.get_industry_group_targets()

    return {
        "country": country_targets,
        "industry": industry_targets,
    }


class CountryGroup(BaseModel):
    """Country group definition."""

    group_name: str
    country_names: list[str]


class IndustryGroup(BaseModel):
    """Industry group definition."""

    group_name: str
    industry_names: list[str]


@router.get("/groups/country")
async def get_country_groups(grouping_repo: GroupingRepositoryDep):
    """Get all country groups (custom from DB only)."""
    groups = await grouping_repo.get_country_groups()
    return {"groups": groups}


@router.get("/groups/industry")
async def get_industry_groups(grouping_repo: GroupingRepositoryDep):
    """Get all industry groups (custom from DB only)."""
    groups = await grouping_repo.get_industry_groups()
    return {"groups": groups}


@router.put("/groups/country")
async def update_country_group(
    group: CountryGroup, grouping_repo: GroupingRepositoryDep
):
    """Create or update a country group."""
    if not group.group_name or not group.group_name.strip():
        raise HTTPException(status_code=400, detail="Group name is required")
    # Filter out empty strings and duplicates
    # Allow empty groups to be created (user can add countries after creation)
    country_names = list(
        dict.fromkeys([c for c in group.country_names if c and c.strip()])
    )

    await grouping_repo.set_country_group(group.group_name.strip(), country_names)
    return {"group_name": group.group_name.strip(), "country_names": country_names}


@router.put("/groups/industry")
async def update_industry_group(
    group: IndustryGroup, grouping_repo: GroupingRepositoryDep
):
    """Create or update an industry group."""
    if not group.group_name or not group.group_name.strip():
        raise HTTPException(status_code=400, detail="Group name is required")
    # Filter out empty strings and duplicates
    # Allow empty groups to be created (user can add industries after creation)
    industry_names = list(
        dict.fromkeys([i for i in group.industry_names if i and i.strip()])
    )

    await grouping_repo.set_industry_group(group.group_name.strip(), industry_names)
    return {"group_name": group.group_name.strip(), "industry_names": industry_names}


@router.delete("/groups/country/{group_name}")
async def delete_country_group(group_name: str, grouping_repo: GroupingRepositoryDep):
    """Delete a country group."""
    await grouping_repo.delete_country_group(group_name)
    return {"deleted": group_name}


@router.delete("/groups/industry/{group_name}")
async def delete_industry_group(group_name: str, grouping_repo: GroupingRepositoryDep):
    """Delete an industry group."""
    await grouping_repo.delete_industry_group(group_name)
    return {"deleted": group_name}


@router.get("/groups/available/countries")
async def get_available_countries(grouping_repo: GroupingRepositoryDep):
    """Get list of all available countries from securities."""
    countries = await grouping_repo.get_available_countries()
    return {"countries": countries}


@router.get("/groups/available/industries")
async def get_available_industries(grouping_repo: GroupingRepositoryDep):
    """Get list of all available industries from securities."""
    industries = await grouping_repo.get_available_industries()
    return {"industries": industries}


@router.get("/groups/allocation")
async def get_group_allocation(
    portfolio_service: PortfolioServiceDep,
    grouping_repo: GroupingRepositoryDep,
    allocation_repo: AllocationRepositoryDep,
):
    """Get current allocation aggregated by groups (for UI display)."""
    summary = await portfolio_service.get_portfolio_summary()

    # Get group mappings from custom groups only
    country_groups = await grouping_repo.get_country_groups()
    industry_groups = await grouping_repo.get_industry_groups()

    # Build reverse mappings (country -> group, industry -> group)
    country_to_group: Dict[str, str] = {}
    for group_name, countries in country_groups.items():
        for country in countries:
            country_to_group[country] = group_name

    industry_to_group: Dict[str, str] = {}
    for group_name, industries in industry_groups.items():
        for industry in industries:
            industry_to_group[industry] = group_name

    # Get saved group targets from database (group-level targets, not aggregated individual)
    saved_country_targets = await allocation_repo.get_country_group_targets()

    # Aggregate country allocations by group (only current values, not targets)
    group_country_values: Dict[str, float] = {}
    for alloc in summary.country_allocations:
        # Map country to group (use "OTHER" if not in any group)
        group = country_to_group.get(alloc.name, "OTHER")
        group_country_values[group] = (
            group_country_values.get(group, 0) + alloc.current_value
        )

    # Use saved group targets, default to 0 if not set
    group_country_targets: Dict[str, float] = {}
    for group_name in set(country_to_group.values()):
        group_country_targets[group_name] = saved_country_targets.get(group_name, 0.0)
        if group_name not in group_country_values:
            group_country_values[group_name] = 0.0

    # Get saved group targets from database (group-level targets, not aggregated individual)
    saved_industry_targets = await allocation_repo.get_industry_group_targets()

    # Aggregate industry allocations by group (only current values, not targets)
    group_industry_values: Dict[str, float] = {}
    for alloc in summary.industry_allocations:
        # Map industry to group (use "OTHER" if not in any group)
        group = industry_to_group.get(alloc.name, "OTHER")
        group_industry_values[group] = (
            group_industry_values.get(group, 0) + alloc.current_value
        )

    # Use saved group targets, default to 0 if not set
    group_industry_targets: Dict[str, float] = {}
    for group_name in set(industry_to_group.values()):
        group_industry_targets[group_name] = saved_industry_targets.get(group_name, 0.0)
        if group_name not in group_industry_values:
            group_industry_values[group_name] = 0.0

    # Build group allocation status
    group_country_allocations = []
    for group_name in sorted(
        set(list(group_country_values.keys()) + list(group_country_targets.keys()))
    ):
        current_value = group_country_values.get(group_name, 0)
        current_pct = (
            current_value / summary.total_value if summary.total_value > 0 else 0
        )
        target_pct = group_country_targets.get(group_name, 0)

        group_country_allocations.append(
            {
                "name": group_name,
                "target_pct": target_pct,
                "current_pct": round(current_pct, 4),
                "current_value": round(current_value, 2),
                "deviation": round(current_pct - target_pct, 4),
            }
        )

    group_industry_allocations = []
    for group_name in sorted(
        set(list(group_industry_values.keys()) + list(group_industry_targets.keys()))
    ):
        current_value = group_industry_values.get(group_name, 0)
        current_pct = (
            current_value / summary.total_value if summary.total_value > 0 else 0
        )
        target_pct = group_industry_targets.get(group_name, 0)

        group_industry_allocations.append(
            {
                "name": group_name,
                "target_pct": target_pct,
                "current_pct": round(current_pct, 4),
                "current_value": round(current_value, 2),
                "deviation": round(current_pct - target_pct, 4),
            }
        )

    return {
        "total_value": summary.total_value,
        "cash_balance": summary.cash_balance,
        "country": group_country_allocations,
        "industry": group_industry_allocations,
    }


@router.put("/groups/targets/country")
async def update_country_group_targets(
    targets: CountryTargets,
    allocation_repo: AllocationRepositoryDep,
    grouping_repo: GroupingRepositoryDep,
):
    """Update country group targets (stores group targets directly)."""
    group_targets = targets.targets

    if not group_targets:
        raise HTTPException(status_code=400, detail="No weights provided")

    # Verify groups exist
    country_groups = await grouping_repo.get_country_groups()
    if not country_groups:
        raise HTTPException(
            status_code=400,
            detail="No country groups defined. Please create groups first.",
        )

    # Store group targets directly (no distribution to individuals)
    for group_name, group_weight in group_targets.items():
        if group_weight < -1 or group_weight > 1:
            raise HTTPException(
                status_code=400,
                detail=f"Weight for {group_name} must be between -1 and 1",
            )

        # Store group target directly
        target = AllocationTarget(
            type="country_group",
            name=group_name,
            target_pct=group_weight,
        )
        await allocation_repo.upsert(target)

    # Return updated group targets
    result_groups = await allocation_repo.get_country_group_targets()

    # Only return groups with non-zero targets
    result_groups = {k: v for k, v in result_groups.items() if v != 0}

    return {
        "weights": result_groups,
        "count": len(result_groups),
    }


@router.put("/groups/targets/industry")
async def update_industry_group_targets(
    targets: IndustryTargets,
    allocation_repo: AllocationRepositoryDep,
    grouping_repo: GroupingRepositoryDep,
):
    """Update industry group targets (stores group targets directly)."""
    group_targets = targets.targets

    if not group_targets:
        raise HTTPException(status_code=400, detail="No weights provided")

    # Verify groups exist
    industry_groups = await grouping_repo.get_industry_groups()
    if not industry_groups:
        raise HTTPException(
            status_code=400,
            detail="No industry groups defined. Please create groups first.",
        )

    # Store group targets directly (no distribution to individuals)
    for group_name, group_weight in group_targets.items():
        if group_weight < -1 or group_weight > 1:
            raise HTTPException(
                status_code=400,
                detail=f"Weight for {group_name} must be between -1 and 1",
            )

        # Store group target directly
        target = AllocationTarget(
            type="industry_group",
            name=group_name,
            target_pct=group_weight,
        )
        await allocation_repo.upsert(target)

    # Return updated group targets
    result_groups = await allocation_repo.get_industry_group_targets()

    # Only return groups with non-zero targets
    result_groups = {k: v for k, v in result_groups.items() if v != 0}

    return {
        "weights": result_groups,
        "count": len(result_groups),
    }
