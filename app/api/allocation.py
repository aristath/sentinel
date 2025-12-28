"""Allocation target management API endpoints."""

from collections import defaultdict
from typing import Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.domain.models import AllocationTarget
from app.infrastructure.dependencies import (
    AllocationRepositoryDep,
    ConcentrationAlertServiceDep,
    GroupingRepositoryDep,
    PortfolioServiceDep,
)

router = APIRouter()


class CountryTargets(BaseModel):
    """Dynamic country allocation weights."""

    targets: dict[str, float]


class IndustryTargets(BaseModel):
    """Dynamic industry allocation weights."""

    targets: dict[str, float]


@router.get("/targets")
async def get_allocation_targets(allocation_repo: AllocationRepositoryDep):
    """Get all allocation targets (country and industry)."""
    targets = await allocation_repo.get_all()

    country = {}
    industry = {}

    # get_all() returns Dict[str, float] with keys like "country:name" or "industry:name"
    for key, target_pct in targets.items():
        parts = key.split(":", 1)
        if len(parts) == 2:
            target_type, name = parts
            if target_type == "country":
                country[name] = target_pct
            elif target_type == "industry":
                industry[name] = target_pct

    return {
        "country": country,
        "industry": industry,
    }


@router.put("/targets/country")
async def update_country_targets(
    targets: CountryTargets, allocation_repo: AllocationRepositoryDep
):
    """Update country allocation weights."""
    updates = targets.targets

    if not updates:
        raise HTTPException(status_code=400, detail="No weights provided")

    for name, weight in updates.items():
        if weight < -1 or weight > 1:
            raise HTTPException(
                status_code=400, detail=f"Weight for {name} must be between -1 and 1"
            )

    for name, weight in updates.items():
        target = AllocationTarget(
            type="country",
            name=name,
            target_pct=weight,
        )
        await allocation_repo.upsert(target)

    country_targets = await allocation_repo.get_by_type("country")
    result = {t.name: t.target_pct for t in country_targets}

    return {
        "weights": result,
        "count": len(result),
    }


@router.put("/targets/industry")
async def update_industry_targets(
    targets: IndustryTargets, allocation_repo: AllocationRepositoryDep
):
    """Update industry allocation weights."""
    updates = targets.targets

    if not updates:
        raise HTTPException(status_code=400, detail="No weights provided")

    for name, weight in updates.items():
        if weight < -1 or weight > 1:
            raise HTTPException(
                status_code=400, detail=f"Weight for {name} must be between -1 and 1"
            )

    for name, weight in updates.items():
        target = AllocationTarget(
            type="industry",
            name=name,
            target_pct=weight,
        )
        await allocation_repo.upsert(target)

    industry_targets = await allocation_repo.get_by_type("industry")
    result = {t.name: t.target_pct for t in industry_targets}

    return {
        "weights": result,
        "count": len(result),
    }


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
    """Get all country groups (custom from DB or fallback to hardcoded)."""
    groups = await grouping_repo.get_country_groups()
    if not groups:
        # Return hardcoded fallback groups so user can see and edit them
        from collections import defaultdict

        from app.application.services.optimization.constraints_manager import (
            TERRITORY_MAPPING,
        )

        reverse_mapping = defaultdict(list)
        for country, group in TERRITORY_MAPPING.items():
            reverse_mapping[group].append(country)
        groups = dict(reverse_mapping)
    return {"groups": groups}


@router.get("/groups/industry")
async def get_industry_groups(grouping_repo: GroupingRepositoryDep):
    """Get all industry groups (custom from DB or fallback to hardcoded)."""
    groups = await grouping_repo.get_industry_groups()
    if not groups:
        # Return hardcoded fallback groups so user can see and edit them
        from collections import defaultdict

        from app.application.services.optimization.constraints_manager import (
            INDUSTRY_GROUP_MAPPING,
        )

        reverse_mapping = defaultdict(list)
        for industry, group in INDUSTRY_GROUP_MAPPING.items():
            reverse_mapping[group].append(industry)
        groups = dict(reverse_mapping)
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
    """Get list of all available countries from stocks."""
    countries = await grouping_repo.get_available_countries()
    return {"countries": countries}


@router.get("/groups/available/industries")
async def get_available_industries(grouping_repo: GroupingRepositoryDep):
    """Get list of all available industries from stocks."""
    industries = await grouping_repo.get_available_industries()
    return {"industries": industries}


@router.get("/groups/allocation")
async def get_group_allocation(
    portfolio_service: PortfolioServiceDep,
    grouping_repo: GroupingRepositoryDep,
):
    """Get current allocation aggregated by groups (for UI display)."""
    summary = await portfolio_service.get_portfolio_summary()

    # Get group mappings (custom or fallback to hardcoded)
    from app.application.services.optimization.constraints_manager import (
        INDUSTRY_GROUP_MAPPING,
        TERRITORY_MAPPING,
    )

    country_groups = await grouping_repo.get_country_groups()
    industry_groups = await grouping_repo.get_industry_groups()

    # Build reverse mappings (country -> group, industry -> group)
    # Use custom groups if available, otherwise fallback to hardcoded mappings
    country_to_group: Dict[str, str] = {}
    if country_groups:
        # Use custom groups
        for group_name, countries in country_groups.items():
            for country in countries:
                country_to_group[country] = group_name
    else:
        # Fallback to hardcoded territory mapping
        country_to_group = TERRITORY_MAPPING.copy()

    industry_to_group: Dict[str, str] = {}
    if industry_groups:
        # Use custom groups
        for group_name, industries in industry_groups.items():
            for industry in industries:
                industry_to_group[industry] = group_name
    else:
        # Fallback to hardcoded industry group mapping
        industry_to_group = INDUSTRY_GROUP_MAPPING.copy()

    # Aggregate country allocations by group
    group_country_values: Dict[str, float] = {}
    group_country_targets: Dict[str, float] = {}
    for alloc in summary.country_allocations:
        # Map country to group (use "OTHER" if not in any group)
        group = country_to_group.get(alloc.name, "OTHER")
        group_country_values[group] = (
            group_country_values.get(group, 0) + alloc.current_value
        )
        # Aggregate targets (sum individual country targets in group)
        group_country_targets[group] = (
            group_country_targets.get(group, 0) + alloc.target_pct
        )

    # Also include groups that exist in mapping but have no current positions
    for group_name in set(country_to_group.values()):
        if group_name not in group_country_values:
            group_country_values[group_name] = 0.0
        if group_name not in group_country_targets:
            group_country_targets[group_name] = 0.0

    # Aggregate industry allocations by group
    group_industry_values: Dict[str, float] = {}
    group_industry_targets: Dict[str, float] = {}
    for alloc in summary.industry_allocations:
        # Map industry to group (use "OTHER" if not in any group)
        group = industry_to_group.get(alloc.name, "OTHER")
        group_industry_values[group] = (
            group_industry_values.get(group, 0) + alloc.current_value
        )
        # Aggregate targets (sum individual industry targets in group)
        group_industry_targets[group] = (
            group_industry_targets.get(group, 0) + alloc.target_pct
        )

    # Also include groups that exist in mapping but have no current positions
    for group_name in set(industry_to_group.values()):
        if group_name not in group_industry_values:
            group_industry_values[group_name] = 0.0
        if group_name not in group_industry_targets:
            group_industry_targets[group_name] = 0.0

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
    """Update country group targets (distributes to individual countries)."""
    group_targets = targets.targets

    if not group_targets:
        raise HTTPException(status_code=400, detail="No weights provided")

    # Get country groups (custom or fallback to hardcoded)
    from app.application.services.optimization.constraints_manager import (
        TERRITORY_MAPPING,
    )

    country_groups = await grouping_repo.get_country_groups()
    if not country_groups:
        # Fallback: build groups from hardcoded mapping
        reverse_mapping = defaultdict(list)
        for country, group in TERRITORY_MAPPING.items():
            reverse_mapping[group].append(country)
        country_groups = dict(reverse_mapping)

    # Distribute group targets to individual countries
    # Strategy: distribute evenly among countries in each group
    for group_name, group_weight in group_targets.items():
        if group_weight < -1 or group_weight > 1:
            raise HTTPException(
                status_code=400,
                detail=f"Weight for {group_name} must be between -1 and 1",
            )

        countries_in_group = country_groups.get(group_name, [])
        if not countries_in_group:
            # If group doesn't exist or is empty, skip
            continue

        # Distribute group weight evenly to all countries in group
        country_weight = (
            group_weight / len(countries_in_group) if countries_in_group else 0
        )

        for country in countries_in_group:
            target = AllocationTarget(
                type="country",
                name=country,
                target_pct=country_weight,
            )
            await allocation_repo.upsert(target)

    # Return updated group targets
    all_targets = await allocation_repo.get_all()
    country_targets: Dict[str, float] = {
        key.split(":", 1)[1]: val
        for key, val in all_targets.items()
        if key.startswith("country:")
    }

    # Re-aggregate to groups (use same mapping as for saving)
    # Build reverse mapping for aggregation
    country_to_group_agg: Dict[str, str] = {}
    for group_name, countries in country_groups.items():
        for country in countries:
            country_to_group_agg[country] = group_name

    result_groups: Dict[str, float] = {}
    # Aggregate by groups
    for country, target_pct in country_targets.items():
        group = country_to_group_agg.get(country, "OTHER")
        result_groups[group] = result_groups.get(group, 0) + target_pct

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
    """Update industry group targets (distributes to individual industries)."""
    group_targets = targets.targets

    if not group_targets:
        raise HTTPException(status_code=400, detail="No weights provided")

    # Get industry groups (custom or fallback to hardcoded)
    from app.application.services.optimization.constraints_manager import (
        INDUSTRY_GROUP_MAPPING,
    )

    industry_groups = await grouping_repo.get_industry_groups()
    if not industry_groups:
        # Fallback: build groups from hardcoded mapping
        reverse_mapping = defaultdict(list)
        for industry, group in INDUSTRY_GROUP_MAPPING.items():
            reverse_mapping[group].append(industry)
        industry_groups = dict(reverse_mapping)

    # Distribute group targets to individual industries
    # Strategy: distribute evenly among industries in each group
    for group_name, group_weight in group_targets.items():
        if group_weight < -1 or group_weight > 1:
            raise HTTPException(
                status_code=400,
                detail=f"Weight for {group_name} must be between -1 and 1",
            )

        industries_in_group = industry_groups.get(group_name, [])
        if not industries_in_group:
            # If group doesn't exist or is empty, skip
            # Note: "OTHER" is a special catch-all group and cannot have targets set directly
            continue

        # Distribute group weight evenly to all industries in group
        industry_weight = (
            group_weight / len(industries_in_group) if industries_in_group else 0
        )

        for industry in industries_in_group:
            target = AllocationTarget(
                type="industry",
                name=industry,
                target_pct=industry_weight,
            )
            await allocation_repo.upsert(target)

    # Return updated group targets
    all_targets = await allocation_repo.get_all()
    industry_targets: Dict[str, float] = {
        key.split(":", 1)[1]: val
        for key, val in all_targets.items()
        if key.startswith("industry:")
    }

    # Re-aggregate to groups (use same mapping as for saving)
    # Build reverse mapping for aggregation
    industry_to_group_agg: Dict[str, str] = {}
    for group_name, industries in industry_groups.items():
        for industry in industries:
            industry_to_group_agg[industry] = group_name

    result_groups: Dict[str, float] = {}
    # Aggregate by groups
    for industry, target_pct in industry_targets.items():
        group = industry_to_group_agg.get(industry, "OTHER")
        result_groups[group] = result_groups.get(group, 0) + target_pct

    # Only return groups with non-zero targets
    result_groups = {k: v for k, v in result_groups.items() if v != 0}

    return {
        "weights": result_groups,
        "count": len(result_groups),
    }
